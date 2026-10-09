"""Historical comparisons require usable values, not just output rows."""

import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from crc_sdk.connectors.parquet import hazard_arrow_schema, write_hazard_dataset
from crc_sdk.geometry import point_to_cell
from crc_sdk.providers.crc_open import CRCOpenFixtureWarning
from crc_sdk.types import HazardDatasetMetadata, SourceProvenance

from pipelines import crc_open_pipeline


@pytest.mark.parametrize("coverage", ["valid", "no_data", "uncovered"])
def test_era5_comparison_requires_usable_values(
    tmp_path, monkeypatch, capsys, coverage
):
    metadata = HazardDatasetMetadata(
        h3_resolution=5,
        value_unit="mm/day",
        value_semantics="rx1day",
        probability_semantics="annual_exceedance",
        producer="test",
        creation_version="test",
        source=SourceProvenance(provider="era5", dataset="synthetic-test"),
    )
    cell = point_to_cell(-79.38, 43.65, 5)
    if coverage == "uncovered":
        cell = point_to_cell(0, 0, 5)
    row = {
        "cell_index": cell,
        "source_id": "test",
        "source_geometry": None,
        "hazard_name": "rx1day",
        "horizon": 2005,
        "pathway": "historic",
        "curve_kind": "fitted",
        "curve_type": "gumbel_r",
        "curve_shape": None,
        "curve_location": 20.0,
        "curve_scale": 5.0,
        "curve_atom_probability": None,
        "curve_atom_location": None,
        "curve_probabilities": None,
        "curve_values": None,
    }
    if coverage == "no_data":
        row.update(
            curve_kind="no_data",
            curve_type="insufficient_informative_support",
            curve_location=None,
            curve_scale=None,
        )
    baseline = tmp_path / "baseline.parquet"
    write_hazard_dataset(
        pa.Table.from_pylist([row], schema=hazard_arrow_schema(metadata)),
        baseline,
        metadata,
    )
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crc_open_pipeline",
            "--fixtures",
            str(Path(__file__).resolve().parents[1] / "fixtures/crc_open"),
            "--output",
            str(output),
            "--era5-rx1day",
            str(baseline),
        ],
    )
    if coverage == "valid":
        with pytest.warns(CRCOpenFixtureWarning):
            crc_open_pipeline.main()
    else:
        with (
            pytest.warns(CRCOpenFixtureWarning),
            pytest.raises(
                LookupError,
                match="missing hazard curves"
                if coverage == "uncovered"
                else "no usable Rx1day return values",
            ),
        ):
            crc_open_pipeline.main()
    printed = capsys.readouterr().out
    assert ("ERA5 historical comparison" in printed) == (coverage == "valid")
    if coverage == "uncovered":
        assert not (output / "era5_historical.parquet").exists()
        return
    historical = pq.read_table(output / "era5_historical.parquet")
    if coverage == "valid":
        assert historical["value_rp10"][0].as_py() > 20
    elif coverage == "no_data":
        assert historical.num_rows > 0
        assert historical["value_rp10"].null_count == historical.num_rows
