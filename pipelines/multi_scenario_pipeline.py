"""Headless multi-scenario portfolio comparison — the notebook's scaled-up twin.

Run with:

    uv run python pipelines/multi_scenario_pipeline.py

Builds two transparent local stress scenarios from the checked-in historical
WRI Aqueduct fixture by increasing the fitted tail scale, writes one
multi-scenario hazard Parquet, then evaluates the same asset portfolio across
every pathway/horizon present. These are sensitivity cases, not climate-model
projections.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from crc_sdk.connectors import (
    read_hazard_dataset,
    read_hazard_metadata,
    write_hazard_dataset,
)
from crc_sdk.workflows import ExecutionOptions, HazardDataset

HAZARD_NAME = "RiverineInundation"

# (pathway, horizon, tail-scale multiplier). These intentionally demonstrate
# canonical scenario dimensions without claiming to be calibrated projections.
SCENARIOS: tuple[tuple[str, int, float], ...] = (
    ("historical", 1980, 1.0),
    ("tail_stress_10pct", 2050, 1.1),
    ("tail_stress_20pct", 2050, 1.2),
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
        default=[100, 500, 1000],
    )
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def build_multi_scenario_hazard(
    baseline_path: Path,
    output: Path,
) -> Path:
    baseline = read_hazard_dataset(baseline_path)
    metadata = read_hazard_metadata(baseline_path)
    rows = []
    for pathway, horizon, scale_multiplier in SCENARIOS:
        for source in baseline.to_pylist():
            row = dict(source)
            row["pathway"] = pathway
            row["horizon"] = horizon
            row["curve_scale"] = float(row["curve_scale"]) * scale_multiplier
            row["source_id"] = sha256(
                f"{source['source_id']}:{pathway}:{horizon}".encode()
            ).hexdigest()
            rows.append(row)
        print(
            f"  {pathway}/{horizon}: {baseline.num_rows} rows "
            f"(tail scale × {scale_multiplier:.2f})"
        )

    combined = pa.Table.from_pylist(rows, schema=baseline.schema)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_hazard_dataset(combined, output, metadata)
    # Round-trip validates uniqueness across (hazard, horizon, pathway, cell, source).
    print(f"hazard: {read_hazard_dataset(output).num_rows} combined rows -> {output}")
    return output


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    assets_path: Path = args.asset_input
    baseline_path: Path = args.hazard_input
    hazard_path = output_dir / "wri_riverine_multi_scenario.parquet"
    evaluation_path = output_dir / "portfolio_multi_scenario.parquet"

    print("building local stress-scenario hazard:")
    build_multi_scenario_hazard(baseline_path, hazard_path)

    # No pathway/horizon filter: one output row per asset × scenario present.
    result = (
        HazardDataset.local(hazard_path)
        .for_assets(assets_path)
        .select(hazard_names=[HAZARD_NAME])
        .return_periods(args.return_periods)
        .write_parquet(
            evaluation_path,
            execution=ExecutionOptions(max_workers=args.max_workers),
        )
    )
    evaluated = pq.read_table(evaluation_path).to_pandas()
    print(f"evaluated rows: {result.row_count}")
    print(f"value columns: {', '.join(result.value_columns)}")
    summary = (
        evaluated.groupby(["pathway", "horizon"], as_index=False)[list(result.value_columns)]
        .mean(numeric_only=True)
        .sort_values(["horizon", "pathway"])
    )
    print(summary.to_string(index=False))
    print(f"wrote {evaluation_path}")


if __name__ == "__main__":
    main()
