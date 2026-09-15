"""A canonical no-data row must not crash or turn into a zero in CLI summaries."""
from argparse import Namespace
from types import SimpleNamespace

import pyarrow as pa
import pytest

from pipelines import jrc_drought_pipeline, jrc_flood_pipeline


@pytest.mark.parametrize("module", [jrc_flood_pipeline, jrc_drought_pipeline])
@pytest.mark.parametrize("values", [[None, 2.0], [None, None]])
def test_null_curve_summary(module, values, tmp_path, monkeypatch, capsys):
    metadata = SimpleNamespace(return_period_support=None, return_period_tail="upper")

    class Plan:
        def __getattr__(self, name):
            return lambda *args, **kwargs: self

        def explain(self):
            return "test plan"

        def materialize(self, path):
            return SimpleNamespace(
                metadata=lambda: metadata,
                provider=SimpleNamespace(source=path),
                materialization=SimpleNamespace(source_version="test"),
            )

    monkeypatch.setattr(module, "parse_args", lambda: Namespace(
        output_dir=tmp_path, dataset="efas", bounds=(0, 0, 1, 1),
        cache_mode="reuse", h3_resolution=6, years=(1995, 2025), return_periods=[100],
    ))
    monkeypatch.setattr(module.HazardDataset, "efas", lambda **kwargs: Plan())
    monkeypatch.setattr(module.HazardDataset, "smi", lambda **kwargs: Plan())
    monkeypatch.setattr(module, "read_hazard_dataset", lambda path: pa.table({"cell_index": [1, 2]}))
    monkeypatch.setattr(module, "curve_quantiles_at", lambda *args: values)
    module.main()
    output = capsys.readouterr().out
    assert f"{values.count(None)} source rows without values" in output
    assert ("unavailable" in output) == all(value is None for value in values)
