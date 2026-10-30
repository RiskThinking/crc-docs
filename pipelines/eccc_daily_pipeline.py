"""Inspect ECCC GeoMet daily climate observations and their source flags."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
from crc_sdk.workflows import ECCCDailyPlan


def run(
    output: Path,
    climate_id: str = "6158731",
    start: int = 2020,
    end: int = 2020,
    mode: str = "reuse",
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    selection = ECCCDailyPlan.for_station(climate_id).years(start, end)
    snapshots = selection.cache(output / "cache", mode=mode).prefetch()
    hashes = {source["year"]: source["sha256"] for source in snapshots}
    replay = selection.cache(output / "cache", mode="offline", sha256=hashes)
    temp = output / "daily.parquet.tmp"
    writer = None
    count = 0
    try:
        for batch in replay.batches():
            if writer is None:
                writer = pq.ParquetWriter(temp, batch.schema)
            writer.write_batch(batch)
            count += batch.num_rows
        if writer is None:
            raise ValueError(
                "No observations returned for the selected station and years"
            )
        writer.close()
        writer = None
        temp.replace(output / "daily.parquet")
    finally:
        if writer is not None:
            writer.close()
        temp.unlink(missing_ok=True)
    summary = {"climate_id": climate_id, "observations": count, "sources": snapshots}
    (output / "provenance.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--climate-id", default="6158731")
    parser.add_argument("--start", type=int, default=2020)
    parser.add_argument("--end", type=int, default=2020)
    parser.add_argument(
        "--output", type=Path, default=Path("pipeline_output/eccc_daily")
    )
    parser.add_argument(
        "--mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.output, args.climate_id, args.start, args.end, args.mode), indent=2
        )
    )
