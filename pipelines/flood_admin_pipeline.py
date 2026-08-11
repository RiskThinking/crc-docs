"""Headless, streaming flood-risk-by-province pipeline — the notebook's scaled-up twin.

Run with:

    uv run python pipelines/flood_admin_pipeline.py

Same code path scales from a laptop-sized AOI to a country/continent: widen
--bounds and raise --max-workers for a production run. Nothing else changes.
JRC's own 10x10-degree tile grid (resolved via `crc_sdk.providers.jrc.JRCProvider`,
not hardcoded) is the unit of parallelism — each tile is fitted to a canonical
hazard curve per H3 cell independently in its own worker
(`JRCIngestPolicy`/`canonicalize_jrc_flood`, the same curve-fit machinery
OS-Climate ingest uses), and pixel reads stream in bounded-memory strips
regardless of tile size. Depths at the requested return period are a curve
evaluation away (`curve_quantiles_at`) rather than a raw per-return-period
raster value — the tile shards this pipeline writes are reusable at any
other return period without re-fetching JRC data. DuckDB handles the admin
join, aggregation, and any disk spilling on its own; nothing downstream of
the hazard fit is ever materialized into a pandas structure.
"""

from __future__ import annotations

import argparse
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pyarrow as pa

from crc_sdk.connectors import (
    JRCIngestPolicy,
    read_hazard_dataset,
    write_hazard_dataset,
)
from crc_sdk.connectors.duckdb import DuckDBConnection, sql_quote
from crc_sdk.geometry import (
    AREAS,
    POINTS,
    POLYGONS,
    FormatAdapter,
    GeoFormat,
    H3Indexer,
    PolyfillMode,
)
from crc_sdk.geometry.pmtiles import PMTilesBuild, PMTilesResult
from crc_sdk.providers.jrc import GLOFAS, JRCProvider, JRCRasterDataset
from crc_sdk.workflows import curve_quantiles_at, return_periods_to_probabilities

DEFAULT_ADMIN_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/"
    "gbOpen/DEU/ADM1/geoBoundaries-DEU-ADM1_simplified.geojson"
)
OVERTURE_CATALOG_URL = "https://stac.overturemaps.org/catalog.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=(5.9, 47.3, 10.5, 52.5),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="AOI to sample; widen for a bigger run (default: %(default)s)",
    )
    parser.add_argument("--h3-resolution", type=int, default=7)
    parser.add_argument(
        "--return-period-years",
        type=int,
        default=100,
        choices=GLOFAS.available_return_periods,
        help="Return period to report depths at; every tile's curve is "
        "still fitted against all of GLOFAS.available_return_periods, so "
        "the written shards are reusable at any other return period too",
    )
    parser.add_argument(
        "--family",
        default="gumbel_r",
        help="Distribution family to fit each cell's return-level curve "
        "against (default: %(default)s)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Worker processes for parallel per-tile hazard fitting "
        "(default: auto-detect from host CPUs)",
    )
    parser.add_argument("--admin-geojson-url", default=DEFAULT_ADMIN_URL)
    parser.add_argument(
        "--skip-places",
        action="store_true",
        help="Skip the Overture Maps impacted-places enrichment",
    )
    parser.add_argument(
        "--skip-pmtiles",
        action="store_true",
        help="Skip the final PMTiles export (requires tippecanoe/tile-join on PATH)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def _canonicalize_tile(
    tile: str,
    output_path: Path,
    *,
    dataset: JRCRasterDataset,
    policy: JRCIngestPolicy,
    bounds: tuple[float, float, float, float],
) -> Path | None:
    """Worker body: fit one JRC tile's return-period curves, write its shard.

    Runs in its own process. Fits against every return period `dataset`
    advertises (not just `--return-period-years`), so the shard this writes
    is reusable at any other return period without re-fetching JRC data --
    `max_workers=1` avoids nesting a second process pool inside this one for
    the write's own curve-reconstruction validation pass.
    """
    provider = JRCProvider(dataset)
    stream = provider.canonicalize_tile(tile, policy, bounds=bounds)
    table = stream.read_all()
    if table.num_rows == 0:
        return None
    write_hazard_dataset(table, output_path, stream.metadata, max_workers=1)
    return output_path


def build_risk_pmtiles(
    con,
    risk_parquet: Path,
    admin_geojson: Path,
    output_pmtiles: Path,
    *,
    bounds: tuple[float, float, float, float],
    h3_resolution: int,
    overture_min_confidence: float,
    work_dir: Path,
) -> PMTilesResult:
    """Export the three layers this pipeline already computes as one PMTiles archive.

    One combined tiling pass, not three separate archives -- see
    crc_sdk.geometry.pmtiles.PMTilesBuild. Hex boundaries come from DuckDB's
    own h3 extension (vectorized SQL, no Python per-cell loop), matching the
    same primitive gen_pmtiles_v2 uses for its hazard-area product.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    # Hex-depth layer: reuse the final risk_by_province rows, attach exact
    # H3 boundary geometry only at the very end (narrow-key-first idiom).
    hex_path = work_dir / "hex_layer.parquet"
    con.execute(
        f"""
        COPY (
            SELECT cell_index, province, depth_m, place_count,
                   h3_cell_to_boundary_wkb(CAST(cell_index AS UBIGINT)) AS geometry
            FROM read_parquet({sql_quote(str(risk_parquet))})
        ) TO {sql_quote(str(hex_path))} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    # Places layer: raw point geometry this time, not the per-hex count the
    # existing places enrichment collapses to -- a "points" layer should be
    # actual points, not one dot per flooded hex. Still restricted to the
    # same flood-exposed cells as the existing places enrichment (not every
    # place in the whole AOI bbox, which for a real city-scale AOI is
    # millions of rows unrelated to this map's subject).
    places_path = work_dir / "places_layer.parquet"
    con.execute("SET s3_region = 'us-west-2'")
    release = con.execute(
        f"SELECT latest FROM read_json_auto({sql_quote(OVERTURE_CATALOG_URL)})"
    ).fetchone()[0]
    places_uri = (
        f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
    )
    places_points_sql = f"""
        (SELECT names.primary AS name, confidence,
                ST_Point(bbox.xmin, bbox.ymin) AS geometry
         FROM read_parquet({sql_quote(places_uri)}, filename=true, hive_partitioning=1)
         WHERE bbox.xmin BETWEEN {bounds[0]} AND {bounds[2]}
           AND bbox.ymin BETWEEN {bounds[1]} AND {bounds[3]}
           AND confidence > {overture_min_confidence})
    """
    indexer = H3Indexer(con)
    places_h3_sql = indexer.build_h3_query(
        places_points_sql,
        h3_resolution,
        PolyfillMode.CENTROID,
        geom_col="geometry",
        h3_col="cell_index",
        preserve_geom=True,
    )
    con.execute(
        f"""
        COPY (
            SELECT p.name, p.confidence, p.geometry
            FROM ({places_h3_sql}) p
            JOIN (
                SELECT DISTINCT cell_index FROM read_parquet({sql_quote(str(risk_parquet))})
            ) r ON p.cell_index = r.cell_index
        ) TO {sql_quote(str(places_path))} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    # Province-polygons layer: the same admin GeoJSON already used for the
    # hazard join, read via the same format adapter H3Indexer uses internally.
    provinces_path = work_dir / "province_layer.parquet"
    admin_relation = FormatAdapter.build_read_relation(
        con,
        str(admin_geojson),
        GeoFormat.GEOJSON,
        geometry_column="geometry",
        preserve_source_geom=False,
    )
    con.execute(
        f"""
        COPY (SELECT * FROM {admin_relation})
        TO {sql_quote(str(provinces_path))} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    return (
        PMTilesBuild(con=con)
        .layer(str(hex_path), name="hex_depth", zooms=(0, 12), preset=AREAS)
        .add_layer(str(places_path), name="places", zooms=(0, 14), preset=POINTS)
        .add_layer(
            str(provinces_path), name="provinces", zooms=(0, 10), preset=POLYGONS
        )
        .write(str(output_pmtiles))
    )


def main() -> None:
    args = parse_args()
    bounds = tuple(args.bounds)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    duck_config = DuckDBConnection.for_analytics(output_dir)
    con = duck_config.connect()
    indexer = H3Indexer(con)

    # 1. Hazard: one worker per JRC tile intersecting the AOI (_canonicalize_tile).
    # One H3 cell can have more than one contributing source pixel -- JRC's
    # own conservative H3 overlap coverage already produces this within a
    # single tile, tile parallelism doesn't add anything new here -- so
    # cells are reduced to their worst-case (max) reconstructed depth before
    # the admin join.
    provider = JRCProvider(GLOFAS, work_dir=output_dir)
    tiles = provider.tiles_for(bounds)
    policy = JRCIngestPolicy(
        h3_resolution=args.h3_resolution,
        family=args.family,
        producer="crc-docs-flood-admin-pipeline",
        creation_version="0.1.0",
        value_semantics="riverine flood depth",
        # Most pixels in a country/continent-scale AOI never flood at any
        # return period and carry a constant, unfittable curve; skip those
        # rather than aborting the whole run.
        on_fit_failure="skip",
    )
    hazard_dir = output_dir / "hazard_shards"
    hazard_dir.mkdir(parents=True, exist_ok=True)
    shard_paths = [
        hazard_dir / f"tile_{index:04d}.parquet" for index in range(len(tiles))
    ]
    with ProcessPoolExecutor(max_workers=args.max_workers) as pool:
        futures = [
            pool.submit(
                _canonicalize_tile,
                tile,
                path,
                dataset=GLOFAS,
                policy=policy,
                bounds=bounds,
            )
            for tile, path in zip(tiles, shard_paths)
        ]
        written = [future.result() for future in futures]
    written = [path for path in written if path is not None]
    if not written:
        raise SystemExit(f"no fittable JRC pixels found for bounds={bounds}")

    curves = pa.concat_tables(
        [read_hazard_dataset(path) for path in written], promote_options="none"
    )
    probability = return_periods_to_probabilities([args.return_period_years])[0]
    depths = curve_quantiles_at(curves, probability)
    curves = curves.append_column("depth_m", pa.array(depths, type=pa.float32()))
    con.register("fitted_curves", curves.select(["cell_index", "depth_m"]))
    hazard_path = output_dir / "hazard.parquet"
    con.execute(
        f"""
        COPY (
            SELECT cell_index, max(depth_m) AS depth_m
            FROM fitted_curves
            GROUP BY cell_index
        ) TO {sql_quote(str(hazard_path))} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    con.unregister("fitted_curves")
    depth_rows = con.execute(
        f"SELECT COUNT(*) FROM read_parquet({sql_quote(str(hazard_path))})"
    ).fetchone()[0]
    print(
        f"hazard: fitted curves across {len(written)} of {len(tiles)} JRC "
        f"tile(s) -> {depth_rows} H3 cells at RP{args.return_period_years} "
        f"-> {hazard_path}"
    )

    # 2. Geography: one polyfill call; DuckDB already parallelizes this internally.
    admin_path = output_dir / "admin.geojson"
    if not admin_path.exists():
        urllib.request.urlretrieve(args.admin_geojson_url, admin_path)
    admin_h3_sql = indexer.build_h3_query_from_file(
        str(admin_path),
        GeoFormat.GEOJSON,
        args.h3_resolution,
        PolyfillMode.OVERLAP,
        preserve_geom=False,
    )
    con.execute(f"CREATE OR REPLACE TEMP VIEW admin_h3 AS {admin_h3_sql}")

    # 3. Join: hazard.parquet already holds the reconstructed, per-cell-
    # reduced depth at the requested return period (step 1) -- this is a
    # plain join, no curve reconstruction here.
    depth_path = output_dir / "depth_by_cell.parquet"
    con.execute(
        f"""
        COPY (
            SELECT h.cell_index, a.shapeName AS province, h.depth_m
            FROM read_parquet({sql_quote(str(hazard_path))}) h
            JOIN admin_h3 a ON h.cell_index = a.h3_index
        ) TO {sql_quote(str(depth_path))} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    depth_rows = con.execute(
        f"SELECT COUNT(*) FROM read_parquet({sql_quote(str(depth_path))})"
    ).fetchone()[0]
    print(f"depth: {depth_rows} cell-province rows -> {depth_path}")

    # 4. Places: same Overture join as the notebook, restricted to the staged
    # join's own distinct cells via a subquery — still pure DuckDB, no Python
    # materialization, and no need to round-trip cell ids through pandas.
    final_path = output_dir / "risk_by_province.parquet"
    if args.skip_places:
        con.execute(
            f"""
            COPY (SELECT *, 0 AS place_count FROM read_parquet({sql_quote(str(depth_path))}))
            TO {sql_quote(str(final_path))} (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
    else:
        con.execute("SET s3_region = 'us-west-2'")
        release = con.execute(
            f"SELECT latest FROM read_json_auto({sql_quote(OVERTURE_CATALOG_URL)})"
        ).fetchone()[0]
        places_path = (
            f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
        )
        places_points_sql = f"""
            (SELECT ST_Point(bbox.xmin, bbox.ymin) AS geometry
             FROM read_parquet({sql_quote(places_path)}, filename=true, hive_partitioning=1)
             WHERE bbox.xmin BETWEEN {bounds[0]} AND {bounds[2]}
               AND bbox.ymin BETWEEN {bounds[1]} AND {bounds[3]}
               AND confidence > 0.7)
        """
        places_h3_sql = indexer.build_h3_query(
            places_points_sql,
            args.h3_resolution,
            PolyfillMode.CENTROID,
            geom_col="geometry",
            h3_col="h3_index",
            preserve_geom=False,
        )
        con.execute(
            f"""
            COPY (
                SELECT d.*, COALESCE(p.place_count, 0) AS place_count
                FROM read_parquet({sql_quote(str(depth_path))}) d
                LEFT JOIN (
                    WITH places_h3 AS ({places_h3_sql})
                    SELECT h3_index AS cell_index, COUNT(*) AS place_count
                    FROM places_h3
                    WHERE h3_index IN (
                        SELECT DISTINCT cell_index FROM read_parquet({sql_quote(str(depth_path))})
                    )
                    GROUP BY h3_index
                ) p ON d.cell_index = p.cell_index
            ) TO {sql_quote(str(final_path))} (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )

    # 5. Summary: a tiny (one row per province) aggregate — safe to print
    # directly via DuckDB's own relation API, no pandas round-trip needed.
    con.sql(
        f"""
        SELECT province,
               avg(depth_m) AS mean_depth_m,
               max(depth_m) AS max_depth_m,
               count(DISTINCT cell_index) AS exposed_cells,
               sum(place_count) AS impacted_places
        FROM read_parquet({sql_quote(str(final_path))})
        GROUP BY province
        ORDER BY mean_depth_m DESC
        """
    ).show()
    print(f"wrote {final_path}")

    # 6. PMTiles: export the three layers above as one downloadable archive.
    # View at https://pmtiles.io -- PMTiles needs a JS map client (MapLibre
    # GL JS) that a notebook/pipeline output can't provide inline.
    if not args.skip_pmtiles:
        pmtiles_path = output_dir / "risk_by_province.pmtiles"
        result = build_risk_pmtiles(
            con,
            final_path,
            admin_path,
            pmtiles_path,
            bounds=bounds,
            h3_resolution=args.h3_resolution,
            overture_min_confidence=0.7,
            work_dir=output_dir,
        )
        print(f"pmtiles: wrote {result.output} (layers={result.layers})")


if __name__ == "__main__":
    main()
