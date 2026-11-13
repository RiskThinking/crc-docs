"""How exposed is a company to climate change?

Looks at one company three ways and writes a small, self-describing result:

A. Free public data: the company's locations in an area from Overture Maps
   Places (matched by brand), and how many hurricanes passed within 50 km of
   each one since 1990 (NOAA IBTrACS, North Atlantic).
B. CRC Open: expected yearly damage at each location from hurricane wind,
   heavy rain and hot days, as a share of building value, in 2025-2035 and
   2070-2080 under SSP5-8.5, using crc-framework's open damage functions.
C. CDT (Climate Digital Twin): the company's scores across all of its assets
   for two pathways and three horizons, and its rank within a market index,
   only when ``RISKTHINKING_API_KEY`` is set.

Run from the repository root:

    uv run python pipelines/how_exposed_is_this_company.py --skip-cdt
    uv run python pipelines/how_exposed_is_this_company.py \\
        --brand "Home Depot" --bounds -98 29 -94 33 --region TX

``--bounds`` is ``min_lon min_lat max_lon max_lat`` (default: Florida).
Outputs land in ``--output`` (default ``pipeline_output/company``):
``summary.json``, ``locations.csv`` and ``locations.geojson`` (one point per
location, for the crc-viz hazard map). Overture places show where a brand
operates; they are not evidence of ownership, value or insurance. See
``notebooks/how_exposed_is_this_company.ipynb`` for the explained version.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import urllib.request
import warnings
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from crc_sdk.connectors.duckdb import DuckDBConnection, sql_quote
from crc_sdk.impacts import impacts
from crc_sdk.workflows import HazardDataset, IBTrACSPlan, ImpactContextColumns

FLORIDA = (-87.7, 24.4, -79.9, 31.1)
OVERTURE_CATALOG = "https://stac.overturemaps.org/catalog.json"
HAZARDS = {
    "cyclone": "hurricane wind",
    "rx1day": "heavy rain",
    "hot_days": "hot days",
}
EARLY, LATE = (2025, 2030, 2035), (2070, 2075, 2080)
# Midpoints of 200 equal probability slices; the mean over them is the
# expected (average-year) damage. Values beyond 1-in-400 are left out.
PROBABILITIES = (np.arange(200) + 0.5) / 200
RETURN_PERIODS = [float(1 / (1 - p)) for p in PROBABILITIES]
HURRICANE_KT = 64
RADIUS_KM = 50
CDT_PATHWAYS = ("ssp245", "ssp585")
CDT_HORIZONS = ("2030", "2050", "2090")
CDT_METRICS = "expected_impact,cvar_95,dcr_score"
MORE_DATA = "mailto:opensource@riskthinking.ai"
TRIAL = "https://velo.riskthinking.ai/cdt-express"


def read_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def overture_files(bounds: tuple[float, float, float, float]) -> tuple[str, list[str]]:
    """Return the latest Overture release and the Places files covering bounds."""
    release = str(read_json(OVERTURE_CATALOG)["latest"])
    collection = read_json(
        f"https://stac.overturemaps.org/{release}/places/place/collection.json"
    )
    files = []
    for link in collection["links"]:
        if link.get("rel") != "item":
            continue
        item = read_json(link["href"])
        west, south, east, north = item["bbox"]
        if not (
            east < bounds[0]
            or west > bounds[2]
            or north < bounds[1]
            or south > bounds[3]
        ):
            files.append(item["assets"]["aws"]["href"])
    return release, files


def find_locations(
    brand: str,
    bounds: tuple[float, float, float, float],
    region: str | None,
    categories: list[str] | None,
    cache: Path,
) -> dict[str, Any]:
    """Places whose Overture brand name matches ``brand`` inside ``bounds``."""
    release, files = overture_files(bounds)
    if not files:
        return {"available": False, "reason": "no Overture Places files cover the area"}
    conditions = [
        f"bbox.xmin BETWEEN {bounds[0]} AND {bounds[2]}",
        f"bbox.ymin BETWEEN {bounds[1]} AND {bounds[3]}",
        f"lower(brand.names.primary) = lower({sql_quote(brand)})",
    ]
    if region:
        conditions.append(f"addresses[1].region = {sql_quote(region)}")
    if categories:
        conditions.append(
            "basic_category IN (" + ", ".join(sql_quote(c) for c in categories) + ")"
        )
    connection = DuckDBConnection.for_analytics(cache).connect()
    table = connection.execute(
        f"""
        SELECT id AS asset_id, names.primary AS name, basic_category AS category,
               addresses[1].locality AS city, bbox.xmin AS longitude,
               bbox.ymin AS latitude
        FROM read_parquet([{", ".join(sql_quote(f) for f in files)}])
        WHERE {" AND ".join(conditions)}
        ORDER BY id
        """
    ).to_arrow_table()
    if table.num_rows == 0:
        return {"available": False, "reason": f"no Overture places for brand {brand!r}"}
    return {
        "available": True,
        "release": release,
        "count": table.num_rows,
        "table": table,
        "attribution": "Overture Maps Foundation, https://docs.overturemaps.org/attribution/",
    }


def distance_km(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    h = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371 * np.arcsin(np.sqrt(h))


def hurricane_tracks(
    bounds: tuple[float, float, float, float], since: int, cache: Path
) -> dict[str, Any]:
    """North Atlantic hurricane-strength track points, densified to ~10 km."""
    plan = IBTrACSPlan("NA", cache / "ibtracs").years(since, datetime.now(UTC).year)
    provenance = plan.prefetch()
    columns = ["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "USA_WIND"]
    table = pa.Table.from_batches(list(plan.batches())).select(columns)
    storms: dict[str, list[tuple[str, float, float, float]]] = {}
    names: dict[str, str] = {}
    pad = 1.0
    for row in table.to_pylist():
        try:
            lat, lon = float(row["LAT"]), float(row["LON"])
            wind = float(row["USA_WIND"])
        except (TypeError, ValueError):
            continue
        if not (
            bounds[0] - pad <= lon <= bounds[2] + pad
            and bounds[1] - pad <= lat <= bounds[3] + pad
        ):
            continue
        storms.setdefault(row["SID"], []).append((row["ISO_TIME"], lat, lon, wind))
        names[row["SID"]] = f"{row['NAME'].strip().title()} {row['SEASON']}"
    steps = np.linspace(0, 1, 8, endpoint=False)
    ids, lats, lons = [], [], []
    for sid, points in storms.items():
        points.sort()
        for (_, la0, lo0, w0), (_, la1, lo1, w1) in pairwise(points):
            if min(w0, w1) < HURRICANE_KT:
                continue
            lats += list(la0 + (la1 - la0) * steps)
            lons += list(lo0 + (lo1 - lo0) * steps)
            ids += [sid] * len(steps)
    return {
        "ids": np.array(ids),
        "lat": np.array(lats),
        "lon": np.array(lons),
        "names": names,
        "provenance": {k: provenance.get(k) for k in ("url", "sha256", "retrieved_at")},
    }


def hurricane_answer(
    locations: pa.Table,
    bounds: tuple[float, float, float, float],
    since: int,
    cache: Path,
) -> dict[str, Any]:
    """Count hurricanes (>= 64 kt) passing within 50 km of each location."""
    tracks = hurricane_tracks(bounds, since, cache)
    lat = np.array(locations.column("latitude").to_pylist())
    lon = np.array(locations.column("longitude").to_pylist())
    counts = []
    storms_near: dict[str, int] = {}
    for start in range(0, len(lat), 100):
        near = (
            distance_km(
                lat[start : start + 100, None],
                lon[start : start + 100, None],
                tracks["lat"][None, :],
                tracks["lon"][None, :],
            )
            <= RADIUS_KM
        )
        for row in near:
            hit = set(tracks["ids"][row].tolist())
            counts.append(len(hit))
            for sid in hit:
                storms_near[sid] = storms_near.get(sid, 0) + 1
    counts_array = np.array(counts)
    years = datetime.now(UTC).year - since
    median = float(np.median(counts_array))
    top = sorted(storms_near.items(), key=lambda item: -item[1])[:5]
    return {
        "available": True,
        "since": since,
        "radius_km": RADIUS_KM,
        "min_wind_kt": HURRICANE_KT,
        "share_with_any": round(float(np.mean(counts_array > 0)), 3),
        "median_count": median,
        "median_every_n_years": round(years / median) if median else None,
        "storms_reaching_most_locations": [
            {"storm": tracks["names"][sid], "locations": n} for sid, n in top
        ],
        "counts": counts,
        "source": tracks["provenance"],
    }


def expected_damage(
    hazard: str,
    locations: pa.Table,
    bounds: tuple[float, float, float, float],
    cache: Path,
) -> dict[tuple[str, int], float]:
    """Expected yearly damage ratio per (asset_id, horizon) for one hazard."""
    plan = (
        HazardDataset.crc_open()
        .for_area(bounds)
        .hazards([hazard])
        .horizons([*EARLY, *LATE])
        .cache(cache / "crc-open", mode="reuse")
    )
    output = cache / f"{hazard}_damage.parquet"
    output.unlink(missing_ok=True)
    request = plan.for_assets(locations).return_periods(RETURN_PERIODS)
    result = request.impact(
        impacts.for_factor(hazard),
        context=ImpactContextColumns(
            country="country", continent="continent", building_type="building_type"
        ),
        name=f"{hazard}_damage_ratio",
        value_unit="fraction",
        value_semantics="damage ratio of building value",
    ).write_parquet(output)
    columns = list(result.value_columns)
    table = pq.read_table(output, columns=["asset_id", "horizon", *columns])
    values = np.column_stack([table.column(c).to_numpy() for c in columns])
    return {
        (asset, int(horizon)): float(mean)
        for asset, horizon, mean in zip(
            table.column("asset_id").to_pylist(),
            table.column("horizon").to_pylist(),
            np.nanmean(values, axis=1),
        )
    }


def crc_open_answer(
    locations: pa.Table,
    bounds: tuple[float, float, float, float],
    cache: Path,
    country: str = "USA",
    continent: str = "North America",
) -> dict[str, Any]:
    """Average expected yearly damage per location over early and late windows."""
    assets = locations.select(["asset_id", "longitude", "latitude"])
    n = assets.num_rows
    assets = assets.append_column("country", pa.array([country] * n))
    assets = assets.append_column("continent", pa.array([continent] * n))
    assets = assets.append_column("building_type", pa.array(["commercial"] * n))
    ids = assets.column("asset_id").to_pylist()
    per_hazard: dict[str, dict[str, list[float]]] = {}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for hazard in HAZARDS:
                damage = expected_damage(hazard, assets, bounds, cache)
                per_hazard[hazard] = {
                    window: [
                        float(
                            np.mean([damage[(a, h)] for h in years if (a, h) in damage])
                        )
                        for a in ids
                    ]
                    for window, years in (("early", EARLY), ("late", LATE))
                }
    except (ValueError, LookupError) as error:  # e.g. no CRC Open cell here
        return {"available": False, "reason": str(error)}

    def pct(values: list[float]) -> float:
        return round(100 * float(np.mean(values)), 2)

    total = {
        window: list(np.sum([per_hazard[h][window] for h in HAZARDS], axis=0))
        for window in ("early", "late")
    }
    return {
        "available": True,
        "pathway": "ssp585",
        "windows": {"early": list(EARLY), "late": list(LATE)},
        "assumptions": f"commercial building in {country}; equal value per location",
        "average_expected_damage_pct": {
            "total": {w: pct(total[w]) for w in total},
            **{h: {w: pct(per_hazard[h][w]) for w in total} for h in HAZARDS},
        },
        "per_location_pct": {
            a: {
                **{
                    f"{h}_{w}": round(100 * per_hazard[h][w][i], 3)
                    for h in HAZARDS
                    for w in total
                },
                **{f"total_{w}": round(100 * total[w][i], 3) for w in total},
            }
            for i, a in enumerate(ids)
        },
        "licence": "CC-BY-NC-4.0",
        "other_pathways": f"Ask the open-source team: {MORE_DATA}",
    }


def cdt_answer(company: str, index: str) -> dict[str, Any]:
    """CDT company scores and its rank in a market index (needs an API key)."""
    if not os.environ.get("RISKTHINKING_API_KEY"):
        return {
            "available": False,
            "reason": "RISKTHINKING_API_KEY not set",
            "trial": TRIAL,
        }
    from velo_sdk.api import APIClient

    client = APIClient()
    found = client.get("/companies/search", params={"name": company})["results"]
    if not found:
        return {"available": False, "reason": f"CDT has no company named {company!r}"}
    match = next(
        (c for c in found if c["name"].lower().startswith(company.lower())), found[0]
    )
    scores = {}
    for pathway in CDT_PATHWAYS:
        for horizon in CDT_HORIZONS:
            try:
                response = client.get(
                    f"/companies/{match['id']}/climate/scores",
                    params={
                        "pathway": pathway,
                        "horizon": horizon,
                        "metric": CDT_METRICS,
                    },
                )
            except Exception as error:  # noqa: BLE001 - report, keep going
                scores[f"{pathway} {horizon}"] = {"error": str(error)[:120]}
                continue
            scores[f"{pathway} {horizon}"] = {
                key: round(float(response[key]), 4)
                for key in CDT_METRICS.split(",")
                if response.get(key) is not None
            }
    ranking: list[dict[str, Any]] = []
    indexes = client.get("/markets/indexes/search", params={"name": index})["results"]
    chosen = next((i for i in indexes if i["name"].lower() == index.lower()), None)
    if chosen:
        response = client.get(
            f"/markets/indexes/{chosen['id']}/companies/climate/scores",
            params={
                "pathway": "ssp585",
                "horizon": "2050",
                "metric": CDT_METRICS,
                "sort_by": "expected_impact",
                "sort_direction": "descending",
                "limit": 100,
            },
        )
        ranking = [
            {
                "company": row["company_name"],
                "expected_impact": round(float(row["expected_impact"]), 4),
            }
            for row in response["results"]
            if row.get("expected_impact") is not None
        ]
    rank = next(
        (i + 1 for i, row in enumerate(ranking) if row["company"] == match["name"]),
        None,
    )
    return {
        "available": True,
        "company": match["name"],
        "scores": scores,
        "metrics": {
            "expected_impact": "average damage, share of tangible asset value",
            "cvar_95": "average damage in the worst 5% of outcomes",
            "dcr_score": "chance of more damage than in the 2010 baseline",
        },
        "index": chosen["name"] if chosen else None,
        "index_ranking_ssp585_2050": ranking,
        "rank": rank,
    }


def write_atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
    os.replace(handle.name, path)


def locations_geojson(
    rows: list[dict[str, Any]],
    counts: list[int] | None,
    per_location: dict[str, dict[str, float]],
    since: int,
) -> dict[str, Any]:
    """One Point per location, ready for the crc-viz hazard map.

    Colour the map by ``hurricanes_within_50km_since_<year>`` (when hurricanes
    were not skipped) or by any of the expected-damage fields (% of value).
    """
    count_key = f"hurricanes_within_{RADIUS_KM}km_since_{since}"
    features = []
    for i, row in enumerate(rows):
        properties = {
            k: v for k, v in row.items() if k not in ("longitude", "latitude")
        }
        if counts:
            properties[count_key] = counts[i]
        properties.update(per_location.get(row["asset_id"], {}))
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["longitude"], row["latitude"]],
                },
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_map(output: Path) -> Path | None:
    """Build the crc-viz hazard map page when the bundle is available locally.

    Needs the repository's ``tools/build_map_page.py``; a downloaded copy of this
    script alone skips the map (the skill then runs that tool itself).
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
    return build(
        output / "locations.geojson", viz, output / "map", "Locations on the CRC map"
    )


def headline(brand: str, places: dict, storms: dict, crc: dict, cdt: dict) -> str:
    parts = []
    if places["available"] and storms.get("available"):
        parts.append(
            f"Since {storms['since']}, a hurricane passed within {RADIUS_KM} km of "
            f"{storms['share_with_any']:.0%} of the {places['count']} {brand} "
            f"locations found in the area."
        )
    if crc.get("available"):
        total = crc["average_expected_damage_pct"]["total"]
        parts.append(
            f"With CRC Open (SSP5-8.5), the average location's expected yearly damage "
            f"from hurricane wind, heavy rain and hot days is {total['early']}% of "
            f"building value in 2025-2035 and {total['late']}% in 2070-2080."
        )
    if cdt.get("available") and cdt.get("rank"):
        parts.append(
            f"CDT ranks {cdt['company']} {cdt['rank']} of "
            f"{len(cdt['index_ranking_ssp585_2050'])} in the {cdt['index']} by "
            f"expected impact (SSP5-8.5, 2050)."
        )
    return " ".join(parts) or f"No data was found for {brand} in this area."


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--brand", default="Walmart", help="Brand name on Overture")
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=FLORIDA,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    parser.add_argument("--region", help="Keep places in this region code, e.g. FL")
    parser.add_argument(
        "--category",
        action="append",
        help="Keep this Overture basic_category (repeatable), e.g. superstore",
    )
    parser.add_argument(
        "--country",
        default="USA",
        help="ISO 3166-1 alpha-3 country of the area, for damage functions",
    )
    parser.add_argument(
        "--continent", default="North America", help="Continent of the area"
    )
    parser.add_argument("--company", help="Company name in CDT (default: --brand)")
    parser.add_argument("--index", default="Dow Jones Industrial Average")
    parser.add_argument("--since", type=int, default=1990)
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/company"))
    parser.add_argument(
        "--skip-hurricanes", action="store_true", help="Skip the IBTrACS history"
    )
    parser.add_argument(
        "--skip-cdt", action="store_true", help="Do not call CDT even when a key is set"
    )
    args = parser.parse_args(argv)
    bounds = tuple(args.bounds)
    if not (
        -180 <= bounds[0] < bounds[2] <= 180 and -90 <= bounds[1] < bounds[3] <= 90
    ):
        parser.error("bounds must be min_lon min_lat max_lon max_lat")

    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "cache"
    cache.mkdir(exist_ok=True)

    places = find_locations(args.brand, bounds, args.region, args.category, cache)
    storms: dict[str, Any] = {"available": False, "reason": "skipped"}
    crc: dict[str, Any] = {"available": False, "reason": "no locations"}
    if places["available"]:
        if not args.skip_hurricanes:
            storms = hurricane_answer(places["table"], bounds, args.since, cache)
        crc = crc_open_answer(
            places["table"], bounds, cache, args.country, args.continent
        )
    cdt = (
        {"available": False, "reason": "skipped"}
        if args.skip_cdt
        else cdt_answer(args.company or args.brand, args.index)
    )

    answer = headline(args.brand, places, storms, crc, cdt)
    summary = {
        "question": "How exposed is a company to climate change?",
        "brand": args.brand,
        "bounds": list(bounds),
        "answer": answer,
        "a_public": {
            "locations": {k: v for k, v in places.items() if k != "table"},
            "hurricanes": {k: v for k, v in storms.items() if k != "counts"},
        },
        "b_crc_open": {k: v for k, v in crc.items() if k != "per_location_pct"},
        "c_cdt": cdt,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_atomic(
        args.output / "summary.json", json.dumps(summary, indent=2, default=str)
    )
    if places["available"]:
        rows = places["table"].to_pylist()
        per_location = crc.get("per_location_pct", {})
        extra = sorted({key for v in per_location.values() for key in v})
        with tempfile.NamedTemporaryFile(
            "w", dir=args.output, delete=False, suffix=".tmp", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow([*rows[0], "hurricanes_since", *extra])
            for i, row in enumerate(rows):
                counts = storms.get("counts")
                writer.writerow(
                    [
                        *row.values(),
                        counts[i] if counts else "",
                        *[
                            per_location.get(row["asset_id"], {}).get(k, "")
                            for k in extra
                        ],
                    ]
                )
        os.replace(handle.name, args.output / "locations.csv")
        write_atomic(
            args.output / "locations.geojson",
            json.dumps(
                locations_geojson(rows, storms.get("counts"), per_location, args.since)
            ),
        )
    print(answer)
    if places["available"]:
        page = build_map(args.output)
        if page:
            print(
                f"Map: {page.resolve()} (one self-contained file; open it in a browser)"
            )
        else:
            print(
                f"No map built (crc-viz bundle not found); open {args.output}/"
                "locations.geojson in QGIS or geojson.io."
            )
    return summary


if __name__ == "__main__":
    main()
