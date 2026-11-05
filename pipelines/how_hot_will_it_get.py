"""How hot will the hottest day get at a place, today and in the future?

Answers one question three ways and writes a small, self-describing result:

A. The nearest NOAA GHCNh weather station: each year's hottest reading and a
   fitted curve (the measured past).
B. CRC Open ``tx_max`` curves for 2025-2100 under SSP5-8.5 (free, ready-made).
C. CDT (Climate Digital Twin) exposure metrics for several pathways, only when
   ``RISKTHINKING_API_KEY`` is set (enterprise; optional).

Run from the repository root:

    uv run python pipelines/how_hot_will_it_get.py
    uv run python pipelines/how_hot_will_it_get.py --name Toronto --latitude 43.68 --longitude -79.63

Outputs land in ``--output`` (default ``pipeline_output/how_hot``):
``summary.json`` (plain-language answer plus provenance) and ``return_levels.csv``.
Temperatures are degrees Celsius. Station values are sampled hourly maxima;
CRC Open and CDT values describe an H3 cell, not a point. See
``notebooks/how_hot_will_it_get.ipynb`` for the explained, illustrated version.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from crc_sdk.workflows import (
    BlockExtremaPolicy,
    HazardDataset,
    curve_parameters_from_row,
)

RETURN_PERIODS = (2, 5, 10, 20, 50, 100)
HORIZONS = (2025, 2050, 2080)
CDT_PATHWAYS = (
    ("historic", 2010),
    ("ssp126", 2050),
    ("ssp245", 2050),
    ("ssp585", 2050),
)
SALES = "mailto:sales@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"
KELVIN = 273.15


def quantiles(
    distribution: Any, return_periods: tuple[int, ...] | list[float]
) -> np.ndarray:
    probabilities = (1 - 1 / np.asarray(return_periods, dtype=float)).tolist()
    return np.asarray(distribution.quantiles(probabilities), dtype=float)


def return_period_of(distribution: Any, value: float) -> float:
    non_exceedance = float(np.asarray(distribution.cdf([value]))[0])
    return float("inf") if non_exceedance >= 1 else 1 / (1 - non_exceedance)


def station_answer(
    latitude: float, longitude: float, years: tuple[int, int], cache: Path
) -> dict[str, Any]:
    """Fit the nearest GHCNh station's annual hottest readings."""
    search = 0.25
    bounds = (
        longitude - search,
        latitude - search,
        longitude + search,
        latitude + search,
    )
    try:
        catalogue = (
            HazardDataset.ghcnh("temperature_max")
            .for_area(bounds)
            .years(*years)
            .cache(cache / "ghcnh", mode="reuse")
            .stations()
            .to_pylist()
        )
    except ValueError:  # no station matches the area and years
        catalogue = []
    if not catalogue:
        return {"available": False, "reason": "no GHCNh station within about 25 km"}
    scale = np.cos(np.radians(latitude))
    for record in catalogue:
        record["distance_km"] = float(
            111
            * np.hypot(
                record["latitude"] - latitude, (record["longitude"] - longitude) * scale
            )
        )
    last_error = "no station could be fitted"
    for station in sorted(catalogue, key=lambda record: record["distance_km"])[:3]:
        plan = (
            HazardDataset.ghcnh("temperature_max")
            .for_stations([station["station"]])
            .years(*years)
            .quality(minimum_hour_fraction=0.75, minimum_day_fraction=0.9)
            .cache(cache / "ghcnh", mode="reuse")
            .canonicalize(policy=BlockExtremaPolicy.curated(minimum_years=15))
        )
        try:
            curve_path = cache / f"station-{station['station']}.parquet"
            plan.materialize(curve_path)
            plan.write_annual_extremes(cache / f"annual-{station['station']}.parquet")
        except (ValueError, LookupError) as error:  # too few complete years
            last_error = str(error)
            continue
        curve_rows = pq.read_table(curve_path).to_pylist()
        if not curve_rows or curve_rows[0]["curve_kind"] == "no_data":
            last_error = f"{station['station']}: too few complete years to fit"
            continue
        annual = pq.read_table(
            cache / f"annual-{station['station']}.parquet"
        ).to_pylist()
        complete = [
            row for row in annual if row["complete"] and row["value"] is not None
        ]
        distribution = curve_parameters_from_row(curve_rows[0]).to_distribution()
        return {
            "available": True,
            "station_id": station["station"],
            "station_name": station["name"],
            "distance_km": round(station["distance_km"], 1),
            "complete_years": len(complete),
            "hottest_reading_c": max(row["value"] for row in complete),
            "return_levels_c": dict(
                zip(
                    RETURN_PERIODS,
                    quantiles(distribution, RETURN_PERIODS).round(2).tolist(),
                )
            ),
            "licence": "CC0-1.0 (NOAA GHCNh)",
        }
    return {"available": False, "reason": last_error}


def crc_open_answer(
    name: str, latitude: float, longitude: float, horizons: tuple[int, ...], cache: Path
) -> dict[str, Any]:
    """Read CRC Open tx_max curves at the place's H3 cell."""
    plan = (
        HazardDataset.crc_open()
        .for_area(
            (longitude - 0.05, latitude - 0.05, longitude + 0.05, latitude + 0.05)
        )
        .hazards(["tx_max"])
        .horizons(list(horizons))
        .cache(cache / "crc-open", mode="reuse")
    )
    place = pa.table(
        {"asset_id": [name], "longitude": [longitude], "latitude": [latitude]}
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            plan.for_assets(place).return_periods([2]).write_parquet(
                cache / "place.parquet"
            )
            plan.materialize(cache / "tx_max.parquet")
    except (ValueError, LookupError) as error:  # e.g. no CRC Open cell here
        return {"available": False, "reason": str(error)}
    cells = pq.read_table(cache / "place.parquet").column("cell_index").to_pylist()
    rows = [
        row
        for row in pq.read_table(cache / "tx_max.parquet").to_pylist()
        if cells and row["cell_index"] == cells[0] and row["curve_kind"] != "no_data"
    ]
    if not rows:
        return {"available": False, "reason": "no CRC Open tx_max curve at this place"}
    cell = cells[0]
    curves = {
        row["horizon"]: curve_parameters_from_row(row).to_distribution() for row in rows
    }
    baseline = min(curves)
    threshold = float(quantiles(curves[baseline], [10])[0])
    metadata = json.loads(
        pq.read_schema(cache / "tx_max.parquet").metadata[b"crc.hazard.metadata"]
    )
    return {
        "available": True,
        "release": plan.resolve().catalog.release,
        "pathway": rows[0]["pathway"],
        "cell_index": str(cell),
        "return_levels_c": {
            horizon: dict(
                zip(
                    RETURN_PERIODS,
                    (quantiles(curve, RETURN_PERIODS) - KELVIN).round(2).tolist(),
                )
            )
            for horizon, curve in sorted(curves.items())
        },
        "baseline_horizon": baseline,
        "baseline_1_in_10_c": round(threshold - KELVIN, 2),
        "baseline_1_in_10_becomes_every_n_years": {
            horizon: round(return_period_of(curve, threshold), 1)
            for horizon, curve in sorted(curves.items())
        },
        "licence": metadata.get("licence") or "CC-BY-NC-4.0",
        "other_pathways": f"Contact sales: {SALES}",
    }


def cdt_answer(latitude: float, longitude: float) -> dict[str, Any]:
    """Query CDT exposure return levels when an API key is configured."""
    if not os.environ.get("RISKTHINKING_API_KEY"):
        return {
            "available": False,
            "reason": "RISKTHINKING_API_KEY not set",
            "trial": TRIAL,
            "sales": SALES,
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


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--name", default="Phoenix, Arizona")
    parser.add_argument("--latitude", type=float, default=33.4278)
    parser.add_argument("--longitude", type=float, default=-112.0037)
    parser.add_argument("--horizons", type=int, nargs="+", default=list(HORIZONS))
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
    cache = args.output / "cache"
    cache.mkdir(exist_ok=True)

    station = station_answer(
        args.latitude, args.longitude, tuple(args.station_years), cache
    )
    crc_open = crc_open_answer(
        args.name, args.latitude, args.longitude, tuple(args.horizons), cache
    )
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(args.latitude, args.longitude)
    )

    if crc_open["available"]:
        shift = crc_open["baseline_1_in_10_becomes_every_n_years"]
        later = {
            horizon: years
            for horizon, years in shift.items()
            if horizon != crc_open["baseline_horizon"]
        }
        answer = (
            f"In {args.name}, a 1-in-10-year hottest day reaches about "
            f"{crc_open['baseline_1_in_10_c']:.1f} °C in {crc_open['baseline_horizon']} "
            f"(CRC Open, {crc_open['pathway'].upper()}). "
            + ". ".join(
                f"By {horizon} that heat returns about every {years:g} years"
                for horizon, years in later.items()
            )
            + "."
        )
    elif station["available"]:
        answer = (
            f"CRC Open has no curve for {args.name}. At {station['station_name']}, "
            f"a 1-in-10-year hottest day measured about "
            f"{station['return_levels_c'][10]:.1f} °C (NOAA GHCNh)."
        )
    else:
        answer = f"No hottest-day data was found for {args.name}."
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
    for horizon, levels in crc_open.get("return_levels_c", {}).items():
        lines += [
            f"crc_open,{crc_open['pathway']} {horizon},{rp},{v}"
            for rp, v in levels.items()
        ]
    if cdt["available"]:
        for label, levels in cdt["return_levels_c"].items():
            lines += [f"cdt,{label},{rp},{v}" for rp, v in levels.items()]
    write_atomic(args.output / "return_levels.csv", "\n".join(lines) + "\n")

    print(answer)
    return summary


if __name__ == "__main__":
    main()
