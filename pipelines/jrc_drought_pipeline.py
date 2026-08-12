"""Materialize EDO drought curves for an AOI through the fluent SDK workflow.

Run with:

    uv run python pipelines/jrc_drought_pipeline.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from crc_sdk.connectors import read_hazard_dataset
from crc_sdk.workflows import (
    EDODroughtPolicy,
    HazardDataset,
    curve_quantiles_at,
    return_periods_to_probabilities,
    warn_if_extrapolated,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=(7.0, 49.0, 11.0, 53.0),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs=2,
        default=(1995, 2025),
        metavar=("START", "END"),
        help="Complete-year observation range, inclusive",
    )
    parser.add_argument("--return-periods", type=int, nargs="+", default=[2, 5, 10, 25])
    parser.add_argument("--h3-resolution", type=int, default=6)
    parser.add_argument(
        "--cache-mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    plan = (
        HazardDataset.smi(version="latest")
        .for_area(tuple(args.bounds))
        .years(args.years[0], args.years[1])
        .cache(output_dir / "edo-smi-source-cache", mode=args.cache_mode)
        .canonicalize(
            policy=EDODroughtPolicy.curated(
                h3_resolution=args.h3_resolution,
            )
        )
    )
    print(plan.explain())
    hazard_path = output_dir / "jrc_edo_drought_by_cell.parquet"
    hazard = plan.materialize(hazard_path)
    metadata = hazard.metadata()
    warn_if_extrapolated(args.return_periods, metadata.return_period_support)

    table = read_hazard_dataset(hazard.provider.source)
    cells = table["cell_index"].to_pylist()
    print(
        f"wrote {hazard_path}: {table.num_rows:,} fitted curves from "
        f"EDO {hazard.materialization.source_version}"
    )
    probabilities = return_periods_to_probabilities(
        args.return_periods,
        tail=metadata.return_period_tail,
    )
    for period, probability in zip(args.return_periods, probabilities):
        by_cell: dict[int, float] = {}
        for cell, severity in zip(cells, curve_quantiles_at(table, probability)):
            by_cell[cell] = min(severity, by_cell.get(cell, float("inf")))
        worst = min(by_cell.values()) if by_cell else 0.0
        print(f"  RP{period}: {len(by_cell):,} cells, worst SMI {worst:.3f}")


if __name__ == "__main__":
    main()
