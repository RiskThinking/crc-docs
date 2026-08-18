# Gap backlog

## CRC-side workflow gaps

| Priority | Gap | Why it unlocks use cases | Suggested increment |
|---|---|---|---|
| P0 | Multi-hazard portfolio orchestration | Finance and insurance users currently must stitch single canonical datasets together | Add `PortfolioAssessment` over multiple `HazardDataset` objects with scenario alignment, missingness policy, and bounded branch computation |
| P0 | Assessment manifest and evidence export | Model-risk, compliance, and sales demos need one auditable artifact | Emit JSON containing package/data versions, hashes, filters, units, probability convention, impact functions, warnings, row counts, and unresolved assets |
| P0 | Dataset onboarding workflow | Zarr/GeoTIFF/Parquet primitives are capable but too low-level for new community datasets | Add `HazardDataset.from_raster/from_zarr/from_table` builders with schema validation, fit policy, coverage estimate, and conformance fixtures |
| P0 | Future open CDT adapter | Preserves one downstream workflow across open and proprietary fronts | Map the released dataset directly into the canonical hazard contract; publish checksummed example subsets |
| P1 | Vulnerability/damage-function packs | Mortgage and insurance demos otherwise depend on ad hoc curves | Add versioned, cited residential/commercial/industrial curves with geography/building context and uncertainty bounds |
| P1 | Scenario/horizon crosswalk | Open sources and CDT pathways may not align | Add explicit scenario vocabulary, equivalence rules, and “not comparable” diagnostics |
| P1 | High-level decision playbooks | Users can calculate values but still need domain outputs | Add mortgage screen, insurance loss, corporate asset review, and compliance evidence workflow modules |
| P1 | Data quality and coverage report | Missing assets and spatial approximations can be mistaken for low risk | Add coverage, duplicate, exact-vs-H3, extrapolation, and fit-quality summaries |
| P2 | Geocoding and entity/ownership adapters | Required to move from borrower/company names to physical assets | Keep optional and modular; integrate open geocoders/entity data without making them core dependencies |
| P2 | Calibration/backtesting harness | Decision users need evidence that transforms and thresholds work | Add observed-event and claims/loss backtests with leakage-safe splits and versioned metrics |

## VELO/CDT-side gaps

| Priority | Gap | Demonstration impact | Suggested increment |
|---|---|---|---|
| P0 | Direct asset score helper | Public `velo-sdk` has asset lookup but climate scores are reached through company asset listings | Add `assets.get_climate_scores(asset_id, pathway, horizon)` and impact equivalent |
| P0 | Assessment/evidence export | Enterprise results need reproducibility and governance | Return method/data/model versions, query parameters, asset snapshot timestamp, warnings, and stable export IDs |
| P0 | MCP/SDK capability parity | Skills need deterministic discovery across tools | Publish a capability manifest and keep MCP tool names/arguments mapped to SDK methods |
| P1 | CRC canonical output crosswalk | Makes paired demos and customer migration credible | Export an optional normalized assessment table keyed by asset, hazard/index, pathway, horizon, metric, and unit |
| P1 | Read-only upload preview and job status | Organization asset onboarding is mutation-heavy and asynchronous | Add validation/preview, explicit commit, job status, and idempotency keys |
| P1 | Coverage/exclusion diagnostics | “No score” must not look like “no risk” | Return missing hazards, low-confidence assets, geocoding ambiguity, and unavailable scenarios |
| P2 | Bring-your-own-hazard through CRC | Lets customers combine proprietary coverage with internal hazards | Accept canonical CRC datasets into controlled enterprise workflows with lineage isolation |

## Quality gates for all demos

1. No silent asset drops.
2. No silent return-period extrapolation.
3. No historical/future scenario substitution.
4. No score-to-decision threshold without owner-approved policy.
5. No live upload, company creation, or external write without explicit authorization.
6. Every result includes source, version, timestamp, units, assumptions, and limitations.

