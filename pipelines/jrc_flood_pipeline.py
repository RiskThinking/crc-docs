"""Materialize JRC flood curves for an AOI through the fluent SDK workflow.

Run with:

    uv run python pipelines/jrc_flood_pipeline.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from crc_sdk.connectors import read_hazard_dataset
from crc_sdk.workflows import (
    HazardDataset,
    JRCFloodPolicy,
    curve_quantiles_at,
    return_periods_to_probabilities,
    warn_if_extrapolated,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=(-79.65, 43.58, -79.15, 43.85),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    p.add_argument(
        "--return-periods", type=int, nargs="+", default=[10, 50, 100, 500]
    )
    p.add_argument(
        "--dataset",
        choices=("efas", "glofas"),
        default="glofas",
        help="Use EFAS for Europe and GloFAS for global coverage",
    )
    p.add_argument("--h3-resolution", type=int, default=9)
    p.add_argument(
        "--cache-mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    p.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return p


def parse_args() -> argparse.Namespace:
    return parser().parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    plan = (
        getattr(HazardDataset, args.dataset)(version="latest")
        .for_area(tuple(args.bounds))
        .cache(output_dir / "jrc-source-cache", mode=args.cache_mode)
        .source_periods("all")
        .canonicalize(policy=JRCFloodPolicy.curated(h3_resolution=args.h3_resolution))
    )
    print(plan.explain())
    hazard_path = output_dir / "jrc_depths_by_cell.parquet"
    hazard = plan.materialize(hazard_path)
    metadata = hazard.metadata()
    warn_if_extrapolated(args.return_periods, metadata.return_period_support)

    table = read_hazard_dataset(hazard.provider.source)
    cells = table["cell_index"].to_pylist()
    print(
        f"wrote {hazard_path}: {table.num_rows:,} fitted curves "
        f"from JRC {hazard.materialization.source_version}"
    )
    probabilities = return_periods_to_probabilities(
        args.return_periods,
        tail=metadata.return_period_tail,
    )
    for period, probability in zip(args.return_periods, probabilities):
        by_cell: dict[int, float] = {}
        for cell, depth in zip(cells, curve_quantiles_at(table, probability)):
            by_cell[cell] = max(depth, by_cell.get(cell, float("-inf")))
        peak = max(by_cell.values()) if by_cell else 0.0
        print(f"  RP{period}: {len(by_cell):,} cells, max depth {peak:.2f} m")


if __name__ == "__main__":
    main()
