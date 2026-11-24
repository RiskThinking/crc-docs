"""Offline checks for the five question pipelines.

CRC Open is replaced by a small local release index built with the public
crc-sdk interface; public-data fits use tables built with ``Samples`` and
``Observations``. Nothing here touches the network.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
from crc_framework import (
    DistributionFamily,
    Duration,
    LengthUnit,
    Measurement,
    PrecipitationAmount,
    QuantileFit,
    SpeedUnit,
    Tail,
    TimeUnit,
    WindSpeed,
)
from crc_sdk import (
    Dataset,
    Observations,
    Period,
    Probability,
    Runtime,
    Samples,
    Scenario,
    Variable,
)

from pipelines import (
    how_exposed_is_this_company,
    how_hard_will_it_rain,
    how_hot_will_it_get,
    which_sites_are_most_at_risk,
    will_my_farm_get_drier,
)

KNOTS = [0.05, 0.2, 0.5, 0.8, 0.9, 0.96, 0.99, 0.995]
WINDOWS = [Period.window(start, start + 3) for start in range(2023, 2089, 5)]
VARIABLES = {
    "crc:tx_max": Measurement(quantity="tx_max", unit="K"),
    "crc:rx1day": Measurement(quantity="rx1day", unit="mm"),
    "crc:hot_days": Measurement(quantity="hot_days", unit="days"),
    "crc:fwi": Measurement(quantity="fwi", unit="dimensionless"),
    "crc:prcptot": Measurement(quantity="prcptot", unit="mm"),
    "crc:dry_days": Measurement(quantity="dry_days", unit="days"),
    "crc:max_consecutive_dry_days": Measurement(
        quantity="max_consecutive_dry_days", unit="days"
    ),
}


def gumbel_knots(location: float, scale: float) -> list[float]:
    return [location - scale * math.log(-math.log(p)) for p in KNOTS]


def write_release(tmp_path: Path, entries: list[tuple]) -> str:
    """A CRC Open release index over Gumbel curves at the given points.

    Each entry is ``(variable, measurement, period, probability, points)`` with
    ``points`` a list of ``(support_id, longitude, latitude, location, scale)``.
    """
    root = tmp_path / "release"
    root.mkdir()
    datasets = []
    for number, (variable, measurement, period, probability, points) in enumerate(
        entries
    ):
        rows: dict[str, list] = {
            k: []
            for k in ("support_id", "longitude", "latitude", "probability", "value")
        }
        for support, lon, lat, location, scale in points:
            rows["support_id"] += [support] * len(KNOTS)
            rows["longitude"] += [lon] * len(KNOTS)
            rows["latitude"] += [lat] * len(KNOTS)
            rows["probability"] += KNOTS
            rows["value"] += gumbel_knots(location, scale)
        uri = f"part-{number:03d}.parquet"
        Dataset.from_quantiles(
            rows,
            variable=Variable(variable, measurement=measurement),
            scenario=None if period.start is None else Scenario("ssp585"),
            period=period,
            probability=probability,
        ).fit(QuantileFit(family=DistributionFamily.GUMBEL_RIGHT)).write(root / uri)
        datasets.append(
            {
                "id": f"dataset-{number}",
                "uri": uri,
                "sha256": "sha256:"
                + hashlib.sha256((root / uri).read_bytes()).hexdigest(),
                "metadata": json.loads(Dataset.open(root / uri).metadata.to_json()),
            }
        )
    index = root / "_INDEX.json"
    index.write_text(
        json.dumps(
            {"schema_version": "1.0", "id": "test-release", "datasets": datasets}
        )
    )
    return str(index)


ANNUAL = Probability.annual(tail=Tail.UPPER)


def test_how_hot_reads_periods_in_celsius(tmp_path, monkeypatch):
    lon, lat = -112.0, 33.4
    entries = [
        (
            "crc:tx_max",
            VARIABLES["crc:tx_max"],
            period,
            ANNUAL,
            [("cell", lon, lat, 318.0 + 0.05 * (period.start - 2023), 1.5)],
        )
        for period in WINDOWS
    ]
    monkeypatch.setattr(
        how_hot_will_it_get, "CRC_OPEN", write_release(tmp_path, entries)
    )
    answer = how_hot_will_it_get.crc_open_answer(
        "Here", lat, lon, (2025, 2050, 2080), Runtime()
    )
    assert answer["available"], answer
    assert list(answer["windows"]) == ["2023-2026", "2048-2051", "2078-2081"]
    levels = answer["return_levels_c"]["2023-2026"]
    expected = 318.0 - 1.5 * math.log(-math.log(0.9)) - 273.15
    assert levels[10] == pytest.approx(expected, abs=0.02)
    shift = answer["baseline_1_in_10_becomes_every_n_years"]
    assert shift["2023-2026"] == pytest.approx(10, abs=0.1)
    assert shift["2048-2051"] < shift["2023-2026"]
    assert shift["2078-2081"] < shift["2048-2051"]
    text = how_hot_will_it_get.headline("Here", {"available": False}, answer)
    assert "2078-2081" in text and "SSP5-8.5" in text


def test_how_hot_reports_a_place_outside_the_release(tmp_path, monkeypatch):
    entries = [
        (
            "crc:tx_max",
            VARIABLES["crc:tx_max"],
            WINDOWS[0],
            ANNUAL,
            [("cell", 10.0, 10.0, 300.0, 1.0)],
        )
    ]
    monkeypatch.setattr(
        how_hot_will_it_get, "CRC_OPEN", write_release(tmp_path, entries)
    )
    answer = how_hot_will_it_get.crc_open_answer("Far", 0.0, 0.0, (2025,), Runtime())
    assert not answer["available"]


def annual_samples(values: list[float], lon: float, lat: float, start: int) -> Samples:
    return Samples.from_table(
        {
            "support_id": ["grid"] * len(values),
            "longitude": [lon] * len(values),
            "latitude": [lat] * len(values),
            "time": list(range(start, start + len(values))),
            "value": values,
        },
        variable=Variable(
            "test:annual_maximum_daily_precipitation",
            measurement=PrecipitationAmount(
                unit=LengthUnit.MILLIMETRE,
                accumulation_duration=Duration(1, unit=TimeUnit.DAY),
            ),
        ),
        probability=ANNUAL,
    )


def test_how_hard_fits_annual_wettest_days():
    rng = np.random.default_rng(7)
    values = (30 + 8 * rng.gumbel(size=30)).round(1).tolist()
    lon, lat = -79.38, 43.65
    annual = annual_samples(values, lon, lat, 1995).read()
    place = how_hard_will_it_rain.place_assets("Here", lat, lon)
    answer = how_hard_will_it_rain.era5_summary(annual, place, (1995, 2024), Runtime())
    assert answer["available"], answer
    assert answer["complete_years"] == 30
    assert answer["wettest_day_mm"] == max(values)
    levels = answer["return_levels_mm"]
    assert levels[2] < levels[10] < levels[25]


def test_how_hard_averages_groups_of_periods(tmp_path, monkeypatch):
    lon, lat = -79.38, 43.65
    entries = [
        (
            "crc:rx1day",
            VARIABLES["crc:rx1day"],
            period,
            ANNUAL,
            [("cell", lon, lat, 30.0 + 0.1 * (period.start - 2023), 8.0)],
        )
        for period in WINDOWS
    ]
    monkeypatch.setattr(
        how_hard_will_it_rain, "CRC_OPEN", write_release(tmp_path, entries)
    )
    answer = how_hard_will_it_rain.crc_open_answer("Here", lat, lon, Runtime())
    assert answer["available"], answer
    assert list(answer["windows"]) == list(how_hard_will_it_rain.WINDOWS)
    assert answer["windows"]["2023-2046"][0] == "2023-2026"
    assert len(answer["windows"]["2068-2091"]) == 5
    assert answer["late_1_in_10_mm"] > answer["baseline_1_in_10_mm"]
    assert answer["baseline_1_in_10_becomes_every_n_years"]["2068-2091"] < 10


def test_which_sites_ranks_changes_across_hazards(tmp_path, monkeypatch):
    sites = [
        {"site": "Hot", "latitude": 33.4, "longitude": -112.0},
        {"site": "Mild", "latitude": 47.6, "longitude": -122.3},
    ]
    entries = []
    for variable in ("crc:tx_max", "crc:rx1day", "crc:hot_days", "crc:fwi"):
        for period in WINDOWS:
            trend = 0.1 * (period.start - 2023)
            entries.append(
                (
                    variable,
                    VARIABLES[variable],
                    period,
                    ANNUAL,
                    [
                        ("hot", -112.0, 33.4, 300.0 + 2 * trend, 2.0),
                        ("mild", -122.3, 47.6, 290.0 + trend, 2.0),
                    ],
                )
            )
    monkeypatch.setattr(
        which_sites_are_most_at_risk, "CRC_OPEN", write_release(tmp_path, entries)
    )
    answer = which_sites_are_most_at_risk.crc_open_answer(sites, Runtime())
    assert answer["available"], answer
    assert answer["windows"]["early"] == ["2023-2026", "2028-2031", "2033-2036"]
    assert answer["windows"]["late"] == ["2068-2071", "2073-2076", "2078-2081"]
    hot = answer["one_in_10"]["Hot"]
    assert hot["tx_max"]["early"] < 40  # converted from kelvin
    assert hot["rx1day"]["change"] == pytest.approx(9.0, abs=0.2)
    assert {top["site"] for top in answer["largest_change"].values()} == {"Hot"}
    assert answer["missing"] == []
    text = which_sites_are_most_at_risk.headline(sites, answer)
    assert "2023-2036" in text and "2068-2081" in text


def test_farm_soil_moisture_annual_minima(tmp_path):
    lon, lat = -4.72, 41.65
    rng = np.random.default_rng(3)
    times, values = [], []
    for year in range(2000, 2024):
        dekads = 36 if year < 2023 else 20  # the last year is incomplete
        low = float(rng.uniform(0.0, 0.4))
        for index in range(dekads):
            month, part = divmod(index, 3)
            times.append(f"{year}-{month + 1:02d}-{1 + 10 * part:02d}")
            values.append(low if index == 20 else 0.8)
    observations = Observations.from_table(
        {
            "support_id": ["pixel"] * len(times),
            "longitude": [lon] * len(times),
            "latitude": [lat] * len(times),
            "time": times,
            "value": values,
        },
        variable=Variable(
            "test:soil_moisture_index",
            measurement=Measurement(quantity="soil_moisture_index", unit="1"),
        ),
    ).read()
    answer = will_my_farm_get_drier.edo_summary(observations, lat, lon, Runtime())
    assert answer["available"], answer
    assert answer["complete_years"] == 23
    driest = answer["driest_soil_index"]
    assert driest[20] < driest[10] < driest[5] < driest[2]


def test_farm_dry_weather_measures(tmp_path, monkeypatch):
    lon, lat = -4.72, 41.65
    entries = []
    for variable, base, trend in (
        ("crc:prcptot", 420.0, -1.0),
        ("crc:dry_days", 250.0, 0.4),
        ("crc:max_consecutive_dry_days", 60.0, 0.5),
    ):
        for period in WINDOWS:
            entries.append(
                (
                    variable,
                    VARIABLES[variable],
                    period,
                    ANNUAL,
                    [("cell", lon, lat, base + trend * (period.start - 2023), 15.0)],
                )
            )
    monkeypatch.setattr(
        will_my_farm_get_drier, "CRC_OPEN", write_release(tmp_path, entries)
    )
    answer = will_my_farm_get_drier.crc_open_answer("Farm", lat, lon, Runtime())
    assert answer["available"], answer
    early, late = answer["windows"]
    assert (early, late) == ("2023-2036", "2068-2081")
    measures = answer["measures"]
    rain = measures["annual_rain_1_in_10_dry_mm"]
    assert rain[late] < rain[early]
    assert measures["annual_rain_typical_mm"][early] > rain[early]
    assert measures["longest_dry_spell_1_in_10_days"]["change_percent"] > 0
    assert answer["early_1_in_10_dry_spell_returns_every_n_years_late"] < 10
    assert "grows" in will_my_farm_get_drier.headline("Farm", answer)


def test_company_expected_damage_uses_builtin_models(tmp_path, monkeypatch):
    locations = pa.table(
        {
            "asset_id": ["store-1", "store-2"],
            "longitude": [-80.2, -81.4],
            "latitude": [25.8, 28.5],
        }
    )
    points = [("a", -80.2, 25.8), ("b", -81.4, 28.5)]
    entries = [
        (
            "crc:cyclone",
            WindSpeed(unit=SpeedUnit.METRES_PER_SECOND),
            Period.timeless(),
            Probability.distribution(),
            [(s, x, y, 25.0, 4.0) for s, x, y in points],
        )
    ]
    for variable, location in (("crc:rx1day", 80.0), ("crc:hot_days", 60.0)):
        for period in WINDOWS:
            entries.append(
                (
                    variable,
                    VARIABLES[variable],
                    period,
                    ANNUAL,
                    [
                        (s, x, y, location + (period.start - 2023), 10.0)
                        for s, x, y in points
                    ],
                )
            )
    monkeypatch.setattr(
        how_exposed_is_this_company, "CRC_OPEN", write_release(tmp_path, entries)
    )
    answer = how_exposed_is_this_company.crc_open_answer(
        locations, (-82.0, 25.0, -80.0, 29.0), Runtime()
    )
    assert answer["available"], answer
    assert answer["locations_with_all_hazards"] == 2
    damage = answer["average_expected_damage_pct"]
    assert damage["cyclone"]["early"] == damage["cyclone"]["late"] > 0
    assert damage["hot_days"]["late"] > damage["hot_days"]["early"] > 0
    assert damage["total"]["early"] == pytest.approx(
        sum(damage[h]["early"] for h in how_exposed_is_this_company.HAZARDS), abs=0.02
    )
    assert set(answer["per_location_pct"]) == {"store-1", "store-2"}
