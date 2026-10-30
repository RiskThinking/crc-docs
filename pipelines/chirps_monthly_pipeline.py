"""Inspect one CHIRPS v3 final monthly precipitation raster window."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
from crc_sdk.workflows import CHIRPSMonthlyPlan


def run(
    output: Path,
    year: int = 2020,
    month: int = 1,
    bounds: tuple[float, float, float, float] = (36.75, -1.35, 36.85, -1.25),
    mode: str = "reuse",
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    selection = CHIRPSMonthlyPlan.monthly(year, month).for_area(bounds)
    source = selection.cache(output / "cache", mode=mode).prefetch()
    replay = selection.cache(output / "cache", mode="offline", sha256=source["sha256"])
    temp = output / "monthly.parquet.tmp"
    writer = None
    count = 0
    try:
        for batch in replay.batches():
            if writer is None:
                writer = pq.ParquetWriter(temp, batch.schema)
            writer.write_batch(batch)
            count += batch.num_rows
        if writer is None:
            raise ValueError("The window contains no observed land pixels")
        writer.close()
        writer = None
        temp.replace(output / "monthly.parquet")
    finally:
        if writer is not None:
            writer.close()
        temp.unlink(missing_ok=True)
    summary = {"source": source, "bounds": bounds, "valid_pixels": count}
    (output / "provenance.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2020)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument(
        "--bounds", type=float, nargs=4, default=(36.75, -1.35, 36.85, -1.25)
    )
    parser.add_argument(
        "--output", type=Path, default=Path("pipeline_output/chirps_monthly")
    )
    parser.add_argument(
        "--mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.output, args.year, args.month, tuple(args.bounds), args.mode),
            indent=2,
        )
    )
