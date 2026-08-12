"""Headless, streaming flood-risk-by-province pipeline — the notebook's scaled-up twin.

Run with:

    uv run python pipelines/flood_admin_pipeline.py

The fluent JRC plan resolves EFAS's current continental release, caches only
the AOI crops, and materializes a canonical hazard dataset. DuckDB handles the
admin join, aggregation, and disk spilling downstream of the fit.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import pyarrow as pa

from crc_sdk.connectors import read_hazard_dataset
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
from crc_sdk.providers.jrc import EFAS
from crc_sdk.workflows import (
    HazardDataset,
    JRCFloodPolicy,
    curve_quantiles_at,
    return_periods_to_probabilities,
    warn_if_extrapolated,
)

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
        choices=EFAS.available_return_periods,
        help="Return period to report; the canonical fit uses every EFAS period",
    )
    parser.add_argument(
        "--cache-mode", choices=("reuse", "offline", "refresh"), default="reuse"
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

    plan = (
        HazardDataset.efas(version="latest")
        .for_area(bounds)
        .cache(output_dir / "efas-source-cache", mode=args.cache_mode)
        .source_periods("all")
        .canonicalize(policy=JRCFloodPolicy.curated(h3_resolution=args.h3_resolution))
    )
    canonical_path = output_dir / "efas_curves.parquet"
    canonical = plan.materialize(canonical_path)
    metadata = canonical.metadata()
    warn_if_extrapolated([args.return_period_years], metadata.return_period_support)
    curves = read_hazard_dataset(canonical.provider.source)
    probability = return_periods_to_probabilities(
        [args.return_period_years], tail=metadata.return_period_tail
    )[0]
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
        f"hazard: EFAS {canonical.materialization.source_version} -> "
        f"{depth_rows} H3 cells at RP{args.return_period_years} -> {hazard_path}"
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
