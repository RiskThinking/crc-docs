---
name: crc-assess-asset-portfolio-risk
description: Assess a user-supplied portfolio or Overture candidate locations against one or more CRC canonical hazard datasets. Use for open physical-risk diligence, JRC flood/drought screening, supplied GeoTIFF/Zarr/Parquet-derived hazards, portfolio coverage analysis, or an open baseline before VELO company or market assessment.
---

# CRC asset portfolio risk

Keep per-hazard results auditable and refuse to fabricate a combined portfolio score.

## Before each assessment: refresh from the canonical source

This installed copy is a bootstrap for `RiskThinking/crc-docs`. Before executing
an assessment, resolve `main` at
`https://api.github.com/repos/RiskThinking/crc-docs/commits/main` using an available
GitHub, web-fetch or Git tool. Record the returned full commit SHA, then load
`https://raw.githubusercontent.com/RiskThinking/crc-docs/<sha>/.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md`
and its required linked files from that same commit. Follow that version for this
run; see its `ai-playbooks/docs/skill-refresh.md` for resolution and provenance.
Do this once per new assessment, not recursively when reading the fetched skill.
An explicit user-pinned revision or requested local development copy takes
precedence and must be labelled. If the commit or required files cannot be
verified, report the limitation and stop assessment execution; never silently
use an older installed copy. This refreshes the run, not the host's installation.

## Guided intake

Treat naming this skill in plain language, or any platform selector
(`$crc-assess-asset-portfolio-risk`, `/crc-assess-asset-portfolio-risk`,
`@crc-assess-asset-portfolio-risk`), as a complete invocation. Reuse a
clear target, portfolio, and decision context; otherwise ask one question:
“Which portfolio or geographic area should I assess, and what decision should
the screen inform?” For a generic geographic demonstration, default to riverine
flood, resolve a narrow AOI, choose EFAS in Europe or GloFAS elsewhere, and
source up to 10 covered Overture candidates at confidence 0.8. Add EDO drought
when the question or geography makes it relevant. Do not ask non-experts for
bounds, H3 resolution, adapters, file paths, raw scenario identifiers, or
Overture categories unless a material ambiguity remains. State inferred choices
before materialization; valid advanced inputs override them.

## Demo bootstrap

When no inputs are supplied, materialize JRC flood through the EFAS/GloFAS
workflow for user-visible bounds, then use
`pipelines/overture_assets_pipeline.py --coverage-hazard <jrc.parquet>` to source
covered candidate locations. When drought is relevant, materialize JRC EDO through
`pipelines/jrc_drought_pipeline.py`. Evaluate each canonical output with its
actual metadata; do not force differing horizons into an equivalence. Write
beneath `pipeline_output/`. Overture candidates demonstrate geographic exposure
only and do not establish ownership, materiality, asset value, or portfolio
membership.

## Execution reference

Use the repository's [setup](../../../ai-playbooks/docs/setup.md) and
[capability matrix](../../../ai-playbooks/docs/capability-matrix.md) for the
tested package baseline and output contract. Run repository-relative commands
from the `crc-docs` root. Helpers produce intermediate data; complete the
reporting and interpretation steps below in the assistant workflow.

## Workflow

1. Validate a unique asset ID and coordinates/H3 cell for every asset. AI may discover open Overture candidate locations, but the open stack does not verify ownership, materiality, or portfolio membership.
2. Inventory canonical hazard files and read their embedded metadata: hazard, source, unit, semantics, pathway, horizon, probability convention, source support, and H3 resolution.
3. Align scenarios and horizons. If they cannot be aligned, keep results separate and say why.
4. In `crc-docs`, start with `notebooks/asset_portfolio_evaluation.ipynb` or `pipelines/asset_portfolio_pipeline.py`. Use `scripts/assess_asset_portfolio.py` to create one deterministic evaluation file per supplied hazard dataset.
5. Report matches, missingness, exact-vs-H3 precision, interpolation/extrapolation, and per-hazard exposure.
6. Use `notebooks/multi_scenario_portfolio.ipynb` only as a transparent sensitivity-stress example, not a calibrated projection. Use `crc-framework` risk aggregation only when binary outcomes, dependencies/independence assumptions, confidence levels, and branch limits are explicitly defined. Read [references/playbook.md](references/playbook.md).
7. Pair with `$velo-assess-company-climate-risk` when entity resolution, ownership, benchmarks, more hazards, proprietary data, or enterprise scenario/risk scores matter.

## Deliverable bundle

Retain one canonical evaluation Parquet per hazard; never replace these with a
presentation-only aggregate. Also create a joined analysis-ready CSV, GeoJSON,
and self-contained HTML report plus a manifest describing every source,
scenario, unit, and non-equivalence. In the response, show a compact table with
asset, hazard, match status, selected metric, unit, pathway, and horizon, sorted
within—not across—incompatible hazards. Include:

- a portfolio map with a hazard selector or small multiples, marking missing
  and extrapolated assets explicitly; and
- per-hazard exposure/concentration charts, with separate panels when units,
  horizons, or semantics differ.

Make the full table and visuals downloadable when supported. Use a bounded,
clearly disclosed top-risk subset only for readability; keep all rows in the
artifacts. Do not fabricate a combined score or silently geocode missing assets.

## Future dataset seam

When the open CDT hazard dataset is released, require it to materialize the current CRC canonical hazard contract. Downstream evaluation must remain unchanged. Until then, label the source as planned and never synthesize its data.
