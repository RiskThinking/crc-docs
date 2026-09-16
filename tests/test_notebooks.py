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
        setup = next(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if "REQUIREMENTS =" in "".join(cell.get("source", []))
        )
        imports = next(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if "pio.renderers.default" in "".join(cell.get("source", []))
        )

        assert "pio.to_image" not in setup, path
        assert "ChromeNotFoundError" not in setup, path
        assert "kaleido" not in setup.lower(), path
        assert "duckdb>=1.4.5,<2" in setup, path
        assert '"plotly", "duckdb", "crc_sdk"' in setup, path
        assert "CRC_NOTEBOOK_STATIC_PREVIEW" in imports, path
        assert '"colab" if IN_COLAB' in imports, path
        assert "### Viewing this notebook" not in all_source, path


def test_flood_demo_reuses_cache_and_explores_canonical_curve() -> None:
    notebook = json.loads(Path("notebooks/flood_risk_by_province.ipynb").read_text())
    source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )

    assert "CACHE_MODE" not in source
    assert 'mode="reuse"' in source
    assert "plan.ensure_materialized()" in source
    assert "OVERTURE_RELEASE_FILE.exists()" in source
    assert "OVERTURE_POINTS_PATH.exists()" in source
    assert "read_parquet('{OVERTURE_POINTS_PATH}')" in source
    assert "RETURN_PERIOD_YEARS = 25" in source
    assert "SOURCE_RETURN_PERIODS = (10, 20, 30, 40, 50, 75, 100, 200, 500)" in source
    assert "widgets.SelectionSlider(" in source
    assert "MEANINGFUL_RETURN_PERIODS = (10, 20, 25, 30, 40, 50, 75, 100, 200, 250, 500, 750, 1000)" in source
    assert 'description="Apply to regional analysis"' in source
    assert "run_regional_analysis(RETURN_PERIOD_YEARS, output=analysis_output)" in source
    assert 'name="Canonical fit at JRC source RPs"' in source
    assert source.count('name="Canonical fitted curve"') == 1
    assert source.count("curve_output = widgets.Output()") == 1
    assert "they are **not raw raster observations**" in source
    assert 'xaxis=dict(title="Return period (years)", range=[10, 1000])' in source
    assert "curve extrapolation beyond RP500" in source
    assert "return_period_years" in source
    assert "MIN_DEPTH_M = 0.5" in source
    assert 'emit("Reusable cache ready: "' in source
    assert "curve_quantiles_at(curves, probability, max_workers=1)" in source
    assert "SELECT depth_m, place_count," in source
    assert "SELECT p.confidence, p.geometry" in source
    assert "SELECT a.shapeName AS province," in source
    assert "SELECT p.name" not in source
