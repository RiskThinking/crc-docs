"""Inspect USGS daily mean streamflow at one explicitly selected gauge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
from crc_sdk.workflows import USGSStreamflowPlan


def run(
    output: Path,
    station: str = "USGS-01491000",
    start: str = "2020-01-01",
    end: str = "2021-12-31",
    mode: str = "reuse",
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    request = USGSStreamflowPlan.for_station(station).between(start, end)
    source = request.cache(output / "cache", mode=mode).prefetch()
    offline = request.cache(output / "cache", mode="offline", sha256=source["sha256"])
    temp = output / "daily.parquet.tmp"
    writer = None
    try:
        for batch in offline.batches():
            if writer is None:
                writer = pq.ParquetWriter(temp, batch.schema)
            writer.write_batch(batch)
        if writer is None:
            raise ValueError("No observations were returned for this selection")
        writer.close()
        writer = None
        temp.replace(output / "daily.parquet")
    finally:
        if writer is not None:
            writer.close()
        temp.unlink(missing_ok=True)
    (output / "provenance.json").write_text(json.dumps(source, indent=2) + "\n")
    return source


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default="USGS-01491000")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2021-12-31")
    parser.add_argument(
        "--output", type=Path, default=Path("pipeline_output/usgs_streamflow")
    )
    parser.add_argument(
        "--mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.output, args.station, args.start, args.end, args.mode), indent=2
        )
    )
