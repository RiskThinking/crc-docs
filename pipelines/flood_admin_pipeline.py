"""Summarise JRC EFAS flood depth by province, with an optional PMTiles map.

Run with:

    uv run python pipelines/flood_admin_pipeline.py
    uv run python pipelines/flood_admin_pipeline.py --bounds 6.8 50.8 7.2 51.1 \
        --return-period-years 100 --skip-places

1. crc-sdk reads the EFAS return-period depth maps inside the box (or any
   one-series crc-sdk Dataset given with ``--hazard``) and queries each pixel
   at its centre for the chosen return period.
2. Pixels are grouped into H3 cells (``--h3-resolution``); a cell keeps its
   deepest pixel.
3. Each cell centre is joined to the admin polygon that contains it
   (geoBoundaries ADM1 for Germany by default).
4. Optionally, Overture Maps places with confidence > 0.7 are counted per
   flooded cell (DuckDB reads Overture's public S3 release).
5. Optionally, ``tippecanoe`` tiles the hex and province layers into one
   PMTiles archive; the step is skipped when tippecanoe is not installed.

Depths are present-climate river flood depths, not projections or losses.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h3
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from crc_sdk import JRC, Assets, Bounds, Cache, Dataset, Runtime

CACHES = {"reuse": Cache.reuse, "offline": Cache.offline, "refresh": Cache.refresh}
DEFAULT_ADMIN_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/"
    "gbOpen/DEU/ADM1/geoBoundaries-DEU-ADM1_simplified.geojson"
)
OVERTURE_CATALOG_URL = "https://stac.overturemaps.org/catalog.json"


def support_centres(table: pa.Table) -> dict[str, tuple[float, float]]:
    """Centre of each support's footprint, or of its H3 cell when it has none."""
    centres: dict[str, tuple[float, float]] = {}
    for support, geometry, cell in zip(
        table["support_id"].to_pylist(),
        table["geometry"].to_pylist(),
        table["cell_id"].to_pylist(),
    ):
        if support in centres:
            continue
        if geometry is not None:
            point = shapely.from_wkb(geometry).centroid
            centres[support] = (point.x, point.y)
        else:
            latitude, longitude = h3.cell_to_latlng(h3.int_to_str(cell))
            centres[support] = (longitude, latitude)
    return centres


def depth_by_cell(
    hazard: Dataset, return_period: float, resolution: int
) -> tuple[dict[str, float], dict[str, int]]:
    """Deepest value per H3 cell at one return period, plus failure counts."""
    if len(hazard.inspect().series) != 1:
        raise ValueError("the hazard must hold exactly one series")
    centres = support_centres(hazard.read().table)
    if not centres:
        raise LookupError("the hazard has no supports in the selected area")
    rows = (
        hazard.evaluate(
            Assets(
                {
                    "support_id": list(centres),
                    "longitude": [c[0] for c in centres.values()],
                    "latitude": [c[1] for c in centres.values()],
                },
                id_column="support_id",
            )
        )
        .return_periods([return_period])
        .read()
        .table.to_pylist()
    )
    cells: dict[str, float] = {}
    failures: Counter[str] = Counter()
    for row in rows:
        if row["value"] is None:
            failures[row["failure"]["code"] if row["failure"] else "no_value"] += 1
            continue
        longitude, latitude = centres[row["asset_id"]]
        cell = h3.latlng_to_cell(latitude, longitude, resolution)
        cells[cell] = max(row["value"], cells.get(cell, float("-inf")))
    return cells, dict(failures)


def provinces_of(
    cells: Sequence[str], admin: dict[str, Any], name: str
) -> dict[str, str]:
    """Admin unit containing each cell centre (cells outside every unit are dropped)."""
    shapes = [shapely.geometry.shape(f["geometry"]) for f in admin["features"]]
    labels = [f["properties"][name] for f in admin["features"]]
    tree = shapely.STRtree(shapes)
    points = [shapely.Point(h3.cell_to_latlng(c)[::-1]) for c in cells]
    found: dict[str, str] = {}
    for point_index, shape_index in zip(*tree.query(points, predicate="within")):
        found.setdefault(cells[point_index], labels[shape_index])
    return found


def overture_places(
    bounds: Sequence[float], cells: set[str], resolution: int, confidence: float = 0.7
) -> Counter[str]:
    """Count Overture places per flooded cell (reads Overture's public S3 data)."""
    import duckdb

    west, south, east, north = bounds
    with duckdb.connect() as con:
        con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region = 'us-west-2'")
        release = con.execute(
            "SELECT latest FROM read_json_auto(?)", [OVERTURE_CATALOG_URL]
        ).fetchone()[0]
        uri = f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
        points = con.execute(
            f"""
            SELECT bbox.xmin, bbox.ymin
            FROM read_parquet('{uri}', hive_partitioning = 1)
            WHERE bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ?
              AND confidence > ?
            """,
            [west, east, south, north, confidence],
        ).fetchall()
    counts: Counter[str] = Counter()
    for x, y in points:
        cell = h3.latlng_to_cell(y, x, resolution)
        if cell in cells:
            counts[cell] += 1
    return counts


def write_geojsonseq(path: Path, features: Sequence[dict[str, Any]]) -> Path:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w") as sink:
        for feature in features:
            sink.write(json.dumps(feature) + "\n")
    os.replace(temporary, path)
    return path


def build_pmtiles(layers: dict[str, Path], output: Path) -> Path | None:
    """One tippecanoe pass over all layers; skipped when tippecanoe is missing."""
    tippecanoe = shutil.which("tippecanoe")
    if tippecanoe is None:
        print("tippecanoe not found on PATH; skipping PMTiles")
        return None
    temporary = output.with_name(f".{output.stem}.tmp.pmtiles")
    command = [tippecanoe, "-o", str(temporary), "--force", "--quiet", "-zg"]
    command += ["--drop-densest-as-needed"]
    for name, path in layers.items():
        command += ["-L", f"{name}:{path}"]
    subprocess.run(command, check=True)
    os.replace(temporary, output)
    return output


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=(5.9, 47.3, 10.5, 52.5),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    parser.add_argument("--h3-resolution", type=int, default=7)
    parser.add_argument("--return-period-years", type=float, default=100)
    parser.add_argument(
        "--hazard", type=Path, help="Use this crc-sdk Dataset, not EFAS"
    )
    parser.add_argument("--cache-mode", choices=sorted(CACHES), default="reuse")
    parser.add_argument("--admin-geojson-url", default=DEFAULT_ADMIN_URL)
    parser.add_argument("--admin-name-property", default="shapeName")
    parser.add_argument("--skip-places", action="store_true")
    parser.add_argument("--skip-pmtiles", action="store_true")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("pipeline_output/flood_admin")
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    west, south, east, north = args.bounds
    if args.hazard is not None:
        hazard = Dataset.open(args.hazard)
    else:
        hazard = (
            JRC(product=JRC.Product.EFAS)
            .select(area=Bounds(west=west, south=south, east=east, north=north))
            .write(
                output / "efas_flood.parquet",
                overwrite=True,
                runtime=Runtime(cache=CACHES[args.cache_mode](output / "cache")),
            )
        )
    variable = hazard.metadata.spec.variables[0]
    cells, failures = depth_by_cell(
        hazard, args.return_period_years, args.h3_resolution
    )

    admin_path = output / "admin.geojson"
    if not admin_path.exists():
        temporary = admin_path.with_name(".admin.geojson.tmp")
        urllib.request.urlretrieve(args.admin_geojson_url, temporary)
        os.replace(temporary, admin_path)
    admin = json.loads(admin_path.read_text())
    provinces = provinces_of(list(cells), admin, args.admin_name_property)
    places = (
        Counter()
        if args.skip_places
        else overture_places(args.bounds, set(provinces), args.h3_resolution)
    )
    rows = [
        {
            "cell": cell,
            "province": province,
            "value": cells[cell],
            "place_count": places.get(cell, 0),
        }
        for cell, province in sorted(provinces.items())
    ]
    temporary = output / ".risk_by_province.parquet.tmp"
    pq.write_table(pa.Table.from_pylist(rows), temporary)
    os.replace(temporary, output / "risk_by_province.parquet")

    by_province: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_province[row["province"]].append(row)
    summary_rows = sorted(
        (
            {
                "province": name,
                "cells": len(items),
                "mean_value": sum(r["value"] for r in items) / len(items),
                "max_value": max(r["value"] for r in items),
                "places_in_cells": sum(r["place_count"] for r in items),
            }
            for name, items in by_province.items()
        ),
        key=lambda row: -row["mean_value"],
    )
    pmtiles = None
    if not args.skip_pmtiles:
        hexes = write_geojsonseq(
            output / "hex_layer.geojsonseq",
            [
                {
                    "type": "Feature",
                    "geometry": shapely.geometry.mapping(
                        shapely.Polygon(
                            [(lng, lat) for lat, lng in h3.cell_to_boundary(r["cell"])]
                        )
                    ),
                    "properties": r,
                }
                for r in rows
            ],
        )
        pmtiles = build_pmtiles(
            {"hex_value": hexes, "provinces": admin_path},
            output / "risk_by_province.pmtiles",
        )
    summary = {
        "hazard": str(hazard.path),
        "variable": variable.id,
        "measurement": str(variable.measurement),
        "return_period_years": args.return_period_years,
        "h3_resolution": args.h3_resolution,
        "cells_with_value": len(cells),
        "cells_in_provinces": len(rows),
        "failures": failures,
        "provinces": summary_rows,
        "pmtiles": str(pmtiles) if pmtiles else None,
        "note": "Hazard values per H3 cell (deepest supporting pixel); not losses.",
    }
    temporary = output / ".summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    os.replace(temporary, output / "summary.json")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
