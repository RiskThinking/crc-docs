# Mortgage flood playbook

Install `crc-sdk[geometry,raster]==0.3.0`. Point-to-H3 conversion needs the geometry extra; JRC GeoTIFF acquisition needs the raster extra.

## Native crc-docs examples

- `notebooks/jrc_global_flood_hazard.ipynb` and `pipelines/jrc_flood_pipeline.py` demonstrate GloFAS acquisition and fitted return-period curves.
- `notebooks/flood_risk_by_province.ipynb` and `pipelines/flood_admin_pipeline.py` demonstrate EFAS spatial aggregation.
- Use the bundled asset script when the decision object is collateral rather than an AOI.

## Inputs

- Asset route: use an authorized CSV, or use
  `pipelines/overture_assets_pipeline.py` to source open candidate locations for
  a demonstration. Overture Places does not establish ownership, collateral,
  occupancy, value, or insurable interest.
- CSV columns: `asset_id`, `longitude`, `latitude`; retain loan/property or
  Overture provenance fields only when appropriate for the output.
- AOI bounds: `min_lon min_lat max_lon max_lat` in WGS84.
- Source: EFAS for Europe; GloFAS elsewhere.
- H3 resolution: default to 9 for asset-level flood acquisition, matching
  `pipelines/jrc_flood_pipeline.py`; record any explicit override in outputs.
- Return periods: choose decision-relevant periods within the resolved source support where possible.

## Interpretation

CRC evaluates upper-tail return period `T` at non-exceedance probability `1 - 1/T`. The output is hazard depth, not probability of default, loan loss, damage, or insurability.

`spatial_match=exact_geometry` indicates refinement against stored source geometry. `spatial_match=h3_cell` is cell-level precision. Multiple matches raise; missing matches raise rather than being silently dropped.

## Decision memo outline

1. Question and scope.
2. Data and source release.
3. Asset coverage and spatial precision.
4. Depths by return period.
5. Interpolation/extrapolation and modelling assumptions.
6. Items requiring borrower evidence or engineering review.
7. Enterprise escalation: additional hazards, scenarios, asset resolution, and risk metrics requested from VELO/CDT.
