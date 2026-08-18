# Asset portfolio playbook

Install `crc-sdk[geometry]==0.3.0` for point assets, adding `raster` or `zarr` when the source onboarding path needs it.

## Native crc-docs learning path

1. `notebooks/asset_portfolio_evaluation.ipynb` / `pipelines/asset_portfolio_pipeline.py` for return-period evaluation.
2. `notebooks/portfolio_impact.ipynb` / `pipelines/portfolio_impact_pipeline.py` for event-aligned impacts.
3. `notebooks/portfolio_risk_metrics.ipynb` / `pipelines/portfolio_risk_pipeline.py` for explicit risk aggregation.
4. `notebooks/multi_scenario_portfolio.ipynb` / `pipelines/multi_scenario_pipeline.py` for transparent local stress scenarios.

## Supported baseline patterns

- Local canonical hazard Parquet through `HazardDataset.local(...)`.
- JRC EFAS/GloFAS flood acquisition and canonicalization.
- JRC EDO Soil Moisture Index drought acquisition and canonicalization.
- Custom source onboarding through GeoTIFF/COG, Zarr, NetCDF, Parquet/Arrow, DuckDB, H3, and fitting primitives.

CSV/JSON business data can be read through DuckDB or converted to Arrow/Parquet, but the public package currently lacks one high-level “onboard arbitrary hazard table” workflow. Treat that as a workflow gap, not as missing low-level capability.

## Aggregation caution

`crc-framework` can compute spanning sets and VaR/CVaR from `BinaryOutcome` objects. Branches grow as `2**n`, and the basic spanning calculation treats factors as independent. Do not convert continuous hazard exposure into binary outcomes or combine factors without a documented policy/model.

## Minimum result manifest

- package versions;
- input asset hash/count;
- hazard dataset hash and embedded provenance;
- filters, return periods/probabilities, and units;
- impact function if any;
- spatial match and missingness summary;
- warnings and extrapolation;
- output file hash/count.
