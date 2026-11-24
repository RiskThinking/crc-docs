"""Fit annual soil-moisture minima from the JRC European Drought Observatory.

Run with:

    uv run python pipelines/jrc_drought_pipeline.py \
        --bounds 8.0 50.0 8.2 50.2 --years 2011 2024

EDO publishes the soil moisture index (SMI) as native dekadal observations
(three per month, on the 1st, 11th and 21st). crc-sdk reads them without
inventing a fixed cadence, so this pipeline takes each pixel's annual minimum
itself and keeps only years with every dekad observed (``--minimum-dekads``
relaxes that). The minima are fitted explicitly (GEV by L-moments, Gumbel for
minima as fallback) and queried as lower-tail return periods: the T-year value
is the SMI reached or undercut once every T years on average. Lower SMI is
drier. Results describe the observed record, not a projection.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h3
import pyarrow as pa
import shapely
from crc_framework import DistributionFamily, SampleEstimator, SampleFit, Tail
from crc_sdk import (
    EDO,
    Assets,
    Bounds,
    Cache,
    FitFailure,
    Observations,
    Period,
    Probability,
    Runtime,
    Samples,
    Variable,
)

CACHES = {"reuse": Cache.reuse, "offline": Cache.offline, "refresh": Cache.refresh}
DEKADS_PER_YEAR = 36
FIT = SampleFit(
    family=DistributionFamily.GENERALIZED_EXTREME_VALUE,
    estimator=SampleEstimator.L_MOMENTS,
    minimum_samples=5,
    fallbacks=(SampleFit(family=DistributionFamily.GUMBEL_LEFT, minimum_samples=5),),
)


def centre(geometry: bytes | None, cell: int) -> tuple[float, float]:
    """Longitude and latitude of a footprint's centre, or of its H3 cell."""
    if geometry is not None:
        point = shapely.from_wkb(geometry).centroid
        return point.x, point.y
    latitude, longitude = h3.cell_to_latlng(h3.int_to_str(cell))
    return longitude, latitude


def annual_minima(
    table: pa.Table, minimum_dekads: int = DEKADS_PER_YEAR
) -> tuple[dict[str, list[Any]], dict[str, int]]:
    """One row per pixel and complete year: the lowest dekadal SMI."""
    groups: dict[tuple[str, int], list[float]] = defaultdict(list)
    places: dict[str, tuple[float, float]] = {}
    for row in table.select(
        ["support_id", "geometry", "cell_id", "time", "value"]
    ).to_pylist():
        if row["support_id"] not in places:
            places[row["support_id"]] = centre(row["geometry"], row["cell_id"])
        key = (row["support_id"], int(row["time"][:4]))
        if row["value"] is not None:
            groups[key].append(row["value"])
        else:
            groups.setdefault(key, [])
    minima: dict[str, list[Any]] = {
        name: [] for name in ("support_id", "longitude", "latitude", "time", "value")
    }
    counts = Counter()
    for (support, year), values in sorted(groups.items()):
        if len(values) < minimum_dekads:
            counts["incomplete_pixel_years"] += 1
            continue
        counts["complete_pixel_years"] += 1
        longitude, latitude = places[support]
        minima["support_id"].append(support)
        minima["longitude"].append(longitude)
        minima["latitude"].append(latitude)
        minima["time"].append(year)
        minima["value"].append(min(values))
    return minima, dict(counts)


def drought_return_levels(
    observations: Observations,
    return_periods: Sequence[float],
    output: Path,
    *,
    minimum_dekads: int = DEKADS_PER_YEAR,
    runtime: Runtime | None = None,
) -> dict[str, Any]:
    """Read SMI, fit annual minima per pixel and query lower-tail return periods."""
    output.mkdir(parents=True, exist_ok=True)
    observed = observations.write(
        output / "edo_smi_dekadal.parquet", overwrite=True, runtime=runtime
    )
    native = observed.read()
    smi = native.metadata.spec.variables[0]
    minima, counts = annual_minima(native.table, minimum_dekads)
    if not minima["support_id"]:
        raise LookupError("no pixel has a complete year of SMI observations")
    samples = Samples.from_table(
        minima,
        variable=Variable(
            "edo:annual_minimum_soil_moisture_index",
            measurement=smi.measurement,
            label="Annual minimum of the dekadal soil moisture index",
        ),
        probability=Probability.annual(tail=Tail.LOWER),
    )
    samples.write(output / "edo_smi_annual_minima.parquet", overwrite=True)
    fitted = samples.fit(FIT, on_failure=FitFailure.KEEP_NO_DATA).write(
        output / "edo_smi_fitted.parquet", overwrite=True
    )
    pixels = sorted(
        set(minima["support_id"]),
    )
    first = {
        support: (lon, lat)
        for support, lon, lat in zip(
            minima["support_id"], minima["longitude"], minima["latitude"]
        )
    }
    assets = Assets(
        {
            "support_id": pixels,
            "longitude": [first[p][0] for p in pixels],
            "latitude": [first[p][1] for p in pixels],
        },
        id_column="support_id",
    )
    evaluation = (
        fitted.evaluate(assets)
        .return_periods(list(return_periods))
        .write(output / "edo_smi_return_levels.parquet", overwrite=True)
    )
    rows = evaluation.read().table.to_pylist()
    levels: dict[str, Any] = {}
    for period in return_periods:
        selected = [row for row in rows if row["query_value"] == period]
        values = [row["value"] for row in selected if row["value"] is not None]
        levels[f"rp{period:g}"] = {
            "pixels_with_value": len(values),
            "driest_smi": min(values) if values else None,
            "median_smi": sorted(values)[len(values) // 2] if values else None,
            "failures": dict(
                Counter(row["failure"]["code"] for row in selected if row["failure"])
            ),
        }
    source = observed.metadata.source
    return {
        "pixels": len(pixels),
        "annual_minima": counts,
        "fit": "GEV (L-moments), Gumbel-for-minima fallback, lower tail",
        "return_periods": levels,
        "outputs": {
            "dekadal": str(observed.path),
            "annual_minima": str(output / "edo_smi_annual_minima.parquet"),
            "fitted": str(fitted.path),
            "return_levels": str(evaluation.path),
        },
        "release": source.release.id if source and source.release else None,
        "resources": [
            {
                "uri": item.uri,
                "sha256": item.sha256,
                "license": item.license,
                "attribution": item.attribution,
            }
            for item in (source.resources if source else ())
        ],
        "interpretation": (
            "Return levels of the annual minimum dekadal SMI over the observed "
            "years; lower is drier. Short records make long return periods "
            "uncertain extrapolations."
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=(8.0, 50.0, 8.5, 50.5),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs=2,
        default=(1995, 2024),
        metavar=("START", "END"),
        help="Calendar years to read, inclusive",
    )
    parser.add_argument(
        "--return-periods", type=float, nargs="+", default=[2, 5, 10, 25]
    )
    parser.add_argument(
        "--minimum-dekads",
        type=int,
        default=DEKADS_PER_YEAR,
        help="Observed dekads a year needs before its minimum is used",
    )
    parser.add_argument("--cache-mode", choices=sorted(CACHES), default="reuse")
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output/edo"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    west, south, east, north = args.bounds
    observations = EDO(product=EDO.Product.SOIL_MOISTURE_INDEX).select(
        area=Bounds(west=west, south=south, east=east, north=north),
        time=Period.window(*args.years),
    )
    runtime = Runtime(cache=CACHES[args.cache_mode](args.output_dir / "cache"))
    summary = {
        "bounds": list(args.bounds),
        "years": list(args.years),
        **drought_return_levels(
            observations,
            args.return_periods,
            args.output_dir,
            minimum_dekads=args.minimum_dekads,
            runtime=runtime,
        ),
    }
    temporary = args.output_dir / ".summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    os.replace(temporary, args.output_dir / "summary.json")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
