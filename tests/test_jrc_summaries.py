"""JRC flood, EDO drought and flood-by-province summaries from public-API inputs."""

from pathlib import Path

import h3
import pyarrow.parquet as pq
import pytest
from crc_framework import DepthAboveGround, LengthUnit, Measurement, Tail
from crc_sdk import Dataset, Observations, Probability, Variable

from pipelines import flood_admin_pipeline, jrc_drought_pipeline, jrc_flood_pipeline

DEPTH = Variable("jrc:flood_depth", measurement=DepthAboveGround(unit=LengthUnit.METRE))


def flood(points: dict[str, tuple[float, float]]) -> Dataset:
    """Depth knots at 10-, 50- and 100-year return periods for point supports."""
    ids = list(points)
    return Dataset.from_quantiles(
        {
            "support_id": [i for i in ids for _ in range(3)],
            "longitude": [points[i][0] for i in ids for _ in range(3)],
            "latitude": [points[i][1] for i in ids for _ in range(3)],
            "probability": [0.9, 0.98, 0.99] * len(ids),
            "value": [v * (n + 1) for n in range(len(ids)) for v in (0.2, 0.6, 1.0)],
        },
        variable=DEPTH,
        probability=Probability.annual(tail=Tail.UPPER),
    )


def test_flood_depths_report_values_and_unsupported_periods(tmp_path: Path):
    dataset = flood({"a": (6.0, 50.0), "b": (6.1, 50.0)})
    summary = jrc_flood_pipeline.depths_by_support(dataset, [10, 100, 500], tmp_path)
    assert summary["pixels"] == 2
    periods = summary["return_periods"]
    assert periods["rp10"]["pixels_with_depth"] == 2
    assert periods["rp100"]["maximum_depth"] == pytest.approx(2.0)
    assert periods["rp500"] == {
        "pixels_with_depth": 0,
        "maximum_depth": None,
        "failures": {"query_outside_support": 2},
    }
    assert pq.read_table(summary["outputs"]["depths"]).num_rows == 6


def test_empty_flood_area_is_an_error(tmp_path: Path):
    dataset = flood({"a": (6.0, 50.0)}).select(variables=[])
    with pytest.raises(LookupError, match="no JRC flood pixels"):
        jrc_flood_pipeline.depths_by_support(dataset, [10], tmp_path)


def dekads(year: int) -> list[str]:
    return [f"{year}-{m:02d}-{d:02d}" for m in range(1, 13) for d in (1, 11, 21)]


def test_drought_fits_complete_annual_minima_only(tmp_path: Path):
    rows: dict[str, list] = {
        k: [] for k in ("support_id", "longitude", "latitude", "time", "value")
    }
    for pixel, (lon, lat) in {"p1": (8.0, 50.0), "p2": (8.1, 50.0)}.items():
        for year in range(2010, 2022):
            times = dekads(year)
            if pixel == "p2" and year == 2021:
                times = times[:30]  # an incomplete year is left out
            for index, time in enumerate(times):
                rows["support_id"].append(pixel)
                rows["longitude"].append(lon)
                rows["latitude"].append(lat)
                rows["time"].append(time)
                rows["value"].append(0.5 + 0.01 * index - 0.02 * (year % 5))
    observations = Observations.from_table(
        rows,
        variable=Variable(
            "edo:soil_moisture_index",
            measurement=Measurement(quantity="soil_moisture_index", unit="1"),
        ),
    )
    summary = jrc_drought_pipeline.drought_return_levels(
        observations, [2, 10], tmp_path
    )
    assert summary["annual_minima"] == {
        "complete_pixel_years": 23,
        "incomplete_pixel_years": 1,
    }
    levels = summary["return_periods"]
    assert levels["rp2"]["pixels_with_value"] == 2
    assert levels["rp10"]["driest_smi"] < levels["rp2"]["driest_smi"] < 0.5


def test_flood_by_province_keeps_the_deepest_pixel_per_cell(tmp_path: Path):
    dataset = flood({"a": (6.95, 50.94), "b": (6.951, 50.94), "c": (20.0, 10.0)})
    cells, failures = flood_admin_pipeline.depth_by_cell(dataset, 100, 7)
    cell = h3.latlng_to_cell(50.94, 6.95, 7)
    assert cells[cell] == pytest.approx(2.0)
    assert failures == {}
    square = [[6.0, 50.0], [8.0, 50.0], [8.0, 52.0], [6.0, 52.0], [6.0, 50.0]]
    admin = {
        "features": [
            {
                "geometry": {"type": "Polygon", "coordinates": [square]},
                "properties": {"shapeName": "Nordrhein-Westfalen"},
            }
        ]
    }
    assert flood_admin_pipeline.provinces_of(list(cells), admin, "shapeName") == {
        cell: "Nordrhein-Westfalen"
    }


def test_pmtiles_are_skipped_without_tippecanoe(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(flood_admin_pipeline.shutil, "which", lambda name: None)
    layer = flood_admin_pipeline.write_geojsonseq(tmp_path / "layer.geojsonseq", [])
    assert (
        flood_admin_pipeline.build_pmtiles({"x": layer}, tmp_path / "x.pmtiles") is None
    )
