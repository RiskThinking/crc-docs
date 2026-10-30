"""Inspect NOAA 2022 relative sea-level scenarios at a U.S. station."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
from crc_sdk.workflows import NOAASeaLevelPlan


def run(
    output: Path,
    station: str = "8638610",
    scenario: str = "all",
    mode: str = "reuse",
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    selection = NOAASeaLevelPlan.for_station(station).scenario(scenario)
    source = selection.cache(output / "cache", mode=mode).prefetch()
    replay = selection.cache(output / "cache", mode="offline", sha256=source["sha256"])
    projections = replay.projections()
    pq.write_table(projections, output / "projections.parquet")
    summary = {"station": station, "rows": projections.num_rows, "source": source}
    (output / "provenance.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default="8638610")
    parser.add_argument(
        "--scenario",
        choices=(
            "all",
            "low",
            "intermediate-low",
            "intermediate",
            "intermediate-high",
            "high",
        ),
        default="all",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("pipeline_output/noaa_sea_level")
    )
    parser.add_argument(
        "--mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    args = parser.parse_args()
    print(
        json.dumps(run(args.output, args.station, args.scenario, args.mode), indent=2)
    )
