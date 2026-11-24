"""How hot will the hottest day get at a place, today and in the future?

Answers one question three ways and writes a small, self-describing result:

A. The nearest NOAA GHCNh weather station: each year's hottest day and a
   fitted curve (the measured past).
B. CRC Open ``tx_max`` curves for four-year periods from 2023-2026 onwards
   under SSP5-8.5 (free, ready-made; CRC Open has no historical baseline).
C. CDT (Climate Digital Twin) exposure metrics for several pathways, only when
   ``RISKTHINKING_API_KEY`` is set (enterprise; optional).

Run from the repository root:

    uv run python pipelines/how_hot_will_it_get.py
    uv run python pipelines/how_hot_will_it_get.py --name Toronto --latitude 43.68 --longitude -79.63

Outputs land in ``--output`` (default ``pipeline_output/how_hot``):
``summary.json`` (plain-language answer plus provenance) and ``return_levels.csv``.
Temperatures are degrees Celsius. Station values are annual maxima of complete
days (24 hourly reports); CRC Open and CDT values describe an H3 cell, not a
point. Set ``CRC_OPEN_CATALOG`` to read another CRC Open release index. See
``notebooks/how_hot_will_it_get.ipynb`` for the explained, illustrated version.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from crc_framework import (
    DistributionFamily,
    SampleEstimator,
    SampleFit,
    TemperatureUnit,
)
from crc_sdk import (
    Assets,
    Bounds,
    Cache,
    Coverage,
    CRCOpen,
    GHCNh,
    Period,
    Runtime,
    decode_curves,
)

CRC_OPEN = os.environ.get(
    "CRC_OPEN_CATALOG", "https://data.riskthinking.ai/crc-open/_CURRENT.json"
)
RETURN_PERIODS = (2, 5, 10, 20, 50, 100)
YEARS = (2025, 2050, 2080)
CDT_PATHWAYS = (
    ("historic", 2010),
    ("ssp126", 2050),
    ("ssp245", 2050),
    ("ssp585", 2050),
)
MORE_DATA = "mailto:opensource@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"
KELVIN = 273.15
STATION_SEARCH_DEGREES = 0.25
MINIMUM_YEARS = 15
# Generalized extreme value by L-moments, Gumbel when that fails.
ANNUAL_MAXIMUM_FIT = SampleFit(
    family=DistributionFamily.GENERALIZED_EXTREME_VALUE,
    estimator=SampleEstimator.L_MOMENTS,
    minimum_samples=MINIMUM_YEARS,
    fallbacks=(
        SampleFit(
            family=DistributionFamily.GUMBEL_RIGHT, minimum_samples=MINIMUM_YEARS
        ),
    ),
)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(h))


def non_exceedance(return_periods: Any) -> list[float]:
    return (1 - 1 / np.asarray(return_periods, dtype=float)).tolist()


def return_period_of(curve: Any, value: float) -> float:
    """Return period (years) of ``value`` on an upper-tail annual curve."""
    if hasattr(curve, "cdf"):
        probability = float(curve.cdf(value))
    else:  # a quantile curve: interpolate within its supplied knots
        probability = float(np.interp(value, curve.values, curve.probabilities))
    return math.inf if probability >= 1 else 1 / (1 - probability)


def licence_of(report: Any) -> str | None:
    for source in report.source_identities:
        for resource in source.resources:
            if resource.license:
                return resource.license
    return None


def station_answer(
    latitude: float, longitude: float, years: tuple[int, int], runtime: Runtime
) -> dict[str, Any]:
    """Fit the nearest GHCNh station's annual hottest days."""
    period = Period.window(*years)
    source = GHCNh(
        indicator=GHCNh.Indicator.ANNUAL_MAXIMUM_DAILY_MAXIMUM_TEMPERATURE,
        coverage=Coverage.minimum_fraction(0.9),  # 90% of the year's days
    )
    search = STATION_SEARCH_DEGREES
    area = Bounds(
        west=longitude - search,
        south=latitude - search,
        east=longitude + search,
        north=latitude + search,
    )
    stations = [
        station
        for station in source.select(area=area, time=period)
        .inspect(runtime=runtime)
        .stations
        if station.latitude is not None and station.longitude is not None
    ]
    if not stations:
        return {"available": False, "reason": "no GHCNh station within about 25 km"}
    stations.sort(
        key=lambda s: distance_km(latitude, longitude, s.latitude, s.longitude)
    )
    last_error = "no station could be fitted"
    for station in stations[:3]:
        annual = source.select(stations=station, time=period).read(runtime=runtime)
        rows = [row for row in annual.table.to_pylist() if row["value"] is not None]
        # A station that moved has one support per location; fit the longest.
        by_support: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_support.setdefault(row["support_id"], []).append(row)
        if not by_support:
            last_error = f"{station.id}: no complete years"
            continue
        support, complete = max(by_support.items(), key=lambda item: len(item[1]))
        if len(complete) < MINIMUM_YEARS:
            last_error = (
                f"{station.id}: {len(complete)} complete years, {MINIMUM_YEARS} needed"
            )
            continue
        fitted = annual.fit(ANNUAL_MAXIMUM_FIT).read(runtime=runtime).table
        curve = next(
            curve
            for curve, support_id in zip(
                decode_curves(fitted), fitted["support_id"].to_pylist(), strict=True
            )
            if support_id == support
        )
        hottest = max(complete, key=lambda row: row["value"])
        return {
            "available": True,
            "station_id": station.id,
            "station_name": station.label,
            "distance_km": round(
                distance_km(latitude, longitude, station.latitude, station.longitude),
                1,
            ),
            "years": list(years),
            "complete_years": len(complete),
            "hottest_reading_c": hottest["value"],
            "hottest_year": int(hottest["time"]),
            "fit": "GEV (L-moments), Gumbel fallback",
            "return_levels_c": dict(
                zip(
                    RETURN_PERIODS,
                    np.round(curve.quantile(non_exceedance(RETURN_PERIODS)), 2)
                    .astype(float)
                    .tolist(),
                    strict=True,
                )
            ),
            "missing_years": annual.report.counts.incomplete_years,
            "licence": licence_of(annual.report) or "CC0-1.0",
        }
    return {"available": False, "reason": last_error}


def window_label(period: Period) -> str:
    return f"{period.start}-{period.end}"


def windows_containing(periods: list[Period], years: tuple[int, ...]) -> list[Period]:
    """The release periods containing each year, in time order, without repeats."""
    chosen: dict[str, Period] = {}
    for year in years:
        for period in periods:
            if period.start is not None and period.start <= year <= period.end:
                chosen[period.id] = period
                break
    return sorted(chosen.values(), key=lambda period: period.start)


def crc_open_answer(
    name: str,
    latitude: float,
    longitude: float,
    years: tuple[int, ...],
    runtime: Runtime,
) -> dict[str, Any]:
    """Read CRC Open tx_max curves at the place's H3 cell."""
    variable = CRCOpen.Variable.ANNUAL_MAXIMUM_DAILY_MAXIMUM_TEMPERATURE
    source = CRCOpen(catalog=CRC_OPEN).select(
        variables=variable,
        area=Bounds(
            west=longitude - 0.01,
            south=latitude - 0.01,
            east=longitude + 0.01,
            north=latitude + 0.01,
        ),
    )
    try:
        inventory = source.inspect(runtime=runtime)
        periods = windows_containing(
            [series.period for series in inventory.series], years
        )
        if not periods:
            return {"available": False, "reason": f"no CRC Open period holds {years}"}
        # Read the cell's curves once, in degrees Celsius; evaluate the place on
        # them and keep the curves for the "how often" question.
        curves = (
            source.select(periods=periods)
            .convert_units(variable=variable.value, unit=TemperatureUnit.CELSIUS)
            .read(runtime=runtime)
        )
        place = Assets(
            {"asset_id": [name], "longitude": [longitude], "latitude": [latitude]}
        )
        levels = (
            curves.evaluate(place)
            .return_periods(RETURN_PERIODS)
            .read(runtime=runtime)
            .table.to_pylist()
        )
    except (ValueError, LookupError) as error:  # e.g. no release index or cell here
        return {"available": False, "reason": str(error)}
    labels = {period.id: window_label(period) for period in periods}
    matched = [row for row in levels if row["value"] is not None]
    if not matched:
        failures = {row["failure"]["code"] for row in levels if row["failure"]}
        return {
            "available": False,
            "reason": f"no CRC Open tx_max curve at this place ({sorted(failures)})",
        }
    support = matched[0]["support_id"]
    return_levels: dict[str, dict[int, float]] = {}
    for row in matched:
        return_levels.setdefault(labels[row["period_id"]], {})[
            int(row["query_value"])
        ] = round(row["value"], 2)
    table = curves.table
    by_period = {
        labels[period_id]: curve
        for curve, period_id, support_id in zip(
            decode_curves(table),
            table["period_id"].to_pylist(),
            table["support_id"].to_pylist(),
            strict=True,
        )
        if support_id == support and curve is not None
    }
    baseline = window_label(periods[0])
    threshold = return_levels[baseline][10]
    return {
        "available": True,
        "release": inventory.series[0].release.id,
        "scenario": "ssp585",
        "note": "CRC Open covers SSP5-8.5 only and has no historical baseline.",
        "support_id": support,
        "windows": {window_label(p): [p.start, p.end] for p in periods},
        "return_levels_c": return_levels,
        "baseline_window": baseline,
        "baseline_1_in_10_c": threshold,
        "baseline_1_in_10_becomes_every_n_years": {
            label: round(return_period_of(curve, threshold), 1)
            for label, curve in sorted(by_period.items())
        },
        "licence": licence_of(curves.report) or "CC-BY-NC-4.0",
        "other_pathways": f"Ask the open-source team: {MORE_DATA}",
    }


def cdt_answer(latitude: float, longitude: float) -> dict[str, Any]:
    """Query CDT exposure return levels when an API key is configured."""
    if not os.environ.get("RISKTHINKING_API_KEY"):
        return {
            "available": False,
            "reason": "RISKTHINKING_API_KEY not set",
            "trial": TRIAL,
        }
    from velo_sdk.api import APIClient

    client = APIClient()
    levels: dict[str, dict[int, float]] = {}
    for pathway, horizon in CDT_PATHWAYS:
        response = client.get(
            "/v4/climate/metrics/exposure",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "risk_factor": "tx_max",  # singular; the plural is ignored
                "pathway": pathway,
                "horizon": str(horizon),
                "return_periods": ",".join(map(str, RETURN_PERIODS)),
            },
        )
        for result in response["results"]:
            if result["index_name"] != "tx_max":
                continue
            levels[f"{pathway} {horizon}"] = {
                int(period): round(float(value) - KELVIN, 2)
                for period, value in result["exposure_return_periods"].items()
            }
    if not levels:
        return {"available": False, "reason": "CDT returned no tx_max results here"}
    missing = [
        f"{pathway} {horizon}"
        for pathway, horizon in CDT_PATHWAYS
        if f"{pathway} {horizon}" not in levels
    ]
    return {"available": True, "return_levels_c": levels, "missing": missing}


def write_atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
    os.replace(handle.name, path)


def headline(name: str, station: dict[str, Any], crc_open: dict[str, Any]) -> str:
    if crc_open["available"]:
        baseline = crc_open["baseline_window"]
        later = {
            window: years
            for window, years in crc_open[
                "baseline_1_in_10_becomes_every_n_years"
            ].items()
            if window != baseline
        }
        return (
            f"In {name}, a 1-in-10-year hottest day reaches about "
            f"{crc_open['baseline_1_in_10_c']:.1f} °C in {baseline} "
            f"(CRC Open, SSP5-8.5). "
            + ". ".join(
                f"In {window} that heat returns about every {years:g} years"
                for window, years in later.items()
            )
            + "."
        )
    if station["available"]:
        return (
            f"CRC Open has no curve for {name}. At {station['station_name']}, "
            f"a 1-in-10-year hottest day measured about "
            f"{station['return_levels_c'][10]:.1f} °C (NOAA GHCNh)."
        )
    return f"No hottest-day data was found for {name}."


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--name", default="Phoenix, Arizona")
    parser.add_argument("--latitude", type=float, default=33.4278)
    parser.add_argument("--longitude", type=float, default=-112.0037)
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=list(YEARS),
        help="Years whose CRC Open four-year period to report",
    )
    parser.add_argument(
        "--station-years",
        type=int,
        nargs=2,
        default=(1995, 2024),
        metavar=("START", "END"),
    )
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/how_hot"))
    parser.add_argument(
        "--skip-cdt", action="store_true", help="Do not call CDT even when a key is set"
    )
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(cache=Cache.reuse(args.output / "cache"))

    station = station_answer(
        args.latitude, args.longitude, tuple(args.station_years), runtime
    )
    crc_open = crc_open_answer(
        args.name, args.latitude, args.longitude, tuple(args.horizons), runtime
    )
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(args.latitude, args.longitude)
    )

    answer = headline(args.name, station, crc_open)
    summary = {
        "question": "How hot will the hottest day get?",
        "place": {
            "name": args.name,
            "latitude": args.latitude,
            "longitude": args.longitude,
        },
        "answer": answer,
        "units": "degrees Celsius; return period in years",
        "a_station": station,
        "b_crc_open": crc_open,
        "c_cdt": cdt,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_atomic(
        args.output / "summary.json", json.dumps(summary, indent=2, default=str)
    )

    lines = ["source,label,return_period,hottest_day_c"]
    if station["available"]:
        lines += [
            f"station,{station['station_id']},{rp},{v}"
            for rp, v in station["return_levels_c"].items()
        ]
    for window, levels in crc_open.get("return_levels_c", {}).items():
        lines += [f"crc_open,ssp585 {window},{rp},{v}" for rp, v in levels.items()]
    if cdt["available"]:
        for label, levels in cdt["return_levels_c"].items():
            lines += [f"cdt,{label},{rp},{v}" for rp, v in levels.items()]
    write_atomic(args.output / "return_levels.csv", "\n".join(lines) + "\n")

    print(answer)
    return summary


if __name__ == "__main__":
    main()
