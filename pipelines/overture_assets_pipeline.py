"""Source open candidate asset locations from the latest Overture Places release.

Run with:

    uv run python pipelines/overture_assets_pipeline.py \
        --bounds 6.95 50.93 6.97 50.95 \
        --output pipeline_output/ai-playbooks/overture-assets.csv

The output is suitable for open climate-risk demonstrations. Overture places are
not evidence of ownership, collateral status, occupancy, replacement value, or
insurance exposure.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

import pyarrow.csv as pacsv

from crc_sdk.connectors.duckdb import DuckDBConnection, sql_quote

OVERTURE_CATALOG_URL = "https://stac.overturemaps.org/catalog.json"


def read_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(  # noqa: S310 - fixed HTTPS STAC host
        url, timeout=30
    ) as response:
        return json.load(response)


def intersects(left: tuple[float, float, float, float], right: list[float]) -> bool:
    return not (
        right[2] < left[0]
        or right[0] > left[2]
        or right[3] < left[1]
        or right[1] > left[3]
    )


def place_assets(bounds: tuple[float, float, float, float]) -> tuple[str, list[str]]:
    catalog = read_json(OVERTURE_CATALOG_URL)
    release = str(catalog["latest"])
    collection_url = (
        f"https://stac.overturemaps.org/{release}/places/place/collection.json"
    )
    collection = read_json(collection_url)
    assets = []
    for link in collection["links"]:
        if link.get("rel") != "item":
            continue
        item = read_json(link["href"])
        if intersects(bounds, item["bbox"]):
            assets.append(item["assets"]["aws"]["href"])
    if not assets:
        raise SystemExit(f"no Overture Places partitions intersect bounds {bounds}")
    return release, assets


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--bounds",
        nargs=4,
        required=True,
        type=float,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--coverage-hazard",
        type=Path,
        help="Optional canonical hazard Parquet; retain only places inside a source geometry",
    )
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--min-confidence", type=float, default=0.8)
    p.add_argument(
        "--category",
        action="append",
        help="Optional exact Overture primary category; repeatable",
    )
    p.add_argument(
        "--allow-unnamed",
        action="store_true",
        help="Include place records without a primary name",
    )
    return p


def main() -> int:
    args = parser().parse_args()
    bounds = tuple(args.bounds)
    if not (
        -180 <= bounds[0] < bounds[2] <= 180
        and -90 <= bounds[1] < bounds[3] <= 90
    ):
        raise SystemExit("bounds must be ordered WGS84 min_lon min_lat max_lon max_lat")
    if args.limit < 1:
        raise SystemExit("limit must be positive")
    if not 0 <= args.min_confidence <= 1:
        raise SystemExit("min-confidence must be within [0, 1]")
    if args.coverage_hazard and not args.coverage_hazard.is_file():
        raise SystemExit(f"coverage hazard not found: {args.coverage_hazard}")

    release, urls = place_assets(bounds)
    quoted_urls = ", ".join(sql_quote(url) for url in urls)
    conditions = [
        f"bbox.xmin BETWEEN {bounds[0]} AND {bounds[2]}",
        f"bbox.ymin BETWEEN {bounds[1]} AND {bounds[3]}",
        f"confidence >= {args.min_confidence}",
    ]
    if not args.allow_unnamed:
        conditions.append("names.primary IS NOT NULL")
    if args.category:
        categories = ", ".join(sql_quote(value) for value in args.category)
        conditions.append(f"categories.primary IN ({categories})")
    if args.coverage_hazard:
        coverage_path = sql_quote(str(args.coverage_hazard.resolve()))
        conditions.append(
            "EXISTS (SELECT 1 FROM read_parquet("
            f"{coverage_path}) AS h WHERE "
            "ST_Intersects(ST_GeomFromWKB(h.source_geometry), p.geometry))"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    con = DuckDBConnection.for_analytics(args.output.parent).connect()
    query = f"""
        SELECT
            'overture-place:' || id AS asset_id,
            bbox.xmin AS longitude,
            bbox.ymin AS latitude,
            names.primary AS asset_name,
            categories.primary AS overture_category,
            confidence AS overture_confidence,
            operating_status,
            id AS overture_record_id,
            '{release}' AS overture_release,
            'Overture Maps Foundation' AS overture_source,
            'https://docs.overturemaps.org/attribution/' AS overture_attribution
        FROM read_parquet([{quoted_urls}]) AS p
        WHERE {' AND '.join(conditions)}
        ORDER BY confidence DESC, id
        LIMIT {args.limit}
    """
    table = con.execute(query).to_arrow_table()
    if table.num_rows == 0:
        raise SystemExit(
            "no Overture places matched; widen bounds, lower min-confidence, "
            "or remove category filters"
        )
    pacsv.write_csv(table, args.output)
    print(
        f"wrote {table.num_rows} Overture candidate locations from release "
        f"{release} -> {args.output}"
    )
    print(
        "warning: candidates are not verified ownership, collateral, occupancy, "
        "replacement value, or insurance exposure"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
