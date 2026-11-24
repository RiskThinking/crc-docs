"""Fit heat and cold return levels from NOAA ISD or GHCNh station records.

Run from the repository root:

    uv run python pipelines/noaa_isd_pipeline.py --stations 71624099999
    uv run python pipelines/noaa_isd_pipeline.py --source ghcnh --stations USW00094846

Use --bounds WEST SOUTH EAST NORTH to select stations by area.

crc-sdk reduces each station's hourly reports to annual maximum daily maximum
and annual minimum daily minimum temperature. A day counts only with reports in
all 24 hours; a year counts only when ``--minimum-coverage`` of its days are
complete. The annual values are saved, then fitted explicitly (GEV by
L-moments, Gumbel fallback) and queried at return periods: upper tail for heat,
lower tail for cold. Values come from sampled hourly reports, not instrument
daily TXx/TNn. Station points do not represent nearby assets.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from crc_framework import DistributionFamily, SampleEstimator, SampleFit
from crc_sdk import (
    ISD,
    Assets,
    Bounds,
    Cache,
    Coverage,
    FitFailure,
    GHCNh,
    Period,
    Runtime,
    Samples,
)

CACHES = {"reuse": Cache.reuse, "offline": Cache.offline, "refresh": Cache.refresh}
PROVIDERS = {"isd": ISD, "ghcnh": GHCNh}
RETURN_PERIODS = (2.0, 5.0, 10.0, 20.0, 50.0, 100.0)
TAILS = {
    "heat": (
        "ANNUAL_MAXIMUM_DAILY_MAXIMUM_TEMPERATURE",
        DistributionFamily.GUMBEL_RIGHT,
    ),
    "cold": (
        "ANNUAL_MINIMUM_DAILY_MINIMUM_TEMPERATURE",
        DistributionFamily.GUMBEL_LEFT,
    ),
}
LEVELS = pa.schema(
    [
        ("station", pa.string()),
        ("support_id", pa.string()),
        ("tail", pa.string()),
        ("return_period_years", pa.float64()),
        ("temperature", pa.float64()),
        ("unit", pa.string()),
        ("failure", pa.string()),
        ("beyond_requested_window", pa.bool_()),
    ]
)


def fit_spec(minimum_years: int, fallback: DistributionFamily) -> SampleFit:
    return SampleFit(
        family=DistributionFamily.GENERALIZED_EXTREME_VALUE,
        estimator=SampleEstimator.L_MOMENTS,
        minimum_samples=minimum_years,
        fallbacks=(SampleFit(family=fallback, minimum_samples=minimum_years),),
    )


def return_levels(
    samples: dict[str, Samples],
    output: Path,
    *,
    minimum_years: int = 20,
    years: int | None = None,
    return_periods: Sequence[float] = RETURN_PERIODS,
    runtime: Runtime | None = None,
) -> dict[str, Any]:
    """Save annual samples per tail, fit them, and query each station support."""
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    report: dict[str, Any] = {}
    for tail, recipe in samples.items():
        annual = recipe.write(
            output / f"{tail}_annual.parquet", overwrite=True, runtime=runtime
        )
        evidence = annual.read()
        table = evidence.table
        unit = evidence.metadata.spec.variables[0].measurement.unit.value
        supports: dict[str, tuple[str | None, float, float]] = {}
        for support, station, geometry in zip(
            table["support_id"].to_pylist(),
            table["station_id"].to_pylist(),
            table["geometry"].to_pylist(),
        ):
            if support not in supports and geometry is not None:
                point = shapely.from_wkb(geometry)
                supports[support] = (station, point.x, point.y)
        fitted = annual.fit(
            fit_spec(minimum_years, TAILS[tail][1]), on_failure=FitFailure.KEEP_NO_DATA
        ).write(output / f"{tail}_fitted.parquet", overwrite=True)
        evaluated = (
            fitted.evaluate(
                Assets(
                    {
                        "support_id": list(supports),
                        "longitude": [s[1] for s in supports.values()],
                        "latitude": [s[2] for s in supports.values()],
                    },
                    id_column="support_id",
                )
            )
            .return_periods(list(return_periods))
            .read()
            .table
        )
        for row in evaluated.to_pylist():
            rows.append(
                {
                    "station": supports[row["asset_id"]][0],
                    "support_id": row["asset_id"],
                    "tail": tail,
                    "return_period_years": row["query_value"],
                    "temperature": row["value"],
                    "unit": unit,
                    "failure": row["failure"]["code"] if row["failure"] else None,
                    "beyond_requested_window": (
                        None if years is None else row["query_value"] > years
                    ),
                }
            )
        counts = evidence.report.counts
        report[tail] = {
            "annual_values": counts.produced,
            "usable_years": counts.usable_years,
            "incomplete_years": counts.incomplete_years,
            "station_supports": len(supports),
            "fit_failures": dict(
                Counter(
                    r["failure"] for r in rows if r["tail"] == tail and r["failure"]
                )
            ),
            "diagnostics": sorted({d.code for d in evidence.report.diagnostics}),
        }
    temporary = output / ".return_levels.parquet.tmp"
    pq.write_table(pa.Table.from_pylist(rows, schema=LEVELS), temporary)
    os.replace(temporary, output / "return_levels.parquet")
    return {"tails": report, "return_levels": str(output / "return_levels.parquet")}


def run(
    stations: list[str] | None,
    output: Path,
    *,
    start: int = 2000,
    end: int = 2024,
    minimum_years: int = 20,
    minimum_coverage: float = 0.9,
    mode: str = "reuse",
    workers: int = 4,
    source: str = "ghcnh",
    bounds: Sequence[float] | None = None,
) -> dict[str, Any]:
    if source not in PROVIDERS:
        raise ValueError("source must be isd or ghcnh")
    if bounds is None and not stations:
        raise ValueError("supply station IDs or bounds")
    provider = PROVIDERS[source]
    selection: dict[str, Any] = {"time": Period.window(start, end)}
    if bounds is not None:
        west, south, east, north = bounds
        selection["area"] = Bounds(west=west, south=south, east=east, north=north)
    else:
        selection["stations"] = stations
    samples = {
        tail: provider(
            indicator=provider.Indicator[indicator],
            coverage=Coverage.minimum_fraction(minimum_coverage),
        ).select(**selection)
        for tail, (indicator, _) in TAILS.items()
    }
    runtime = Runtime(
        cache=CACHES[mode](output / "cache"), workers=workers, memory_limit="1GB"
    )
    summary = {
        "source": source,
        "selection": {
            "stations": stations,
            "bounds": list(bounds) if bounds else None,
            "years": [start, end],
        },
        **return_levels(
            samples,
            output,
            minimum_years=minimum_years,
            years=end - start + 1,
            runtime=runtime,
        ),
        "interpretation": (
            f"Derived from NOAA {source.upper()} hourly reports, not instrument "
            "daily TXx/TNn. Return levels assume a stationary baseline; long "
            "return periods are uncertain extrapolations."
        ),
    }
    temporary = output / ".summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    os.replace(temporary, output / "summary.json")
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # GHCNh merges ISD's same-time reports; crc-sdk 1.0.0a2 cannot yet read ISD hourly data.
    parser.add_argument("--source", choices=sorted(PROVIDERS), default="ghcnh")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--stations", nargs="+", help="IDs for the chosen source")
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
    parser.add_argument(
        "--minimum-coverage",
        type=float,
        default=0.9,
        help="Fraction of complete days a year needs",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cache-mode", choices=sorted(CACHES), default="reuse")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    stations = args.stations
    if stations is None and args.bounds is None:
        stations = ["71624099999"] if args.source == "isd" else ["USW00094846"]
    summary = run(
        stations,
        args.output or Path(f"pipeline_output/noaa_{args.source}"),
        start=args.start,
        end=args.end,
        minimum_years=args.minimum_years,
        minimum_coverage=args.minimum_coverage,
        mode=args.cache_mode,
        workers=args.workers,
        source=args.source,
        bounds=args.bounds,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
