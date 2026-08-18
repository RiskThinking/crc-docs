---
name: velo-underwrite-property-climate
description: Perform a higher-calibre property climate underwriting assessment through VELO/CDT using velo-sdk or an equivalent authorized MCP surface. Use for a named property or VELO asset when the user needs proprietary asset resolution, multi-factor climate impacts, future pathways and horizons, VaR/CVaR, or an enterprise twin to a CRC mortgage flood screen.
---

# VELO property climate underwriting

Use enterprise data to deepen a CRC baseline; do not turn a platform score into an automatic lending decision.

## Demo bootstrap

This live enterprise skill does not require a local CSV or Parquet. If the user
has not supplied an asset ID, use the authorized MCP or SDK connection to search
their property query, show candidates, and require a selection when ambiguous.
If no authorized connection is available, explain the prerequisite and stop;
never replace enterprise evidence with synthetic data.

## Workflow

1. Require an existing VELO `asset_id` or search query. If search returns ambiguity, show candidates and stop for selection.
2. Discover valid pathways and horizons from the connected tool or SDK. Never guess an allowed value.
3. Resolve the asset and its owner. The public `velo-sdk` 0.0.20 reaches asset climate/impact scores through the owning company's asset lists; see [references/playbook.md](references/playbook.md).
4. Run `scripts/underwrite_property.py` for a read-only SDK assessment, or use semantically equivalent authorized MCP tools.
5. Capture asset identity, scenario, total risk metrics, factor impacts/attribution, missing fields, and response time/version evidence available from the tool.
6. Compare with the CRC result only after aligning the asset, hazard/factor, horizon/pathway, unit, and metric. Label all non-equivalent results.
7. Write an underwriting evidence memo that distinguishes measured output, platform classification, house policy, and expert judgment.

## Safety

- Read `RISKTHINKING_API_KEY` from the environment; never request or print it.
- Do not create a company, upload assets, or otherwise mutate VELO unless the user explicitly authorizes that action and confirms the target organization.
- Do not claim that DCR, expected impact, VaR, CVaR, or a factor impact equals JRC flood depth.
- Escalate low-confidence identity, missing coverage, or unmatched assets; never interpret them as low risk.
