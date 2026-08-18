#!/usr/bin/env python3
"""Apply a declared piecewise flood depth-damage curve to portfolio events."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.csv as pacsv
from crc_sdk.impacts import PiecewiseLinearImpact
from crc_sdk.workflows import ExecutionOptions, HazardDataset


def csv_floats(value: str) -> list[float]:
    try:
        return [float(item) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from error


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hazard", required=True, type=Path, help="CRC canonical flood Parquet")
    p.add_argument("--assets", required=True, type=Path, help="CSV with asset_id, longitude, latitude")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--periods", nargs="+", type=float, default=[25, 100, 250, 500])
    p.add_argument("--pathway", required=True, help="Exact canonical pathway to evaluate")
    p.add_argument("--horizon", required=True, type=int, help="Exact canonical horizon to evaluate")
    p.add_argument("--depth-knots", required=True, type=csv_floats, help="Example: 0,0.2,1,2")
    p.add_argument("--damage-knots", required=True, type=csv_floats, help="Example: 0,0,0.25,1")
    p.add_argument("--workers", type=int, default=1, help="Explicit process count; raise only after profiling")
    return p


def main() -> int:
    args = parser().parse_args()
    if len(args.depth_knots) != len(args.damage_knots) or len(args.depth_knots) < 2:
        raise SystemExit("depth and damage knots must have equal length >= 2")
    if any(ratio < 0 or ratio > 1 for ratio in args.damage_knots):
        raise SystemExit("damage ratios must be within [0, 1]")

    curve = PiecewiseLinearImpact(exposure=args.depth_knots, impact=args.damage_knots)
    assets = pacsv.read_csv(args.assets)
    request = (
        HazardDataset.local(args.hazard)
        .for_assets(assets)
        .select(pathways=[args.pathway], horizons=[args.horizon])
        .return_periods(args.periods)
        .impact(
            curve,
            name="declared_flood_damage_ratio",
            value_unit="fraction",
            value_semantics="event-aligned damage ratio",
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = request.write_parquet(args.output, execution=ExecutionOptions(max_workers=args.workers))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
