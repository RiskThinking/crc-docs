"""Will a farm get less rain and longer dry spells, and how bad could a dry year get?

Answers one question three ways and writes a small, self-describing result:

A. JRC European Drought Observatory Soil Moisture Index (Europe only): the
   fitted curve of each year's driest soil (the measured past).
B. CRC Open annual rain (``prcptot``), dry days and longest dry spell
   (``max_consecutive_dry_days``) for 2025-2035 and 2070-2080 under SSP5-8.5,
   each window averaged over three horizons.
C. CDT (Climate Digital Twin) annual rain in a typical and a 1-in-10 dry year,
   historical vs 2070-2090 under three pathways, only when
   ``RISKTHINKING_API_KEY`` is set.

Run from the repository root:

    uv run python pipelines/will_my_farm_get_drier.py --skip-edo
    uv run python pipelines/will_my_farm_get_drier.py --name "Kansas wheat" --latitude 38.5 --longitude -98.5 --skip-edo

Outputs land in ``--output`` (default ``pipeline_output/farm``): ``summary.json``
(plain-language answer plus provenance). EDO takes about 30 seconds per year
and needs 20 complete years. See ``notebooks/will_my_farm_get_drier.ipynb``
for the explained version.
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
    EDODroughtPolicy,
    HazardDataset,
    curve_parameters_from_row,
)
from shapely import wkb
from shapely.geometry import Point

EARLY, LATE = (2025, 2030, 2035), (2070, 2075, 2080)
CDT_REQUESTS = [("historic", 2010)] + [
    (pathway, horizon)
    for pathway in ("ssp126", "ssp245", "ssp585")
    for horizon in (2070, 2080, 2090)
]
SALES = "mailto:sales@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"
RP_GRID = np.geomspace(1.2, 100, 200)


def upper(distribution: Any, rp: Any) -> np.ndarray:
    """Value reached or exceeded once every ``rp`` years."""
    probabilities = (1 - 1 / np.asarray(rp, dtype=float)).tolist()
    return np.asarray(distribution.quantiles(probabilities), dtype=float)


def lower(distribution: Any, rp: Any) -> np.ndarray:
    """Value at or below which a year falls once every ``rp`` years."""
    probabilities = (1 / np.asarray(rp, dtype=float)).tolist()
    return np.asarray(distribution.quantiles(probabilities), dtype=float)


def edo_answer(
    latitude: float, longitude: float, years: tuple[Any, ...], cache: Path
) -> dict[str, Any]:
    """Fit the EDO Soil Moisture Index annual minima near the farm."""
    plan = (
        HazardDataset.smi(version="latest")
        .for_area((longitude - 0.1, latitude - 0.1, longitude + 0.1, latitude + 0.1))
        .years(*years)
        .cache(cache / "edo", mode="reuse")
        .canonicalize(policy=EDODroughtPolicy.curated(h3_resolution=6))
    )
    (cache / "smi.parquet").unlink(missing_ok=True)  # EDO plans don't overwrite
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            plan.materialize(cache / "smi.parquet")
    except (ValueError, LookupError) as error:  # e.g. outside Europe
        return {"available": False, "reason": str(error)}
    rows = [
        row
        for row in pq.read_table(cache / "smi.parquet").to_pylist()
        if row["curve_kind"] != "no_data"
    ]
    if not rows:
        return {"available": False, "reason": "no soil-moisture curve near the farm"}
    farm = Point(longitude, latitude)
    row = min(
        rows,
        key=lambda row: (
            wkb.loads(row["source_geometry"]).distance(farm)
            if row["source_geometry"]
            else 0
        ),
    )
    soil = curve_parameters_from_row(row).to_distribution()
    return {
        "available": True,
        "driest_soil_index": {
            rp: round(float(lower(soil, [rp])[0]), 2) for rp in (2, 5, 10, 20)
        },
        "meaning": "Soil Moisture Index annual minimum; 0 is normal, below 0 is drier",
        "licence": "CC-BY-4.0 (JRC EDO)",
    }


def crc_open_curves(
    name: str, latitude: float, longitude: float, hazard: str, cache: Path
) -> dict[int, Any]:
    plan = (
        HazardDataset.crc_open()
        .for_area(
            (longitude - 0.05, latitude - 0.05, longitude + 0.05, latitude + 0.05)
        )
        .hazards([hazard])
        .horizons(list(EARLY + LATE))
        .cache(cache / "crc-open", mode="reuse")
    )
    farm = pa.table(
        {"asset_id": [name], "longitude": [longitude], "latitude": [latitude]}
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        plan.for_assets(farm).return_periods([2]).write_parquet(
            cache / f"farm_{hazard}.parquet"
        )
        plan.materialize(cache / f"{hazard}.parquet")
    cells = (
        pq.read_table(cache / f"farm_{hazard}.parquet").column("cell_index").to_pylist()
    )
    return {
        row["horizon"]: curve_parameters_from_row(row).to_distribution()
        for row in pq.read_table(cache / f"{hazard}.parquet").to_pylist()
        if cells and row["cell_index"] == cells[0] and row["curve_kind"] != "no_data"
    }


def window(curves: dict[int, Any], horizons: tuple[int, ...], side: Any, rp: Any):
    return np.mean([side(curves[h], rp) for h in horizons if h in curves], axis=0)


def crc_open_answer(
    name: str, latitude: float, longitude: float, cache: Path
) -> dict[str, Any]:
    """CRC Open dry-weather measures, early vs late window."""
    try:
        rain = crc_open_curves(name, latitude, longitude, "prcptot", cache)
        dry = crc_open_curves(name, latitude, longitude, "dry_days", cache)
        spell = crc_open_curves(
            name, latitude, longitude, "max_consecutive_dry_days", cache
        )
    except (ValueError, LookupError) as error:
        return {"available": False, "reason": str(error)}
    if not (rain and dry and spell):
        return {"available": False, "reason": "missing CRC Open curves at this farm"}
    measures = {
        "annual_rain_typical_mm": (rain, lower, 2),
        "annual_rain_1_in_10_dry_mm": (rain, lower, 10),
        "dry_days_1_in_10": (dry, upper, 10),
        "longest_dry_spell_1_in_10_days": (spell, upper, 10),
    }
    values = {}
    for key, (curves, side, rp) in measures.items():
        early = float(window(curves, EARLY, side, [rp])[0])
        late = float(window(curves, LATE, side, [rp])[0])
        values[key] = {
            "2025-2035": round(early, 1),
            "2070-2080": round(late, 1),
            "change_percent": round(100 * (late / early - 1), 1),
        }
    threshold = values["longest_dry_spell_1_in_10_days"]["2025-2035"]
    late_levels = window(spell, LATE, upper, RP_GRID)
    late_rp = float(np.exp(np.interp(threshold, late_levels, np.log(RP_GRID))))
    return {
        "available": True,
        "pathway": "ssp585",
        "windows": {"2025-2035": list(EARLY), "2070-2080": list(LATE)},
        "measures": values,
        "early_1_in_10_dry_spell_returns_every_n_years_late": round(late_rp, 1),
        "licence": "CC-BY-NC-4.0",
        "other_pathways": f"Contact sales: {SALES}",
    }


def cdt_answer(latitude: float, longitude: float) -> dict[str, Any]:
    """CDT annual rain, typical and 1-in-10 dry year, historical vs late century."""
    if not os.environ.get("RISKTHINKING_API_KEY"):
        return {
            "available": False,
            "reason": "RISKTHINKING_API_KEY not set",
            "trial": TRIAL,
            "sales": SALES,
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
    cache = args.output / "cache"
    cache.mkdir(exist_ok=True)

    edo_years = tuple(args.edo_years) if args.edo_years else ("all_complete",)
    edo = (
        {"available": False, "reason": "skipped"}
        if args.skip_edo
        else edo_answer(args.latitude, args.longitude, edo_years, cache)
    )
    crc_open = crc_open_answer(args.name, args.latitude, args.longitude, cache)
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(args.latitude, args.longitude)
    )

    if crc_open["available"]:
        m = crc_open["measures"]
        spell = m["longest_dry_spell_1_in_10_days"]
        trend = (
            "grows"
            if spell["2070-2080"] > spell["2025-2035"]
            else "shrinks"
            if spell["2070-2080"] < spell["2025-2035"]
            else "changes"
        )
        answer = (
            f"At {args.name}, a 1-in-10 dry year brings about "
            f"{m['annual_rain_1_in_10_dry_mm']['2025-2035']:.0f} mm of rain in "
            f"2025-2035 and about {m['annual_rain_1_in_10_dry_mm']['2070-2080']:.0f} mm "
            f"in 2070-2080 (CRC Open, SSP585). The 1-in-10-year longest dry spell {trend} "
            f"from {m['longest_dry_spell_1_in_10_days']['2025-2035']:.0f} to "
            f"{m['longest_dry_spell_1_in_10_days']['2070-2080']:.0f} days."
        )
    else:
        answer = f"No CRC Open dry-weather data was found for {args.name}."
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
