# Capability matrix

Baseline checked on 2026-09-15: published [crc-sdk 0.7.1](https://pypi.org/project/crc-sdk/0.7.1/)
and [crc-framework 0.2.5](https://pypi.org/project/crc-framework/0.2.5/).
The repository lockfile pins the tested environment. Runtime validation and its
limits are recorded in [verification](dogfood-verification.md).

## Open computation and workflows

| Capability | Available surface | Limits and example use |
|---|---|---|
| Probability and fitting | Framework empirical, tabulated, fitted, hurdle and point-mass distributions; explicit fitting and diagnostics | A hurdle's dry-event atom is a modelling assumption. Inspect fit policy and source support; do not assume every source row has a parametric fit. |
| Canonical hazard storage | SDK Arrow/Parquet contract, metadata, validation and streaming writers | Schema 1.2 adds tabulated probability/value lists and explicit `no_data` reason codes alongside fitted, hurdle and point-mass rows. Use SDK readers/evaluators instead of extracting only scalar fit parameters. |
| Source acquisition | Lazy EFAS/GloFAS flood and EDO SMI drought plans with bounded areas, versioned caches and curated policies | Read resolved source, units, tail and support; summarize curve kinds and retain any available treatment diagnostics. Historical observations do not supply future climate projections. |
| Agricultural evidence | `AgriculturalLayer.usda_cdl()` and `.ftw_fields()` with bounded scans and the common DuckDB/Arrow processing surface | Crop samples and predicted fields do not establish yield, ownership or financial materiality. See the [agricultural playbook](../agricultural-climate-risk.md). |
| Other data | GeoTIFF/COG, Zarr, NetCDF, Arrow/Parquet, JSON/SQL through DuckDB; explicit canonical writers | Format access is available; an arbitrary dataset still needs a scientifically justified canonicalization policy. OS-Climate fixtures run locally; the live feed is not validated here. |
| Spatial processing | H3 indexing, source-geometry refinement, admin overlays, coverage/lookup writers and PMTiles | Point matching can refine H3 candidates against source WKB. H3-only assets retain cell precision; regional max/min summaries are not exact asset assessments. PMTiles needs external tiling tools. |
| Portfolio evaluation | `HazardDataset.local(...).for_assets(...).select(...).return_periods(...)` | One row per asset/hazard/scenario; ambiguous and unmatched joins raise. A matched `no_data` curve instead yields null values. Preserve both coverage and value availability. |
| Event-aligned impact | `.impact(...)`, framework transforms and registry-backed impacts with `ImpactContextColumns` | Evaluates the impact at each hazard return period. This is not necessarily a quantile of the transformed loss distribution. Registry availability does not establish applicability to an insured exposure. |
| Risk aggregation | Framework microscores, binary outcomes, spanning sets, VaR/CVaR and attribution | Basic branch construction assumes independent outcomes and grows as `2**n`; set branch limits. The example threshold model is not a full joint continuous-loss model. |
| Multi-hazard/scenario work | Scenario filters and multi-scenario canonical evaluation; repository wrapper loops over separate hazards | There is no automatic cross-hazard score, dependence calibration or scenario-equivalence policy. Keep incompatible results separate. |
| Evidence | Canonical source/evaluation metadata; agricultural manifest and preserved result files | A complete assessment-wide report, hashes, coverage exceptions and semantic comparison remain the skill's responsibility. |

The logical hazard key includes hazard, horizon, pathway, H3 cell and source ID;
a cell can intersect more than one source pixel. Ordered canonical writes sort
and validate keys using DuckDB, which may spill. `write_hazard_stream(...,
ordered=False)` offers validated direct streaming without global physical sort.
Neither option removes the need to budget memory, temporary disk and output size.

## VELO/CDT access

Prefer OAuth-connected CDT Express MCP and discover its current tool schemas.
The optional fallback scripts target `velo-sdk==0.0.20`; MCP and that pinned SDK
have different surfaces. API-double tests validate the scripts, not a live service.

| Problem | Enterprise route | Interpretation limit |
|---|---|---|
| Property assessment | Resolve asset identity; request asset climate scores and available location metrics | Direct asset scoring exists in MCP; the pinned SDK helper routes through the owner's asset scores. Location metrics are not automatically asset scores. |
| Company/index diligence | Resolve entity/index, obtain totals and bounded constituent/asset scores | Rankings and country/type concentrations are not factor attribution. Use explicit impact/factor responses when available. |
| Insurability triage | Retrieve in-scope asset metrics under one scenario; use documented platform classifications | The pinned SDK describes `cvar_95 >= 0.35` as “uninsurable” and `>= 0.75` as “stranded.” These are platform labels, not universal underwriting rules; verify current metric definitions. |
| Paired open/enterprise assessment | Map asset identity, source, hazard, scenario, unit and method | Flood depth, damage ratio, DCR and VaR/CVaR are not interchangeable. Use the [crosswalk](../../.agents/skills/compare-crc-velo-assessments/references/crosswalk.md). |

Enterprise hazard breadth, proprietary ownership data and future scenarios depend
on the connected service and entitlements. Confirm availability from returned
evidence rather than promising fixed coverage. No complete CRC/VELO implementation
parity is claimed.
