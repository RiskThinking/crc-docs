"""Historical comparisons require usable values, not just output rows."""

import hashlib
import json
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from crc_sdk.connectors.parquet import hazard_arrow_schema, write_hazard_dataset
from crc_sdk.geometry import point_to_cell
from crc_sdk.types import EnsembleDescriptor, HazardDatasetMetadata, SourceProvenance

from pipelines import crc_open_pipeline


@pytest.fixture
def canonical_source(tmp_path):
    release = "test-release"
    source = tmp_path / "source"
    root = source / release
    metadata = HazardDatasetMetadata(
        h3_resolution=5,
        value_unit="mm/day",
        value_semantics="rx1day",
        producer="test",
        creation_version="test",
        probability_semantics="annual_value_distribution",
        ensemble=EnsembleDescriptor(pooling="pooled", scenario="ssp585"),
        source=SourceProvenance(provider="test", dataset="rainfall"),
    )
    groups = {}
    for site in crc_open_pipeline.SITES:
        cell = point_to_cell(site["longitude"], site["latitude"], 5)
        parent = (cell & ~(15 << 52)) | ((1 << 45) - 1)
        groups.setdefault(f"{parent:x}", set()).add(cell)
    partitions = []
    for parent, cells in groups.items():
        relative = f"rx1day/h3_r0={parent}/part-00000.parquet"
        path = root / relative
        path.parent.mkdir(parents=True)
        rows = [
            {
                "cell_index": cell,
                "source_id": "test",
                "source_geometry": None,
                "hazard_name": "rx1day",
                "horizon": horizon,
                "pathway": "ssp585",
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
            for cell in sorted(cells)
            for horizon in crc_open_pipeline.HORIZONS
        ]
        write_hazard_dataset(
            pa.Table.from_pylist(rows, schema=hazard_arrow_schema(metadata)),
            path,
            metadata,
        )
        partitions.append(
            {
                "path": relative,
                "h3_r0": parent,
                "rows": len(rows),
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "horizons": list(crc_open_pipeline.HORIZONS),
            }
        )
    catalog = {
        "catalog_version": 1,
        "schema_version": "1.3",
        "release": release,
        "pathways": ["ssp585"],
        "licence": "CC-BY-NC-4.0",
        "attribution": "test data",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "hazards": {
            "rx1day": {
                "unit": "mm/day",
                "value_semantics": "rx1day",
                "h3_resolution": 5,
                "tail": "upper",
                "probability_semantics": "annual_value_distribution",
                "pooling": "pooled",
                "pathways": ["ssp585"],
                "horizons": list(crc_open_pipeline.HORIZONS),
                "partitions": partitions,
            }
        },
    }
    payload = json.dumps(catalog, sort_keys=True).encode()
    (root / "_CATALOG.json").write_bytes(payload)
    (root / "_SUCCESS").write_text(hashlib.sha256(payload).hexdigest())
    return source, release


@pytest.mark.parametrize("coverage", ["valid", "no_data", "uncovered"])
def test_era5_comparison_requires_usable_values(
    tmp_path, monkeypatch, capsys, coverage, canonical_source
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
    cells = {
        point_to_cell(site["longitude"], site["latitude"], 5)
        for site in crc_open_pipeline.SITES
    }
    if coverage == "uncovered":
        cells = {point_to_cell(0, 0, 5)}
    row = {
        "cell_index": next(iter(cells)),
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
        pa.Table.from_pylist(
            [dict(row, cell_index=cell) for cell in sorted(cells)],
            schema=hazard_arrow_schema(metadata),
        ),
        baseline,
        metadata,
    )
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crc_open_pipeline",
            "--source",
            str(canonical_source[0]),
            "--release",
            canonical_source[1],
            "--output",
            str(output),
            "--era5-rx1day",
            str(baseline),
        ],
    )
    if coverage == "valid":
        crc_open_pipeline.main()
    else:
        with pytest.raises(
            LookupError,
            match="missing hazard curves"
            if coverage == "uncovered"
            else "no usable Rx1day return values",
        ):
            crc_open_pipeline.main()
    printed = capsys.readouterr().out
    projected = pq.read_table(output / "ssp585_portfolio.parquet")
    assert projected.num_rows == len(crc_open_pipeline.SITES) * len(
        crc_open_pipeline.HORIZONS
    )
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


def test_custom_assets_require_explicit_bounds(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["crc_open_pipeline", "--assets", "portfolio.csv"])
    with pytest.raises(SystemExit) as error:
        crc_open_pipeline.main()
    assert error.value.code == 2
    assert "--assets requires --bounds" in capsys.readouterr().err


@pytest.mark.parametrize("format", ["csv", "parquet"])
def test_custom_portfolio_and_horizon(tmp_path, monkeypatch, canonical_source, format):
    path = tmp_path / f"assets.{format}"
    if format == "csv":
        path.write_text("asset_id,longitude,latitude\nDemo,-79.38,43.65\n")
    else:
        pq.write_table(
            pa.table(
                {
                    "asset_id": ["Demo"],
                    "longitude": [-79.38],
                    "latitude": [43.65],
                }
            ),
            path,
        )
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crc_open_pipeline",
            "--assets",
            str(path),
            "--bounds",
            *map(str, crc_open_pipeline.BOUNDS),
            "--source",
            str(canonical_source[0]),
            "--release",
            canonical_source[1],
            "--horizons",
            "2050",
            "--output",
            str(output),
        ],
    )
    crc_open_pipeline.main()
    rows = pq.read_table(output / "ssp585_portfolio.parquet")
    assert rows.num_rows == 1
    assert rows["asset_id"].to_pylist() == ["Demo"]
    assert rows["horizon"].to_pylist() == [2050]
