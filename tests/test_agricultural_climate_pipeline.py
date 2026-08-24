from argparse import Namespace
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from crc_sdk.connectors.duckdb import DuckDBConnection

from pipelines.agricultural_climate_pipeline import (
    build_map_artifacts,
    write_manifest,
)


def test_ftw_publication_uses_field_schema_and_writes_manifest(tmp_path: Path) -> None:
    agricultural_path = tmp_path / "ftw-agricultural-units.parquet"
    evaluation_path = tmp_path / "ftw-hazard-evaluation.parquet"
    connection = DuckDBConnection.for_analytics(
        tmp_path / "duckdb-spill",
        extensions=("spatial",),
    )
    with connection.connect() as con:
        con.execute(
            f"""
            COPY (
                SELECT *
                FROM (VALUES
                    ('field-1', 2024, 80.0, 100.0, 40.0,
                     ST_GeomFromText('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))'),
                     0.5, 0.5, 1::UBIGINT, 'FR', 's3://example/field-1'),
                    ('field-2', 2024, 100.0, 300.0, 80.0,
                     ST_GeomFromText('POLYGON((1 0, 1 1, 2 1, 2 0, 1 0))'),
                     1.5, 0.5, 2::UBIGINT, 'FR', 's3://example/field-2')
                ) AS fields(
                    asset_id, year, confidence, area_m2, perimeter_m, geometry,
                    longitude, latitude, cell_index, country_code, source_path
                )
            ) TO '{agricultural_path}' (FORMAT PARQUET)
            """
        )
    pq.write_table(
        pa.table(
            {
                "asset_id": ["field-1"],
                "spatial_match": ["exact"],
                "value_rp10": [2.0],
            }
        ),
        evaluation_path,
    )
    args = Namespace(
        source="ftw",
        output_dir=tmp_path,
        skip_pmtiles=True,
        pmtiles_output=None,
        pmtiles_threads=None,
        bounds=[0.0, 0.0, 2.0, 1.0],
        year=2024,
        hazard=None,
    )

    map_path, summary_path, pmtiles_path = build_map_artifacts(
        args, agricultural_path, evaluation_path, connection
    )
    manifest_path = write_manifest(
        args,
        7,
        agricultural_path,
        evaluation_path,
        1,
        1,
        map_path,
        summary_path,
        pmtiles_path,
    )

    mapped = pq.read_table(map_path)
    summary = pq.read_table(summary_path)
    assert "geometry" in mapped.column_names
    assert "crop_code" not in mapped.column_names
    assert set(summary.column_names) >= {
        "field_units",
        "observed_field_area_m2",
        "average_confidence",
        "area_weighted_confidence",
        "area_weighted_value_rp10",
    }
    assert summary["field_units"].to_pylist() == [1, 1]
    by_coverage = {
        row["hazard_coverage"]: row for row in summary.to_pylist()
    }
    assert float(by_coverage["modeled_hazard"]["observed_field_area_m2"]) == 100.0
    assert (
        float(by_coverage["outside_modeled_hazard"]["observed_field_area_m2"])
        == 300.0
    )
    assert by_coverage["modeled_hazard"]["area_weighted_value_rp10"] == 2.0
    assert by_coverage["outside_modeled_hazard"]["area_weighted_value_rp10"] is None
    assert manifest_path.is_file()
