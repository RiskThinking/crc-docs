# Climate Risk Commons Documentation

Examples, notebooks, and headless pipelines for
[`crc-sdk`](https://pypi.org/project/crc-sdk/) and its
[`crc-framework`](https://pypi.org/project/crc-framework/) dependency.

## Setup

```shell
uv sync
```

Notebooks expect to be run with the working directory set to `notebooks/`
(so their `data/` cache lands next to them). Pipelines can be run from the
repo root.

```shell
uv run jupyter lab notebooks/
uv run python pipelines/asset_portfolio_pipeline.py
```

## Learning path

Two tracks share the same packages: **areal / spatial analytics** and
**asset portfolios**. The portfolio track is ordered and uses the checked-in
Cologne fixtures under `fixtures/os_climate/`, so it runs without AWS access.

### Areal / spatial

| Notebook | Pipeline twin | What it shows |
|---|---|---|
| [`notebooks/flood_risk_by_province.ipynb`](notebooks/flood_risk_by_province.ipynb) | [`pipelines/flood_admin_pipeline.py`](pipelines/flood_admin_pipeline.py) | JRC GeoTIFF → H3 → admin join → Overture places → PMTiles |
| [`notebooks/jrc_global_flood_hazard.ipynb`](notebooks/jrc_global_flood_hazard.ipynb) | [`pipelines/jrc_flood_pipeline.py`](pipelines/jrc_flood_pipeline.py) | Streamed GeoTIFF/COG → H3 sampling (JRC LISFLOOD) |

### Asset portfolios

| # | Notebook | Pipeline twin | What it shows |
|---|---|---|---|
| 1 | [`notebooks/hurdle_fit_primer.ipynb`](notebooks/hurdle_fit_primer.ipynb) | — | Reconstruct a canonical hurdle + sample diagnostics |
| 2 | [`notebooks/asset_portfolio_evaluation.ipynb`](notebooks/asset_portfolio_evaluation.ipynb) | [`pipelines/asset_portfolio_pipeline.py`](pipelines/asset_portfolio_pipeline.py) | Fluent `HazardDataset` portfolio RP evaluation |
| 3 | [`notebooks/portfolio_impact.ipynb`](notebooks/portfolio_impact.ipynb) | [`pipelines/portfolio_impact_pipeline.py`](pipelines/portfolio_impact_pipeline.py) | Event-aligned `PiecewiseLinearImpact` → \$ damage |
| 4 | [`notebooks/portfolio_risk_metrics.ipynb`](notebooks/portfolio_risk_metrics.ipynb) | [`pipelines/portfolio_risk_pipeline.py`](pipelines/portfolio_risk_pipeline.py) | Microscores → portfolio VaR / CVaR + attribution |
| 5 | [`notebooks/multi_scenario_portfolio.ipynb`](notebooks/multi_scenario_portfolio.ipynb) | [`pipelines/multi_scenario_pipeline.py`](pipelines/multi_scenario_pipeline.py) | Historical vs transparent local tail stresses in one evaluation |

## Smoke tests

[`examples/smoke/`](examples/smoke/) holds the original live SDK smoke scripts
these docs grew out of. Useful for regression checks; the notebooks above are
the narrative entry point.

```shell
uv run python examples/smoke/e2e_os_climate.py
uv run python examples/smoke/e2e_asset_portfolio.py
uv run python examples/smoke/e2e_impact_portfolio.py
```

## Notes

- The portfolio track reads checked-in Parquet fixtures and is fully offline.
  Its multi-scenario cases are sensitivity stresses, not calibrated projections.
- The areal track still fetches public boundary / raster inputs from
  geoBoundaries, JRC, and Overture.
- Cached notebook outputs under `notebooks/data/` are gitignored.
- Pipeline outputs land in `pipeline_output/` (also gitignored).
- GitHub's notebook preview cannot run JS, so Plotly figures emit a static PNG
  fallback via kaleido when notebooks are executed locally before commit.
