"""Headless JRC flood-hazard-by-H3-cell pipeline -- the notebook's scaled-up twin.

Run with:

    uv run python pipelines/jrc_flood_pipeline.py

Same `GeoTiffRaster.scan_h3` path as the notebook: widen or drop --bounds to
sample a whole 10x10-degree JRC tile instead of one neighborhood, and adjust
--return-periods to compare more (or fewer) of them. Reading happens in
bounded-memory strips regardless of raster size, so peak memory stays flat
as the AOI grows -- the same property the internal flood-extraction pipeline
relies on to process rasters far larger than available RAM.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from crc_sdk.connectors.duckdb.geotiff import GeoTiffRaster

JRC_BASE_URL = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard"

OUTPUT_SCHEMA = pa.schema(
    [("cell", pa.uint64()), ("depth_m", pa.float32()), ("return_period", pa.int32())]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tile",
        default="ID54_N50_W80",
        help="JRC 10x10-degree tile id (default: %(default)s, covering Toronto)",
    )
    parser.add_argument(
        "--return-periods", type=int, nargs="+", default=[10, 50, 100, 500]
    )
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=None,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="AOI to sample; omit to sample the whole tile",
    )
    parser.add_argument(
        "--h3-resolution",
        type=int,
        default=None,
        help="Override the resolution inferred from the raster's own pixel size",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "jrc_depths_by_cell.parquet"
    bounds = tuple(args.bounds) if args.bounds else None

    # One writer across every return period: each tile is streamed, sampled,
    # and appended in turn, so peak memory is one return period's cell
    # count, never the whole run's.
    with pq.ParquetWriter(out_path, OUTPUT_SCHEMA, compression="zstd") as writer:
        for rp in args.return_periods:
            url = f"{JRC_BASE_URL}/RP{rp}/{args.tile}_RP{rp}_depth.tif"
            raster = GeoTiffRaster.open(url)
            try:
                table = (
                    raster.scan_h3(
                        bounds=bounds,
                        h3_resolution=args.h3_resolution,
                        mask=lambda band: band > 0.0,
                    )
                    .relation()
                    .project(f"cell, value AS depth_m, {rp}::INTEGER AS return_period")
                    .to_arrow_table()
                )
            finally:
                raster.close()
            writer.write_table(table)
            print(f"{args.tile} RP{rp}: {table.num_rows:,} cells")

    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
