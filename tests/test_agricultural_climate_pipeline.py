"""Agricultural units are evaluated at their centres and mapped with coverage."""

import json
from pathlib import Path

import h3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import shapely
from crc_framework import DepthAboveGround, LengthUnit, Tail
from crc_sdk import Dataset, Probability, Variable

from pipelines import agricultural_climate_pipeline as pipeline


def hazard(points: dict[str, tuple[float, float]]) -> Dataset:
    ids = list(points)
    return Dataset.from_quantiles(
        {
            "support_id": [i for i in ids for _ in range(2)],
            "longitude": [points[i][0] for i in ids for _ in range(2)],
            "latitude": [points[i][1] for i in ids for _ in range(2)],
            "probability": [0.9, 0.99] * len(ids),
            "value": [0.5, 2.0] * len(ids),
        },
        variable=Variable(
            "jrc:flood_depth", measurement=DepthAboveGround(unit=LengthUnit.METRE)
        ),
        probability=Probability.annual(tail=Tail.UPPER),
    )


def usda_units() -> pa.Table:
    covered, outside = (
        h3.latlng_to_cell(42.0, -93.6, 7),
        h3.latlng_to_cell(42.2, -93.4, 7),
    )
    rows = []
    for cell, code, count in ((covered, 1, 30), (covered, 5, 10), (outside, 1, 5)):
        lat, lon = h3.cell_to_latlng(cell)
        rows.append(
            {
                "asset_id": f"2024:{code}:{cell}",
                "cell": cell,
                "year": 2024,
                "crop_code": code,
                "crop_name": {1: "Corn", 5: "Soybeans"}[code],
                "pixel_count": count,
                "sampled_crop_share": count / 40 if cell == covered else 1.0,
                "longitude": lon,
                "latitude": lat,
            }
        )
    return pa.Table.from_pylist(rows)


def test_usda_units_are_weighted_by_pixels(tmp_path: Path):
    units = usda_units()
    lat, lon = h3.cell_to_latlng(units["cell"][0].as_py())
    evaluation = pipeline.evaluate_units(
        units, hazard({"gauge": (lon, lat)}), [10, 100], tmp_path / "evaluation.parquet"
    )
    map_path, summary_path = pipeline.map_and_summary(
        "usda", units, evaluation, tmp_path
    )
    features = [json.loads(line) for line in map_path.read_text().splitlines()]
    assert len(features) == 3
    assert {f["properties"]["hazard_coverage"] for f in features} == {
        "modeled_hazard",
        "outside_hazard",
    }
    corn = next(
        f for f in features if f["properties"]["asset_id"].startswith("2024:1:")
    )
    assert corn["geometry"]["type"] == "Polygon"
    summary = pq.read_table(summary_path).to_pylist()
    modeled = [r for r in summary if r["hazard_coverage"] == "modeled_hazard"]
    assert {r["crop_name"]: r["pixel_count"] for r in modeled} == {
        "Corn": 30,
        "Soybeans": 10,
    }
    assert modeled[0]["pixel_count_weighted_rp100"] == pytest.approx(2.0)
    outside = [r for r in summary if r["hazard_coverage"] == "outside_hazard"]
    assert outside[0]["pixel_count_weighted_rp100"] is None


def test_ftw_fields_keep_polygons_and_area_weights(tmp_path: Path):
    fields = [
        shapely.box(2.40, 48.00, 2.41, 48.01),
        shapely.box(2.42, 48.00, 2.43, 48.01),
    ]
    units = pa.Table.from_pylist(
        [
            {
                "asset_id": f"field-{n}",
                "geometry": shapely.to_wkb(shape),
                "area_m2": 1000.0 * (n + 1),
                "perimeter_m": 400.0,
                "confidence": 90.0,
                "longitude": shape.centroid.x,
                "latitude": shape.centroid.y,
            }
            for n, shape in enumerate(fields)
        ]
    )
    centre = fields[0].centroid
    evaluation = pipeline.evaluate_units(
        units, hazard({"pixel": (centre.x, centre.y)}), [10], tmp_path / "e.parquet"
    )
    map_path, summary_path = pipeline.map_and_summary(
        "ftw", units, evaluation, tmp_path
    )
    first = json.loads(map_path.read_text().splitlines()[0])
    assert first["geometry"]["type"] == "Polygon"
    assert first["properties"]["rp10"] == pytest.approx(0.5)
    summary = {r["hazard_coverage"]: r for r in pq.read_table(summary_path).to_pylist()}
    assert summary["modeled_hazard"]["area_m2"] == 1000.0
    assert summary["outside_hazard"]["area_m2"] == 2000.0


def test_pmtiles_step_is_optional(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pipeline.shutil, "which", lambda name: None)
    layer = tmp_path / "map.geojsonseq"
    layer.write_text("")
    assert pipeline.build_pmtiles(layer, tmp_path / "map.pmtiles") is None


def test_usda_cells_keep_their_deepest_pixel(tmp_path: Path):
    units = usda_units()
    cell = units["cell"][0].as_py()
    lat, lon = h3.cell_to_latlng(cell)
    pixels = hazard({"a": (lon, lat), "b": (lon + 0.002, lat)})
    rows = pipeline.evaluate_units(
        units, pixels, [100], tmp_path / "cells.parquet", cell_resolution=7
    ).to_pylist()
    covered = [r for r in rows if r["asset_id"].endswith(cell)]
    assert {r["value"] for r in covered} == {2.0}
    assert {r["support_id"] for r in covered} == {f"h3:{cell}"}
    outside = [r for r in rows if not r["asset_id"].endswith(cell)]
    assert {r["failure"] for r in outside} == {"no_covering_support"}
