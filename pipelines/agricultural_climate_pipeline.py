"""Build bounded agricultural H3 units and optionally evaluate a CRC hazard.

Examples:

    uv run python pipelines/agricultural_climate_pipeline.py \
      --source usda --bounds -93.7 41.9 -93.2 42.3 --year 2025 \
      --crop-codes 1 5 --hazard pipeline_output/iowa-glofas.parquet

    uv run python pipelines/agricultural_climate_pipeline.py \
      --source ftw --country-code FR --bounds 2.0 47.5 3.0 48.5 \
      --year 2024 --minimum-confidence 80 \
      --hazard pipeline_output/france-edo-smi.parquet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from crc_sdk.connectors.duckdb import DuckDBConnection, sql_quote
from crc_sdk.geometry.pmtiles import AREAS, PMTilesBuild
from crc_sdk.workflows import (
    AgriculturalLayer,
    AssetPortfolio,
    CellColumn,
    HazardDataset,
    JRCFloodPolicy,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("usda", "ftw"))
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--country-code", help="Required for FTW")
    parser.add_argument("--crop-codes", type=int, nargs="+", default=[1, 5])
    parser.add_argument("--minimum-confidence", type=float, default=80.0)
    parser.add_argument("--h3-resolution", type=int)
    parser.add_argument(
        "--hazard",
        type=Path,
        help="Existing canonical CRC hazard Parquet; otherwise materialize GloFAS",
    )
    parser.add_argument(
        "--cache-mode", choices=("reuse", "offline", "refresh"), default="reuse"
    )
    parser.add_argument(
        "--return-periods", type=float, nargs="+", default=[10, 25, 100]
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("pipeline_output/agriculture")
    )
    parser.add_argument(
        "--skip-pmtiles",
        action="store_true",
        help="Skip the final map archive (requires tippecanoe on PATH)",
    )
    parser.add_argument(
        "--pmtiles-output",
        type=Path,
        help="Optional PMTiles destination; defaults inside --output-dir",
    )
    parser.add_argument(
        "--pmtiles-threads",
        type=int,
        help="Optional tippecanoe thread limit (useful inside notebook kernels)",
    )
    parser.add_argument(
        "--pmtiles-from-map",
        type=Path,
        help="Tile an existing map GeoParquet and exit (notebook-safe helper)",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolution(args: argparse.Namespace) -> int:
    if args.hazard:
        hazard_resolution = HazardDataset.local(args.hazard).metadata().h3_resolution
        if args.h3_resolution is not None and args.h3_resolution != hazard_resolution:
            raise ValueError(
                "--h3-resolution must match the canonical hazard metadata "
                f"({hazard_resolution})"
            )
        return hazard_resolution
    return args.h3_resolution if args.h3_resolution is not None else 7


def ensure_hazard(args: argparse.Namespace) -> Path:
    """Use a supplied canonical hazard or materialize bounded GloFAS flood."""
    if args.hazard is not None:
        return args.hazard
    resolution = args.h3_resolution if args.h3_resolution is not None else 7
    hazard_path = args.output_dir / "glofas-flood-curves.parquet"
    hazard = (
        HazardDataset.glofas(version="latest")
        .for_area(tuple(args.bounds))
        .cache(args.output_dir / "glofas-source-cache", mode=args.cache_mode)
        .source_periods("all")
        .canonicalize(policy=JRCFloodPolicy.curated(h3_resolution=resolution))
        .materialize(hazard_path)
    )
    args.hazard = Path(hazard.provider.source)
    return args.hazard


def build_agricultural_units(
    args: argparse.Namespace, connection: DuckDBConnection, resolution: int
) -> Path:
    bounds = tuple(args.bounds)
    output = args.output_dir / f"{args.source}-agricultural-units.parquet"
    if args.source == "usda":
        scan = (
            AgriculturalLayer.usda_cdl()
            .resolution("30m")
            .for_area(bounds)
            .years(args.year)
            .classes(args.crop_codes)
            .scan()
        )
        pipeline = (
            scan.pipeline(connection=connection)
            .select(
                "*, CAST(h3_latlng_to_cell(latitude, longitude, "
                f"{resolution}) AS UBIGINT) AS cell_index"
            )
            .aggregate(
                "count(*) AS pixel_count, avg(longitude) AS longitude, "
                "avg(latitude) AS latitude, any_value(source_path) AS source_path",
                groups="cell_index, year, crop_code, crop_name",
            )
            .select("concat(year, ':', crop_code, ':', cell_index) AS asset_id, *")
        )
    else:
        if not args.country_code:
            raise ValueError("--country-code is required for --source ftw")
        scan = (
            AgriculturalLayer.ftw_fields()
            .in_country(args.country_code)
            .for_area(bounds)
            .years(args.year)
            .confidence_at_least(args.minimum_confidence)
            .scan()
        )
        pipeline = scan.pipeline(connection=connection).select(
            "id AS asset_id, year, confidence, area_m2, perimeter_m, "
            "geometry, "
            "ST_X(ST_Centroid(geometry)) AS longitude, "
            "ST_Y(ST_Centroid(geometry)) AS latitude, "
            "CAST(h3_latlng_to_cell(ST_Y(ST_Centroid(geometry)), "
            f"ST_X(ST_Centroid(geometry)), {resolution}) AS UBIGINT) AS cell_index, "
            "country_code, source_path"
        )
    if args.source != "usda":
        return pipeline.write_parquet(output, overwrite=True)

    # DuckDB 1.5.x does not currently execute window expressions correctly
    # over a Python Arrow batch reader. Keep the remote scan one-pass and
    # bounded, then compute crop shares from the small local aggregate.
    staged = output.with_name(f".{output.stem}-counts.parquet")
    pipeline.write_parquet(staged, overwrite=True)
    try:
        with closing(connection.connect()) as con:
            con.execute(
                f"""
                COPY (
                    SELECT *, pixel_count::DOUBLE / sum(pixel_count) OVER
                        (PARTITION BY cell_index, year) AS sampled_crop_share
                    FROM read_parquet({sql_quote(str(staged))})
                ) TO {sql_quote(str(output))}
                  (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE true)
                """
            )
    finally:
        staged.unlink(missing_ok=True)
    return output


def filter_hazard_covered_units(
    args: argparse.Namespace,
    agricultural_path: Path,
    connection: DuckDBConnection,
) -> tuple[Path, int, int]:
    """Retain evaluation candidates while preserving overall coverage counts."""
    assert args.hazard is not None
    matched = args.output_dir / f"{args.source}-hazard-covered-units.parquet"
    with closing(connection.connect()) as con:
        total = con.execute(
            f"SELECT count(*) FROM read_parquet({sql_quote(str(agricultural_path))})"
        ).fetchone()[0]
        con.execute(
            f"""
            COPY (
                SELECT a.*
                FROM read_parquet({sql_quote(str(agricultural_path))}) a
                SEMI JOIN (
                    SELECT DISTINCT cell_index
                    FROM read_parquet({sql_quote(str(args.hazard))})
                ) h USING (cell_index)
            ) TO {sql_quote(str(matched))}
              (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE true)
            """
        )
        matched_rows = con.execute(
            f"SELECT count(*) FROM read_parquet({sql_quote(str(matched))})"
        ).fetchone()[0]
    return matched, int(matched_rows), int(total - matched_rows)


def evaluate_hazard(args: argparse.Namespace, agricultural_path: Path) -> Path | None:
    if args.hazard is None:
        return None
    columns = pq.read_schema(agricultural_path).names
    passthrough = tuple(
        name
        for name in columns
        if name not in ("asset_id", "cell_index", "geometry")
    )
    assets = AssetPortfolio(
        agricultural_path,
        id_column="asset_id",
        location=CellColumn(),
        passthrough_columns=passthrough,
    )
    output = args.output_dir / f"{args.source}-hazard-evaluation.parquet"
    HazardDataset.local(args.hazard).for_assets(assets).return_periods(
        args.return_periods
    ).write_parquet(output)
    return output


def build_map_artifacts(
    args: argparse.Namespace,
    agricultural_path: Path,
    evaluation_path: Path,
    connection: DuckDBConnection,
) -> tuple[Path, Path, Path | None]:
    """Create a source-aware agricultural/hazard map, summary, and archive."""
    map_path = args.output_dir / f"{args.source}-crop-flood-map.parquet"
    summary_path = args.output_dir / f"{args.source}-crop-flood-summary.parquet"
    value_columns = [
        name
        for name in pq.read_schema(evaluation_path).names
        if name.startswith("value_")
    ]
    value_projection = ", ".join(f"e.{name}" for name in value_columns)
    if value_projection:
        value_projection = ", " + value_projection
    weight_column = "pixel_count" if args.source == "usda" else "area_m2"
    weight_prefix = "pixel" if args.source == "usda" else "area"
    weighted_values = ", ".join(
        f"sum({weight_column} * {name}) "
        f"FILTER (WHERE {name} IS NOT NULL AND {weight_column} IS NOT NULL) / "
        f"nullif(sum({weight_column}) "
        f"FILTER (WHERE {name} IS NOT NULL AND {weight_column} IS NOT NULL), 0) "
        f"AS {weight_prefix}_weighted_{name}"
        for name in value_columns
    )
    if weighted_values:
        weighted_values = ", " + weighted_values

    if args.source == "usda":
        agricultural_projection = "a.*"
        geometry_projection = (
            "h3_cell_to_boundary_wkb(CAST(a.cell_index AS UBIGINT)) AS geometry"
        )
        summary_projection = f"""
            SELECT crop_code, crop_name, hazard_coverage,
                   count(*) AS h3_crop_units,
                   sum(pixel_count) AS sampled_pixels,
                   sum(pixel_count * sampled_crop_share) /
                       nullif(sum(pixel_count), 0) AS pixel_weighted_crop_share
                   {weighted_values}
            FROM read_parquet({sql_quote(str(map_path))})
            GROUP BY crop_code, crop_name, hazard_coverage
            ORDER BY crop_code, hazard_coverage
        """
        properties = (
            "asset_id",
            "year",
            "crop_code",
            "crop_name",
            "pixel_count",
            "sampled_crop_share",
            "hazard_coverage",
            "spatial_match",
            *value_columns,
        )
    else:
        agricultural_projection = "a.* EXCLUDE (geometry)"
        geometry_projection = "a.geometry AS geometry"
        summary_projection = f"""
            SELECT country_code, year, hazard_coverage,
                   count(*) AS field_units,
                   sum(area_m2) AS observed_field_area_m2,
                   avg(confidence) AS average_confidence,
                   sum(area_m2 * confidence) /
                       nullif(sum(area_m2), 0) AS area_weighted_confidence
                   {weighted_values}
            FROM read_parquet({sql_quote(str(map_path))})
            GROUP BY country_code, year, hazard_coverage
            ORDER BY country_code, year, hazard_coverage
        """
        properties = (
            "asset_id",
            "year",
            "confidence",
            "area_m2",
            "perimeter_m",
            "country_code",
            "hazard_coverage",
            "spatial_match",
            *value_columns,
        )

    with closing(connection.connect()) as con:
        con.execute(
            f"""
            COPY (
                SELECT {agricultural_projection},
                       CASE WHEN e.asset_id IS NULL
                            THEN 'outside_modeled_hazard'
                            ELSE 'modeled_hazard' END AS hazard_coverage,
                       e.spatial_match{value_projection},
                       {geometry_projection}
                FROM read_parquet({sql_quote(str(agricultural_path))}) a
                LEFT JOIN read_parquet({sql_quote(str(evaluation_path))}) e
                  USING (asset_id)
            ) TO {sql_quote(str(map_path))}
              (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE true)
            """
        )
        con.execute(
            f"""
            COPY (
                {summary_projection}
            ) TO {sql_quote(str(summary_path))}
              (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE true)
            """
        )
        pmtiles_path: Path | None = None
        if not args.skip_pmtiles:
            pmtiles_path = args.pmtiles_output or (
                args.output_dir / f"{args.source}-crop-flood.pmtiles"
            )
            write_pmtiles_archive(
                map_path,
                pmtiles_path,
                args.output_dir / "pmtiles-work",
                connection=con,
                properties=properties,
                threads=args.pmtiles_threads,
            )
    return map_path, summary_path, pmtiles_path


def write_pmtiles_archive(
    map_path: Path,
    output: Path,
    work_dir: Path,
    *,
    connection: Any | None = None,
    properties: tuple[str, ...] | None = None,
    threads: int | None = None,
) -> Path:
    """Write the local agricultural/hazard GeoParquet as a vector-tile layer."""
    (
        PMTilesBuild(
            con=connection,
            work_dir=work_dir,
            tippecanoe_threads=threads,
        )
        .layer(
            map_path,
            name="crop_flood",
            zooms=(5, 13),
            preset=AREAS,
            property_columns=properties,
        )
        .write(output)
    )
    return output


def write_manifest(
    args: argparse.Namespace,
    resolution: int,
    agricultural_path: Path,
    evaluation_path: Path | None,
    matched_rows: int | None,
    missing_rows: int | None,
    map_path: Path,
    summary_path: Path,
    pmtiles_path: Path | None,
) -> Path:
    manifest: dict[str, Any] = {
        "agricultural_source": args.source,
        "bounds_wgs84": args.bounds,
        "year": args.year,
        "h3_resolution": resolution,
        "agricultural_output": str(agricultural_path),
        "agricultural_sha256": _sha256(agricultural_path),
        "agricultural_rows": pq.read_metadata(agricultural_path).num_rows,
        "hazard_input": str(args.hazard) if args.hazard else None,
        "hazard_evaluation": str(evaluation_path) if evaluation_path else None,
        "hazard_evaluation_sha256": (
            _sha256(evaluation_path) if evaluation_path else None
        ),
        "hazard_matched_agricultural_rows": matched_rows,
        "hazard_unmatched_agricultural_rows": missing_rows,
        "map_output": str(map_path),
        "map_output_sha256": _sha256(map_path),
        "summary_output": str(summary_path),
        "summary_output_sha256": _sha256(summary_path),
        "pmtiles_output": str(pmtiles_path) if pmtiles_path else None,
        "pmtiles_sha256": _sha256(pmtiles_path) if pmtiles_path else None,
        "warnings": [
            (
                "Agricultural observations and hazard curves are separate evidence "
                "layers; no combined risk score was inferred."
            ),
            (
                "FTW polygons are remote-sensing field units, not legal parcels or "
                "proof of ownership."
            ),
            ("USDA CDL pixel_count is a bounded pixel sample, not acreage or yield."),
        ],
    }
    if args.hazard:
        manifest["hazard_metadata"] = (
            HazardDataset.local(args.hazard).metadata().model_dump(mode="json")
        )
    path = args.output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


def main() -> None:
    args = parse_args()
    if args.pmtiles_from_map is not None:
        output = args.pmtiles_output or args.pmtiles_from_map.with_suffix(".pmtiles")
        write_pmtiles_archive(
            args.pmtiles_from_map,
            output,
            args.output_dir / "pmtiles-work",
            threads=args.pmtiles_threads,
        )
        print(f"pmtiles: {output}")
        return
    if args.source is None or args.bounds is None:
        raise SystemExit("--source and --bounds are required for an agricultural run")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_pmtiles:
        # Keep tippecanoe out of the process that opens the native Icechunk
        # repository. The clean parent orchestrates a bounded data-only child,
        # then tiles its small local GeoParquet after that child exits.
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                *sys.argv[1:],
                "--skip-pmtiles",
            ],
            check=True,
        )
        map_path = args.output_dir / f"{args.source}-crop-flood-map.parquet"
        pmtiles_path = args.pmtiles_output or (
            args.output_dir / f"{args.source}-crop-flood.pmtiles"
        )
        write_pmtiles_archive(
            map_path,
            pmtiles_path,
            args.output_dir / "pmtiles-work",
            threads=args.pmtiles_threads,
        )
        manifest_path = args.output_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["pmtiles_output"] = str(pmtiles_path)
        manifest["pmtiles_sha256"] = _sha256(pmtiles_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(f"pmtiles: {pmtiles_path}")
        return
    ensure_hazard(args)
    resolution = _resolution(args)
    connection = DuckDBConnection.for_analytics(
        args.output_dir / "duckdb-spill",
        extensions=("spatial", "httpfs", "h3"),
        config={"threads": 1} if args.source == "usda" else None,
    )
    agricultural_path = build_agricultural_units(args, connection, resolution)
    evaluation_input = agricultural_path
    matched_rows = missing_rows = None
    if args.hazard:
        evaluation_input, matched_rows, missing_rows = filter_hazard_covered_units(
            args, agricultural_path, connection
        )
    evaluation_path = evaluate_hazard(args, evaluation_input)
    assert evaluation_path is not None
    map_path, summary_path, _ = build_map_artifacts(
        args, agricultural_path, evaluation_path, connection
    )
    pmtiles_path = None
    manifest_path = write_manifest(
        args,
        resolution,
        agricultural_path,
        evaluation_path,
        matched_rows,
        missing_rows,
        map_path,
        summary_path,
        pmtiles_path,
    )
    print(f"agricultural units: {agricultural_path}")
    print(f"hazard evaluation: {evaluation_path or 'not requested'}")
    print(f"map data: {map_path}")
    print(f"summary: {summary_path}")
    print(f"pmtiles: {pmtiles_path or 'skipped'}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
