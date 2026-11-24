"""Published IDF rates, their confidence half-widths and the Gumbel refit."""

import math

import pyarrow as pa
import pytest
from crc_framework import (
    Aggregation,
    Duration,
    PrecipitationRate,
    PrecipitationRateUnit,
    Tail,
    TimeUnit,
)
from crc_sdk import Dataset, Period, Probability, StationReference, Variable

from pipelines import eccc_idf_pipeline

PERIODS = [2.0, 5.0, 10.0, 25.0, 50.0, 100.0]
STATIONS = [
    StationReference(
        "6158731", "TORONTO INTL A", -79.63, 43.68, Period.window(1950, 2020)
    ),
    StationReference("6106000", "OTTAWA CDA", -75.72, 45.38, Period.window(2000, 2020)),
]


def published() -> Dataset:
    """Exact Gumbel rates (location 20, scale 5 mm/h), one knot per period."""
    rows = {
        k: [] for k in ("support_id", "longitude", "latitude", "probability", "value")
    }
    for station in STATIONS:
        for period in PERIODS:
            q = 1 - 1 / period
            rows["support_id"].append(station.id)
            rows["longitude"].append(station.longitude)
            rows["latitude"].append(station.latitude)
            rows["probability"].append(q)
            rows["value"].append(20 - 5 * math.log(-math.log(q)))
    return Dataset.from_quantiles(
        rows,
        variable=Variable(
            "eccc_idf:rainfall_rate:60min",
            measurement=PrecipitationRate(
                unit=PrecipitationRateUnit.MILLIMETRES_PER_HOUR,
                accumulation_duration=Duration(1, unit=TimeUnit.HOUR),
                aggregation=Aggregation.MAXIMUM,
            ),
        ),
        probability=Probability.annual(tail=Tail.UPPER),
    )


def test_audit_matches_published_rates_and_refit():
    intervals = pa.Table.from_pylist(
        [
            {
                "support_id": "6158731",
                "coordinate": {"kind": "return_period", "time": None, "years": 100.0},
                "interval": {"confidence": 0.95, "lower": 35.0, "upper": 45.0},
            }
        ]
    )
    rows = eccc_idf_pipeline.audit_duration(
        published(), STATIONS, "1h", PERIODS, intervals
    )
    assert len(rows) == len(STATIONS) * len(PERIODS)
    toronto = {r["return_period_years"]: r for r in rows if r["station"] == "6158731"}
    assert toronto[100.0]["published_mm_h"] == pytest.approx(43.0, abs=0.01)
    assert toronto[100.0]["confidence_95_half_width_mm_h"] == pytest.approx(5.0)
    assert toronto[2.0]["confidence_95_half_width_mm_h"] is None
    assert all(abs(r["fit_residual_mm_h"]) < 1e-6 for r in rows)
    ottawa = {r["return_period_years"]: r for r in rows if r["station"] == "6106000"}
    assert ottawa[25.0]["beyond_record_span"] is True
    assert toronto[50.0]["beyond_record_span"] is False
    depth = toronto[2.0]["published_duration_depth_mm"]
    assert depth == pytest.approx(toronto[2.0]["published_mm_h"])


def test_station_selection_by_id_box_or_all():
    choose = eccc_idf_pipeline.choose_stations
    assert [s.id for s in choose(STATIONS, ["6106000"])] == ["6106000"]
    boxes = [(-79.7, 43.6, -79.6, 43.7), (-79.65, 43.65, -79.6, 43.7)]
    assert [s.id for s in choose(STATIONS, areas=boxes)] == ["6158731"]
    assert len(choose(STATIONS)) == 2
    with pytest.raises(ValueError, match="unknown"):
        choose(STATIONS, ["0000000"])
    with pytest.raises(ValueError, match="no ECCC IDF station"):
        choose(STATIONS, areas=[(0, 0, 1, 1)])


def test_durations_map_to_typed_values():
    assert eccc_idf_pipeline.duration_of("15min") == Duration(900, unit=TimeUnit.SECOND)
    assert eccc_idf_pipeline.duration_of("24h") == Duration(24, unit=TimeUnit.HOUR)
