"""Saved notebook output must remain viewable without an active kernel."""

import base64
import struct
from pathlib import Path

import nbformat


def test_crc_open_notebook_has_portable_executed_outputs():
    notebook = nbformat.read(Path("notebooks/crc_open_hazards.ipynb"), as_version=4)
    nbformat.validate(notebook)
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    assert [cell.execution_count for cell in code] == list(range(1, len(code) + 1))
    outputs = [output for cell in code for output in cell.outputs]
    assert not any(output.output_type == "error" for output in outputs)
    assert not notebook.metadata.get("widgets")
    figures = [
        output.data
        for output in outputs
        if "application/vnd.plotly.v1+json" in output.get("data", {})
    ]
    assert len(figures) >= 2
    for figure in figures:
        image = base64.b64decode(figure["image/png"])
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", image[16:24])
        assert width >= 600 and height >= 300
