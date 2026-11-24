"""Build agricultural units for an area and evaluate a flood (or other) hazard on them.

Examples:

    uv run python pipelines/agricultural_climate_pipeline.py \
      --source usda --bounds -93.7 41.9 -93.2 42.3 --year 2024 --crop-codes 1 5

    uv run python pipelines/agricultural_climate_pipeline.py \
      --source ftw --bounds 2.40 48.00 2.45 48.05 --minimum-confidence 80 \
      --hazard pipeline_output/france-flood.parquet

USDA Cropland pixels of the chosen crop codes are counted per H3 cell; Fields
of the World supplies predicted field polygons. Without ``--hazard`` the
pipeline reads JRC GloFAS flood depths for the same box. Any crc-sdk Dataset
file with one series works as ``--hazard``. Each unit is evaluated at its
centre (H3 cell centre or field centroid) for the requested return periods.

Outputs: the units, the long-format evaluation, a GeoJSONSeq map layer, a
summary table, a manifest with checksums and, when ``tippecanoe`` is on PATH,
a PMTiles archive (``--skip-pmtiles`` to skip). Agricultural observations and
hazard values are separate evidence; no combined risk score is inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h3
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import shapely
from crc_sdk import (
    JRC,
    Assets,
    Bounds,
    Cache,
    Dataset,
    EvaluationArtifact,
    FieldsOfTheWorld,
    Period,
    Runtime,
    USDACropland,
)

CACHES = {"reuse": Cache.reuse, "offline": Cache.offline, "refresh": Cache.refresh}
WARNINGS = (
    (
        "Agricultural observations and hazard values are separate evidence layers; "
        "no combined risk score was inferred."
    ),
    "FTW polygons are remote-sensing field units, not legal parcels.",
    "USDA CDL pixel_count is a pixel sample, not acreage or yield.",
)


def _bounds(values: Sequence[float]) -> Bounds:
    west, south, east, north = values
    return Bounds(west=west, south=south, east=east, north=north)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_parquet(table: pa.Table, path: Path) -> Path:
    temporary = path.with_name(f".{path.name}.tmp")
    pq.write_table(table, temporary)
    os.replace(temporary, path)
    return path


def usda_units(
    bounds: Sequence[float],
    year: int,
    crop_codes: Sequence[int],
    resolution: int,
    runtime: Runtime,
) -> pa.Table:
    """Count the chosen crop pixels per H3 cell; share is among those crops."""
    layer = USDACropland().select(
        area=_bounds(bounds), periods=[Period.window(year, year)]
    )
    counts: Counter[tuple[str, int, str]] = Counter()
    wanted = pa.array([float(code) for code in crop_codes])
    with layer.batches(runtime=runtime) as stream:
        for batch in stream:
            kept = batch.filter(pc.is_in(batch["value"], value_set=wanted))
            if not kept.num_rows:
                continue
            centres = shapely.centroid(
                shapely.from_wkb(kept["geometry"].to_numpy(zero_copy_only=False))
            )
            xs, ys = shapely.get_x(centres), shapely.get_y(centres)
            for x, y, code, label in zip(
                xs, ys, kept["value"].to_pylist(), kept["label"].to_pylist()
            ):
                counts[(h3.latlng_to_cell(y, x, resolution), int(code), label)] += 1
    totals: Counter[str] = Counter()
    for (cell, _, _), count in counts.items():
        totals[cell] += count
    rows = []
    for (cell, code, label), count in sorted(counts.items()):
        latitude, longitude = h3.cell_to_latlng(cell)
        rows.append(
            {
                "asset_id": f"{year}:{code}:{cell}",
                "cell": cell,
                "year": year,
                "crop_code": code,
                "crop_name": label,
                "pixel_count": count,
                "sampled_crop_share": count / totals[cell],
                "longitude": longitude,
                "latitude": latitude,
            }
        )
    return pa.Table.from_pylist(rows)


def ftw_units(
    bounds: Sequence[float], minimum_confidence: float, runtime: Runtime
) -> pa.Table:
    """Fields of the World polygons with area, perimeter and model score."""
    layer = FieldsOfTheWorld().select(area=_bounds(bounds))
    fields: dict[str, dict[str, Any]] = defaultdict(dict)
    names = {
        "ftw:field_area": "area_m2",
        "ftw:field_perimeter": "perimeter_m",
        "ftw:model_score": "confidence",
    }
    with layer.batches(runtime=runtime) as stream:
        for batch in stream:
            for row in batch.to_pylist():
                field = fields[row["support_id"]]
                field.update(asset_id=row["label"], geometry=row["geometry"])
                if row["variable_id"] in names:
                    field[names[row["variable_id"]]] = row["value"]
    rows = []
    for field in fields.values():
        if field.get("confidence") is None or field["confidence"] < minimum_confidence:
            continue
        centre = shapely.from_wkb(field["geometry"]).centroid
        rows.append({**field, "longitude": centre.x, "latitude": centre.y})
    return pa.Table.from_pylist(rows)


def evaluate_units(
    units: pa.Table, hazard: Dataset, return_periods: Sequence[float], output: Path
) -> EvaluationArtifact:
    """Query the hazard at each unit's centre; unmatched units keep failure rows."""
    if len(hazard.inspect().series) != 1:
        raise ValueError("--hazard must hold exactly one series; select one first")
    assets = Assets(units.select(["asset_id", "longitude", "latitude"]))
    return (
        hazard.evaluate(assets)
        .return_periods(list(return_periods))
        .write(output, overwrite=True)
    )


def map_and_summary(
    source: str,
    units: pa.Table,
    evaluation: pa.Table,
    output_dir: Path,
) -> tuple[Path, Path]:
    """One GeoJSON feature per unit with its hazard values, plus a summary table."""
    values: dict[str, dict[str, float | None]] = defaultdict(dict)
    coverage: dict[str, str] = {}
    for row in evaluation.to_pylist():
        values[row["asset_id"]][f"rp{row['query_value']:g}"] = row["value"]
        if row["support_id"] is None:
            coverage[row["asset_id"]] = "outside_hazard"
        elif row["value"] is None:
            coverage.setdefault(row["asset_id"], "missing_hazard_value")
        else:
            coverage.setdefault(row["asset_id"], "modeled_hazard")
    queries = sorted(
        {key for v in values.values() for key in v}, key=lambda k: float(k[2:])
    )
    weight = "pixel_count" if source == "usda" else "area_m2"
    group = ("crop_code", "crop_name") if source == "usda" else ()
    map_path = output_dir / f"{source}-crop-hazard.geojsonseq"
    temporary = map_path.with_name(f".{map_path.name}.tmp")
    sums: dict[tuple, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    with temporary.open("w") as features:
        for unit in units.to_pylist():
            status = coverage.get(unit["asset_id"], "outside_hazard")
            hazard = values.get(unit["asset_id"], {})
            if source == "usda":
                boundary = [
                    (lng, lat) for lat, lng in h3.cell_to_boundary(unit["cell"])
                ]
                geometry = shapely.Polygon(boundary)
            else:
                geometry = shapely.from_wkb(unit["geometry"])
            properties = {
                key: value
                for key, value in unit.items()
                if key not in ("geometry", "longitude", "latitude")
            }
            properties.update(hazard_coverage=status, **hazard)
            features.write(
                json.dumps(
                    {
                        "type": "Feature",
                        "geometry": shapely.geometry.mapping(geometry),
                        "properties": properties,
                    }
                )
                + "\n"
            )
            key = (*(unit[name] for name in group), status)
            bucket = sums[key]
            bucket["units"] += 1
            bucket[weight] += unit[weight] or 0.0
            for query in queries:
                if hazard.get(query) is not None and unit[weight]:
                    bucket[f"weighted_{query}"] += unit[weight] * hazard[query]
                    bucket[f"weight_{query}"] += unit[weight]
    os.replace(temporary, map_path)
    rows = []
    for key, bucket in sorted(sums.items(), key=lambda item: str(item[0])):
        row = dict(zip((*group, "hazard_coverage"), key))
        row.update(units=int(bucket["units"]), **{weight: bucket[weight]})
        for query in queries:
            total = bucket.get(f"weight_{query}", 0.0)
            row[f"{weight}_weighted_{query}"] = (
                bucket[f"weighted_{query}"] / total if total else None
            )
        rows.append(row)
    summary_path = _write_parquet(
        pa.Table.from_pylist(rows), output_dir / f"{source}-crop-hazard-summary.parquet"
    )
    return map_path, summary_path


def build_pmtiles(
    geojsonseq: Path, output: Path, threads: int | None = None
) -> Path | None:
    """Tile the map layer with tippecanoe; skipped cleanly when it is missing."""
    tippecanoe = shutil.which("tippecanoe")
    if tippecanoe is None:
        print("tippecanoe not found on PATH; skipping PMTiles")
        return None
    temporary = output.with_name(f".{output.stem}.tmp.pmtiles")
    environment = dict(os.environ)
    if threads:
        environment["TIPPECANOE_MAX_THREADS"] = str(threads)
    subprocess.run(
        [
            tippecanoe,
            "-o",
            str(temporary),
            "--force",
            "--quiet",
            "-l",
            "crop_hazard",
            "-Z5",
            "-z13",
            "--drop-densest-as-needed",
            str(geojsonseq),
        ],
        check=True,
        env=environment,
    )
    os.replace(temporary, output)
    return output


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", choices=("usda", "ftw"), required=True)
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        required=True,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    parser.add_argument("--year", type=int, default=2024, help="USDA CDL year")
    parser.add_argument("--crop-codes", type=int, nargs="+", default=[1, 5])
    parser.add_argument("--minimum-confidence", type=float, default=80.0)
    parser.add_argument("--h3-resolution", type=int, default=7, help="USDA units")
    parser.add_argument(
        "--hazard", type=Path, help="crc-sdk Dataset file; default reads JRC GloFAS"
    )
    parser.add_argument(
        "--return-periods", type=float, nargs="+", default=[10, 25, 100]
    )
    parser.add_argument("--cache-mode", choices=sorted(CACHES), default="reuse")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("pipeline_output/agriculture")
    )
    parser.add_argument("--skip-pmtiles", action="store_true")
    parser.add_argument("--pmtiles-output", type=Path)
    parser.add_argument("--pmtiles-threads", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(cache=CACHES[args.cache_mode](output / "cache"))
    if args.hazard is not None:
        hazard = Dataset.open(args.hazard)
    else:
        hazard = (
            JRC(product=JRC.Product.GLOFAS)
            .select(area=_bounds(args.bounds))
            .write(output / "glofas-flood.parquet", overwrite=True, runtime=runtime)
        )
    if args.source == "usda":
        units = usda_units(
            args.bounds, args.year, args.crop_codes, args.h3_resolution, runtime
        )
    else:
        units = ftw_units(args.bounds, args.minimum_confidence, runtime)
    if not units.num_rows:
        raise LookupError("no agricultural units in the selected area")
    units_path = _write_parquet(
        units, output / f"{args.source}-agricultural-units.parquet"
    )
    evaluation = evaluate_units(
        units,
        hazard,
        args.return_periods,
        output / f"{args.source}-hazard-evaluation.parquet",
    )
    map_path, summary_path = map_and_summary(
        args.source, units, evaluation.read().table, output
    )
    pmtiles = None
    if not args.skip_pmtiles:
        pmtiles = build_pmtiles(
            map_path,
            args.pmtiles_output or output / f"{args.source}-crop-hazard.pmtiles",
            args.pmtiles_threads,
        )
    counts = evaluation.metadata.report.counts
    manifest = {
        "agricultural_source": args.source,
        "bounds_wgs84": list(args.bounds),
        "hazard": str(hazard.path),
        "hazard_variables": [v.id for v in hazard.metadata.spec.variables],
        "units": units.num_rows,
        "matched_units": counts.matched_assets,
        "unmatched_units": counts.unmatched_assets,
        "files": {
            str(path): _sha256(path)
            for path in (units_path, evaluation.path, map_path, summary_path, pmtiles)
            if path is not None
        },
        "warnings": list(WARNINGS),
    }
    temporary = output / ".manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(temporary, output / "manifest.json")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    main()
