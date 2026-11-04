#!/usr/bin/env python3
"""Apply a declared flood depth-damage curve to portfolio events.

The curve is an ``ImpactExpression``: either an approved definition loaded from
JSON (``--curve-json``) or a tabulated curve built from knots. Its SHA-256
``definition_hash`` is printed, written beside the output, and recorded in the
output Parquet metadata, so every result names the exact curve it used.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.csv as pacsv
from crc_sdk.impacts import ImpactCalibration, ImpactExpression
from crc_sdk.workflows import ExecutionOptions, HazardDataset

CALIBRATION = ImpactCalibration(
    exposure_variable="flood_depth",
    exposure_unit="m",
    impact_metric="damage_ratio",
    impact_unit="1",
)


def csv_floats(value: str) -> list[float]:
    try:
        return [float(item) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from error


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hazard", required=True, type=Path, help="CRC canonical flood Parquet")
    p.add_argument("--assets", required=True, type=Path, help="CSV with asset_id, longitude, latitude")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--periods", nargs="+", type=float, default=[25, 100, 250, 500])
    p.add_argument("--pathway", required=True, help="Exact canonical pathway to evaluate")
    p.add_argument("--horizon", required=True, type=int, help="Exact canonical horizon to evaluate")
    curve = p.add_mutually_exclusive_group(required=True)
    curve.add_argument("--curve-json", type=Path, help="Approved ImpactExpression definition (JSON)")
    curve.add_argument("--depth-knots", type=csv_floats, help="Example: 0,0.2,1,2 (metres)")
    p.add_argument("--damage-knots", type=csv_floats, help="Example: 0,0,0.25,1 (damage ratio)")
    p.add_argument("--workers", type=int, default=1, help="Explicit process count; raise only after profiling")
    return p


def load_curve(args: argparse.Namespace) -> ImpactExpression:
    if args.curve_json is not None:
        if args.damage_knots is not None:
            raise SystemExit("--damage-knots is only used with --depth-knots")
        curve = ImpactExpression.from_json(args.curve_json.read_text())
        if curve.calibration.exposure_unit != "m" or curve.calibration.impact_unit != "1":
            raise SystemExit("the curve must map flood depth in metres to a damage ratio (unit 1)")
        return curve
    if args.damage_knots is None:
        raise SystemExit("--depth-knots requires --damage-knots")
    if len(args.depth_knots) != len(args.damage_knots) or len(args.depth_knots) < 2:
        raise SystemExit("depth and damage knots must have equal length >= 2")
    if any(ratio < 0 or ratio > 1 for ratio in args.damage_knots):
        raise SystemExit("damage ratios must be within [0, 1]")
    return ImpactExpression.tabulated(
        list(zip(args.depth_knots, args.damage_knots)),
        calibration=CALIBRATION,
        clamp={"minimum": 0.0, "maximum": 1.0},
    )


def main() -> int:
    args = parser().parse_args()
    curve = load_curve(args)
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
    curve_path = args.output.with_name(f"{args.output.stem}-curve.json")
    curve_path.write_text(curve.to_json())
    print(result)
    print(f"curve: {curve.definition_hash} -> {curve_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
