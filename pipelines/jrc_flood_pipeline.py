"""Query JRC EFAS or GloFAS flood depths per map pixel for an area.

Run with:

    uv run python pipelines/jrc_flood_pipeline.py --dataset glofas \
        --bounds -79.45 43.64 -79.40 43.68

JRC publishes one depth map per return period. crc-sdk reads the pixels inside
the box as supplied quantile knots (no fitting) and keeps each pixel's own
footprint. Each pixel is queried at its centre for the requested return
periods. A period outside the published maps returns ``query_outside_support``
instead of an extrapolated depth. Depths are river flood depths above ground
for the present climate, not projections.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h3
import pyarrow as pa
import shapely
from crc_sdk import JRC, Assets, Bounds, Cache, Dataset, Runtime

CACHES = {"reuse": Cache.reuse, "offline": Cache.offline, "refresh": Cache.refresh}


def source_cache(output: Path) -> Path:
    """Source cache directory: ``CRC_DOCS_CACHE`` when set, else under the output."""
    return Path(os.environ.get("CRC_DOCS_CACHE") or output / "cache")


def support_points(table: pa.Table) -> dict[str, list[Any]]:
    """One point per support: its footprint's centre (or its H3 cell's centre)."""
    seen: dict[str, tuple[float, float]] = {}
    for support, geometry, cell in zip(
        table["support_id"].to_pylist(),
        table["geometry"].to_pylist(),
        table["cell_id"].to_pylist(),
    ):
        if support in seen:
            continue
        if geometry is not None:
            centre = shapely.from_wkb(geometry).centroid
            seen[support] = (centre.x, centre.y)
        else:
            latitude, longitude = h3.cell_to_latlng(h3.int_to_str(cell))
            seen[support] = (longitude, latitude)
    return {
        "support_id": list(seen),
        "longitude": [point[0] for point in seen.values()],
        "latitude": [point[1] for point in seen.values()],
    }


def depths_by_support(
    flood: Dataset,
    return_periods: Sequence[float],
    output: Path,
    *,
    runtime: Runtime | None = None,
) -> dict[str, Any]:
    """Save the selected curves, query every support, and summarise per period."""
    output.mkdir(parents=True, exist_ok=True)
    runtime = runtime or Runtime()
    curves = flood.write(
        output / "jrc_flood_curves.parquet", overwrite=True, runtime=runtime
    )
    points = support_points(curves.read().table)
    if not points["support_id"]:
        raise LookupError("the selected area contains no JRC flood pixels")
    assets = Assets(points, id_column="support_id")
    evaluation = (
        curves.evaluate(assets)
        .return_periods(list(return_periods))
        .write(output / "jrc_flood_depths.parquet", overwrite=True)
    )
    rows = evaluation.read().table.to_pylist()
    summary: dict[str, Any] = {}
    for period in return_periods:
        selected = [row for row in rows if row["query_value"] == period]
        values = [row["value"] for row in selected if row["value"] is not None]
        summary[f"rp{period:g}"] = {
            "pixels_with_depth": len(values),
            "maximum_depth": max(values) if values else None,
            "failures": dict(
                Counter(row["failure"]["code"] for row in selected if row["failure"])
            ),
        }
    variable = curves.metadata.spec.variables[0]
    source = curves.metadata.source
    return {
        "variable": variable.id,
        "measurement": str(variable.measurement),
        "release": source.release.id if source and source.release else None,
        "pixels": len(points["support_id"]),
        "return_periods": summary,
        "outputs": {
            "curves": str(curves.path),
            "depths": str(evaluation.path),
        },
        "resources": [
            {
                "uri": item.uri,
                "sha256": item.sha256,
                "license": item.license,
                "attribution": item.attribution,
            }
            for item in (source.resources if source else ())
        ],
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=(-79.45, 43.64, -79.40, 43.68),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    p.add_argument(
        "--return-periods", type=float, nargs="+", default=[10, 50, 100, 500]
    )
    p.add_argument(
        "--dataset",
        choices=[product.value for product in JRC.Product],
        default=JRC.Product.GLOFAS.value,
        help="EFAS covers Europe; GloFAS is global",
    )
    p.add_argument("--cache-mode", choices=sorted(CACHES), default="reuse")
    p.add_argument("--output-dir", type=Path, default=Path("pipeline_output/jrc_flood"))
    return p


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parser().parse_args(argv)
    west, south, east, north = args.bounds
    flood = JRC(product=JRC.Product(args.dataset)).select(
        area=Bounds(west=west, south=south, east=east, north=north)
    )
    runtime = Runtime(cache=CACHES[args.cache_mode](source_cache(args.output_dir)))
    summary = {
        "dataset": args.dataset,
        "bounds": list(args.bounds),
        **depths_by_support(
            flood, args.return_periods, args.output_dir, runtime=runtime
        ),
    }
    temporary = args.output_dir / ".summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    os.replace(temporary, args.output_dir / "summary.json")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
