"""Screen daily rainfall hazards for an illustrative Toronto portfolio.

Run with crc-sdk 0.8.1 or later:
  uv run python pipelines/crc_open_pipeline.py

For your own CSV or Parquet assets, supply --assets and --bounds. Assets require
asset_id, longitude and latitude columns. Outputs are hazard quantiles, not
vulnerability or financial loss estimates. An optional ERA5 comparison uses a
different source and methodology and is not a pure climate change estimate.

See notebooks/crc_open_hazards.ipynb for coverage discovery and rendered charts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from crc_sdk.workflows import HazardDataset
from pyarrow import csv

RELEASE = "ssp585-global-2026-10-20-v1"
SOURCE = "https://data.riskthinking.ai/crc-open"
BOUNDS = (-79.52, 43.60, -79.25, 43.78)
HORIZONS = (2030, 2050, 2080)
RETURN_PERIODS = (10, 100)
SITES = [
    {"asset_id": "West depot", "longitude": -79.47, "latitude": 43.65},
    {"asset_id": "Central clinic", "longitude": -79.38, "latitude": 43.65},
    {"asset_id": "East warehouse", "longitude": -79.29, "latitude": 43.70},
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default=SOURCE, help="Catalogue root URL or directory"
    )
    parser.add_argument("--release", default=RELEASE, help="Pinned release ID")
    parser.add_argument("--assets", type=Path, help="CSV or Parquet asset locations")
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Acquisition area; required with --assets",
    )
    parser.add_argument("--horizons", type=int, nargs="+", default=list(HORIZONS))
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/crc_open"))
    parser.add_argument(
        "--era5-rx1day",
        type=Path,
        help="Optional canonical ERA5 historical Rx1day Parquet for the same locations",
    )
    args = parser.parse_args()
    if args.assets is not None and args.bounds is None:
        parser.error("--assets requires --bounds to limit acquisition")
    if args.assets is None:
        assets = pa.Table.from_pylist(SITES)
    elif args.assets.suffix.lower() == ".csv":
        assets = csv.read_csv(args.assets)
    else:
        assets = pq.ParquetFile(args.assets).read()
    args.output.mkdir(parents=True, exist_ok=True)
    plan = (
        HazardDataset.crc_open(release=args.release, source=args.source)
        .for_area(args.bounds or BOUNDS)
        .hazards(["rx1day"])
        .horizons(args.horizons)
        .cache(args.output / "cache", mode="reuse")
    )
    selection = plan.resolve()
    print(
        json.dumps(
            {
                "release": selection.catalog.release,
                "catalog_sha256": selection.catalog_sha256,
                "partitions": len(selection.partitions),
                "whole_file_bytes": selection.total_bytes,
                "licence": selection.catalog.licence,
                "attribution": selection.catalog.attribution,
            },
            indent=2,
        )
    )
    projected = (
        plan.for_assets(assets)
        .return_periods(RETURN_PERIODS)
        .write_parquet(args.output / "ssp585_portfolio.parquet")
    )
    print(
        json.dumps(
            pq.ParquetFile(projected.output)
            .read()
            .select(
                [
                    "asset_id",
                    "horizon",
                    "pathway",
                    "spatial_match",
                    *projected.value_columns,
                ]
            )
            .to_pylist(),
            indent=2,
        )
    )
    if args.era5_rx1day is not None:
        baseline = HazardDataset.local(args.era5_rx1day)
        metadata = baseline.metadata()
        if (
            metadata.source.provider != "era5"
            or metadata.value_unit != "mm/day"
            or baseline.provider.list_hazards() != ("rx1day",)
        ):
            raise ValueError("comparison requires a canonical ERA5 Rx1day baseline")
        historical = (
            baseline.for_assets(assets)
            .select(hazard_names=["rx1day"])
            .return_periods(RETURN_PERIODS)
            .write_parquet(args.output / "era5_historical.parquet")
        )
        historical_table = pq.ParquetFile(historical.output).read()
        if not any(
            pc.any(pc.is_finite(historical_table[column])).as_py()
            for column in historical.value_columns
        ):
            raise LookupError("ERA5 baseline has no usable Rx1day return values")
        print("ERA5 historical comparison (different source, period and methodology):")
        print(
            json.dumps(
                historical_table.select(
                    [
                        "asset_id",
                        "horizon",
                        "pathway",
                        *historical.value_columns,
                    ]
                ).to_pylist(),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
