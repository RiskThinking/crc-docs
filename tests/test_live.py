"""Execute notebooks and pipelines against live public data.

Opt in with ``CRC_DOCS_LIVE=1``. Runs use the small CI configuration
(``CRC_DOCS_CI=1``) and never call CDT unless a key is present.
"""

import base64
import json
import os
from pathlib import Path

import nbclient
import nbformat
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CRC_DOCS_LIVE") != "1", reason="set CRC_DOCS_LIVE=1"
)

NOTEBOOKS = sorted(
    path
    for path in Path("notebooks").rglob("*.ipynb")
    if json.loads(path.read_text())["metadata"].get("crc_docs", {}).get("ci")
)
PLOTLY = "application/vnd.plotly.v1+json"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=str)
def test_notebook_executes_and_renders(
    path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CRC_DOCS_CI", "1")
    monkeypatch.setenv("CRC_NOTEBOOK_STATIC_PREVIEW", "1")
    notebook = nbformat.read(path, as_version=4)
    timeout = notebook.metadata["crc_docs"].get("timeout_seconds", 900)
    nbclient.NotebookClient(
        notebook, timeout=timeout, resources={"metadata": {"path": str(path.parent)}}
    ).execute()
    executed = os.environ.get("CRC_DOCS_EXECUTED_DIR")
    if executed:
        Path(executed).mkdir(parents=True, exist_ok=True)
        nbformat.write(notebook, Path(executed) / path.name)
    figures = [
        output.data
        for cell in notebook.cells
        if cell.cell_type == "code"
        for output in cell.outputs
        if PLOTLY in output.get("data", {})
    ]
    assert figures
    for figure in figures:
        assert base64.b64decode(figure["image/png"]).startswith(b"\x89PNG")


def test_how_hot_pipeline(tmp_path: Path) -> None:
    from pipelines.how_hot_will_it_get import main

    summary = main(
        ["--output", str(tmp_path), "--station-years", "2005", "2024", "--skip-cdt"]
    )
    assert summary["a_station"]["available"]
    shift = summary["b_crc_open"]["baseline_1_in_10_becomes_every_n_years"]
    assert shift[2080] < shift[2025]
    assert (tmp_path / "return_levels.csv").read_text().count("\n") > 10


@pytest.mark.skipif(
    not os.environ.get("RISKTHINKING_API_KEY"), reason="needs a CDT API key"
)
def test_how_hot_cdt() -> None:
    pytest.importorskip("velo_sdk")
    from pipelines.how_hot_will_it_get import cdt_answer

    levels = cdt_answer(33.4278, -112.0037)["return_levels_c"]
    assert set(levels) == {"historic 2010", "ssp126 2050", "ssp245 2050", "ssp585 2050"}
    # Plausible Phoenix hottest days, and warmer futures than the baseline.
    assert 40 < levels["historic 2010"][10] < 55
    assert levels["ssp585 2050"][10] > levels["historic 2010"][10]
