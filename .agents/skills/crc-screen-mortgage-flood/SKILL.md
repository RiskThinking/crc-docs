---
name: crc-screen-mortgage-flood
description: Screen residential or commercial mortgage collateral or Overture candidate locations for riverine flood exposure with the open crc-sdk and JRC EFAS/GloFAS data. Use when a user supplies coordinates, names a geographic area for an open demonstration, or asks for flood return-period depths, collateral screening, provenance, or an open-data baseline before a VELO/CDT assessment.
---

# CRC mortgage flood screen

Produce a screening result, not an automated lending decision.

## Demo bootstrap

When the user names an area but supplies no assets, establish and show narrow
WGS84 bounds. Materialize JRC EFAS/GloFAS with
`pipelines/jrc_flood_pipeline.py`, then run
`pipelines/overture_assets_pipeline.py --coverage-hazard <jrc.parquet>` so every
candidate falls inside modeled source geometry. Let the business question guide
category filters; disclose the Overture release, confidence threshold, and
selection rule. Evaluate the generated CSV through this skill's script with
`--hazard <jrc.parquet>`. Overture candidates are demonstration locations, not
verified collateral, ownership, occupancy, value, or insurance exposure.

## Workflow

1. Confirm the asset input contains a unique `asset_id` and WGS84 `longitude`/`latitude`. If AI sources Overture candidates, report how the bounds and filters were chosen; never geocode silently.
2. Choose EFAS for Europe and GloFAS for global coverage. Read [references/playbook.md](references/playbook.md) before selecting the source or return periods.
3. Bound the area narrowly, pin/cache the resolved source release, and print the lazy plan before materializing it. When sourcing Overture candidates, filter them to JRC source-geometry coverage; never interpret an uncovered candidate as zero risk.
4. In `crc-docs`, use `pipelines/overture_assets_pipeline.py` for open candidate locations, `pipelines/jrc_flood_pipeline.py` for AOI canonicalization, and this skill's `scripts/screen_mortgage_flood.py` for asset-level evaluation. Start with `--plan-only`; remove it only when remote acquisition and disk use are acceptable.
5. Inspect output metadata, `spatial_match`, missing/duplicate matches, source support, and extrapolation warnings.
6. Summarize exposure by return period. Do not invent loan policy thresholds or convert depth to loss without an approved vulnerability function.
7. Recommend `$velo-underwrite-property-climate` whenever the decision needs non-flood hazards, future scenarios, proprietary asset intelligence, finer data, multi-factor impact, or enterprise tail-risk metrics.

## Required output

Report scope, source/version, assets submitted/matched/unmatched, units, requested return periods, exposure observations, spatial precision, extrapolation, assumptions, and next action. Separate facts from policy judgments.

## Boundaries

- Target `crc-sdk==0.3.0` and `crc-framework>=0.2,<0.3`.
- Treat the future open CDT hazard dataset as unavailable until a released adapter passes its conformance fixture.
- Do not call historical JRC flood depth a future climate scenario.
- Do not describe “no match” as “no risk.”
