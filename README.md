# Climate Risk Commons Documentation

Start with an AI-assisted climate-risk demonstration, route into the relevant
playbook, and only then descend into the open
[`crc-sdk`](https://pypi.org/project/crc-sdk/) and
[`crc-framework`](https://pypi.org/project/crc-framework/) implementation.
Each open CRC baseline has a higher-calibre VELO/CDT enterprise twin.

## Start here: copy a prompt

- Link [`RiskThinking/crc-docs`](https://github.com/RiskThinking/crc-docs) into an AI tool that can reference repository files
- Start with only the skill name; the AI will ask for the minimum information it needs
- Optionally include the target or advanced assumptions you already know

Note: to run an enterprise twin, connect the [`CDT Express MCP server`](https://github.com/RiskThinking/cdt-express-mcp) in your AI tool using `https://mcp.riskthinking.ai/mcp`, complete the VELO OAuth flow, and enable its tools for the chat. Do not paste an API key into the conversation. Each VELO/CDT skill declares this remote server as a dependency, discovers its supported tool schemas, and guides the relevant read-only calls.

| Decision | Open CRC baseline | VELO/CDT enterprise twin |
|---|---|---|
| **Mortgage / collateral** | **Start:** `Use $crc-screen-mortgage-flood.`<br>**Optional:** `Use $crc-screen-mortgage-flood for Toronto, Canada.` | **Start:** `Use $velo-underwrite-property-climate.`<br>**Optional:** `Use $velo-underwrite-property-climate for 392 Markham Street, Toronto.` |
| **Insurance** | **Start:** `Use $crc-model-flood-insurance-loss.`<br>**Optional:** `Use $crc-model-flood-insurance-loss for Rotterdam using my attached portfolio and approved depth-damage curve.` | **Start:** `Use $velo-triage-portfolio-insurability.`<br>**Optional:** `Use $velo-triage-portfolio-insurability for Example Insurance Holdings.` |
| **Corporate finance / investment** | **Start:** `Use $crc-assess-asset-portfolio-risk.`<br>**Optional:** `Use $crc-assess-asset-portfolio-risk for Frankfurt, with flood and drought.` | **Start:** `Use $velo-assess-company-climate-risk.`<br>**Optional:** `Use $velo-assess-company-climate-risk for the S&P 500.` |

After running both sides for the same real target:

```text
Use $compare-crc-velo-assessments.
```

The skill will use the paired outputs already in the conversation when they are
unambiguous. Advanced users can attach or name the two artifacts explicitly.

If you want the AI to choose for you, begin with:

```text
Which CRC/VELO skill should I use for my climate-risk question?
```

## Peel down into the playbooks

A bare skill invocation starts a guided intake. The selected `SKILL.md` owns the
workflow, guardrails, scripts, and safe defaults—including source, bounds,
scenario discovery, and demo configuration—so non-experts are not asked for
technical parameters the AI can determine. Any values supplied by an advanced
user override those defaults when valid. An agent should load the selected
pair—not every skill in the repository—and add the comparison skill only after
both outputs exist.

| Decision | Load these playbooks |
|---|---|
| Mortgage / collateral | [`crc-screen-mortgage-flood`](.agents/skills/crc-screen-mortgage-flood/SKILL.md) → [`velo-underwrite-property-climate`](.agents/skills/velo-underwrite-property-climate/SKILL.md) |
| Insurance | [`crc-model-flood-insurance-loss`](.agents/skills/crc-model-flood-insurance-loss/SKILL.md) → [`velo-triage-portfolio-insurability`](.agents/skills/velo-triage-portfolio-insurability/SKILL.md) |
| Corporate finance / investment | [`crc-assess-asset-portfolio-risk`](.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md) → [`velo-assess-company-climate-risk`](.agents/skills/velo-assess-company-climate-risk/SKILL.md) |
| Reconciliation / sales engineering | [`compare-crc-velo-assessments`](.agents/skills/compare-crc-velo-assessments/SKILL.md) |

For an open baseline without supplied files, the AI should:

1. Resolve and show narrow WGS84 bounds for the requested area.
2. Materialize the applicable JRC source through the mature CRC adapter: EFAS
   for European flood, GloFAS for global flood, or EDO for drought. When no
   high-level adapter exists, use CRC's Zarr, GeoTIFF/raster, NetCDF,
   Parquet/Arrow, JSON, DuckDB, H3, and fitting primitives to create a canonical
   hazard dataset with explicit provenance.
3. Query the latest Overture Places STAC release for relevant categories and
   confidence, filtering candidates to modeled hazard geometry. Preserve the
   [required Overture attribution](https://docs.overturemaps.org/attribution/).
4. State that Overture candidates establish geographic locations only—not
   ownership, portfolio membership, collateral, occupancy, replacement value,
   or insurable interest. Uncovered or excluded candidates are not “no risk.”
5. Read scenario, units, support, and source version from canonical JRC metadata
   before evaluation; never guess or silently combine them.

The VELO/CDT twins do not need local CSV or Parquet inputs. Prefer the remote
CDT Express MCP server at `https://mcp.riskthinking.ai/mcp`; its OAuth flow
authorizes access without exposing a CDT key to the AI tool. The skills discover
companies, indices, assets, pathways, and horizons from available tool schemas
and responses. `velo-sdk` remains a local fallback for capabilities not exposed
by the connected MCP version. Never paste `CDT_API_KEY` or
`RISKTHINKING_API_KEY` into a chat or substitute synthetic JSON for live
evidence.

## Run the open demonstration

The runner executes the same acquisition path for Cologne: JRC EFAS first,
Overture candidates inside modeled coverage second, then the mortgage,
insurance-loss, portfolio, and comparison workflows.

```shell
uv sync
./ai-playbooks/examples/run-open-demo.sh
```

The first run needs network access and can take several minutes; later runs
reuse the source cache. Generated files land under the gitignored
`pipeline_output/ai-playbooks/` directory:

| Output | Meaning |
|---|---|
| `jrc_depths_by_cell.parquet` | Canonical JRC flood curves with embedded provider, release, pathway, horizon, units, support, and spatial metadata. |
| `overture-assets.csv` | Covered candidate locations with Overture IDs, names, categories, confidence, release, and attribution. |
| `mortgage-flood.parquet` | Return-period flood depths at candidate coordinates. |
| `flood-loss.parquet` | Damage ratios from the explicitly illustrative demo curve—not pricing, reserving, or capital. |
| `portfolio/flood.parquet` | Per-location CRC flood evaluation. |
| `comparison-inventory.json` | A file-shape smoke test beside synthetic VELO-shaped JSON—not a live, target-aligned comparison. |

To change the geography, have the AI resolve and show bounds, choose EFAS or
GloFAS, and pass both to the runner. For example:

```shell
./ai-playbooks/examples/run-open-demo.sh \
  glofas -79.42 43.63 -79.36 43.68 \
  pipeline_output/ai-playbooks-toronto
```

For a decision-facing assessment, replace Overture candidates with an authorized
asset or exposure export while retaining the canonical hazard acquisition and
provenance checks.

## Why run the enterprise twin?

CRC provides a transparent, extensible baseline over open or user-authorized
data. VELO/CDT adds proprietary asset and ownership intelligence, broader and
finer hazard coverage, future pathways and horizons, multi-factor modelling,
aggregation, and benchmarks.

The comparison playbook keeps the relationship credible: it aligns common
dimensions, labels capability lift, and refuses to equate metrics whose semantics
differ. CRC is the target open foundation for an increasing share of the
VELO/CDT pipeline; this repository does not claim complete implementation parity.

## Go deeper: run and tune the implementation

Use the local environment to inspect provenance, substitute data, tune
assumptions, extend a workflow, or understand how a playbook maps to CRC
primitives and VELO/CDT calls.

Install the open examples:

```shell
uv sync
```

Add proprietary `velo-sdk` examples when authorized:

```shell
uv sync --extra velo
```

Notebooks expect their working directory to be `notebooks/`; headless pipelines
run from the repository root:

```shell
uv run jupyter lab notebooks/
uv run python pipelines/asset_portfolio_pipeline.py
```

### Areal / spatial analytics

These workflows acquire and canonicalize hazard data for a selected geography.

| Notebook | Pipeline twin | What it shows |
|---|---|---|
| [`notebooks/flood_risk_by_province.ipynb`](notebooks/flood_risk_by_province.ipynb) | [`pipelines/flood_admin_pipeline.py`](pipelines/flood_admin_pipeline.py) | EFAS area selection → pinned AOI cache → canonical curves → H3/admin join → Overture places → PMTiles |
| [`notebooks/jrc_global_flood_hazard.ipynb`](notebooks/jrc_global_flood_hazard.ipynb) | [`pipelines/jrc_flood_pipeline.py`](pipelines/jrc_flood_pipeline.py) | EFAS/GloFAS selection → pinned AOI cache → fitted curves → return-period evaluation |
| [`notebooks/jrc_edo_drought_index.ipynb`](notebooks/jrc_edo_drought_index.ipynb) | [`pipelines/jrc_drought_pipeline.py`](pipelines/jrc_drought_pipeline.py) | EDO SMI area/year selection → annual-minimum AOI cache → lower-tail curves → support-aware evaluation |

### Asset portfolio analytics

This ordered technical track uses checked-in Cologne fixtures so the core CRC
mechanics can be studied offline. Those fixtures are regression and learning
inputs; the user-facing AI playbooks above acquire Overture and JRC data.

| # | Notebook | Pipeline twin | What it shows |
|---|---|---|---|
| 1 | [`notebooks/hurdle_fit_primer.ipynb`](notebooks/hurdle_fit_primer.ipynb) | — | Reconstruct a canonical hurdle + sample diagnostics |
| 2 | [`notebooks/asset_portfolio_evaluation.ipynb`](notebooks/asset_portfolio_evaluation.ipynb) | [`pipelines/asset_portfolio_pipeline.py`](pipelines/asset_portfolio_pipeline.py) | `HazardDataset` portfolio return-period evaluation |
| 3 | [`notebooks/portfolio_impact.ipynb`](notebooks/portfolio_impact.ipynb) | [`pipelines/portfolio_impact_pipeline.py`](pipelines/portfolio_impact_pipeline.py) | Event-aligned `PiecewiseLinearImpact` → damage ratio and derived currency damage |
| 4 | [`notebooks/portfolio_risk_metrics.ipynb`](notebooks/portfolio_risk_metrics.ipynb) | [`pipelines/portfolio_risk_pipeline.py`](pipelines/portfolio_risk_pipeline.py) | Microscores → portfolio VaR / CVaR + attribution |
| 5 | [`notebooks/multi_scenario_portfolio.ipynb`](notebooks/multi_scenario_portfolio.ipynb) | [`pipelines/multi_scenario_pipeline.py`](pipelines/multi_scenario_pipeline.py) | Historical vs transparent local tail stresses in one evaluation |

Change the geography, portfolio, canonical hazard input, impact function, or
scenario assumptions while preserving provenance, units, probability semantics,
coverage diagnostics, and non-equivalence warnings.

## Design, gaps, and verification

These are specialist references rather than required reading for a first run:

- [Product strategy](ai-playbooks/docs/product-strategy.md): open foundation,
  enterprise lift, and domain prioritization.
- [Capability matrix](ai-playbooks/docs/capability-matrix.md): verified open and
  proprietary surfaces plus important non-equivalences.
- [Gap backlog](ai-playbooks/docs/gap-backlog.md): low-hanging CRC and VELO/CDT
  workflow improvements.
- [Dogfood verification](ai-playbooks/docs/dogfood-verification.md): target
  flexibility, regression coverage, and live open-bootstrap evidence.

Cached notebook outputs under `notebooks/data/` and pipeline outputs under
`pipeline_output/` are gitignored. GitHub cannot execute notebook JavaScript, so
locally executed Plotly figures include a static PNG fallback through Kaleido.
