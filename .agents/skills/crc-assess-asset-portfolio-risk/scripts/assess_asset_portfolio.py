#!/usr/bin/env python3
"""Evaluate supplied assets against multiple CRC canonical hazard files separately."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pyarrow.csv as pacsv
from crc_sdk.workflows import ExecutionOptions, HazardDataset


def hazard_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("hazard must be NAME=PATH")
    name, raw_path = value.split("=", 1)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise argparse.ArgumentTypeError("hazard name must be lowercase letters, numbers, _ or -")
    return name, Path(raw_path)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", required=True, type=Path)
    p.add_argument("--hazard", action="append", required=True, type=hazard_arg, help="Repeat NAME=PATH")
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--periods", nargs="+", type=float, default=[25, 100, 500])
    p.add_argument("--pathway", action="append", help="Optional exact canonical pathway; repeatable")
    p.add_argument("--horizon", action="append", type=int, help="Optional exact canonical horizon; repeatable")
    p.add_argument("--workers", type=int, default=1, help="Explicit process count; raise only after profiling")
    return p


def main() -> int:
    args = parser().parse_args()
    assets = pacsv.read_csv(args.assets)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, hazard_path in args.hazard:
        dataset = HazardDataset.local(hazard_path)
        print(f"{name}: {dataset.metadata()}")
        request = dataset.for_assets(assets).select(pathways=args.pathway, horizons=args.horizon).return_periods(args.periods)
        output = args.output_dir / f"{name}.parquet"
        print(request.write_parquet(output, execution=ExecutionOptions(max_workers=args.workers)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
