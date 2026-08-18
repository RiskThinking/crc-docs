---
name: velo-underwrite-property-climate
description: Perform a higher-calibre property climate underwriting assessment through VELO/CDT using the remote CDT Express MCP server or velo-sdk. Use for a named property or VELO asset when the user needs proprietary asset resolution, multi-factor climate impacts, future pathways and horizons, VaR/CVaR, or an enterprise twin to a CRC mortgage flood screen.
---

# VELO property climate underwriting

Use enterprise data to deepen a CRC baseline; do not turn a platform score into an automatic lending decision.

## Guided intake

Treat `Use $velo-underwrite-property-climate` as a complete invocation. Reuse a
clear property from the conversation; otherwise ask only for a property name,
address, or VELO asset ID. Search through the authorized connection, select
automatically only when identity is unambiguous, and show a short candidate list
when it is not. Discover supported pathways and horizons internally. Recommend
a decision-relevant scenario or comparison and ask a concise follow-up only when
the choice would materially change the assessment. Do not ask for API IDs or raw
scenario codes that the service can discover. Valid advanced inputs override
defaults.

## CDT Express MCP execution

Prefer the declared `CDT Express` remote MCP dependency for an AI chat session.
If it is not connected, direct the user to add
`https://mcp.riskthinking.ai/mcp` and complete VELO OAuth; never request an API
key in chat. Inspect the connected tool list and input schemas before calls.
Use `search_assets`, `get_asset`, and `get_asset_climate_scores`; use the climate
metric and distribution tools only when their schemas support the requested
factor-level evidence. Read [references/playbook.md](references/playbook.md) for
the current MCP sequence and SDK fallback. Do not invent missing tools or
fields.

## Demo bootstrap

This live enterprise skill does not require a local CSV or Parquet. If the user
has not supplied an asset ID, use the authorized MCP connection, or the SDK
fallback, to search
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

## Deliverable bundle

Retain the unmodified authorized MCP responses, or SDK export, as private JSON
with tool names and inputs. Also create a flattened analysis-ready CSV, GeoJSON
when authorized coordinates are returned, and a self-contained HTML report with
a provenance manifest. In the response, show a compact table of scenario,
overall metrics, factor metrics, units, and missing fields. Include:

- a property map that identifies the resolved asset and spatial precision
  without exposing unnecessary private attributes; and
- a factor-contribution or scenario-comparison chart using only semantically
  compatible returned metrics.

Make sanitized table and visual artifacts downloadable when the host permits.
If the service does not return coordinates, show the identity evidence but do
not geocode the address or manufacture a map point without user approval.

## Safety

- Read `RISKTHINKING_API_KEY` from the environment; never request or print it.
- Do not create a company, upload assets, or otherwise mutate VELO unless the user explicitly authorizes that action and confirms the target organization.
- Do not claim that DCR, expected impact, VaR, CVaR, or a factor impact equals JRC flood depth.
- Escalate low-confidence identity, missing coverage, or unmatched assets; never interpret them as low risk.
