"""CRC Open screening against a synthetic Dataset 2.0 release index."""

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pytest
from crc_framework import (
    Aggregation,
    DepthAboveGround,
    Duration,
    LengthUnit,
    PrecipitationAmount,
    PrecipitationRate,
    PrecipitationRateUnit,
    Tail,
    TimeUnit,
)
from crc_sdk import Dataset, Period, Probability, Scenario, Variable

from pipelines import crc_open_pipeline

DAY = Duration(1, unit=TimeUnit.DAY)
RX1DAY = Variable(
    "crc:rx1day",
    measurement=PrecipitationRate(
        unit=PrecipitationRateUnit.MILLIMETRES_PER_DAY,
        accumulation_duration=DAY,
        aggregation=Aggregation.MAXIMUM,
    ),
)
WINDOWS = {2030: (2028, 2031), 2050: (2048, 2051), 2080: (2078, 2081)}


def knots(sites: dict, offset: float) -> dict:
    count = len(sites["asset_id"])
    return {
        "support_id": [s for s in sites["asset_id"] for _ in range(3)],
        "longitude": [x for x in sites["longitude"] for _ in range(3)],
        "latitude": [y for y in sites["latitude"] for _ in range(3)],
        "probability": [0.5, 0.9, 0.99] * count,
        "value": [v + offset for _ in range(count) for v in (30.0, 50.0, 80.0)],
    }


@pytest.fixture
def release(tmp_path: Path) -> str:
    """A local release index: one Rx1day dataset per four-year window."""
    resources = []
    for year, (start, end) in WINDOWS.items():
        dataset = Dataset.from_quantiles(
            knots(crc_open_pipeline.SITES, offset=(year - 2030) / 10),
            variable=RX1DAY,
            scenario=Scenario("ssp585"),
            period=Period.window(start, end),
            probability=Probability.annual(tail=Tail.UPPER),
        ).write(tmp_path / f"rx1day-{start}.parquet")
        resources.append(
            {
                "id": dataset.path.stem,
                "uri": dataset.path.name,
                "sha256": "sha256:"
                + hashlib.sha256(dataset.path.read_bytes()).hexdigest(),
                "metadata": json.loads(dataset.metadata.to_json()),
                # The whole world is always a valid conservative extent.
                "extent": {
                    "west": -180.0,
                    "south": -90.0,
                    "east": 180.0,
                    "north": 90.0,
                },
            }
        )
    index = tmp_path / "_INDEX.json"
    index.write_text(
        json.dumps({"schema_version": "1.1", "id": "fixture", "datasets": resources})
    )
    return str(index)


def test_screen_maps_years_to_windows_and_keeps_long_rows(tmp_path, release):
    summary = crc_open_pipeline.screen(
        pa.table(crc_open_pipeline.SITES), tmp_path / "out", catalog=release
    )
    assert summary["years_to_windows"] == {
        "2030": "2028-2031",
        "2050": "2048-2051",
        "2080": "2078-2081",
    }
    rows = summary["rows"]
    assert len(rows) == 3 * 3 * 2
    assert summary["matched_assets"] == 3 and summary["unmatched_assets"] == 0
    rp100 = {
        (r["asset_id"], r["period"]): r["rx1day_mm_day"]
        for r in rows
        if r["return_period_years"] == 100
    }
    assert rp100[("Central clinic", "2028-2031")] == pytest.approx(80.0)
    assert rp100[("Central clinic", "2048-2051")] == pytest.approx(82.0)
    assert "SSP5-8.5 only" in summary["note"]
    assert (tmp_path / "out" / "ssp585_portfolio.parquet").is_file()


def test_unmatched_assets_keep_failure_rows(tmp_path, release):
    assets = pa.table(
        {"asset_id": ["Demo"], "longitude": [-79.40], "latitude": [43.70]}
    )
    summary = crc_open_pipeline.screen(
        assets, tmp_path / "out", years=[2050], catalog=release
    )
    assert summary["unmatched_assets"] == 1
    assert {r["failure"] for r in summary["rows"]} == {"no_covering_support"}


def test_year_outside_release_is_rejected(tmp_path, release):
    with pytest.raises(LookupError, match="2100"):
        crc_open_pipeline.screen(
            pa.table(crc_open_pipeline.SITES),
            tmp_path / "out",
            years=[2100],
            catalog=release,
        )


def test_cli_reads_custom_csv_assets(tmp_path, release):
    path = tmp_path / "assets.csv"
    path.write_text("asset_id,longitude,latitude\nWest depot,-79.47,43.65\n")
    output = tmp_path / "cli"
    summary = crc_open_pipeline.main(
        [
            "--catalog",
            release,
            "--assets",
            str(path),
            "--years",
            "2050",
            "--output",
            str(output),
        ]
    )
    assert [r["asset_id"] for r in summary["rows"]] == ["West depot"] * 2
    assert json.loads((output / "summary.json").read_text())["rows"]


@pytest.mark.parametrize("case", ["valid", "uncovered", "not_daily"])
def test_historical_comparison_requires_daily_values(tmp_path, case):
    sites = crc_open_pipeline.SITES
    measurement = PrecipitationAmount(
        unit=LengthUnit.MILLIMETRE, accumulation_duration=DAY
    )
    table = knots(sites, offset=-10)
    if case == "uncovered":
        table["longitude"] = [0.0] * len(table["longitude"])
        table["latitude"] = [0.0] * len(table["latitude"])
    if case == "not_daily":
        measurement = DepthAboveGround(unit=LengthUnit.METRE)
    baseline = Dataset.from_quantiles(
        table,
        variable=Variable("era5:rx1day", measurement=measurement),
        probability=Probability.annual(tail=Tail.UPPER),
    ).write(tmp_path / "era5.parquet")
    assets = pa.table(sites)
    if case == "valid":
        rows = crc_open_pipeline.compare_historical(
            assets, baseline.path, tmp_path, [10, 100]
        )
        assert len(rows) == 6 and all(r["value"] > 20 for r in rows)
    elif case == "uncovered":
        with pytest.raises(LookupError, match="no usable Rx1day"):
            crc_open_pipeline.compare_historical(assets, baseline.path, tmp_path, [10])
    else:
        with pytest.raises(ValueError, match="daily-precipitation"):
            crc_open_pipeline.compare_historical(assets, baseline.path, tmp_path, [10])
