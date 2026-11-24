"""Read one public climate source with crc-sdk 1.0 and save it as canonical Parquet.

Run from the repository root after ``uv sync --locked``:

    uv run python pipelines/source_pipeline.py --source eccc-daily
    uv run python pipelines/source_pipeline.py --source hydat --station 02HA014
    uv run python pipelines/source_pipeline.py --source noaa-sea-level
    uv run python pipelines/source_pipeline.py --source nex --start 2014 --end 2014

Every source is a crc-sdk provider recipe. The pipeline selects a station, an
area and/or a year window, writes the recipe's canonical rows atomically (the
file reopens with ``Observations.open``, ``Projections.open``, ``Samples.open``
or ``Dataset.open``) and records source checksums, licences, attribution,
retrieval times, row counts and diagnostics in ``summary.json``.

``--cache-mode offline`` replays the verified bytes cached by an earlier run
without network access. Outputs are source evidence, not asset hazard estimates.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crc_sdk import (
    CHIRPS,
    HYDAT,
    NEX,
    USGS,
    Bounds,
    Cache,
    ECCCDaily,
    IBTrACS,
    NOAASeaLevel,
    NOAAWaterLevels,
    Period,
    Runtime,
)

CACHES = {"reuse": Cache.reuse, "offline": Cache.offline, "refresh": Cache.refresh}


def source_cache(output: Path) -> Path:
    """Source cache directory: ``CRC_DOCS_CACHE`` when set, else under the output."""
    return Path(os.environ.get("CRC_DOCS_CACHE") or output / "cache")


@dataclass(frozen=True)
class Options:
    """One source's selection; every field has a per-source default."""

    station: str | None = None
    bounds: tuple[float, float, float, float] | None = None
    start: int | None = None
    end: int | None = None
    scenario: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class Source:
    describe: str
    defaults: Options
    build: Callable[[Options, Runtime], dict[str, Any]]
    note: str


def _bounds(values: Sequence[float]) -> Bounds:
    west, south, east, north = values
    return Bounds(west=west, south=south, east=east, north=north)


def _years(options: Options) -> Period:
    assert options.start is not None and options.end is not None
    return Period.window(options.start, options.end)


def _chirps(options: Options, runtime: Runtime) -> dict[str, Any]:
    assert options.bounds is not None
    recipe = CHIRPS().select(area=_bounds(options.bounds), time=_years(options))
    return {"observations": recipe}


def _station_daily(provider: type[ECCCDaily | HYDAT]):
    def build(options: Options, runtime: Runtime) -> dict[str, Any]:
        recipe = provider().select(stations=options.station, time=_years(options))
        return {"observations": recipe}

    return build


def _usgs(options: Options, runtime: Runtime) -> dict[str, Any]:
    # A station ID or a box; with no station, every discharge gauge in the box.
    selection: dict[str, Any] = {"time": _years(options)}
    if options.station is not None:
        selection["stations"] = options.station
    else:
        assert options.bounds is not None
        selection["area"] = _bounds(options.bounds)
    return {"observations": USGS().select(**selection)}


def _ibtracs(options: Options, runtime: Runtime) -> dict[str, Any]:
    assert options.bounds is not None
    recipe = IBTrACS(agency=IBTrACS.Agency.USA).select(
        area=_bounds(options.bounds), time=_years(options)
    )
    return {"observations": recipe}


def _water_levels(options: Options, runtime: Runtime) -> dict[str, Any]:
    source = NOAAWaterLevels().select(stations=options.station)
    return {
        "observations": source,
        "levels": source.levels(),
        "confidence_intervals": source.confidence_intervals(),
    }


def _sea_level(options: Options, runtime: Runtime) -> dict[str, Any]:
    recipe = NOAASeaLevel().select(stations=options.station)
    if options.scenario is not None:
        recipe = recipe.select(scenarios=options.scenario)
    return {"projections": recipe}


def _nex(options: Options, runtime: Runtime) -> dict[str, Any]:
    assert options.bounds is not None
    source = NEX(
        indicator=NEX.Indicator.ANNUAL_MAXIMUM_DAILY_PRECIPITATION,
        model=options.model,
        scenario=options.scenario,
    )
    # NEX needs one published model/scenario/member combination.
    series = source.inspect(runtime=runtime).series
    if not series:
        raise LookupError(f"NEX publishes no {options.model} {options.scenario} series")
    recipe = source.select(
        series=series[0], area=_bounds(options.bounds), time=_years(options)
    )
    return {"samples": recipe}


SOURCES: dict[str, Source] = {
    "chirps": Source(
        "CHIRPS v3 final monthly precipitation pixels",
        Options(bounds=(36.75, -1.35, 36.85, -1.25), start=2020, end=2020),
        _chirps,
        "Monthly precipitation totals on CHIRPS pixels; reads only the window.",
    ),
    "eccc-daily": Source(
        "ECCC GeoMet daily climate observations",
        Options(station="6158731", start=2020, end=2020),
        _station_daily(ECCCDaily),
        "Station observations as published; missing values keep their row.",
    ),
    "hydat": Source(
        "HYDAT daily mean discharge and water level via GeoMet",
        Options(station="02HA014", start=2020, end=2020),
        _station_daily(HYDAT),
        "Gauge observations, not flood depths.",
    ),
    "usgs": Source(
        "USGS daily mean streamflow",
        Options(bounds=(-75.79, 38.99, -75.78, 39.0), start=2020, end=2021),
        _usgs,
        "Discharge keeps its source unit (ft^3/s); USGS revises recent values.",
    ),
    "ibtracs": Source(
        "NOAA IBTrACS storm track points (USA agency)",
        Options(bounds=(-98.0, 18.0, -78.0, 31.0), start=2024, end=2024),
        _ibtracs,
        "Storm positions and intensities; not an asset wind hazard.",
    ),
    "noaa-water-levels": Source(
        "NOAA CO-OPS extreme water levels",
        Options(station="8638610"),
        _water_levels,
        "Station datum and epoch apply; not asset flood depths or projections.",
    ),
    "noaa-sea-level": Source(
        "NOAA 2022 relative sea-level scenarios",
        Options(station="8638610"),
        _sea_level,
        "Relative sea-level change at the station, not water depths at assets.",
    ),
    "nex": Source(
        "NASA NEX-GDDP-CMIP6 annual maximum daily precipitation",
        Options(
            bounds=(-79.5, 43.5, -79.25, 43.75),
            start=2014,
            end=2014,
            scenario="historical",
            model="ACCESS-CM2",
        ),
        _nex,
        "One downscaled model run; one model is not a climate projection range.",
    ),
}


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    os.replace(temporary, path)


def provenance(metadata: Any) -> dict[str, Any]:
    """Source identity, row counts and diagnostics of a written artifact."""
    source = metadata.source
    report = metadata.report
    return {
        "provider": source.provider if source else None,
        "product": source.product if source else None,
        "release": (
            {"id": source.release.id, "sha256": source.release.sha256}
            if source and source.release
            else None
        ),
        "resources": [
            {
                "uri": item.uri,
                "sha256": item.sha256,
                "license": item.license,
                "attribution": item.attribution,
                "retrieved_at": item.retrieved_at,
            }
            for item in (source.resources if source else ())
        ],
        "counts": {
            name: getattr(report.counts, name)
            for name in ("requested", "produced", "no_data", "skipped")
        },
        "diagnostics": [
            {"code": item.code, "message": item.message} for item in report.diagnostics
        ],
    }


def run(
    source: str,
    output: Path,
    *,
    options: Options | None = None,
    cache_mode: str = "reuse",
    cache: Path | None = None,
) -> dict[str, Any]:
    """Read one source into ``output`` and return the summary written beside it."""
    spec = SOURCES[source]
    chosen = {
        name: value
        for name, value in vars(options or Options()).items()
        if value is not None
    }
    selected = Options(**{**vars(spec.defaults), **chosen})
    output.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(cache=CACHES[cache_mode](cache or source_cache(output)))
    outputs: dict[str, str] = {}
    artifacts: dict[str, Any] = {}
    for name, recipe in spec.build(selected, runtime).items():
        path = output / f"{name}.parquet"
        saved = recipe.write(path, overwrite=True, runtime=runtime)
        outputs[name] = str(path)
        artifacts[name] = provenance(saved.metadata)
    summary: dict[str, Any] = {
        "source": source,
        "description": spec.describe,
        "selection": vars(selected),
        "outputs": outputs,
        "artifacts": artifacts,
        "interpretation": spec.note,
    }
    if source == "ibtracs":
        import pyarrow.parquet as pq

        storms = pq.read_table(outputs["observations"], columns=["group_id", "time"])
        points = Counter((row["group_id"], row["time"]) for row in storms.to_pylist())
        summary["storms"] = dict(Counter(storm for storm, _ in points).most_common())
    _write_json(output / "summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--station", help="Station or gauge ID for station sources")
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="WGS84 box for area sources",
    )
    parser.add_argument("--start", type=int, help="First calendar year")
    parser.add_argument("--end", type=int, help="Last calendar year, inclusive")
    parser.add_argument("--scenario", help="NOAA sea-level or NEX scenario ID")
    parser.add_argument("--model", help="NEX model ID")
    parser.add_argument("--cache-mode", choices=sorted(CACHES), default="reuse")
    parser.add_argument("--cache", type=Path, help="Shared source cache directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    summary = run(
        args.source,
        args.output or Path("pipeline_output") / args.source,
        options=Options(
            station=args.station,
            bounds=tuple(args.bounds) if args.bounds else None,
            start=args.start,
            end=args.end if args.end is not None else args.start,
            scenario=args.scenario,
            model=args.model,
        ),
        cache_mode=args.cache_mode,
        cache=args.cache,
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
