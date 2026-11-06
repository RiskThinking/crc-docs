"""Committed notebooks must render on GitHub without a kernel.

Notebooks marked with ``metadata.crc_docs`` follow the current conventions:
sequential execution, a PNG preview for every Plotly figure and no saved
enterprise (CDT) outputs. Every notebook must be valid and free of errors.
"""

import base64
import json
import re
import struct
from pathlib import Path

import nbformat
import pytest

NOTEBOOKS = sorted(Path("notebooks").rglob("*.ipynb"))
CURRENT = [
    path for path in NOTEBOOKS if "crc_docs" in json.loads(path.read_text())["metadata"]
]
PLOTLY = "application/vnd.plotly.v1+json"


def outputs(notebook):
    return [
        output
        for cell in notebook.cells
        if cell.cell_type == "code"
        for output in cell.outputs
    ]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=str)
def test_notebook_is_valid_and_error_free(path: Path) -> None:
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    assert not any(output.output_type == "error" for output in outputs(notebook))


def test_current_notebooks_exist() -> None:
    assert CURRENT, "No notebook declares metadata.crc_docs"


@pytest.mark.parametrize("path", CURRENT, ids=str)
def test_current_notebook_has_saved_previews(path: Path) -> None:
    notebook = nbformat.read(path, as_version=4)
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    assert [cell.execution_count for cell in code] == list(range(1, len(code) + 1))
    figures = [
        output.data for output in outputs(notebook) if PLOTLY in output.get("data", {})
    ]
    assert figures, "expected at least one saved figure"
    for figure in figures:
        image = base64.b64decode(figure["image/png"], validate=True)
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", image[16:24])
        assert width >= 600 and height >= 300


@pytest.mark.parametrize("path", CURRENT, ids=str)
def test_current_notebook_keeps_enterprise_results_small(path: Path) -> None:
    """CDT results may be committed only as small aggregated tables and charts."""
    notebook = nbformat.read(path, as_version=4)
    expects_results = notebook.metadata["crc_docs"].get("cdt_outputs", False)
    for cell in notebook.cells:
        if cell.cell_type != "code" or "velo_sdk" not in cell.source:
            continue
        saved = json.dumps([dict(output) for output in cell.outputs])
        assert len(saved) < 20_000, "CDT outputs must be aggregated, not raw"
        assert "exposure_distribution" not in saved
        if expects_results:
            rich = [output for output in cell.outputs if output.output_type != "stream"]
            assert rich, "re-run with a CDT key before committing (cdt_outputs)"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=str)
def test_notebook_never_pins_old_packages(path: Path) -> None:
    # A pinned install inside a kernel would replace the locked environment
    # for every notebook that runs after it.
    notebook = nbformat.read(path, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            assert not re.search(r"crc-(sdk|framework)[\[\]\w,]*==", cell.source)
