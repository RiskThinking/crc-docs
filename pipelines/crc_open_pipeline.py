"""Screen daily rainfall extremes for an illustrative Toronto portfolio with CRC Open.

Run with:

    uv run python pipelines/crc_open_pipeline.py
    uv run python pipelines/crc_open_pipeline.py --assets assets.csv --years 2050

Assets need asset_id, longitude and latitude columns (CSV or Parquet). CRC Open
covers SSP5-8.5 only and has no historical baseline. Its periods are four-year
windows; each requested year selects the window that contains it. Outputs are
Rx1day return levels (mm/day) on CRC Open's H3 cells, not vulnerability or
financial loss estimates. An optional historical Rx1day dataset (for example
an ERA5 fit written with crc-sdk) can be evaluated at the same assets; it uses
a different source, period and method, so the difference is not a pure
climate-change signal.

Set ``CRC_OPEN_CATALOG`` to read a different CRC Open release index. See
notebooks/sources/crc_open_hazards.ipynb for coverage discovery and charts.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
from crc_framework import Duration, TimeUnit
from crc_sdk import Assets, Bounds, Cache, CRCOpen, Dataset, Runtime

CRC_OPEN = os.environ.get(
    "CRC_OPEN_CATALOG", "https://data.riskthinking.ai/crc-open/_CURRENT.json"
)
RX1DAY = CRCOpen.Variable.ANNUAL_MAXIMUM_DAILY_PRECIPITATION
YEARS = (2030, 2050, 2080)
RETURN_PERIODS = (10, 100)
SITES = {
    "asset_id": ["West depot", "Central clinic", "East warehouse"],
    "longitude": [-79.47, -79.38, -79.29],
    "latitude": [43.65, 43.65, 43.70],
}
NOTE = (
    "CRC Open: SSP5-8.5 only, no historical baseline; four-year period windows; "
    "values are hazard return levels on H3 cells, not losses."
)


def source_cache(output: Path) -> Path:
    """Source cache directory: ``CRC_DOCS_CACHE`` when set, else under the output."""
    return Path(os.environ.get("CRC_DOCS_CACHE") or output / "cache")


def load_assets(path: Path | None) -> pa.Table:
    if path is None:
        return pa.table(SITES)
    if path.suffix.lower() == ".csv":
        from pyarrow import csv

        return csv.read_csv(path)
    import pyarrow.parquet as pq

    return pq.read_table(path)


def area_of(assets: pa.Table, margin: float = 0.05) -> Bounds:
    """A small box around the assets, so only nearby release shards are read."""
    longitudes = assets["longitude"].to_pylist()
    latitudes = assets["latitude"].to_pylist()
    return Bounds(
        west=max(-180.0, min(longitudes) - margin),
        south=max(-90.0, min(latitudes) - margin),
        east=min(180.0, max(longitudes) + margin),
        north=min(90.0, max(latitudes) + margin),
    )


def windows_for(source: CRCOpen, years: Sequence[int], runtime: Runtime) -> dict:
    """Map each requested year to the release period window that contains it."""
    periods = {series.period for series in source.inspect(runtime=runtime).series}
    chosen = {}
    for year in years:
        match = [p for p in periods if p.start is not None and p.start <= year <= p.end]
        if not match:
            raise LookupError(f"CRC Open has no period containing {year}")
        chosen[year] = match[0]
    return chosen


def screen(
    assets: pa.Table,
    output: Path,
    *,
    years: Sequence[int] = YEARS,
    return_periods: Sequence[float] = RETURN_PERIODS,
    catalog: str = CRC_OPEN,
    runtime: Runtime | None = None,
) -> dict[str, Any]:
    """Evaluate CRC Open Rx1day at the assets for the windows holding ``years``."""
    output.mkdir(parents=True, exist_ok=True)
    runtime = runtime or Runtime(cache=Cache.reuse(source_cache(output)))
    source = CRCOpen(catalog=catalog).select(area=area_of(assets), variables=RX1DAY)
    windows = windows_for(source, years, runtime)
    labels = {p.id: f"{p.start}-{p.end}" for p in windows.values()}
    evaluation = (
        source.select(periods=list(dict.fromkeys(windows.values())))
        .evaluate(Assets(assets))
        .return_periods(list(return_periods))
        .write(output / "ssp585_portfolio.parquet", overwrite=True, runtime=runtime)
    )
    result = evaluation.read()
    rows = [
        {
            "asset_id": row["asset_id"],
            "period": labels.get(row["period_id"]),
            "return_period_years": row["query_value"],
            "rx1day_mm_day": row["value"],
            "cell": row["support_id"],
            "failure": row["failure"]["code"] if row["failure"] else None,
        }
        for row in result.table.to_pylist()
    ]
    source_identity = evaluation.metadata.source
    release = source_identity.release if source_identity else None
    return {
        "catalog": catalog,
        "release": release.id if release else None,
        "resources": [
            {"uri": item.uri, "sha256": item.sha256, "license": item.license}
            for item in (source_identity.resources[:1] if source_identity else ())
        ],
        "years_to_windows": {str(y): f"{p.start}-{p.end}" for y, p in windows.items()},
        "rows": rows,
        "matched_assets": result.report.counts.matched_assets,
        "unmatched_assets": result.report.counts.unmatched_assets,
        "output": str(evaluation.path),
        "note": NOTE,
    }


def compare_historical(
    assets: pa.Table, baseline: Path, output: Path, return_periods: Sequence[float]
) -> list[dict[str, Any]]:
    """Evaluate a historical daily-rainfall-maximum dataset at the same assets."""
    dataset = Dataset.open(baseline)
    variables = dataset.metadata.spec.variables
    measurement = variables[0].measurement if len(variables) == 1 else None
    duration = getattr(measurement, "accumulation_duration", None)
    if duration != Duration(1, unit=TimeUnit.DAY):
        raise ValueError("comparison requires one daily-precipitation-maximum variable")
    historical = (
        dataset.evaluate(Assets(assets))
        .return_periods(list(return_periods))
        .write(output / "historical_rx1day.parquet", overwrite=True)
    )
    rows = historical.read().table.to_pylist()
    if not any(row["value"] is not None for row in rows):
        failures = sorted({row["failure"]["code"] for row in rows if row["failure"]})
        raise LookupError(f"baseline has no usable Rx1day return values: {failures}")
    return [
        {
            "asset_id": row["asset_id"],
            "return_period_years": row["query_value"],
            "value": row["value"],
            "failure": row["failure"]["code"] if row["failure"] else None,
        }
        for row in rows
    ]


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--catalog", default=CRC_OPEN, help="Release index path or URL")
    parser.add_argument("--assets", type=Path, help="CSV or Parquet asset locations")
    parser.add_argument("--years", type=int, nargs="+", default=list(YEARS))
    parser.add_argument(
        "--return-periods", type=float, nargs="+", default=list(RETURN_PERIODS)
    )
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/crc_open"))
    parser.add_argument(
        "--historical-rx1day",
        type=Path,
        help="Optional historical Rx1day Dataset (e.g. an ERA5 fit) to compare",
    )
    args = parser.parse_args(argv)
    assets = load_assets(args.assets)
    summary = screen(
        assets,
        args.output,
        years=args.years,
        return_periods=args.return_periods,
        catalog=args.catalog,
    )
    if args.historical_rx1day is not None:
        summary["historical"] = compare_historical(
            assets, args.historical_rx1day, args.output, args.return_periods
        )
        summary["historical_note"] = (
            "Different source, period and method; not a pure climate-change signal."
        )
    temporary = args.output / ".summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    os.replace(temporary, args.output / "summary.json")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
