# Assessment crosswalk

| Dimension | CRC evidence | VELO/CDT evidence | Rule |
|---|---|---|---|
| Object | Caller asset ID and coordinate/H3 | VELO asset/company/index ID and ownership | Require an explicit mapping; address similarity alone is insufficient |
| Hazard | Hazard name and value semantics | Impact factor/index | Record mapping version; do not assume names imply identical models |
| Scenario | Canonical pathway/horizon, often historical for JRC | VELO pathway and decadal horizon | Historical and future scenarios are not directly comparable |
| Hazard value | Return-period exposure in source units | Usually not the same public response object | Never compare directly to DCR/VaR/CVaR |
| Impact | Explicit user/registry transform and units | VELO impact score/attribution | Directional unless model and units are proven equivalent |
| Risk | CRC VaR/CVaR from explicit outcomes/distributions | VELO DCR, expected impact, VaR/CVaR | Require identical loss basis, confidence, aggregation, and scenario for direct comparison |
| Spatial | H3 resolution and `spatial_match` | Proprietary asset/hazard resolution | Explain granularity as capability lift |
| Provenance | Canonical metadata, source cache/version, package version | API result and available generation/method metadata | Flag missing version/evidence fields on either side |

## Recommended demo table

| Question | CRC baseline | VELO/CDT twin | Decision effect | Confidence/limits |
|---|---|---|---|---|

Fill one row per decision-relevant finding. Avoid a single “winner” score.

