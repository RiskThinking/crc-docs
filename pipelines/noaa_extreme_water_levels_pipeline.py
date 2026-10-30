"""Inspect NOAA annual high-water exceedance estimates at one station."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
from crc_sdk.workflows import NOAAExtremeWaterLevelPlan


def run(
    output: Path,
    station: str = "8638610",
    mode: str = "reuse",
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    selection = NOAAExtremeWaterLevelPlan.for_station(station)
    sources = selection.cache(output / "cache", mode=mode).prefetch()
    hashes = {key: item["sha256"] for key, item in sources.items()}
    replay = selection.cache(output / "cache", mode="offline", sha256=hashes)
    info = replay.source_info()
    levels = replay.source_levels()
    annual = replay.annual_extremes()
    pq.write_table(levels, output / "exceedance_levels.parquet")
    pq.write_table(annual, output / "annual_detrended.parquet")
    summary = {
        "station": station,
        "levels": levels.num_rows,
        "annual_extremes": annual.num_rows,
        "context": info,
        "sources": sources,
    }
    (output / "provenance.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default="8638610")
    parser.add_argument(
        "--output", type=Path, default=Path("pipeline_output/noaa_water_levels")
    )
    parser.add_argument(
        "--mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.station, args.mode), indent=2))
