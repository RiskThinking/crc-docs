"""Station recipes keep independent identities and fits while reusing daily data."""

import calendar
import json
from datetime import date, timedelta
from urllib.parse import unquote

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from crc_sdk.connectors.parquet import read_hazard_metadata
from crc_sdk.workflows import HazardDataset, distribution_from_hazard_row

from pipelines import noaa_isd_pipeline


@pytest.mark.parametrize("source", ["isd", "ghcnh"])
@pytest.mark.parametrize("selection", ["stations", "area"])
def test_heat_and_cold_recipes_reuse_offline_cache(
    tmp_path, monkeypatch, source, selection
):
    if source == "isd":
        station, latitude, longitude = "71624099999", 43.677, -79.631
    else:
        station, latitude, longitude = "USW00094846", 41.9603, -87.9317
    bounds = (longitude - 0.01, latitude - 0.01, longitude + 0.01, latitude + 0.01)
    catalogue = pa.Table.from_pylist(
        [
            {
                "station": station,
                "name": "Synthetic station",
                "latitude": latitude,
                "longitude": longitude,
                "elevation": 200.0,
                "start_year": 2000,
                "end_year": 2005,
            }
        ]
    )

    def fetch_catalogue(*args):
        return catalogue, {
            "url": "https://example.test/catalogue.csv",
            "raw_sha256": "catalogue-fingerprint",
        }

    def fetch_daily(station_id, year, *args, **kwargs):
        rows = [
            {
                "station": station_id,
                "day": date(year, 1, 1) + timedelta(days=day),
                "latitude": latitude,
                "latitude_max": latitude,
                "longitude": longitude,
                "longitude_max": longitude,
                "elevation": 200.0,
                "elevation_max": 200.0,
                "reports": 24,
                "accepted_reports": 24,
                "valid_hours": 24,
                "temperature_max": 30.0 + (year - 2000) ** 0.7,
                "temperature_min": -20.0 - (year - 2000) ** 0.7,
            }
            for day in range(366 if calendar.isleap(year) else 365)
        ]
        return pa.Table.from_pylist(rows), {"url": "https://example.test/observations"}

    monkeypatch.setattr("crc_sdk.workflows.stations.fetch_catalogue", fetch_catalogue)
    monkeypatch.setattr(f"crc_sdk.providers.{source}.fetch_daily", fetch_daily)
    factory = HazardDataset.isd if source == "isd" else HazardDataset.ghcnh
    base = factory()
    base = (
        base.for_area(bounds) if selection == "area" else base.for_stations([station])
    )
    base = base.years(2000, 2005).cache(tmp_path / "cache")
    assert base.prefetch().cache_misses == 6

    def no_network(*args, **kwargs):
        raise AssertionError("the offline run must reuse its catalogue and daily data")

    monkeypatch.setattr("crc_sdk.workflows.stations.fetch_catalogue", no_network)
    monkeypatch.setattr(f"crc_sdk.providers.{source}.fetch_daily", no_network)
    summary = noaa_isd_pipeline.run(
        None if selection == "area" else [station],
        tmp_path,
        start=2000,
        end=2005,
        minimum_years=4,
        mode="offline",
        source=source,
        bounds=bounds if selection == "area" else None,
    )
    assert summary["fitted_station_curves"] == 2
    assert summary["station_year_cache_hits"] == 6
    assert summary["station_year_cache_misses"] == 0
    levels = pq.ParquetFile(tmp_path / "return_levels.parquet").read().to_pylist()
    assert len(levels) == 12
    for recipe, tail, family in (
        ("temperature_max", "upper", "genextreme"),
        ("temperature_min", "lower", "gumbel_l"),
    ):
        path = tmp_path / f"{recipe}_curves.parquet"
        curves = pq.ParquetFile(path).read()
        assert curves.num_rows == 1
        row = curves.to_pylist()[0]
        assert row["hazard_name"] == f"{source}_{recipe}"
        assert row["source_id"] == f"noaa-{source}:{station}"
        assert row["curve_type"] == family
        metadata = read_hazard_metadata(path)
        assert metadata.return_period_tail == tail
        request = json.loads(
            unquote(str(metadata.source.uri).split("#crc-request=")[1])
        )
        assert request["recipe"] == recipe
        assert request["stations"] == [station]
        assert request["areas"] == ([list(bounds)] if selection == "area" else [])
        if selection == "area":
            assert request["catalogue"]["raw_sha256"] == "catalogue-fingerprint"
        fitted = distribution_from_hazard_row(row)
        evaluated = [
            item for item in levels if item["hazard_name"] == f"{source}_{recipe}"
        ]
        assert len(evaluated) == 6
        for item in evaluated:
            period = item["return_period_years"]
            probability = 1 - 1 / period if tail == "upper" else 1 / period
            assert item["tail"] == tail
            assert item["temperature_degC"] == pytest.approx(
                float(fitted.ppf(probability))
            )
        temperatures = [item["temperature_degC"] for item in evaluated]
        assert temperatures == sorted(temperatures, reverse=tail == "lower")
        assert all(
            value > 0 if tail == "upper" else value < 0 for value in temperatures
        )
