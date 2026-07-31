"""Headless asset-portfolio evaluation — the notebook's scaled-up twin.

Run with:

    uv run python pipelines/asset_portfolio_pipeline.py

Evaluates the checked-in Cologne OS-Climate fixture for every asset via the
fluent ``HazardDataset`` API. Replace ``--hazard-input`` and ``--asset-input``
with larger canonical Parquet datasets and raise ``--max-workers`` for a
larger run; peak memory stays bounded by the streaming evaluator.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.parquet as pq

from crc_sdk.connectors import read_hazard_dataset
from crc_sdk.workflows import ExecutionOptions, HazardDataset

HAZARD_NAME = "RiverineInundation"
PATHWAY = "historical"
HORIZON = 1980


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
    evaluation_path = output_dir / "portfolio_evaluation.parquet"

    assets = pq.read_table(assets_path)
    hazard = read_hazard_dataset(hazard_path)
    print(f"hazard: {hazard.num_rows} rows <- {hazard_path}")

    result = (
        HazardDataset.local(hazard_path)
        .for_assets(assets_path)
        .select(
            hazard_names=[HAZARD_NAME],
            horizons=[HORIZON],
            pathways=[PATHWAY],
        )
        .return_periods(args.return_periods)
        .write_parquet(
            evaluation_path,
            execution=ExecutionOptions(max_workers=args.max_workers),
        )
    )
    evaluated = pq.read_table(evaluation_path)
    print(f"assets: {assets.num_rows} <- {assets_path}")
    print(f"evaluated rows: {result.row_count}")
    print(f"value columns: {', '.join(result.value_columns)}")
    print(evaluated.to_pandas().to_string(index=False))
    print(f"wrote {evaluation_path}")


if __name__ == "__main__":
    main()
