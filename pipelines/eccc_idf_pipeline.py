"""Audit ECCC design rainfall rates, their canonical refits and release changes.

Run against a local crc-sdk checkout with the geometry extra:
    uv pip install --python .venv/bin/python --no-deps --editable ../crc-sdk
    uv run --no-sync python pipelines/eccc_idf_pipeline.py
    uv run --no-sync python pipelines/eccc_idf_pipeline.py \
        --compare-version 3.20 --cache-mode offline

Use repeated --bounds arguments instead of --stations for a union of areas:
    uv run --no-sync python pipelines/eccc_idf_pipeline.py --province ON \
        --bounds -79.65 43.65 -79.61 43.70 --bounds -75.70 45.30 -75.65 45.35

All boxes are within the chosen province; overlaps never duplicate stations.
Area selection reads the province's station files. Prefetch the areas online
before using --cache-mode offline; an explicit-station cache may be incomplete.

The current release stages a provincial ZIP on first acquisition. Cache reuse and
cross-duration reads need only small station TXT files. Outputs describe station
points; they do not assign rainfall to nearby properties or predict flooding.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from crc_sdk.connectors.adapters import CurveFitIngestPolicy
from crc_sdk.workflows import (
    HazardDataset,
    curve_quantiles,
    return_periods_to_probabilities,
)


def compare_releases(
    rows: list[dict[str, Any]], current: str, previous: str
) -> list[dict[str, Any]]:
    """Compare matching station/duration/period labels; expose support changes."""
    keys = ("station", "duration_minutes", "return_period_years")
    old = {tuple(r[k] for k in keys): r for r in rows if r["version"] == previous}
    comparisons = []
    for row in rows:
        key = tuple(row[k] for k in keys)
        if row["version"] != current or key not in old:
            continue
        before = old[key]
        delta = row["published_mm_h"] - before["published_mm_h"]
        comparisons.append(
            {
                **{k: row[k] for k in keys},
                "previous_version": previous,
                "current_version": current,
                "previous_mm_h": before["published_mm_h"],
                "current_mm_h": row["published_mm_h"],
                "change_mm_h": delta,
                "change_percent": (
                    100 * delta / before["published_mm_h"]
                    if before["published_mm_h"]
                    else None
                ),
                "record_changed": any(
                    row[k] != before[k]
                    for k in ("start_year", "end_year", "record_years")
                ),
                "coordinates_changed": any(
                    row[k] != before[k] for k in ("latitude", "longitude")
                ),
            }
        )
    return comparisons


def run(
    output: Path,
    *,
    province: str = "ON",
    stations: tuple[str, ...] | None = None,
    areas: Sequence[Sequence[float]] | None = None,
    durations: tuple[str, ...] = ("15min", "1h", "24h"),
    version: str = "3.40",
    compare_version: str | None = None,
    cache_mode: str = "reuse",
    cache: Path | None = None,
) -> dict[str, Any]:
    if stations is not None and areas is not None:
        raise ValueError("supply station IDs or areas, not both")
    station_ids = ("6158731",) if stations is None else stations
    if not durations or len(set(durations)) != len(durations):
        raise ValueError("durations must be nonempty and unique")
    if compare_version == version:
        raise ValueError("comparison requires two different releases")
    output.mkdir(parents=True, exist_ok=True)
    cache = cache or output / "cache"
    versions = (version, compare_version) if compare_version else (version,)
    rows: list[dict[str, Any]] = []
    sources = []
    acquisition = []
    for release in versions:
        selection = HazardDataset.eccc_idf(
            durations[0], province=province, version=release
        )
        selection = (
            selection.for_areas(areas)
            if areas is not None
            else selection.for_stations(station_ids)
        )
        base = selection.cache(cache, mode=cache_mode)
        print(base.explain())
        prefetched = base.prefetch()
        acquisition.append(
            {
                "version": release,
                "cache_hits": prefetched.cache_hits,
                "cache_misses": prefetched.cache_misses,
            }
        )
        for duration in durations:
            destination = output / release / duration
            destination.mkdir(parents=True, exist_ok=True)
            plan = (
                base.duration(duration)
                .cache(cache, mode="offline")
                .canonicalize(
                    policy=CurveFitIngestPolicy(
                        h3_resolution=5,
                        family="gumbel_r",
                        producer="crc-sdk",
                        maximum_absolute_residual=0.15,
                        diagnostics=destination / "fit_diagnostics.parquet",
                    )
                )
            )
            published = plan.source_curves()
            sources.append(published)
            source_by_id = {r["station"]: r for r in published.to_pylist()}
            curve_path = destination / "curves.parquet"
            plan.materialize(curve_path)
            curves = pq.ParquetFile(curve_path).read()
            for curve in curves.to_pylist():
                source = source_by_id[curve["source_id"].split(":", 1)[1]]
                periods = source["return_periods"]
                values = curve_quantiles(
                    pa.Table.from_pylist([curve], schema=curves.schema),
                    return_periods_to_probabilities(periods),
                    max_workers=1,
                )[0]
                for i, (period, fitted) in enumerate(zip(periods, values)):
                    official = source["intensity"][i]
                    rows.append(
                        {
                            **{
                                k: source[k]
                                for k in (
                                    "station",
                                    "name",
                                    "latitude",
                                    "longitude",
                                    "start_year",
                                    "end_year",
                                    "record_years",
                                    "duration_minutes",
                                )
                            },
                            "version": release,
                            "duration": duration,
                            "return_period_years": period,
                            "published_mm_h": official,
                            "confidence_95_half_width_mm_h": source[
                                "confidence_half_width"
                            ][i],
                            "fitted_mm_h": float(fitted),
                            "fit_residual_mm_h": float(fitted) - official,
                            "published_duration_depth_mm": official
                            * source["duration_minutes"]
                            / 60,
                            "beyond_record_length": period > source["record_years"],
                        }
                    )
    pq.write_table(
        pa.concat_tables(sources), output / "published_source_curves.parquet"
    )
    rate_schema = pa.schema(
        [(name, pa.string()) for name in ("station", "name", "version", "duration")]
        + [(name, pa.float64()) for name in (
            "latitude", "longitude", "published_mm_h", "confidence_95_half_width_mm_h",
            "fitted_mm_h", "fit_residual_mm_h", "published_duration_depth_mm",
        )]
        + [(name, pa.int64()) for name in (
            "start_year", "end_year", "record_years", "duration_minutes",
            "return_period_years",
        )]
        + [("beyond_record_length", pa.bool_())]
    )
    pq.write_table(
        pa.Table.from_pylist(rows, schema=rate_schema), output / "rainfall_rates.parquet"
    )
    comparisons = (
        compare_releases(rows, version, compare_version) if compare_version else []
    )
    if compare_version:
        if not comparisons:
            raise ValueError("releases share no station/duration/return-period labels")
        pq.write_table(
            pa.Table.from_pylist(comparisons), output / "release_changes.parquet"
        )
    summary = {
        "province": province,
        "stations": sorted({row["station"] for row in rows}),
        "areas": base.requested_areas,
        "durations": list(durations),
        "acquisition": acquisition,
        "rate_rows": len(rows),
        "comparison_rows": len(comparisons),
        "maximum_absolute_fit_residual_mm_h": max(
            (abs(r["fit_residual_mm_h"]) for r in rows), default=None
        ),
        "interpretation": (
            "Published central rates and 95% confidence half-widths are distinct from "
            "the SDK quantile refit. Release changes can reflect record, station or "
            "method changes; they are not climate trends. Duration depths use rounded "
            "published rates and can differ from ECCC's separately rounded "
            "amount table. "
            "24-hour moving maxima are not calendar-day Rx1day. These station rates "
            "are not flood depths or climate-adjusted projections."
        ),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--province", default="ON")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--stations", nargs="+", help="Explicit ECCC climate IDs")
    selection.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        action="append",
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Select a WGS84 box within the province; repeat for a union of boxes",
    )
    parser.add_argument("--durations", nargs="+", default=["15min", "1h", "24h"])
    parser.add_argument("--version", choices=("3.20", "3.40"), default="3.40")
    parser.add_argument("--compare-version", choices=("3.20", "3.40"))
    parser.add_argument(
        "--cache-mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/eccc_idf"))
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.output,
                province=args.province,
                stations=tuple(args.stations) if args.stations is not None else None,
                areas=args.bounds,
                durations=tuple(args.durations),
                version=args.version,
                compare_version=args.compare_version,
                cache_mode=args.cache_mode,
                cache=args.cache,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
