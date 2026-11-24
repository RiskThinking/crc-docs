"""Audit ECCC published rainfall IDF rates against a Gumbel refit.

Run from the repository root after ``uv sync --locked``:

    uv run python pipelines/eccc_idf_pipeline.py
    uv run python pipelines/eccc_idf_pipeline.py --province ON \
        --bounds -79.65 43.65 -79.61 43.70 --bounds -75.70 45.30 -75.65 45.35

crc-sdk reads ECCC's current IDF release for one province. Each station's
published central rates for a duration are a quantile curve (one knot per
published return period), used exactly as published. The pipeline also fits a
Gumbel distribution to those knots and reports the residual at every published
return period, next to ECCC's 95% confidence half-width. Select stations by ID
or with one or more WGS84 boxes inside the province.

Outputs describe station points; they do not assign rainfall to nearby
properties, predict flooding or adjust for climate change. 24-hour moving
maxima are not calendar-day Rx1day.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from crc_framework import DistributionFamily, Duration, QuantileFit, TimeUnit
from crc_sdk import (
    ECCCIDF,
    Assets,
    Cache,
    Dataset,
    FitFailure,
    Runtime,
    StationReference,
)

CACHES = {"reuse": Cache.reuse, "offline": Cache.offline, "refresh": Cache.refresh}
DURATIONS = {
    "5min": 5,
    "10min": 10,
    "15min": 15,
    "30min": 30,
    "1h": 60,
    "2h": 120,
    "6h": 360,
    "12h": 720,
    "24h": 1440,
}
REFIT = QuantileFit(family=DistributionFamily.GUMBEL_RIGHT)
SCHEMA = pa.schema(
    [
        ("station", pa.string()),
        ("name", pa.string()),
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        ("start_year", pa.int64()),
        ("end_year", pa.int64()),
        ("duration", pa.string()),
        ("duration_minutes", pa.int64()),
        ("return_period_years", pa.float64()),
        ("published_mm_h", pa.float64()),
        ("confidence_95_half_width_mm_h", pa.float64()),
        ("fitted_mm_h", pa.float64()),
        ("fit_residual_mm_h", pa.float64()),
        ("published_duration_depth_mm", pa.float64()),
        ("beyond_record_span", pa.bool_()),
    ]
)


def duration_of(label: str) -> Duration:
    minutes = DURATIONS[label]
    if minutes % 60 == 0:
        return Duration(minutes // 60, unit=TimeUnit.HOUR)
    return Duration(minutes * 60, unit=TimeUnit.SECOND)


def choose_stations(
    stations: Sequence[StationReference],
    ids: Sequence[str] | None = None,
    areas: Sequence[Sequence[float]] | None = None,
) -> list[StationReference]:
    """Stations by exact ID, inside any of the boxes, or all (each station once)."""
    if ids is None and areas is None:
        return list(stations)
    if ids is not None:
        known = {station.id: station for station in stations}
        missing = sorted(set(ids) - set(known))
        if missing:
            raise ValueError(f"unknown ECCC IDF stations: {missing}")
        return [known[i] for i in dict.fromkeys(ids)]
    chosen = [
        station
        for station in stations
        if station.longitude is not None
        and any(
            west <= station.longitude <= east and south <= station.latitude <= north
            for west, south, east, north in areas or ()
        )
    ]
    if not chosen:
        raise ValueError("no ECCC IDF station lies inside the boxes")
    return chosen


def audit_duration(
    published: Dataset,
    stations: Sequence[StationReference],
    label: str,
    return_periods: Sequence[float],
    intervals: pa.Table | None = None,
) -> list[dict[str, Any]]:
    """Published rate, its 95% half-width and the Gumbel refit per station/period."""
    assets = Assets(
        {
            "station": [s.id for s in stations],
            "longitude": [s.longitude for s in stations],
            "latitude": [s.latitude for s in stations],
        },
        id_column="station",
    )
    query = list(return_periods)
    exact = published.evaluate(assets).return_periods(query).read().table
    fitted = (
        published.fit(REFIT, on_failure=FitFailure.KEEP_NO_DATA)
        .evaluate(assets)
        .return_periods(query)
        .read()
        .table
    )
    refit = {
        (row["asset_id"], row["query_value"]): row["value"]
        for row in fitted.to_pylist()
    }
    widths = {}
    for row in intervals.to_pylist() if intervals is not None else ():
        if row["interval"] is not None and row["coordinate"]["years"] is not None:
            key = (row["support_id"], row["coordinate"]["years"])
            widths[key] = (row["interval"]["upper"] - row["interval"]["lower"]) / 2
    by_id = {s.id: s for s in stations}
    minutes = DURATIONS[label]
    rows = []
    for row in exact.to_pylist():
        if row["value"] is None:
            continue
        station = by_id[row["asset_id"]]
        period = row["query_value"]
        estimate = refit.get((station.id, period))
        start = station.period.start if station.period else None
        end = station.period.end if station.period else None
        rows.append(
            {
                "station": station.id,
                "name": station.label,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "start_year": start,
                "end_year": end,
                "duration": label,
                "duration_minutes": minutes,
                "return_period_years": period,
                "published_mm_h": row["value"],
                "confidence_95_half_width_mm_h": widths.get(
                    (row["support_id"], period)
                ),
                "fitted_mm_h": estimate,
                "fit_residual_mm_h": (
                    None if estimate is None else estimate - row["value"]
                ),
                "published_duration_depth_mm": row["value"] * minutes / 60,
                "beyond_record_span": (
                    None if start is None else period > end - start + 1
                ),
            }
        )
    return rows


def run(
    output: Path,
    *,
    province: str = "ON",
    stations: Sequence[str] | None = None,
    areas: Sequence[Sequence[float]] | None = None,
    durations: Sequence[str] = ("15min", "1h", "24h"),
    cache_mode: str = "reuse",
    cache: Path | None = None,
) -> dict[str, Any]:
    if stations is not None and areas is not None:
        raise ValueError("supply station IDs or areas, not both")
    if not durations or len(set(durations)) != len(durations):
        raise ValueError("durations must be nonempty and unique")
    output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(cache=CACHES[cache_mode](cache or output / "cache"))
    region = ECCCIDF.Province(province)
    rows: list[dict[str, Any]] = []
    release = None
    selected: list[StationReference] = []
    for label in durations:
        idf = ECCCIDF(duration=duration_of(label), province=region)
        inventory = idf.inspect(runtime=runtime)
        release = inventory.releases[0].id if inventory.releases else release
        selected = choose_stations(
            inventory.stations, stations if areas is None else None, areas
        )
        intervals = idf.confidence_intervals().read(runtime=runtime).table
        periods = sorted(
            {
                row["years"]
                for row in intervals.column("coordinate").to_pylist()
                if row["years"] is not None
            }
        )
        rows += audit_duration(idf, selected, label, periods, intervals)
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    temporary = output / ".rainfall_rates.parquet.tmp"
    pq.write_table(table, temporary)
    os.replace(temporary, output / "rainfall_rates.parquet")
    residuals = [abs(r["fit_residual_mm_h"]) for r in rows if r["fit_residual_mm_h"]]
    summary = {
        "province": province,
        "release": release,
        "stations": sorted({row["station"] for row in rows}),
        "areas": [list(area) for area in areas or ()],
        "durations": list(durations),
        "rate_rows": len(rows),
        "maximum_absolute_fit_residual_mm_h": max(residuals, default=None),
        "output": str(output / "rainfall_rates.parquet"),
        "interpretation": (
            "Published central rates and 95% confidence half-widths are distinct "
            "from the Gumbel refit of those rates. Duration depths use rounded "
            "published rates. 24-hour moving maxima are not calendar-day Rx1day. "
            "Station rates are not flood depths or climate-adjusted projections."
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
    parser.add_argument(
        "--province", choices=[p.value for p in ECCCIDF.Province], default="ON"
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--stations", nargs="+", help="Explicit ECCC climate IDs")
    selection.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        action="append",
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Select stations in a WGS84 box; repeat for a union of boxes",
    )
    parser.add_argument(
        "--durations",
        nargs="+",
        choices=list(DURATIONS),
        default=["15min", "1h", "24h"],
    )
    parser.add_argument("--cache-mode", choices=sorted(CACHES), default="reuse")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/eccc_idf"))
    args = parser.parse_args(argv)
    stations = args.stations
    if stations is None and args.bounds is None and args.province == "ON":
        stations = ["6158731"]  # Toronto Pearson
    summary = run(
        args.output,
        province=args.province,
        stations=stations,
        areas=args.bounds,
        durations=args.durations,
        cache_mode=args.cache_mode,
        cache=args.cache,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
