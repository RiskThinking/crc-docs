"""Which sites in a portfolio face the biggest climate change, and from what?

Screens a list of sites three ways and writes a small, self-describing result:

A. ERA5 (free global reanalysis, 1.5 degree WeatherBench 2 copy): each site's
   1-in-10-year hottest and wettest day in the recent past.
B. CRC Open: 1-in-10-year values for four hazards in 2025-2035 and 2070-2080
   under SSP5-8.5 (each window averaged over three horizons), and their change.
C. CDT (Climate Digital Twin): 1-in-10-year hottest day and hot days for a
   historical baseline and three pathways in 2070-2090, only when
   ``RISKTHINKING_API_KEY`` is set.

Run from the repository root:

    uv run python pipelines/which_sites_are_most_at_risk.py --skip-era5
    uv run python pipelines/which_sites_are_most_at_risk.py --sites my_sites.csv

``--sites`` is a CSV with ``site,latitude,longitude`` columns and an optional
``city`` (default: ten
example warehouses in North America). Outputs land in ``--output`` (default
``pipeline_output/sites``): ``summary.json``, ``site_hazards.csv`` and
``sites.geojson`` (one point per site with its CRC Open values, for the crc-viz
hazard map; inside the repository the map page is written to ``map/``). ERA5
takes about 15 seconds per year per hazard; ``--skip-era5`` skips it. See
``notebooks/which_sites_are_most_at_risk.ipynb`` for the explained version.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from crc_sdk.fitting import fit_distribution
from crc_sdk.workflows import BlockExtremaPolicy, HazardDataset

EXAMPLE_SITES = [
    ("Phoenix", 33.45, -112.07),
    ("Los Angeles", 34.05, -118.24),
    ("Seattle", 47.61, -122.33),
    ("Denver", 39.74, -104.99),
    ("Houston", 29.76, -95.37),
    ("Chicago", 41.88, -87.63),
    ("Atlanta", 33.75, -84.39),
    ("Miami", 25.77, -80.19),
    ("Toronto", 43.65, -79.38),
    ("New York", 40.71, -74.00),
]
HAZARDS = {
    "tx_max": ("hottest day", "degC"),
    "rx1day": ("wettest day", "mm"),
    "hot_days": ("hot days", "days"),
    "fwi": ("wildfire weather (Fire Weather Index)", "index"),
}
EARLY, LATE = (2025, 2030, 2035), (2070, 2075, 2080)
CDT_REQUESTS = [("historic", 2010)] + [
    (pathway, horizon)
    for pathway in ("ssp126", "ssp245", "ssp585")
    for horizon in (2070, 2080, 2090)
]
MORE_DATA = "mailto:opensource@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"
KELVIN = 273.15


def read_sites(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        rows = EXAMPLE_SITES
    else:
        with path.open(newline="") as handle:
            rows = [
                (
                    row["site"],
                    float(row["latitude"]),
                    float(row["longitude"]),
                    (row.get("city") or "").strip(),
                )
                for row in csv.DictReader(handle)
            ]
    names = [row[0] for row in rows]
    if len(set(names)) != len(names):
        raise ValueError("site names must be unique")
    sites = []
    for name, lat, lon, *city in rows:
        site = {"site": name, "latitude": lat, "longitude": lon}
        if city and city[0]:  # optional ``city`` column, shown beside the name
            site["city"] = city[0]
        sites.append(site)
    return sites


def era5_answer(
    sites: list[dict[str, Any]], years: tuple[int, int], cache: Path
) -> dict[str, Any]:
    """1-in-10-year ERA5 hottest and wettest day at each site's nearest grid point."""
    lats = [site["latitude"] for site in sites]
    lons = [site["longitude"] for site in sites]
    bounds = (min(lons) - 2, min(lats) - 2, max(lons) + 2, max(lats) + 2)
    values: dict[str, dict[str, float]] = {site["site"]: {} for site in sites}
    for recipe, label in (("txx", "hottest_day_c"), ("rx1day", "wettest_day_mm")):
        plan = (
            HazardDataset.era5(recipe, store="wb2-1p5")
            .for_area(bounds)
            .years(*years)
            .cache(cache / "era5", mode="reuse")
            .canonicalize(
                policy=BlockExtremaPolicy.curated(h3_resolution=3, minimum_years=4)
            )
        )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                annual = plan.annual_extremes().to_pylist()
        except (ValueError, LookupError) as error:
            return {"available": False, "reason": str(error)}
        records: dict[tuple[float, float], list[float]] = {}
        for row in annual:
            if row["value"] is not None:
                records.setdefault((row["latitude"], row["longitude"]), []).append(
                    row["value"]
                )
        if not records:
            return {"available": False, "reason": "no ERA5 values for these sites"}
        grid = np.array(list(records))
        for site in sites:
            index = np.argmin(
                np.hypot(grid[:, 0] - site["latitude"], grid[:, 1] - site["longitude"])
            )
            sample = records[tuple(grid[index])]
            if len(sample) < 4:
                continue
            fitted = fit_distribution(sample, "genextreme", method="lmoments")
            level = float(np.asarray(fitted.distribution.quantiles([0.9]))[0])
            values[site["site"]][label] = round(level, 1)
    return {
        "available": True,
        "years": list(years),
        "grid_spacing_degrees": 1.5,
        "one_in_10": values,
        "licence": "CC-BY-4.0 (Copernicus ERA5)",
    }


def crc_open_answer(sites: list[dict[str, Any]], cache: Path) -> dict[str, Any]:
    """CRC Open 1-in-10-year values per site and hazard, early vs late window."""
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    release = None
    for site in sites:
        lat, lon = site["latitude"], site["longitude"]
        asset = pa.table(
            {"asset_id": [site["site"]], "longitude": [lon], "latitude": [lat]}
        )
        for hazard in HAZARDS:  # asset evaluation takes one hazard at a time
            plan = (
                HazardDataset.crc_open()
                .for_area((lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05))
                .hazards([hazard])
                .horizons(list(EARLY + LATE))
                .cache(cache / "crc-open", mode="reuse")
            )
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    plan.for_assets(asset).return_periods([10]).write_parquet(
                        cache / "site.parquet"
                    )
            except (ValueError, LookupError):  # e.g. outside CRC Open coverage
                missing.append(f"{site['site']}/{hazard}")
                continue
            release = release or plan.resolve().catalog.release
            rows += pq.read_table(cache / "site.parquet").to_pylist()
    if not rows:
        return {"available": False, "reason": "no CRC Open curves for these sites"}
    sums: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        if row["value_rp10"] is None:
            continue
        window = "early" if row["horizon"] in EARLY else "late"
        value = row["value_rp10"] - (KELVIN if row["hazard_name"] == "tx_max" else 0)
        sums.setdefault((row["asset_id"], row["hazard_name"], window), []).append(value)
    table: dict[str, dict[str, dict[str, float]]] = {}
    for (site, hazard, window), values in sums.items():
        table.setdefault(site, {}).setdefault(hazard, {})[window] = float(
            np.mean(values)
        )
    for hazards in table.values():
        for entry in hazards.values():
            if "early" in entry and "late" in entry:
                entry["change"] = entry["late"] - entry["early"]
            for key in entry:
                entry[key] = round(entry[key], 1)
    largest = {}
    for hazard in HAZARDS:
        changes = {
            site: hazards[hazard]["change"]
            for site, hazards in table.items()
            if "change" in hazards.get(hazard, {})
        }
        if changes:
            top = max(changes, key=changes.get)
            largest[hazard] = {"site": top, "change": changes[top]}
    return {
        "available": True,
        "release": release,
        "pathway": "ssp585",
        "windows": {"early": list(EARLY), "late": list(LATE)},
        "one_in_10": table,
        "largest_change": largest,
        "missing": missing,
        "licence": "CC-BY-NC-4.0",
        "other_pathways": f"Ask the open-source team: {MORE_DATA}",
    }


def cdt_answer(sites: list[dict[str, Any]]) -> dict[str, Any]:
    """CDT 1-in-10-year hottest day and hot days, historical vs late century."""
    if not os.environ.get("RISKTHINKING_API_KEY"):
        return {
            "available": False,
            "reason": "RISKTHINKING_API_KEY not set",
            "trial": TRIAL,
        }
    from velo_sdk.api import APIClient

    client = APIClient()
    samples: dict[tuple[str, str, str], list[float]] = {}
    for site in sites:
        for pathway, horizon in CDT_REQUESTS:
            response = client.get(
                "/v4/climate/metrics/exposure",
                params={
                    "latitude": site["latitude"],
                    "longitude": site["longitude"],
                    "risk_factor": "tx_max,hot_days",  # singular; plural is ignored
                    "pathway": pathway,
                    "horizon": str(horizon),
                    "return_periods": "10",
                },
            )
            for result in response["results"]:
                hazard = result["index_name"]
                if hazard not in ("tx_max", "hot_days"):
                    continue
                value = float(result["exposure_return_periods"]["10"])
                value -= KELVIN if hazard == "tx_max" else 0
                samples.setdefault((site["site"], hazard, pathway), []).append(value)
    if not samples:
        return {"available": False, "reason": "CDT returned no results here"}
    table: dict[str, dict[str, dict[str, float]]] = {}
    for (site, hazard, pathway), values in samples.items():
        label = "historic 2010" if pathway == "historic" else f"{pathway} 2070-2090"
        table.setdefault(site, {}).setdefault(hazard, {})[label] = round(
            float(np.mean(values)), 1
        )
    return {"available": True, "one_in_10": table}


def sites_geojson(
    sites: list[dict[str, Any]], table: dict[str, dict[str, dict[str, float]]]
) -> dict[str, Any]:
    """One Point per site: ``<hazard>_2025_2035``, ``<hazard>_2070_2080`` and ``<hazard>_change``.

    The names match ``tools/build_map_page.py``, which declares each field's unit.
    """
    names = {"early": "2025_2035", "late": "2070_2080", "change": "change"}
    features = []
    for site in sites:
        city = site.get("city", "")
        title = (
            f"{site['site']} ({city})"
            if city and city.lower() not in site["site"].lower()
            else site["site"]
        )
        properties: dict[str, Any] = {"title": title, "site": site["site"]}
        if city:
            properties["city"] = city
        for hazard in HAZARDS:
            for key, value in table.get(site["site"], {}).get(hazard, {}).items():
                properties[f"{hazard}_{names[key]}"] = value
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [site["longitude"], site["latitude"]],
                },
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def live_map_link(geojson: Path) -> str | None:
    """Link to the hosted map viewer with every site packed into the #fragment.

    Needs no bundle, only the repository's ``tools/build_map_page.py``.
    """
    root = Path(__file__).resolve().parents[1]
    if not (root / "tools" / "build_map_page.py").is_file():
        return None
    sys.path.insert(0, str(root))
    try:
        from tools.build_map_page import encode_link
    except ImportError:
        return None
    return encode_link(json.loads(geojson.read_text()))


def build_map(output: Path) -> Path | None:
    """Build the crc-viz map page when the repository's map tool and bundle are here.

    A downloaded copy of this script alone skips it (the skill then runs
    ``build_map_page.py`` itself).
    """
    root = Path(__file__).resolve().parents[1]
    if not (root / "tools" / "build_map_page.py").is_file():
        return None
    sys.path.insert(0, str(root))
    try:
        from tools.build_map_page import build, find_bundle
    except ImportError:
        return None
    viz = find_bundle(download=False)
    if viz is None:
        return None
    return build(output / "sites.geojson", viz, output / "map", "Sites on the CRC map")


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
    parser.add_argument("--sites", type=Path, help="CSV with site,latitude,longitude")
    parser.add_argument(
        "--era5-years",
        type=int,
        nargs=2,
        default=(2002, 2021),
        metavar=("START", "END"),
        help="ERA5 years (the free 1.5 degree copy ends in 2021)",
    )
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/sites"))
    parser.add_argument(
        "--skip-era5", action="store_true", help="Skip the slower ERA5 baseline"
    )
    parser.add_argument(
        "--skip-cdt", action="store_true", help="Do not call CDT even when a key is set"
    )
    args = parser.parse_args(argv)

    sites = read_sites(args.sites)
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "cache"
    cache.mkdir(exist_ok=True)

    era5 = (
        {"available": False, "reason": "skipped"}
        if args.skip_era5
        else era5_answer(sites, tuple(args.era5_years), cache)
    )
    crc_open = crc_open_answer(sites, cache)
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(sites)
    )

    if crc_open["available"]:
        parts = [
            f"{HAZARDS[hazard][0]}: {top['site']} ({top['change']:+g} {HAZARDS[hazard][1]})"
            for hazard, top in crc_open["largest_change"].items()
        ]
        answer = (
            f"Largest change in 1-in-10-year values from 2025-2035 to 2070-2080 "
            f"(CRC Open, SSP585) across {len(sites)} sites. " + "; ".join(parts) + "."
        )
    else:
        answer = "No CRC Open data was found for these sites."
    summary = {
        "question": "Which sites face the biggest climate change, and from what?",
        "sites": sites,
        "answer": answer,
        "units": {hazard: unit for hazard, (_, unit) in HAZARDS.items()},
        "a_era5": era5,
        "b_crc_open": crc_open,
        "c_cdt": cdt,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_atomic(
        args.output / "summary.json", json.dumps(summary, indent=2, default=str)
    )

    lines = ["source,site,hazard,label,value"]
    if era5["available"]:
        for site, values in era5["one_in_10"].items():
            lines += [f"era5,{site},{key},past,{v}" for key, v in values.items()]
    for site, hazards in crc_open.get("one_in_10", {}).items():
        for hazard, entry in hazards.items():
            lines += [f"crc_open,{site},{hazard},{k},{v}" for k, v in entry.items()]
    if cdt["available"]:
        for site, hazards in cdt["one_in_10"].items():
            for hazard, entry in hazards.items():
                lines += [f"cdt,{site},{hazard},{k},{v}" for k, v in entry.items()]
    write_atomic(args.output / "site_hazards.csv", "\n".join(lines) + "\n")

    if crc_open["available"]:
        write_atomic(
            args.output / "sites.geojson",
            json.dumps(sites_geojson(sites, crc_open["one_in_10"])),
        )
        page = build_map(args.output)
        link = live_map_link(args.output / "sites.geojson")
        if link:
            print(f"Live map: {link}")
        if page:
            print(
                f"Map: {page.resolve()} (one self-contained file; open it in a browser)"
            )
        else:
            print(
                f"No map built (crc-viz bundle not found); open {args.output}/"
                "sites.geojson in QGIS or geojson.io."
            )

    print(answer)
    return summary


if __name__ == "__main__":
    main()
