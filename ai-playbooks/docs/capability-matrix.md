# Capability matrix

What the open packages can do is documented in the
[crc-sdk docs](https://github.com/RiskThinking/crc-sdk/blob/main/docs/README.md) and [crc-framework docs](https://github.com/RiskThinking/crc-framework-rs/blob/main/docs/README.md). This
page records only the interpretation limits that matter in an assessment.
`uv.lock` pins the tested environment; [verification](dogfood-verification.md)
records how the skills were last checked.

## Open computation and workflows

| Capability | Reference | Limits and example use |
|---|---|---|
| Probability and fitting | [SDK fitting](https://github.com/RiskThinking/crc-sdk/blob/main/docs/fitting.md); [framework Python API](https://github.com/RiskThinking/crc-framework-rs/blob/main/docs/python.md) | A hurdle's dry-event atom is a modelling assumption. Inspect fit policy and source support; do not assume every source row has a parametric fit. |
| Canonical hazard data | [SDK concepts](https://github.com/RiskThinking/crc-sdk/blob/main/docs/concepts.md#canonical-hazard-datasets) | Use SDK readers and evaluators instead of extracting only scalar fit parameters. `no_data` rows carry reason codes and are not zero risk. |
| Source acquisition | [SDK data sources](https://github.com/RiskThinking/crc-sdk/blob/main/docs/README.md#data-sources) | Read resolved source, units, tail and support; summarize curve kinds and retain treatment diagnostics. Historical observations do not supply future climate projections. |
| Agricultural evidence | [SDK agriculture](https://github.com/RiskThinking/crc-sdk/blob/main/docs/sources/agriculture.md); [agricultural playbook](../agricultural-climate-risk.md) | Crop samples and predicted fields do not establish yield, ownership or financial materiality. |
| Your own data | [SDK bring your own data](https://github.com/RiskThinking/crc-sdk/blob/main/docs/bring-your-own-data.md) | Format access is available; an arbitrary dataset still needs a scientifically justified canonicalization policy. |
| Spatial processing | [SDK spatial support](https://github.com/RiskThinking/crc-sdk/blob/main/docs/concepts.md#spatial-support); [runtime](https://github.com/RiskThinking/crc-sdk/blob/main/docs/runtime.md) | H3-only assets keep cell precision; regional max/min summaries are not exact asset assessments. PMTiles needs external tiling tools. |
| Portfolio evaluation | [SDK portfolio](https://github.com/RiskThinking/crc-sdk/blob/main/docs/portfolio.md) | Ambiguous and unmatched joins raise; a matched `no_data` curve yields null values. Report both coverage and value availability. |
| Event-aligned impact | [SDK impacts](https://github.com/RiskThinking/crc-sdk/blob/main/docs/portfolio.md#apply-an-impact-function); [impact contracts](https://github.com/RiskThinking/crc-framework-rs/blob/main/docs/impact-contracts.md) | Evaluates the impact at each hazard return period, which is not necessarily a quantile of the transformed loss distribution. Registry availability does not establish applicability to an insured exposure. |
| Risk aggregation | [framework Python API](https://github.com/RiskThinking/crc-framework-rs/blob/main/docs/python.md) | Basic branch construction assumes independent outcomes and grows as `2**n`; set branch limits. The example threshold model is not a full joint continuous-loss model. |
| Multi-hazard/scenario work | Repository wrapper over separate hazards | There is no automatic cross-hazard score, dependence calibration or scenario-equivalence policy. Keep incompatible results separate. |
| Evidence | Canonical metadata; agricultural manifest | A complete assessment-wide report, hashes, coverage exceptions and semantic comparison remain the skill's responsibility. |

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
