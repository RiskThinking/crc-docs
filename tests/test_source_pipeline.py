"""The source pipeline writes canonical evidence and a provenance summary."""

import json

import pytest
from crc_framework import Duration, LengthUnit, PrecipitationAmount, TimeUnit
from crc_sdk import Observations, TimeSeriesColumns, Variable

from pipelines import source_pipeline


def fake_source(options, runtime):
    rows = {
        "support_id": ["gauge"] * 3,
        "longitude": [24.0] * 3,
        "latitude": [60.0] * 3,
        "time": ["2020-01-01", "2020-01-02", "2020-01-03"],
        "value": [1.0, None, 3.0],
        "group_id": ["storm-a", "storm-a", "storm-b"],
    }
    recipe = Observations.from_table(
        rows,
        variable=Variable(
            "test:rain",
            measurement=PrecipitationAmount(
                unit=LengthUnit.MILLIMETRE,
                accumulation_duration=Duration(1, unit=TimeUnit.DAY),
            ),
        ),
        columns=TimeSeriesColumns(group_id="group_id"),
    )
    return {"observations": recipe}


@pytest.fixture
def registered(monkeypatch):
    source = source_pipeline.Source(
        "Synthetic gauge", source_pipeline.Options(station="gauge"), fake_source, "test"
    )
    monkeypatch.setitem(source_pipeline.SOURCES, "ibtracs", source)
    return source


def test_run_writes_evidence_and_summary(tmp_path, registered):
    summary = source_pipeline.run("ibtracs", tmp_path)
    written = Observations.open(summary["outputs"]["observations"])
    assert written.read().table.num_rows == 3
    counts = summary["artifacts"]["observations"]["counts"]
    assert counts["produced"] == 3 and counts["no_data"] == 1
    assert summary["selection"]["station"] == "gauge"
    assert summary["storms"] == {"storm-a": 2, "storm-b": 1}
    assert json.loads((tmp_path / "summary.json").read_text())["source"] == "ibtracs"


def test_rerun_overwrites_atomically(tmp_path, registered):
    source_pipeline.run("ibtracs", tmp_path)
    again = source_pipeline.run(
        "ibtracs", tmp_path, options=source_pipeline.Options(start=2021)
    )
    assert again["selection"]["start"] == 2021
    assert not list(tmp_path.glob(".*.tmp"))


def test_every_source_has_complete_defaults():
    for name, source in source_pipeline.SOURCES.items():
        defaults = source.defaults
        assert defaults.station or defaults.bounds, name
    with pytest.raises(SystemExit):
        source_pipeline.main(["--source", "unknown"])
