"""How much rain can fall in one day at a place, and is that getting worse?

Answers one question three ways and writes a small, self-describing result:

A. ERA5 (free global reanalysis, 1.5 degree WeatherBench 2 copy): each year's
   wettest day and a fitted curve (the recorded past, on a coarse grid).
B. CRC Open ``rx1day`` curves for 2025-2090 under SSP5-8.5, averaged over
   windows of horizons because single horizons are noisy (free, ready-made).
C. CDT (Climate Digital Twin) return levels for a historical baseline and
   three pathways in 2070-2090, only when ``RISKTHINKING_API_KEY`` is set.

Run from the repository root:

    uv run python pipelines/how_hard_will_it_rain.py
    uv run python pipelines/how_hard_will_it_rain.py --name Chicago --latitude 41.88 --longitude -87.63 --skip-era5

Outputs land in ``--output`` (default ``pipeline_output/how_hard_rain``):
``summary.json`` (plain-language answer plus provenance) and ``return_levels.csv``.
Rain is millimetres on the wettest day of the year. ERA5 takes about 15 seconds
per year; ``--skip-era5`` gives a quick answer from CRC Open (and CDT) alone.
See ``notebooks/how_hard_will_it_rain.ipynb`` for the explained version.
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
from shapely import wkb
from shapely.geometry import Point

RETURN_PERIODS = (2, 5, 10, 25)
WINDOWS = {
    "2025-2045": (2025, 2030, 2035, 2040, 2045),
    "2050-2065": (2050, 2055, 2060, 2065),
    "2070-2090": (2070, 2075, 2080, 2085, 2090),
}
CDT_PATHWAYS = ("ssp126", "ssp245", "ssp585")
CDT_LATE_HORIZONS = (2070, 2080, 2090)
MORE_DATA = "mailto:opensource@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"
RP_GRID = np.geomspace(1.2, 100, 200)


def quantiles(distribution: Any, return_periods: Any) -> np.ndarray:
    probabilities = (1 - 1 / np.asarray(return_periods, dtype=float)).tolist()
    return np.asarray(distribution.quantiles(probabilities), dtype=float)


def levels_dict(levels: Any) -> dict[int, float]:
    return dict(zip(RETURN_PERIODS, np.round(levels, 1).tolist()))


def era5_answer(
    latitude: float, longitude: float, years: tuple[int, int], cache: Path
) -> dict[str, Any]:
    """Fit ERA5 annual wettest days at the grid point nearest the place."""
    plan = (
        HazardDataset.era5("rx1day", store="wb2-1p5")
        .for_area((longitude - 0.1, latitude - 0.1, longitude + 0.1, latitude + 0.1))
        .years(*years)
        .cache(cache / "era5", mode="reuse")
        .canonicalize(
            policy=BlockExtremaPolicy.curated(
                h3_resolution=5, minimum_years=min(20, years[1] - years[0] + 1)
            )
        )
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            annual = plan.annual_extremes().to_pylist()
            plan.materialize(cache / "era5_rx1day.parquet")
    except (ValueError, LookupError) as error:
        return {"available": False, "reason": str(error)}
    rows = [
        row
        for row in pq.read_table(cache / "era5_rx1day.parquet").to_pylist()
        if row["curve_kind"] != "no_data"
    ]
    annual = [row for row in annual if row["value"] is not None]
    if not rows or not annual:
        return {"available": False, "reason": "no ERA5 curve could be fitted here"}
    # The search box can touch two grid cells: use the one containing (or nearest
    # to) the place for both the curve and the yearly values.
    place = Point(longitude, latitude)
    row = min(rows, key=lambda row: wkb.loads(row["source_geometry"]).distance(place))
    cell = wkb.loads(row["source_geometry"])
    point = [
        sample
        for sample in annual
        if cell.covers(Point(sample["longitude"], sample["latitude"]))
    ]
    if not point:
        return {"available": False, "reason": "no ERA5 yearly values in the grid cell"}
    wettest = max(point, key=lambda sample: sample["value"])
    curve = curve_parameters_from_row(row).to_distribution()
    return {
        "available": True,
        "grid_point": [point[0]["latitude"], point[0]["longitude"]],
        "grid_spacing_degrees": 1.5,
        "years": list(years),
        "wettest_day_mm": round(float(wettest["value"]), 1),
        "wettest_year": int(wettest["year"]),
        "return_levels_mm": levels_dict(quantiles(curve, RETURN_PERIODS)),
        "licence": "CC-BY-4.0 (Copernicus ERA5)",
    }


def crc_open_answer(
    name: str, latitude: float, longitude: float, cache: Path
) -> dict[str, Any]:
    """Average CRC Open rx1day curves over windows of horizons at the place's cell."""
    horizons = [horizon for window in WINDOWS.values() for horizon in window]
    plan = (
        HazardDataset.crc_open()
        .for_area(
            (longitude - 0.05, latitude - 0.05, longitude + 0.05, latitude + 0.05)
        )
        .hazards(["rx1day"])
        .horizons(horizons)
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
            plan.materialize(cache / "rx1day.parquet")
    except (ValueError, LookupError) as error:  # e.g. no CRC Open cell here
        return {"available": False, "reason": str(error)}
    cells = pq.read_table(cache / "place.parquet").column("cell_index").to_pylist()
    rows = [
        row
        for row in pq.read_table(cache / "rx1day.parquet").to_pylist()
        if cells and row["cell_index"] == cells[0] and row["curve_kind"] != "no_data"
    ]
    if not rows:
        return {"available": False, "reason": "no CRC Open rx1day curve at this place"}
    curves = {
        row["horizon"]: curve_parameters_from_row(row).to_distribution() for row in rows
    }
    windows = {
        name: np.mean(
            [quantiles(curves[h], RP_GRID) for h in years if h in curves], axis=0
        )
        for name, years in WINDOWS.items()
        if any(h in curves for h in years)
    }
    first, last = next(iter(windows)), list(windows)[-1]
    threshold = float(np.interp(10, RP_GRID, windows[first]))
    metadata = json.loads(
        pq.read_schema(cache / "rx1day.parquet").metadata[b"crc.hazard.metadata"]
    )
    return {
        "available": True,
        "release": plan.resolve().catalog.release,
        "pathway": rows[0]["pathway"],
        "cell_index": str(cells[0]),
        "windows": {name: list(WINDOWS[name]) for name in windows},
        "return_levels_mm": {
            name: levels_dict(np.interp(RETURN_PERIODS, RP_GRID, levels))
            for name, levels in windows.items()
        },
        "baseline_window": first,
        "baseline_1_in_10_mm": round(threshold, 1),
        "late_1_in_10_mm": round(float(np.interp(10, RP_GRID, windows[last])), 1),
        "baseline_1_in_10_becomes_every_n_years": {
            name: round(float(np.exp(np.interp(threshold, levels, np.log(RP_GRID)))), 1)
            for name, levels in windows.items()
        },
        "licence": metadata.get("licence") or "CC-BY-NC-4.0",
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
        default=(1992, 2021),
        metavar=("START", "END"),
        help="ERA5 years (the free 1.5 degree copy ends in 2021)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("pipeline_output/how_hard_rain")
    )
    parser.add_argument(
        "--skip-era5", action="store_true", help="Skip the slower ERA5 baseline"
    )
    parser.add_argument(
        "--skip-cdt", action="store_true", help="Do not call CDT even when a key is set"
    )
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "cache"
    cache.mkdir(exist_ok=True)

    era5 = (
        {"available": False, "reason": "skipped"}
        if args.skip_era5
        else era5_answer(args.latitude, args.longitude, tuple(args.era5_years), cache)
    )
    crc_open = crc_open_answer(args.name, args.latitude, args.longitude, cache)
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(args.latitude, args.longitude)
    )

    if crc_open["available"]:
        first = crc_open["baseline_window"]
        shift = crc_open["baseline_1_in_10_becomes_every_n_years"]
        last = list(shift)[-1]
        answer = (
            f"In {args.name}, a 1-in-10-year wettest day brings about "
            f"{crc_open['baseline_1_in_10_mm']:.0f} mm of rain in {first} "
            f"(CRC Open, {crc_open['pathway'].upper()}). By {last} the 1-in-10-year "
            f"day brings about {crc_open['late_1_in_10_mm']:.0f} mm, and "
            f"{crc_open['baseline_1_in_10_mm']:.0f} mm falls about every "
            f"{shift[last]:g} years."
        )
    elif era5["available"]:
        answer = (
            f"CRC Open has no curve for {args.name}. In ERA5 "
            f"({era5['years'][0]}-{era5['years'][1]}), a 1-in-10-year wettest day "
            f"brought about {era5['return_levels_mm'][10]:.0f} mm."
        )
    else:
        answer = f"No heavy-rain data was found for {args.name}."
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
        lines += [
            f"crc_open,{crc_open['pathway']} {window},{rp},{v}"
            for rp, v in levels.items()
        ]
    if cdt["available"]:
        for label, levels in cdt["return_levels_mm"].items():
            lines += [f"cdt,{label},{rp},{v}" for rp, v in levels.items()]
    write_atomic(args.output / "return_levels.csv", "\n".join(lines) + "\n")

    print(answer)
    return summary


if __name__ == "__main__":
    main()
