"""Inspect NOAA IBTrACS storm tracks; output is not an asset wind hazard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
from crc_sdk.workflows import IBTrACSPlan


def run(output: Path, storm: str, mode: str = "reuse") -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    plan = IBTrACSPlan("last3years", output / "cache", mode=mode).for_storms([storm])
    provenance = plan.prefetch()
    # Use the verified snapshot after acquisition, even when refreshing.
    plan = IBTrACSPlan(
        "last3years",
        output / "cache",
        mode="offline",
        expected_sha256=str(provenance["sha256"]),
    ).for_storms([storm])
    writer = None
    count = 0
    try:
        for batch in plan.batches():
            if writer is None:
                writer = pq.ParquetWriter(output / "track.parquet", batch.schema)
            writer.write_batch(batch)
            count += batch.num_rows
    finally:
        if writer is not None:
            writer.close()
    if not count:
        raise ValueError(f"storm {storm} not found in this snapshot")
    summary = {"storm": storm, "track_points": count, "source": provenance}
    (output / "provenance.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/ibtracs"))
    parser.add_argument("--storm", default="2024279N21265")
    parser.add_argument(
        "--mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.storm, args.mode), indent=2))
