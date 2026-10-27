"""Published rainfall, fit accuracy and release auditing share one offline cache."""

import hashlib
import math

import pyarrow.parquet as pq
import pytest
from crc_sdk.providers import eccc_idf

from pipelines.eccc_idf_pipeline import run


@pytest.mark.parametrize("selection", ["stations", "areas"])
def test_pipeline_preserves_source_and_audits_release_support(
    tmp_path, monkeypatch, selection
):
    calls = []

    def fetch(version, province, stations):
        calls.append((version, province, tuple(stations)))
        periods = [2, 5, 10, 25, 50, 100] + ([200] if version == "3.40" else [])
        year = 1980 if version == "3.40" else 1970
        latitude = "43 40'N" if version == "3.40" else "43 41'N"
        lines = [
            "SYNTHETIC A                 ON        6158731",
            f"Latitude: {latitude}    Longitude: 79 38'W",
            f"Years/Années : {year} - 2020",
            "Table 2b :",
            "Duration/Durée  " + " ".join(map(str, periods)) + " #Years",
        ]
        for duration, minutes in eccc_idf.DURATIONS.items():
            rates = [
                (20 - 5 * math.log(-math.log(1 - 1 / t))) * 60 / minutes
                for t in periods
            ]
            label = duration.replace("min", " min").replace("h", " h")
            lines += [
                label + " " + " ".join(f"{v:.1f}" for v in rates) + " 40",
                " ".join(["+/- 1.0"] * len(periods)) + " 40",
            ]
        lines.append("Table 3")
        raw = "\n".join(lines).encode("cp1252")
        yield (
            "6158731",
            raw,
            {
                "checksum": hashlib.sha256(raw).hexdigest(),
                "url": "https://example.test/idf.zip",
                "member": "synthetic.txt",
            },
        )

    monkeypatch.setattr(eccc_idf, "fetch_stations", fetch)
    boxes = [(-79.65, 43.65, -79.61, 43.70), (-79.64, 43.66, -79.62, 43.71)]
    kwargs = {"areas": [*boxes, boxes[0]]} if selection == "areas" else {}
    summary = run(tmp_path, compare_version="3.20", **kwargs)
    assert summary["stations"] == ["6158731"]
    assert summary["areas"] == (tuple(boxes) if selection == "areas" else ())
    assert all(
        call[2] == (() if selection == "areas" else ("6158731",)) for call in calls
    )
    assert len(calls) == 2
    assert summary["rate_rows"] == 39 and summary["comparison_rows"] == 18
    assert summary["maximum_absolute_fit_residual_mm_h"] < 0.15
    rates = pq.read_table(tmp_path / "rainfall_rates.parquet").to_pylist()
    assert any(r["return_period_years"] == 200 for r in rates)
    assert any(r["beyond_record_length"] for r in rates)
    one_hour = next(r for r in rates if r["duration_minutes"] == 60)
    assert one_hour["published_mm_h"] == one_hour["published_duration_depth_mm"]
    changes = pq.read_table(tmp_path / "release_changes.parquet").to_pylist()
    assert all(r["record_changed"] and r["coordinates_changed"] for r in changes)
    assert all(r["change_percent"] == 0 for r in changes)
    assert all(r["return_period_years"] != 200 for r in changes)

    def no_network(*args, **kwargs):
        raise AssertionError("offline replay must use verified source bytes")

    monkeypatch.setattr(eccc_idf, "fetch_stations", no_network)
    assert (
        run(tmp_path, compare_version="3.20", cache_mode="offline", **kwargs)[
            "rate_rows"
        ]
        == 39
    )


def test_station_and_area_selection_are_mutually_exclusive(tmp_path):
    with pytest.raises(ValueError, match="not both"):
        run(tmp_path, stations=("6158731",), areas=[(-80, 43, -79, 44)])


def test_cli_passes_repeated_bounds_as_one_area_selection(monkeypatch):
    import sys

    from pipelines import eccc_idf_pipeline

    captured = {}

    def run(output, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(eccc_idf_pipeline, "run", run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eccc_idf_pipeline.py",
            "--bounds",
            "-80",
            "43",
            "-79",
            "44",
            "--bounds",
            "-78",
            "45",
            "-77",
            "46",
        ],
    )
    eccc_idf_pipeline.main()
    assert captured["stations"] is None
    assert captured["areas"] == [[-80, 43, -79, 44], [-78, 45, -77, 46]]
