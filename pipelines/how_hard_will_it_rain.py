"""How much rain can fall in one day at a place, and is that getting worse?

Answers one question three ways and writes a small, self-describing result:

A. ERA5 (free global reanalysis, 0.25 degree hourly copy): each year's wettest
   day and a fitted curve (the recorded past, on a reanalysis grid).
B. CRC Open ``rx1day`` curves for four-year periods from 2023-2026 to
   2088-2091 under SSP5-8.5, averaged over groups of periods because single
   periods are noisy (free, ready-made; CRC Open has no historical baseline).
C. CDT (Climate Digital Twin) return levels for a historical baseline and
   three pathways in 2070-2090, only when ``RISKTHINKING_API_KEY`` is set.

Run from the repository root:

    uv run python pipelines/how_hard_will_it_rain.py --skip-era5
    uv run python pipelines/how_hard_will_it_rain.py --name Chicago --latitude 41.88 --longitude -87.63 --skip-era5

Outputs land in ``--output`` (default ``pipeline_output/how_hard_rain``):
``summary.json`` (plain-language answer plus provenance) and ``return_levels.csv``.
Rain is millimetres on the wettest day of the year. ERA5 is slow: its public
store keeps one global field per hour, so every year downloads about 16 GB
even for one place. ``--skip-era5`` gives a quick answer from CRC Open (and
CDT) alone. Set ``CRC_OPEN_CATALOG`` to read another CRC Open release index.
See ``notebooks/how_hard_will_it_rain.ipynb`` for the explained version.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from crc_framework import DistributionFamily, SampleEstimator, SampleFit
from crc_sdk import (
    ERA5,
    Assets,
    Bounds,
    Cache,
    CRCOpen,
    FitFailure,
    Period,
    ReadResult,
    Runtime,
)

CRC_OPEN = os.environ.get(
    "CRC_OPEN_CATALOG", "https://data.riskthinking.ai/crc-open/_CURRENT.json"
)
RETURN_PERIODS = (2, 5, 10, 25)
# Groups of CRC Open four-year periods, by the years they span.
WINDOWS = {
    "2023-2046": (2023, 2046),
    "2048-2066": (2048, 2066),
    "2068-2091": (2068, 2091),
}
CDT_PATHWAYS = ("ssp126", "ssp245", "ssp585")
CDT_LATE_HORIZONS = (2070, 2080, 2090)
MORE_DATA = "mailto:opensource@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"
RP_GRID = np.geomspace(1.2, 100, 200)


def levels_dict(levels: Any) -> dict[int, float]:
    return dict(zip(RETURN_PERIODS, np.round(levels, 1).tolist(), strict=True))


def licence_of(report: Any) -> str | None:
    for source in report.source_identities:
        for resource in source.resources:
            if resource.license:
                return resource.license
    return None


def place_assets(name: str, latitude: float, longitude: float) -> Assets:
    return Assets(
        {"asset_id": [name], "longitude": [longitude], "latitude": [latitude]}
    )


def annual_fit(years: int) -> SampleFit:
    """GEV by L-moments with a Gumbel fallback, needing most of the years."""
    minimum = min(20, years)
    return SampleFit(
        family=DistributionFamily.GENERALIZED_EXTREME_VALUE,
        estimator=SampleEstimator.L_MOMENTS,
        minimum_samples=minimum,
        fallbacks=(
            SampleFit(family=DistributionFamily.GUMBEL_RIGHT, minimum_samples=minimum),
        ),
    )


def era5_summary(
    annual: ReadResult,
    place: Assets,
    years: tuple[int, int],
    runtime: Runtime,
) -> dict[str, Any]:
    """Fit annual wettest days and read them at the grid cell holding the place."""
    fitted = annual.fit(annual_fit(years[1] - years[0] + 1), on_failure=FitFailure.SKIP)
    rows = (
        fitted.evaluate(place)
        .return_periods(RETURN_PERIODS)
        .read(runtime=runtime)
        .table.to_pylist()
    )
    matched = [row for row in rows if row["value"] is not None]
    if not matched:
        return {"available": False, "reason": "no ERA5 curve could be fitted here"}
    support = matched[0]["support_id"]
    samples = [
        row
        for row in annual.table.to_pylist()
        if row["support_id"] == support and row["value"] is not None
    ]
    wettest = max(samples, key=lambda row: row["value"])
    cell = shapely.from_wkb(samples[0]["geometry"]).centroid
    return {
        "available": True,
        "grid_point": [round(cell.y, 3), round(cell.x, 3)],
        "grid_spacing_degrees": 0.25,
        "years": list(years),
        "complete_years": len(samples),
        "wettest_day_mm": round(float(wettest["value"]), 1),
        "wettest_year": int(wettest["time"]),
        "fit": "GEV (L-moments), Gumbel fallback",
        "return_levels_mm": levels_dict([row["value"] for row in matched]),
        "licence": licence_of(annual.report) or "CC-BY-4.0",
    }


def era5_answer(
    name: str,
    latitude: float,
    longitude: float,
    years: tuple[int, int],
    runtime: Runtime,
) -> dict[str, Any]:
    """ERA5 annual wettest days at the 0.25 degree cell holding the place."""
    samples = ERA5(indicator=ERA5.Indicator.ANNUAL_MAXIMUM_DAILY_PRECIPITATION).select(
        area=Bounds(
            west=longitude - 0.1,
            south=latitude - 0.1,
            east=longitude + 0.1,
            north=latitude + 0.1,
        ),
        time=Period.window(*years),
    )
    try:
        annual = samples.read(runtime=runtime)
    except (ValueError, LookupError) as error:
        return {"available": False, "reason": str(error)}
    return era5_summary(annual, place_assets(name, latitude, longitude), years, runtime)


def crc_open_answer(
    name: str, latitude: float, longitude: float, runtime: Runtime
) -> dict[str, Any]:
    """Average CRC Open rx1day return levels over groups of periods at the place."""
    source = CRCOpen(catalog=CRC_OPEN).select(
        variables=CRCOpen.Variable.ANNUAL_MAXIMUM_DAILY_PRECIPITATION,
        area=Bounds(
            west=longitude - 0.01,
            south=latitude - 0.01,
            east=longitude + 0.01,
            north=latitude + 0.01,
        ),
    )
    try:
        inventory = source.inspect(runtime=runtime)
        evaluation = (
            source.evaluate(place_assets(name, latitude, longitude))
            .return_periods(RP_GRID.tolist())
            .read(runtime=runtime)
        )
    except (ValueError, LookupError) as error:  # e.g. no release index or cell here
        return {"available": False, "reason": str(error)}
    periods = {series.period.id: series.period for series in inventory.series}
    curves: dict[str, list[float]] = {}
    support = None
    for row in evaluation.table.to_pylist():
        if row["value"] is not None:
            curves.setdefault(row["period_id"], []).append(row["value"])
            support = row["support_id"]
    if not curves:
        return {"available": False, "reason": "no CRC Open rx1day curve at this place"}
    grouped: dict[str, list[str]] = {
        label: [
            period_id
            for period_id, period in sorted(periods.items(), key=lambda p: p[1].start)
            if period_id in curves and first <= period.start and period.end <= last
        ]
        for label, (first, last) in WINDOWS.items()
    }
    windows = {
        label: np.mean([curves[period_id] for period_id in ids], axis=0)
        for label, ids in grouped.items()
        if ids
    }
    first, last = next(iter(windows)), list(windows)[-1]
    threshold = float(np.interp(10, RP_GRID, windows[first]))
    return {
        "available": True,
        "release": inventory.series[0].release.id,
        "scenario": "ssp585",
        "note": "CRC Open covers SSP5-8.5 only and has no historical baseline.",
        "support_id": support,
        "windows": {
            label: [f"{periods[i].start}-{periods[i].end}" for i in ids]
            for label, ids in grouped.items()
            if ids
        },
        "return_levels_mm": {
            label: levels_dict(np.interp(RETURN_PERIODS, RP_GRID, levels))
            for label, levels in windows.items()
        },
        "baseline_window": first,
        "baseline_1_in_10_mm": round(threshold, 1),
        "late_1_in_10_mm": round(float(np.interp(10, RP_GRID, windows[last])), 1),
        "baseline_1_in_10_becomes_every_n_years": {
            label: round(
                float(np.exp(np.interp(threshold, levels, np.log(RP_GRID)))), 1
            )
            for label, levels in windows.items()
        },
        "licence": licence_of(evaluation.report) or "CC-BY-NC-4.0",
        "other_pathways": f"Ask the open-source team: {MORE_DATA}",
    }


def cdt_answer(latitude: float, longitude: float) -> dict[str, Any]:
    """Query CDT rx1day return levels when an API key is configured."""
    if not os.environ.get("RISKTHINKING_API_KEY"):
        return {
            "available": False,
            "reason": "RISKTHINKING_API_KEY not set",
            "trial": TRIAL,
        }
    from velo_sdk.api import APIClient

    client = APIClient()
    requests = [("historic", 2010)] + [
        (pathway, horizon) for pathway in CDT_PATHWAYS for horizon in CDT_LATE_HORIZONS
    ]
    samples: dict[str, list[list[float]]] = {}
    for pathway, horizon in requests:
        response = client.get(
            "/v4/climate/metrics/exposure",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "risk_factor": "rx1day",  # singular; the plural is ignored
                "pathway": pathway,
                "horizon": str(horizon),
                "return_periods": ",".join(map(str, RETURN_PERIODS)),
            },
        )
        for result in response["results"]:
            if result["index_name"] != "rx1day":
                continue
            values = result["exposure_return_periods"]
            samples.setdefault(pathway, []).append(
                [float(values[str(period)]) for period in RETURN_PERIODS]
            )
    if not samples:
        return {"available": False, "reason": "CDT returned no rx1day results here"}
    late = f"{CDT_LATE_HORIZONS[0]}-{CDT_LATE_HORIZONS[-1]}"
    return {
        "available": True,
        "return_levels_mm": {
            ("historic 2010" if pathway == "historic" else f"{pathway} {late}"): (
                levels_dict(np.mean(values, axis=0))
            )
            for pathway, values in samples.items()
        },
        "missing": [p for p in ("historic", *CDT_PATHWAYS) if p not in samples],
    }


def write_atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
    os.replace(handle.name, path)


def headline(name: str, era5: dict[str, Any], crc_open: dict[str, Any]) -> str:
    if crc_open["available"]:
        first = crc_open["baseline_window"]
        shift = crc_open["baseline_1_in_10_becomes_every_n_years"]
        last = list(shift)[-1]
        return (
            f"In {name}, a 1-in-10-year wettest day brings about "
            f"{crc_open['baseline_1_in_10_mm']:.0f} mm of rain in {first} "
            f"(CRC Open, SSP5-8.5). By {last} the 1-in-10-year "
            f"day brings about {crc_open['late_1_in_10_mm']:.0f} mm, and "
            f"{crc_open['baseline_1_in_10_mm']:.0f} mm falls about every "
            f"{shift[last]:g} years."
        )
    if era5["available"]:
        return (
            f"CRC Open has no curve for {name}. In ERA5 "
            f"({era5['years'][0]}-{era5['years'][1]}), a 1-in-10-year wettest day "
            f"brought about {era5['return_levels_mm'][10]:.0f} mm."
        )
    return f"No heavy-rain data was found for {name}."


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--name", default="Toronto, Canada")
    parser.add_argument("--latitude", type=float, default=43.65)
    parser.add_argument("--longitude", type=float, default=-79.38)
    parser.add_argument(
        "--era5-years",
        type=int,
        nargs=2,
        default=(1995, 2024),
        metavar=("START", "END"),
        help="ERA5 years to fit (about 16 GB of downloads per year)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("pipeline_output/how_hard_rain")
    )
    parser.add_argument(
        "--skip-era5", action="store_true", help="Skip the slow ERA5 baseline"
    )
    parser.add_argument(
        "--skip-cdt", action="store_true", help="Do not call CDT even when a key is set"
    )
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(cache=Cache.reuse(args.output / "cache"))

    era5 = (
        {"available": False, "reason": "skipped"}
        if args.skip_era5
        else era5_answer(
            args.name, args.latitude, args.longitude, tuple(args.era5_years), runtime
        )
    )
    crc_open = crc_open_answer(args.name, args.latitude, args.longitude, runtime)
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(args.latitude, args.longitude)
    )

    answer = headline(args.name, era5, crc_open)
    summary = {
        "question": "How much rain can fall in one day, and is that getting worse?",
        "place": {
            "name": args.name,
            "latitude": args.latitude,
            "longitude": args.longitude,
        },
        "answer": answer,
        "units": "millimetres on the wettest day of the year; return period in years",
        "a_era5": era5,
        "b_crc_open": crc_open,
        "c_cdt": cdt,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_atomic(
        args.output / "summary.json", json.dumps(summary, indent=2, default=str)
    )

    lines = ["source,label,return_period,wettest_day_mm"]
    if era5["available"]:
        label = f"era5 {era5['years'][0]}-{era5['years'][1]}"
        lines += [
            f"era5,{label},{rp},{v}" for rp, v in era5["return_levels_mm"].items()
        ]
    for window, levels in crc_open.get("return_levels_mm", {}).items():
        lines += [f"crc_open,ssp585 {window},{rp},{v}" for rp, v in levels.items()]
    if cdt["available"]:
        for label, levels in cdt["return_levels_mm"].items():
            lines += [f"cdt,{label},{rp},{v}" for rp, v in levels.items()]
    write_atomic(args.output / "return_levels.csv", "\n".join(lines) + "\n")

    print(answer)
    return summary


if __name__ == "__main__":
    main()
