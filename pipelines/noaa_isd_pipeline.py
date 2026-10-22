"""Audit NOAA ISD or GHCNh station extremes and fit heat/cold curves.

Requires crc-sdk >=0.9.0a1 and its geometry extra. Run from the repository root:
    python pipelines/noaa_isd_pipeline.py --stations 71624099999
    python pipelines/noaa_isd_pipeline.py --source ghcnh --stations USW00094846

Use --bounds WEST SOUTH EAST NORTH to select station locations by area.

Daily caches serve both temperature tails. No hourly files are retained.
Station points do not represent nearby assets or an H3 cell's entire area.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from crc_sdk.workflows import (
    BlockExtremaPolicy,
    GHCNhPlan,
    HazardDataset,
    ISDPlan,
    curve_quantiles,
    return_periods_to_probabilities,
)


def run(
    stations: list[str] | None,
    output: Path,
    *,
    start: int = 2000,
    end: int = 2024,
    minimum_years: int = 20,
    mode: str = "reuse",
    workers: int = 4,
    source: str = "isd",
    bounds: Sequence[float] | None = None,
) -> dict[str, object]:
    if source not in ("isd", "ghcnh"):
        raise ValueError("source must be isd or ghcnh")
    factory = HazardDataset.isd if source == "isd" else HazardDataset.ghcnh
    output.mkdir(parents=True, exist_ok=True)

    def recipe_plan(recipe: str, cache_mode: str) -> ISDPlan | GHCNhPlan:
        selection = factory(recipe)
        if bounds is not None:
            selection = selection.for_area(bounds)
        elif stations:
            selection = selection.for_stations(stations)
        else:
            raise ValueError("supply station IDs or bounds")
        return (
            selection.years(start, end)
            .quality(minimum_hour_fraction=0.75, minimum_day_fraction=0.9)
            .execution(workers=workers, memory_limit="256MB")
            .cache(output / "cache", mode=cache_mode)
        )

    base = recipe_plan("temperature_max", mode)
    print(base.explain())
    if bounds is not None:
        metadata = base.stations()
        pq.write_table(metadata, output / "selected_stations.parquet")
        base = base.resolve_stations()
    prefetched = base.prefetch()
    periods = (2.0, 5.0, 10.0, 20.0, 50.0, 100.0)
    level_schema = pa.schema(
        [
            ("station", pa.string()),
            ("hazard_name", pa.string()),
            ("tail", pa.string()),
            ("return_period_years", pa.float64()),
            ("temperature_degC", pa.float64()),
            ("beyond_requested_window", pa.bool_()),
        ]
    )
    count = 0
    with pq.ParquetWriter(output / "return_levels.parquet", level_schema) as writer:
        for recipe, tail in (
            ("temperature_max", "upper"),
            ("temperature_min", "lower"),
        ):
            plan = recipe_plan(recipe, "offline")
            if bounds is not None:
                plan = plan.resolve_stations()
            plan = plan.canonicalize(
                policy=BlockExtremaPolicy.curated(
                    minimum_years=minimum_years,
                    diagnostics=output / f"{recipe}_diagnostics.parquet",
                )
            )
            plan.write_annual_extremes(output / f"{recipe}_annual.parquet")
            curves = output / f"{recipe}_curves.parquet"
            plan.materialize(curves)
            probabilities = return_periods_to_probabilities(periods, tail=tail)
            for batch in pq.ParquetFile(curves).iter_batches(batch_size=4096):
                table = pa.Table.from_batches([batch])
                values = curve_quantiles(table, probabilities, max_workers=1)
                rows = [
                    {
                        "station": row["source_id"].split(":", 1)[1],
                        "hazard_name": row["hazard_name"],
                        "tail": tail,
                        "return_period_years": period,
                        "temperature_degC": value,
                        "beyond_requested_window": period > end - start + 1,
                    }
                    for row, levels in zip(table.to_pylist(), values)
                    for period, value in zip(periods, levels)
                ]
                writer.write_table(pa.Table.from_pylist(rows, schema=level_schema))
                count += table.num_rows
    summary = {
        "source_version": prefetched.source_version,
        "station_year_cache_hits": prefetched.cache_hits,
        "station_year_cache_misses": prefetched.cache_misses,
        "fitted_station_curves": count,
        "return_levels": str(output / "return_levels.parquet"),
        "interpretation": (
            f"Derived from NOAA {source.upper()} sampled temperature, "
            "not instrument daily TXx/TNn. "
            "Return levels assume a stationary baseline. Check annual completeness "
            "and fit diagnostics; long return periods are uncertain extrapolations."
        ),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("isd", "ghcnh"), default="isd")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--stations", nargs="+", help="Explicit IDs for the chosen source"
    )
    selection.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Select catalogue station locations inside this WGS84 box",
    )
    parser.add_argument("--start", type=int, default=2000)
    parser.add_argument("--end", type=int, default=2024)
    parser.add_argument("--minimum-years", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--cache-mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    stations = args.stations
    if stations is None and args.bounds is None:
        stations = ["71624099999"] if args.source == "isd" else ["USW00094846"]
    output = args.output or Path(f"pipeline_output/noaa_{args.source}")
    print(
        json.dumps(
            run(
                stations,
                output,
                start=args.start,
                end=args.end,
                minimum_years=args.minimum_years,
                mode=args.cache_mode,
                workers=args.workers,
                source=args.source,
                bounds=args.bounds,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
