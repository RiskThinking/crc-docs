"""Heat and cold station samples are saved, fitted per tail and queried."""

import random

import pyarrow.parquet as pq
import pytest
from crc_framework import Tail, Temperature, TemperatureUnit
from crc_sdk import Probability, Samples, TimeSeriesColumns, Variable

from pipelines import noaa_isd_pipeline


def samples(tail: Tail, centre: float, years: int = 25) -> Samples:
    rng = random.Random(7)
    count = years
    return Samples.from_table(
        {
            "support_id": ["USW00094846@a"] * count,
            "station": ["USW00094846"] * count,
            "longitude": [-87.93] * count,
            "latitude": [41.96] * count,
            "time": list(range(2000, 2000 + count)),
            "value": [centre + rng.gauss(0, 2) for _ in range(count)],
        },
        variable=Variable(
            f"test:{tail.value}", measurement=Temperature(unit=TemperatureUnit.CELSIUS)
        ),
        probability=Probability.annual(tail=tail),
        columns=TimeSeriesColumns(station_id="station"),
    )


def test_heat_and_cold_return_levels(tmp_path):
    summary = noaa_isd_pipeline.return_levels(
        {"heat": samples(Tail.UPPER, 34.0), "cold": samples(Tail.LOWER, -22.0)},
        tmp_path,
        years=25,
    )
    levels = pq.read_table(summary["return_levels"]).to_pylist()
    heat = {
        r["return_period_years"]: r["temperature"]
        for r in levels
        if r["tail"] == "heat"
    }
    cold = {
        r["return_period_years"]: r["temperature"]
        for r in levels
        if r["tail"] == "cold"
    }
    assert heat[100.0] > heat[2.0] > 30
    assert cold[100.0] < cold[2.0] < -15
    assert {r["station"] for r in levels} == {"USW00094846"}
    assert {r["unit"] for r in levels} == {"degC"}
    assert [r["beyond_requested_window"] for r in levels if r["tail"] == "heat"] == [
        False,
        False,
        False,
        False,
        True,
        True,
    ]
    assert summary["tails"]["heat"]["annual_values"] == 25
    assert (tmp_path / "heat_annual.parquet").is_file()


def test_short_records_keep_a_fit_failure(tmp_path):
    summary = noaa_isd_pipeline.return_levels(
        {"heat": samples(Tail.UPPER, 34.0, years=4)}, tmp_path, minimum_years=20
    )
    levels = pq.read_table(summary["return_levels"]).to_pylist()
    assert all(r["temperature"] is None and r["failure"] for r in levels)
    assert summary["tails"]["heat"]["fit_failures"]


def test_station_or_bounds_is_required(tmp_path):
    with pytest.raises(ValueError, match="station IDs or bounds"):
        noaa_isd_pipeline.run(None, tmp_path)
