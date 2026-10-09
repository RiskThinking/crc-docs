"""Evaluate the SSP585 fixture; optionally compare an ERA5 Rx1day baseline.

Run from crc-docs with crc-sdk 0.8.0a3 or later:
  uv run python pipelines/crc_open_pipeline.py

A historical comparison is a source/methodology cross-check, not a pure climate
change estimate: ERA5 reanalysis and pooled bias-corrected projections differ.

See notebooks/crc_open_hazards.ipynb for catalogue exploration and city curves.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from crc_sdk.workflows import HazardDataset

RELEASE = "ssp585-fixture-2026-10-08-v2"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        default=str(Path(__file__).resolve().parents[1] / "fixtures/crc_open"),
        help="Local directory or HTTP root containing release directories",
    )
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/crc_open"))
    parser.add_argument(
        "--era5-rx1day",
        type=Path,
        help="Optional canonical ERA5 historical Rx1day Parquet",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assets = pa.table(
        {"asset_id": ["Toronto"], "longitude": [-79.38], "latitude": [43.65]}
    )
    plan = (
        HazardDataset.crc_open(release=RELEASE, fixtures=args.fixtures)
        .for_area((-79.5, 43.5, -79.2, 43.8))
        .hazards(["rx1day"])
        .horizons([2050])
        .cache(args.output / "cache", mode="reuse")
    )
    print(plan.explain())
    projected = (
        plan.for_assets(assets)
        .return_periods([10, 100])
        .write_parquet(args.output / "ssp585_2050.parquet")
    )
    print(
        json.dumps(
            pq.read_table(projected.output)
            .select(["asset_id", "horizon", "pathway", *projected.value_columns])
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
            .return_periods([10, 100])
            .write_parquet(args.output / "era5_historical.parquet")
        )
        historical_table = pq.read_table(historical.output)
        if not any(
            pc.any(pc.is_finite(historical_table[column])).as_py()
            for column in historical.value_columns
        ):
            raise LookupError(
                "ERA5 baseline has no usable Rx1day return values for Toronto"
            )
        print("ERA5 historical comparison (different source, period and methodology):")
        print(
            json.dumps(
                historical_table.select(
                    ["asset_id", "horizon", "pathway", *historical.value_columns]
                ).to_pylist(),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
