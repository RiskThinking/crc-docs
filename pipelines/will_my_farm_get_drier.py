"""Will a farm get less rain and longer dry spells, and how bad could a dry year get?

Answers one question three ways and writes a small, self-describing result:

A. JRC European Drought Observatory Soil Moisture Index (Europe only): the
   fitted curve of each year's driest soil at the farm's grid cell (the
   measured past).
B. CRC Open annual rain (``prcptot``), dry days and longest dry spell
   (``max_consecutive_dry_days``) for 2023-2036 and 2068-2081 under
   SSP5-8.5, each averaged over three four-year periods (CRC Open has no
   historical baseline).
C. CDT (Climate Digital Twin) annual rain in a typical and a 1-in-10 dry year,
   historical vs 2070-2090 under three pathways, only when
   ``RISKTHINKING_API_KEY`` is set.

Run from the repository root:

    uv run python pipelines/will_my_farm_get_drier.py --skip-edo
    uv run python pipelines/will_my_farm_get_drier.py --name "Kansas wheat" --latitude 38.5 --longitude -98.5 --skip-edo

Outputs land in ``--output`` (default ``pipeline_output/farm``): ``summary.json``
(plain-language answer plus provenance). EDO downloads one file per year (about
a minute each the first time) and needs 20 complete years. Set
``CRC_OPEN_CATALOG`` to read another CRC Open release index. See
``notebooks/will_my_farm_get_drier.ipynb`` for the explained version.
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
from crc_framework import DistributionFamily, SampleFit, Tail
from crc_sdk import (
    EDO,
    Assets,
    Bounds,
    Cache,
    CRCOpen,
    Distance,
    Period,
    Probability,
    ReadResult,
    Runtime,
    Samples,
    SpatialMatch,
    Variable,
)

CRC_OPEN = os.environ.get(
    "CRC_OPEN_CATALOG", "https://data.riskthinking.ai/crc-open/_CURRENT.json"
)
# CRC Open four-year periods containing these years form each window.
EARLY_YEARS, LATE_YEARS = (2025, 2030, 2035), (2070, 2075, 2080)
RAIN = CRCOpen.Variable.ANNUAL_TOTAL_WET_DAY_PRECIPITATION.value
DRY_DAYS = "crc:dry_days"
DRY_SPELL = CRCOpen.Variable.ANNUAL_MAXIMUM_CONSECUTIVE_DRY_DAYS.value
CDT_REQUESTS = [("historic", 2010)] + [
    (pathway, horizon)
    for pathway in ("ssp126", "ssp245", "ssp585")
    for horizon in (2070, 2080, 2090)
]
MORE_DATA = "mailto:opensource@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"
RP_GRID = np.geomspace(1.2, 100, 200)
# Non-exceedance probabilities: typical (0.5) and 1-in-10 dry (0.1) years,
# the 1-in-10 high value (0.9), and the return-period grid for the dry spell.
PROBABILITIES = sorted({0.1, 0.5, 0.9, *(1 - 1 / RP_GRID).tolist()})
DEKADS_PER_YEAR = 36
EDO_MINIMUM_YEARS = 20
EDO_RETURN_PERIODS = (2, 5, 10, 20)


def licence_of(report: Any) -> str | None:
    for source in report.source_identities:
        for resource in source.resources:
            if resource.license:
                return resource.license
    return None


def edo_annual_minima(
    observations: ReadResult, latitude: float, longitude: float
) -> Samples | None:
    """Annual minimum of complete years at the EDO grid cell holding the farm."""
    rows = [row for row in observations.table.to_pylist() if row["value"] is not None]
    if not rows:
        return None
    farm = shapely.Point(longitude, latitude)
    shapes = {row["support_id"]: shapely.from_wkb(row["geometry"]) for row in rows}
    support = min(
        shapes,
        key=lambda s: (not shapes[s].covers(farm), shapes[s].distance(farm)),
    )
    years: dict[int, list[float]] = {}
    for row in rows:
        if row["support_id"] == support:
            years.setdefault(int(row["time"][:4]), []).append(row["value"])
    complete = {
        year: min(values)
        for year, values in sorted(years.items())
        if len(values) == DEKADS_PER_YEAR
    }
    if not complete:
        return None
    centre = shapes[support].centroid
    measurement = observations.metadata.spec.variables[0].measurement
    return Samples.from_table(
        {
            "support_id": [support] * len(complete),
            "longitude": [centre.x] * len(complete),
            "latitude": [centre.y] * len(complete),
            "time": list(complete),
            "value": list(complete.values()),
        },
        variable=Variable(
            "edo:soil_moisture_index_annual_minimum",
            measurement=measurement,
            label="Annual minimum of the dekadal Soil Moisture Index",
        ),
        probability=Probability.annual(tail=Tail.LOWER),
    )


def edo_summary(
    observations: ReadResult, latitude: float, longitude: float, runtime: Runtime
) -> dict[str, Any]:
    annual = edo_annual_minima(observations, latitude, longitude)
    if annual is None:
        return {"available": False, "reason": "no complete soil-moisture years here"}
    minima = annual.read(runtime=runtime)
    years = minima.table.num_rows
    if years < EDO_MINIMUM_YEARS:
        return {
            "available": False,
            "reason": f"{years} complete years, {EDO_MINIMUM_YEARS} needed",
        }
    farm = Assets(
        {"asset_id": ["farm"], "longitude": [longitude], "latitude": [latitude]}
    )
    levels = (
        minima.fit(
            SampleFit(
                family=DistributionFamily.GUMBEL_RIGHT,
                minimum_samples=EDO_MINIMUM_YEARS,
            )
        )
        .evaluate(
            farm, spatial=SpatialMatch.nearest(max_distance=Distance.kilometres(10))
        )
        .return_periods(EDO_RETURN_PERIODS)  # lower tail: q = 1 / T
        .read(runtime=runtime)
        .table.to_pylist()
    )
    return {
        "available": True,
        "grid_cell": minima.table["support_id"][0].as_py(),
        "complete_years": years,
        "years": [
            minima.table["time"][0].as_py(),
            minima.table["time"][years - 1].as_py(),
        ],
        "driest_soil_index": {
            int(row["query_value"]): round(row["value"], 2)
            for row in levels
            if row["value"] is not None
        },
        "meaning": (
            "Soil Moisture Index annual minimum; 1 is field capacity (wet), "
            "0 is the wilting point"
        ),
        "fit": "Gumbel on annual minima, lower tail",
        "licence": licence_of(observations.report) or "CC-BY-4.0",
    }


def edo_answer(
    latitude: float, longitude: float, years: tuple[int, int] | None, runtime: Runtime
) -> dict[str, Any]:
    """Fit the EDO Soil Moisture Index annual minima at the farm's grid cell."""
    source = EDO(product=EDO.Product.SOIL_MOISTURE_INDEX).select(
        area=Bounds(
            west=longitude - 0.03,
            south=latitude - 0.03,
            east=longitude + 0.03,
            north=latitude + 0.03,
        )
    )
    try:
        if years is None:  # every published year; incomplete ones are dropped
            period = source.inspect(runtime=runtime).series[0].period
            years = (period.start, period.end)
        observations = source.select(time=Period.window(*years)).read(runtime=runtime)
    except (ValueError, LookupError) as error:  # e.g. outside Europe
        return {"available": False, "reason": str(error)}
    return edo_summary(observations, latitude, longitude, runtime)


def windows(periods: list[Period]) -> dict[str, list[Period]]:
    """The early and late groups of CRC Open periods, labelled by their span."""
    groups = {}
    for years in (EARLY_YEARS, LATE_YEARS):
        chosen = sorted(
            {
                period.id: period
                for period in periods
                if period.start is not None
                and any(period.start <= year <= period.end for year in years)
            }.values(),
            key=lambda period: period.start,
        )
        if chosen:
            groups[f"{chosen[0].start}-{chosen[-1].end}"] = chosen
    return groups


def crc_open_answer(
    name: str, latitude: float, longitude: float, runtime: Runtime
) -> dict[str, Any]:
    """CRC Open dry-weather measures, early vs late window."""
    source = CRCOpen(catalog=CRC_OPEN).select(
        variables=[RAIN, DRY_DAYS, DRY_SPELL],
        area=Bounds(
            west=longitude - 0.01,
            south=latitude - 0.01,
            east=longitude + 0.01,
            north=latitude + 0.01,
        ),
    )
    farm = Assets(
        {"asset_id": [name], "longitude": [longitude], "latitude": [latitude]}
    )
    try:
        inventory = source.inspect(runtime=runtime)
        groups = windows(
            list({s.period.id: s.period for s in inventory.series}.values())
        )
        if len(groups) != 2:
            return {
                "available": False,
                "reason": "CRC Open lacks the early or late periods",
            }
        selected = [period for group in groups.values() for period in group]
        evaluation = (
            source.select(periods=selected)
            .evaluate(farm)
            .probabilities(PROBABILITIES)
            .read(runtime=runtime)
        )
    except (ValueError, LookupError) as error:  # e.g. no release index or cell here
        return {"available": False, "reason": str(error)}
    values: dict[tuple[str, str], dict[float, float]] = {}
    for row in evaluation.table.to_pylist():
        if row["value"] is not None:
            values.setdefault((row["variable_id"], row["period_id"]), {})[
                row["query_value"]
            ] = row["value"]

    def window(variable: str, label: str, probabilities: list[float]) -> np.ndarray:
        curves = [
            [values[(variable, period.id)][p] for p in probabilities]
            for period in groups[label]
            if (variable, period.id) in values
        ]
        if not curves:
            raise LookupError(f"no CRC Open {variable} curve at this farm")
        return np.mean(curves, axis=0)

    early, late = groups
    measures_spec = {
        "annual_rain_typical_mm": (RAIN, 0.5),
        "annual_rain_1_in_10_dry_mm": (RAIN, 0.1),
        "dry_days_1_in_10": (DRY_DAYS, 0.9),
        "longest_dry_spell_1_in_10_days": (DRY_SPELL, 0.9),
    }
    try:
        measures = {}
        for key, (variable, probability) in measures_spec.items():
            first = float(window(variable, early, [probability])[0])
            second = float(window(variable, late, [probability])[0])
            measures[key] = {
                early: round(first, 1),
                late: round(second, 1),
                "change_percent": round(100 * (second / first - 1), 1),
            }
        grid = (1 - 1 / RP_GRID).tolist()
        late_spell = window(DRY_SPELL, late, grid)
    except LookupError as error:
        return {"available": False, "reason": str(error)}
    threshold = measures["longest_dry_spell_1_in_10_days"][early]
    late_rp = float(np.exp(np.interp(threshold, late_spell, np.log(RP_GRID))))
    return {
        "available": True,
        "release": inventory.series[0].release.id,
        "scenario": "ssp585",
        "note": "CRC Open covers SSP5-8.5 only and has no historical baseline.",
        "windows": {
            label: [f"{p.start}-{p.end}" for p in group]
            for label, group in groups.items()
        },
        "measures": measures,
        "early_1_in_10_dry_spell_returns_every_n_years_late": round(late_rp, 1),
        "licence": licence_of(evaluation.report) or "CC-BY-NC-4.0",
        "other_pathways": f"Ask the open-source team: {MORE_DATA}",
    }


def cdt_answer(latitude: float, longitude: float) -> dict[str, Any]:
    """CDT annual rain, typical and 1-in-10 dry year, historical vs late century."""
    if not os.environ.get("RISKTHINKING_API_KEY"):
        return {
            "available": False,
            "reason": "RISKTHINKING_API_KEY not set",
            "trial": TRIAL,
        }
    from velo_sdk.api import APIClient

    client = APIClient()
    samples: dict[str, list[list[float]]] = {}
    for pathway, horizon in CDT_REQUESTS:
        response = client.get(
            "/v4/climate/metrics/exposure",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "risk_factor": "prcptot",  # singular; the plural is ignored
                "pathway": pathway,
                "horizon": str(horizon),
                "percentiles": "10,50",
            },
        )
        for result in response["results"]:
            if result["index_name"] == "prcptot":
                percentiles = result["exposure_percentiles"]
                samples.setdefault(pathway, []).append(
                    [float(percentiles["50"]), float(percentiles["10"])]
                )
    if not samples:
        return {"available": False, "reason": "CDT returned no prcptot results here"}
    table = {}
    for pathway, values in samples.items():
        typical, dry = np.mean(values, axis=0)
        label = "historic 2010" if pathway == "historic" else f"{pathway} 2070-2090"
        table[label] = {
            "annual_rain_typical_mm": round(float(typical), 1),
            "annual_rain_1_in_10_dry_mm": round(float(dry), 1),
        }
    return {"available": True, "annual_rain": table}


def write_atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
    os.replace(handle.name, path)


def headline(name: str, crc_open: dict[str, Any]) -> str:
    if not crc_open["available"]:
        return f"No CRC Open dry-weather data was found for {name}."
    early, late = crc_open["windows"]
    m = crc_open["measures"]
    rain = m["annual_rain_1_in_10_dry_mm"]
    spell = m["longest_dry_spell_1_in_10_days"]
    trend = (
        "grows"
        if spell[late] > spell[early]
        else "shrinks"
        if spell[late] < spell[early]
        else "stays"
    )
    return (
        f"At {name}, a 1-in-10 dry year brings about {rain[early]:.0f} mm of rain "
        f"in {early} and about {rain[late]:.0f} mm in {late} (CRC Open, SSP5-8.5). "
        f"The 1-in-10-year longest dry spell {trend} from {spell[early]:.0f} to "
        f"{spell[late]:.0f} days."
    )


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--name", default="Valladolid wheat farm, Spain")
    parser.add_argument("--latitude", type=float, default=41.65)
    parser.add_argument("--longitude", type=float, default=-4.72)
    parser.add_argument(
        "--edo-years",
        type=int,
        nargs=2,
        metavar=("START", "END"),
        help="EDO years (default: all complete years; at least 20 are needed)",
    )
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/farm"))
    parser.add_argument(
        "--skip-edo", action="store_true", help="Skip the slower EDO baseline"
    )
    parser.add_argument(
        "--skip-cdt", action="store_true", help="Do not call CDT even when a key is set"
    )
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(cache=Cache.reuse(args.output / "cache"))

    edo = (
        {"available": False, "reason": "skipped"}
        if args.skip_edo
        else edo_answer(
            args.latitude,
            args.longitude,
            tuple(args.edo_years) if args.edo_years else None,
            runtime,
        )
    )
    crc_open = crc_open_answer(args.name, args.latitude, args.longitude, runtime)
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(args.latitude, args.longitude)
    )

    answer = headline(args.name, crc_open)
    summary = {
        "question": "Will the farm get drier?",
        "place": {
            "name": args.name,
            "latitude": args.latitude,
            "longitude": args.longitude,
        },
        "answer": answer,
        "a_edo": edo,
        "b_crc_open": crc_open,
        "c_cdt": cdt,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_atomic(
        args.output / "summary.json", json.dumps(summary, indent=2, default=str)
    )
    print(answer)
    return summary


if __name__ == "__main__":
    main()
