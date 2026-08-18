# Capability matrix

Status reflects the public package surfaces verified on 2026-08-18 plus the product context supplied for this project.

| Capability | CRC open stack | VELO/CDT enterprise | Demonstration implication |
|---|---|---|---|
| Computation core | Distributions, explicit curve fitting, impact transforms, microscores, spanning sets, VaR/CVaR, attribution | Enterprise scores and impacts are delivered through VELO/CDT | Explain CRC as the open computational foundation and VELO/CDT as the industrialized data/product layer |
| Flood data | JRC GloFAS and EFAS lazy ingestion and canonicalization | Broader proprietary hazard catalogue and finer coverage | Pair every open flood screen with a multi-hazard enterprise run |
| Drought data | JRC EDO Soil Moisture Index workflow | Broader hazard/scenario coverage | Use CRC for transparent drought screening; use VELO/CDT when business impact needs multiple interacting factors |
| Arbitrary data | Canonical Parquet; GeoTIFF/COG, Zarr, NetCDF, DuckDB/Arrow and geometry primitives | API/MCP-managed datasets and assets | CRC can onboard customer/open data, but needs more high-level recipes and validation |
| OS-Climate | Provider code exists; project context says the feed is currently unplugged | Not required for the proprietary route | Mark unavailable until a live integration test passes |
| Asset input | Caller supplies assets, or AI sources Overture candidate locations by AOI/category for an open demonstration | Public and organization companies/assets, ownership, indexes | Overture supports geographic screening but does not establish ownership, materiality, collateral, value, or portfolio membership |
| Hazard breadth | Currently concrete public workflows for riverine flood and SMI drought | Product site states 50+ hazards and multi-factor scenario data | Do not imply CRC parity; show the delta explicitly |
| Scenario support | Canonical horizon/pathway fields; depends on source data | Pathways and decadal horizons exposed by SDK | Align scenarios before comparison; historical JRC results are not future-scenario equivalents |
| Spatial precision | H3 plus exact source-geometry refinement when WKB is present | Asset-level proprietary data and finer hazard granularity | Report `spatial_match` and source resolution in the baseline |
| Portfolio metrics | Low-level binary outcomes, spanning sets, VaR/CVaR; single-dataset portfolio evaluation | Company/index scores, asset scores, country/type aggregation, impact attribution | CRC needs a high-level multi-hazard portfolio workflow |
| Insurability | User-defined impact curves and transparent risk primitives | SDK exposes “uninsurable” (`cvar_95 >= 0.35`) and “stranded” (`cvar_95 >= 0.75`) company-asset lists | Treat VELO labels as platform classifications, not universal actuarial definitions |
| Evidence and provenance | Canonical hazard/evaluation metadata and pinned source caches | API responses; public SDK does not expose a complete evidence bundle | Add a cross-stack assessment manifest and version/method export |
| Authentication | None for public/local data unless the source requires it | API key / remote MCP | Never place credentials in skill content or outputs |

## Important non-equivalences

- JRC flood depth at a return period is not the same object as VELO DCR, expected impact, VaR, or CVaR.
- Historical open observations are not interchangeable with a future climate pathway/horizon.
- A user-supplied coordinate or Overture candidate is not automatically equivalent to VELO's resolved physical asset or ownership record.
- A custom depth-damage ratio is not the same as VELO's proprietary impact model.
