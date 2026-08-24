# Agricultural climate-risk playbook

Use this playbook to answer location-specific questions such as:

- Which sampled crop classes in an Iowa procurement area overlap modeled
  riverine-flood exposure?
- Which high-confidence predicted fields in a French sourcing region intersect
  lower-tail soil-moisture drought conditions?
- Where is agricultural coverage missing, uncertain, or spatially mismatched?

## Choose the agricultural evidence layer

Use USDA NASS CDL inside the conterminous United States when crop class matters.
Select a narrow AOI, one or more years, and only relevant class codes. Use the
30 m series for 2008–2025 continuity; use 10 m only for 2024–2025 questions
that need the native newer product. Treat code 0 as background and code 81 as
a real Clouds/No Data class.

Use FTW outside the US, or when field boundaries rather than crop type are the
needed unit. Preserve continuous confidence, the observation year, and field
area. FTW does not supply crop type, cadastral boundaries, tenure, ownership,
yield, or financial materiality. A confidence threshold is a screening policy,
not a statement that excluded places contain no fields.

## Pair with climate evidence

Choose EFAS flood for Europe, GloFAS flood elsewhere, and EDO Soil Moisture
Index where its coverage and lower-tail semantics answer the decision. Build
one canonical hazard Parquet per source, then let its embedded H3 resolution
control agricultural indexing. Do not relabel a historical hazard as a future
scenario, and do not compare flood depth with SMI numerically.

The agricultural pipeline materializes bounded GloFAS curves automatically when
`--hazard` is omitted, so the Iowa crop/flood example is one command:

```shell
uv run python pipelines/agricultural_climate_pipeline.py \
  --source usda --bounds -93.965 42.03 -93.91 42.085 --year 2025 \
  --crop-codes 1 5 --return-periods 10 100
```

For Europe, materialize EDO with `pipelines/jrc_drought_pipeline.py`, then run
the agricultural pipeline with `--source ftw --country-code <ISO2>`.

## Interpret the outputs

Keep agricultural observations, canonical hazard curves, and evaluated hazard
values as separate artifacts. Report:

- agricultural source, version, year, resolution, license, and filters;
- hazard source, release, pathway, horizon, unit, probability convention, and
  source support from embedded metadata;
- matched and missing agricultural units, with exact/H3 match labels;
- USDA sampled crop composition or FTW confidence/field area;
- return-period hazard values with interpolation/extrapolation warnings.

Use the source-aware summaries: USDA reports sampled pixels, crop share, and
pixel-weighted hazard values by crop and coverage status; FTW reports field
counts, observed field area, confidence, and area-weighted hazard values by
country, year, and coverage status. Do not create a combined "farm risk score"
without an authorized impact model, exposure values, and a documented
aggregation policy. Observed crop cover is not yield, production, revenue,
ownership, or vulnerability.

## Reproducible bundle

Retain `*-agricultural-units.parquet`, `*-hazard-evaluation.parquet`, the
agricultural/hazard map and source-aware summary Parquets, PMTiles, and
`manifest.json`. Add a CSV or GeoJSON only as a presentation derivative. The
notebook `notebooks/agricultural_climate_risk.ipynb` and pipeline
`pipelines/agricultural_climate_pipeline.py` are twins: use the notebook to
explore assumptions and the pipeline for repeatable/headless execution.
