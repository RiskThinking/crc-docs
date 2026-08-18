#!/usr/bin/env python3
"""Plan or run a JRC flood screen for point collateral assets."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.csv as pacsv
from crc_sdk.workflows import ExecutionOptions, HazardDataset, JRCFloodPolicy


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", required=True, type=Path, help="CSV with asset_id, longitude, latitude")
    p.add_argument("--hazard", type=Path, help="Existing canonical JRC flood Parquet")
    p.add_argument("--dataset", choices=("efas", "glofas"))
    p.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    p.add_argument("--cache", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--hazard-output",
        type=Path,
        help="Optional path for the materialized canonical JRC hazard dataset",
    )
    p.add_argument("--periods", nargs="+", type=float, default=[25, 100, 500])
    p.add_argument("--h3-resolution", type=int, default=10)
    p.add_argument("--cache-mode", choices=("reuse", "offline", "refresh", "stream"), default="reuse")
    p.add_argument("--workers", type=int, default=1, help="Explicit process count; raise only after profiling")
    p.add_argument("--plan-only", action="store_true", help="Explain without fetching or writing")
    return p


def main() -> int:
    args = parser().parse_args()
    if args.hazard:
        if args.hazard_output or args.dataset or args.bounds or args.cache:
            raise SystemExit(
                "--hazard cannot be combined with --hazard-output, --dataset, "
                "--bounds, or --cache"
            )
        source = HazardDataset.local(args.hazard)
        print(source.metadata())
        if args.plan_only:
            return 0
    else:
        if not args.dataset or not args.bounds or not args.cache:
            raise SystemExit(
                "provide --hazard, or provide --dataset, --bounds, and --cache"
            )
        source = getattr(HazardDataset, args.dataset)(version="latest")
        plan = (
            source.for_area(tuple(args.bounds))
            .cache(args.cache, mode=args.cache_mode)
            .source_periods("all")
            .canonicalize(policy=JRCFloodPolicy.curated(h3_resolution=args.h3_resolution))
        )
        print(plan.explain())
        if args.plan_only:
            return 0

        if args.hazard_output:
            args.hazard_output.parent.mkdir(parents=True, exist_ok=True)
            plan.materialize(args.hazard_output)
            source = HazardDataset.local(args.hazard_output)
        else:
            source = plan

    assets = pacsv.read_csv(args.assets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = source.for_assets(assets).return_periods(args.periods).write_parquet(
        args.output, execution=ExecutionOptions(max_workers=args.workers)
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
