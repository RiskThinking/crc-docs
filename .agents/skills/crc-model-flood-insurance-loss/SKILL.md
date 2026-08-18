---
name: crc-model-flood-insurance-loss
description: Apply an explicit depth-damage function to a CRC canonical flood dataset for an insured property portfolio. Use when the user asks for transparent flood damage ratios, event-aligned impacts, insurance exposure screening, vulnerability assumptions, or an open baseline to pair with VELO portfolio insurability triage.
---

# CRC flood insurance loss

Model hazard-to-damage transparently. Do not call the result a premium, technical price, reserve, or regulatory capital requirement.

## Guided intake

Treat `Use $crc-model-flood-insurance-loss` as a complete invocation. Reuse
clear targets and attachments; otherwise ask one question: “Which portfolio or
area should I assess, and is this an exploratory demonstration or a
decision-facing analysis?” For a demonstration, infer the narrow AOI, JRC
EFAS/GloFAS source, covered Overture candidates, standard return periods, and
the illustrative curve documented below. Do not ask for bounds, paths, source
products, or raw scenario identifiers. For decision-facing work, require an
authorized exposure set and approved curve. Read pathway and horizon from
metadata; if several valid scenarios remain, recommend a concise choice and ask
only then. Never mix scenarios. Valid advanced inputs override defaults.

## Demo bootstrap

When the user supplies no files, materialize canonical JRC EFAS/GloFAS for a
narrow, user-visible AOI, then use `pipelines/overture_assets_pipeline.py` with
`--coverage-hazard` to source candidate locations inside modeled geometry. Use
depth knots `0,0.2,1,2` metres and damage-ratio knots
`0,0,0.25,1` only as an explicitly illustrative curve. Write beneath
`pipeline_output/`. Overture records are not an insured portfolio, and real
analysis requires authorized exposures and an applicable, approved curve.

## Workflow

1. Require a CRC canonical flood Parquet file and an asset CSV with `asset_id`, `longitude`, and `latitude`.
2. Obtain an approved depth-damage curve with depth and damage-ratio knots. If none is supplied, use an illustrative curve only and label every result non-production.
3. Require exactly one pathway and horizon, then select both before evaluating return periods. Never let a multi-scenario canonical file silently expand the loss output.
4. Read [references/playbook.md](references/playbook.md) to preserve the event-aligned return-period interpretation.
5. For the user-facing open demo, acquire Overture candidates and canonical JRC flood as described above, then run `scripts/model_flood_loss.py`. Use `notebooks/portfolio_impact.ipynb` or `pipelines/portfolio_impact_pipeline.py` only for a technical, checked-in learning example.
6. Check source units/semantics, curve applicability, building/geography context, spatial matching, missing assets, and extrapolation.
7. If asset values are supplied, calculate currency loss only as an explicitly derived field and retain the damage ratio. Never infer coverage terms, deductibles, limits, or business interruption.
8. Use `pipelines/portfolio_risk_pipeline.py` only when the requested decision requires explicitly constructed binary outcomes and VaR/CVaR. Pair the result with `$velo-triage-portfolio-insurability` for multi-hazard portfolio triage and VELO platform classifications.

## Required output

Include the exact curve knots/version/source, event-aligned semantics, asset coverage, damage ratios by return period, concentration observations, uncertainty/limitations, and recommended calibration or engineering review.
