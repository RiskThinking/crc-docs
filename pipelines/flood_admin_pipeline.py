"""Headless, streaming flood-risk-by-province pipeline — the notebook's scaled-up twin.

Run with:

    uv run python pipelines/flood_admin_pipeline.py

Same code path scales from a laptop-sized AOI to a country/continent: widen
--bounds, raise --max-workers (and optionally shrink --tile-degrees for finer
parallel granularity) for a production run. Nothing else changes. DuckDB
already parallelizes the join/aggregation, streaming and spilling to disk on
its own; --max-workers instead governs the two pure-Python stages it doesn't
touch — per-pixel curve fitting (tiled ingest) and per-row curve
reconstruction (return-period evaluation). Neither stage, nor the join
between them, is ever materialized into one Python/pandas structure: the join
is staged straight to Parquet via DuckDB's own COPY, and curve evaluation
streams that stage through bounded Arrow batches with incremental writes —
so peak memory stays bounded by --depth-batch-rows, not the AOI's row count.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

from crc_sdk.connectors import HurdleFitPolicy, OSClimateIngestPolicy
from crc_sdk.connectors.duckdb import DuckDBConnection, sql_quote
from crc_sdk.geometry import GeoFormat, H3Indexer, PolyfillMode
from crc_sdk.workflows import (
    OSClimateSelectionSpec,
    run_tiled_canonicalization,
    stream_curve_quantiles_to_parquet,
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
        help="AOI to ingest; widen for a bigger run (default: %(default)s)",
    )
    parser.add_argument("--h3-resolution", type=int, default=7)
    parser.add_argument("--return-period-years", type=int, default=100)
    parser.add_argument(
        "--tile-degrees",
        type=float,
        default=2.0,
        help="Parallel hazard-tile size in degrees (default: %(default)s)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Worker processes for tiled ingest + curve evaluation "
        "(default: auto-detect from host CPUs)",
    )
    parser.add_argument(
        "--depth-batch-rows",
        type=int,
        default=50_000,
        help="Rows per streaming batch for curve evaluation; bounds peak "
        "memory independent of the join's total row count (default: %(default)s)",
    )
    parser.add_argument("--admin-geojson-url", default=DEFAULT_ADMIN_URL)
    parser.add_argument(
        "--skip-places",
        action="store_true",
        help="Skip the Overture Maps impacted-places enrichment",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bounds = tuple(args.bounds)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    non_exceedance = 1 - 1 / args.return_period_years

    duck_config = DuckDBConnection.for_analytics(output_dir)
    con = duck_config.connect()
    indexer = H3Indexer(con)

    # 1. Hazard: tile-parallel canonicalization, each tile out-of-core on its own worker.
    spec = OSClimateSelectionSpec(
        hazard_type="RiverineInundation",
        indicator_id="flood_depth",
        model_gcm="historical",
        scenario="historical",
        year=1980,
    )
    policy = OSClimateIngestPolicy(
        h3_resolution=args.h3_resolution,
        family="gumbel_r",
        producer="crc-sdk-pipeline",
        creation_version="0.1.0",
        value_semantics="riverine flood depth return level",
        source_version="WRI Aqueduct Floods v2 (2020)",
        hurdle=HurdleFitPolicy(atom_probability=0.9, atom_location=0.0),
        maximum_normalized_rmse=0.3,
        on_fit_failure="skip",
    )
    hazard_dir = output_dir / "hazard_shards"
    shards = run_tiled_canonicalization(
        spec,
        policy,
        bounds,
        hazard_dir,
        tile_degrees=args.tile_degrees,
        max_workers=args.max_workers,
    )
    print(f"hazard: {len(shards)} non-empty tile shard(s) under {hazard_dir}")

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

    # 3. Join: staged straight to Parquet via DuckDB's own COPY — the join,
    # any disk spilling under memory pressure, and the write are all DuckDB's
    # problem, never a Python object. One glob read streams every hazard
    # shard; no shard-aware code needed downstream.
    hazard_glob = str(hazard_dir / "*.parquet")
    staged_join_path = output_dir / "staged_join.parquet"
    con.execute(
        f"""
        COPY (
            SELECT h.cell_index, a.shapeName AS province, h.curve_kind,
                   h.curve_type, h.curve_shape, h.curve_location, h.curve_scale,
                   h.curve_atom_probability, h.curve_atom_location
            FROM read_parquet({sql_quote(hazard_glob)}) h
            JOIN admin_h3 a ON h.cell_index = a.h3_index
        ) TO {sql_quote(staged_join_path)} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    # 4. Depth-at-return-period: the one step DuckDB/Arrow can't vectorize —
    # curve reconstruction is Pydantic validation plus a per-row Rust call.
    # Streamed through in --depth-batch-rows-sized Arrow batches, each
    # evaluated and appended immediately, so peak memory never scales with
    # the AOI's total row count, however large the staged join is.
    depth_path = output_dir / "depth_by_cell.parquet"
    depth_rows = stream_curve_quantiles_to_parquet(
        con,
        f"SELECT * FROM read_parquet({sql_quote(staged_join_path)})",
        non_exceedance,
        depth_path,
        passthrough_columns=["cell_index", "province"],
        batch_rows=args.depth_batch_rows,
        max_workers=args.max_workers,
    )
    print(f"depth: {depth_rows} cell-province rows evaluated -> {depth_path}")

    # 5. Places: same Overture join as the notebook, restricted to the staged
    # join's own distinct cells via a subquery — still pure DuckDB, no Python
    # materialization, and no need to round-trip cell ids through pandas.
    final_path = output_dir / "risk_by_province.parquet"
    if args.skip_places:
        con.execute(
            f"""
            COPY (SELECT *, 0 AS place_count FROM read_parquet({sql_quote(depth_path)}))
            TO {sql_quote(final_path)} (FORMAT PARQUET, COMPRESSION ZSTD)
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
                FROM read_parquet({sql_quote(depth_path)}) d
                LEFT JOIN (
                    WITH places_h3 AS ({places_h3_sql})
                    SELECT h3_index AS cell_index, COUNT(*) AS place_count
                    FROM places_h3
                    WHERE h3_index IN (
                        SELECT DISTINCT cell_index FROM read_parquet({sql_quote(depth_path)})
                    )
                    GROUP BY h3_index
                ) p ON d.cell_index = p.cell_index
            ) TO {sql_quote(final_path)} (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )

    # 6. Summary: a tiny (one row per province) aggregate — safe to print
    # directly via DuckDB's own relation API, no pandas round-trip needed.
    con.sql(
        f"""
        SELECT province,
               avg(depth_m) AS mean_depth_m,
               max(depth_m) AS max_depth_m,
               count(DISTINCT cell_index) AS exposed_cells,
               sum(place_count) AS impacted_places
        FROM read_parquet({sql_quote(final_path)})
        GROUP BY province
        ORDER BY mean_depth_m DESC
        """
    ).show()
    print(f"wrote {final_path}")


if __name__ == "__main__":
    main()
