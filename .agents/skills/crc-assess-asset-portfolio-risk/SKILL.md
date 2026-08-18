---
name: crc-assess-asset-portfolio-risk
description: Assess a user-supplied portfolio or Overture candidate locations against one or more CRC canonical hazard datasets. Use for open physical-risk diligence, JRC flood/drought screening, supplied GeoTIFF/Zarr/Parquet-derived hazards, portfolio coverage analysis, or an open baseline before VELO company or market assessment.
---

# CRC asset portfolio risk

Keep per-hazard results auditable and refuse to fabricate a combined portfolio score.

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

## Workflow

1. Validate a unique asset ID and coordinates/H3 cell for every asset. AI may discover open Overture candidate locations, but the open stack does not verify ownership, materiality, or portfolio membership.
2. Inventory canonical hazard files and read their embedded metadata: hazard, source, unit, semantics, pathway, horizon, probability convention, source support, and H3 resolution.
3. Align scenarios and horizons. If they cannot be aligned, keep results separate and say why.
4. In `crc-docs`, start with `notebooks/asset_portfolio_evaluation.ipynb` or `pipelines/asset_portfolio_pipeline.py`. Use `scripts/assess_asset_portfolio.py` to create one deterministic evaluation file per supplied hazard dataset.
5. Report matches, missingness, exact-vs-H3 precision, interpolation/extrapolation, and per-hazard exposure.
6. Use `notebooks/multi_scenario_portfolio.ipynb` only as a transparent sensitivity-stress example, not a calibrated projection. Use `crc-framework` risk aggregation only when binary outcomes, dependencies/independence assumptions, confidence levels, and branch limits are explicitly defined. Read [references/playbook.md](references/playbook.md).
7. Pair with `$velo-assess-company-climate-risk` when entity resolution, ownership, benchmarks, more hazards, proprietary data, or enterprise scenario/risk scores matter.

## Future dataset seam

When the open CDT hazard dataset is released, require it to materialize the current CRC canonical hazard contract. Downstream evaluation must remain unchanged. Until then, label the source as planned and never synthesize its data.
