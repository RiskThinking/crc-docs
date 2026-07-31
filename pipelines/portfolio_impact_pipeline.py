"""Headless event-aligned portfolio impact — the notebook's scaled-up twin.

Run with:

    uv run python pipelines/portfolio_impact_pipeline.py

Reuses the checked-in Cologne riverine fixture, then writes both raw flood-depth
and damage-ratio evaluations so dollar losses can be derived from replacement
values. Pass a picklable top-level impact (as here) to keep ``--max-workers``
greater than one available.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from crc_sdk.connectors import read_hazard_dataset
from crc_sdk.impacts import PiecewiseLinearImpact
from crc_sdk.workflows import ExecutionOptions, HazardDataset

HAZARD_NAME = "RiverineInundation"
PATHWAY = "historical"
HORIZON = 1980

# Hypothetical depth–damage curve: flood depth (m) → fractional damage.
DEPTH_DAMAGE = PiecewiseLinearImpact(
    exposure=[0.0, 0.1, 0.5, 1.0, 2.0, 4.0],
    impact=[0.0, 0.01, 0.08, 0.22, 0.55, 1.0],
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--hazard-input",
        type=Path,
        default=Path("fixtures/os_climate/hazard.parquet"),
    )
    parser.add_argument(
        "--asset-input",
        type=Path,
        default=Path("fixtures/os_climate/assets.parquet"),
    )
    parser.add_argument(
        "--return-periods",
        type=float,
        nargs="+",
        default=[25, 50, 100, 250, 500, 1000],
    )
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    assets_path: Path = args.asset_input
    hazard_path: Path = args.hazard_input
    raw_path = output_dir / "portfolio_before_impact.parquet"
    impact_path = output_dir / "portfolio_after_impact.parquet"

    assets = pq.read_table(assets_path)
    hazard = read_hazard_dataset(hazard_path)
    print(f"assets: {assets.num_rows} <- {assets_path}")
    print(f"hazard: {hazard.num_rows} rows <- {hazard_path}")

    request = (
        HazardDataset.local(hazard_path)
        .for_assets(assets_path)
        .select(
            hazard_names=[HAZARD_NAME],
            horizons=[HORIZON],
            pathways=[PATHWAY],
        )
        .return_periods(args.return_periods)
    )
    execution = ExecutionOptions(max_workers=args.max_workers)
    raw_result = request.write_parquet(raw_path, execution=execution)
    impact_result = request.impact(
        DEPTH_DAMAGE,
        name="piecewise_depth_damage",
        value_unit="fraction",
        value_semantics="hypothetical fractional asset damage",
    ).write_parquet(impact_path, execution=execution)

    raw = pq.read_table(raw_path).to_pandas().set_index("asset_id")
    impacted = pq.read_table(impact_path).to_pandas().set_index("asset_id")
    print(
        "asset | RP | depth (m) | damage ratio | replacement value | estimated damage"
    )
    for asset_id, raw_row in raw.iterrows():
        impact_row = impacted.loc[asset_id]
        replacement = float(raw_row["replacement_value"])
        for period, column in zip(args.return_periods, raw_result.value_columns):
            depth = float(raw_row[column])
            ratio = float(impact_row[column])
            expected = float(DEPTH_DAMAGE.evaluate(np.asarray([depth]))[0])
            if not np.isclose(ratio, expected):
                raise RuntimeError(
                    f"{asset_id} {column} impact mismatch: {ratio} != {expected}"
                )
            print(
                f"{asset_id:13} | {period:6g} | {depth:9.4f} | {ratio:12.4f} | "
                f"{replacement:17,.0f} | {ratio * replacement:16,.0f}"
            )

    print(f"raw: {raw_path} ({raw_result.row_count} rows)")
    print(f"impact: {impact_path} ({impact_result.row_count} rows)")


if __name__ == "__main__":
    main()
