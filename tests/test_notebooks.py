import json
from pathlib import Path


NOTEBOOKS = sorted(Path("notebooks").glob("*.ipynb"))


def test_all_notebooks_use_browser_free_runtime_setup() -> None:
    assert len(NOTEBOOKS) == 9

    for path in NOTEBOOKS:
        notebook = json.loads(path.read_text())
        all_source = "\n".join(
            "".join(cell.get("source", [])) for cell in notebook["cells"]
        )
        setup = "".join(notebook["cells"][2]["source"])
        imports = "".join(notebook["cells"][3]["source"])

        assert "pio.to_image" not in setup, path
        assert "ChromeNotFoundError" not in setup, path
        assert "kaleido" not in setup.lower(), path
        assert "duckdb>=1.4.5,<2" in setup, path
        assert '"plotly", "duckdb", "crc_sdk"' in setup, path
        assert "CRC_NOTEBOOK_STATIC_PREVIEW" in imports, path
        assert '"colab" if IN_COLAB' in imports, path
        assert "### Viewing this notebook" not in all_source, path
