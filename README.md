# Climate Risk Commons Documentation

Start with an AI-assisted climate-risk demonstration, route into the relevant
playbook, and only then descend into the open
[`crc-sdk`](https://pypi.org/project/crc-sdk/) and
[`crc-framework`](https://pypi.org/project/crc-framework/) implementation.
Each open CRC baseline has a higher-calibre VELO/CDT enterprise twin.

## Start here: copy a prompt

- Link [`RiskThinking/crc-docs`](https://github.com/RiskThinking/crc-docs) into an AI tool that can reference repository files
- Copy a prompt from the table below
- Replace `{placeholders}` for desired targets (e.g. `{city}, {country}` to `Toronto, Canada`)

| Decision | Open CRC baseline | VELO/CDT enterprise twin |
|---|---|---|
| **Mortgage / collateral** | Use `$crc-screen-mortgage-flood` for `{city}, {country}`. Resolve and show narrow WGS84 bounds. Choose JRC EFAS for Europe or GloFAS elsewhere, show the lazy plan, and ask before materializing it. Then source up to `{10}` relevant candidates from the latest Overture Places release, filtered to JRC source-geometry coverage. Report category, confidence, release, and that these are not verified collateral. Evaluate 25-, 100-, and 500-year flood depths; do not make a lending decision. | Use `$velo-underwrite-property-climate` for `{property name or VELO asset ID}` in `{city}, {country}`. Discover valid pathways and horizons, show ambiguous matches for selection, then assess `{pathway}` at `{horizon}`. Report identity evidence, multi-factor drivers, tail-risk metrics, and what the enterprise result adds beyond the JRC screen. |
| **Insurance** | Use `$crc-model-flood-insurance-loss` for open candidate locations in `{city}, {country}`. Materialize canonical JRC flood data, then source Overture candidates for the same bounds filtered to modeled JRC coverage. Read pathway and horizon from the metadata. Use our approved `{depth/damage knots}`; if none are supplied, use the repository's illustrative knots and label the result non-production. Preserve event-aligned return periods and state that Overture candidates are not an insured portfolio. | Use `$velo-triage-portfolio-insurability` for `{company or company ID}` under `{pathway}` at `{horizon}`. Resolve supported values first. List VELO-classified uninsurable and stranded assets, overlap, countries, asset types, and coverage exceptions. Keep platform classifications separate from underwriting policy. |
| **Corporate finance / investment** | Use `$crc-assess-asset-portfolio-risk` for `{city/region}`. Resolve and show bounds, then materialize applicable JRC hazards: EFAS/GloFAS flood and, when relevant, EDO drought. Source Overture candidates inside hazard coverage using categories relevant to `{business question}`; disclose that ownership and materiality are unverified. Keep hazards separate when horizons or semantics differ and do not fabricate a combined score. | Use `$velo-assess-company-climate-risk` for `{company}` or market index `{index}`. Show matching candidates before selection. Compare `{pathway A}` with `{pathway B}` at `{horizon}`, then report total score, factor attribution, country concentration, asset-type concentration, coverage exceptions, and the capability lift over the Overture/JRC baseline. |

After running both sides for the same real target:

```text
Use $compare-crc-velo-assessments on {crc-output.parquet} and
{velo-output.json}. Align asset/entity, hazard/factor, pathway, horizon, metric,
unit, spatial precision, and source version. Classify each comparison as direct,
directional, capability-lift-only, or not comparable. Explain whether the added
enterprise evidence changes the decision and record reproducible gaps.
```

If you want the AI to choose for you, begin with:

```text
Inspect .agents/skills/ in this repository. For my
{mortgage / insurance / investment} question, recommend an open CRC skill and
its VELO/CDT twin, explain the evidence each can provide, and list required
approvals or credentials. Do not materialize data yet.
```

## Peel down into the playbooks

The prompt gives the AI the decision and target. The selected `SKILL.md` supplies
the workflow, guardrails, scripts, and deeper domain reference. An agent should
load the selected pair—not every skill in the repository—and add the comparison
skill only after both outputs exist.

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

The VELO/CDT twins do not need local CSV or Parquet inputs. They require an
authorized MCP connection or `velo-sdk` configuration, then discover companies,
indices, assets, pathways, and horizons from the connected service. Never paste
`RISKTHINKING_API_KEY` into a chat or substitute synthetic JSON for live evidence.

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
