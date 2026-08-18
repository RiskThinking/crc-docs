---
name: velo-assess-company-climate-risk
description: Assess company or market-index physical climate risk with VELO/CDT using the remote CDT Express MCP server or velo-sdk company, asset, market, climate-score, impact, and aggregation APIs. Use for investment diligence, lending portfolios, company benchmarking, country or asset-type concentration, scenario comparison, or the enterprise twin to a CRC supplied-asset assessment.
---

# VELO company climate risk

Use VELO's asset and ownership intelligence to answer a business diligence question; preserve scenario and metric definitions.

## Guided intake

Treat `Use $velo-assess-company-climate-risk` as a complete invocation. Reuse a
clear company, index, and decision context; otherwise ask one question: “Which
company or market index should I assess, and what decision should it inform?”
Resolve identity and supported pathways/horizons through the authorized
connection. Choose only an unambiguous match, recommend a useful scenario
comparison, and ask a concise follow-up only when identity or scenario intent
is materially ambiguous. Do not ask non-experts for company IDs, index IDs, or
raw scenario codes the service can discover. Valid advanced inputs override
defaults.

## CDT Express MCP execution

Prefer the declared `CDT Express` remote MCP dependency for an AI chat session.
If it is not connected, direct the user to add
`https://mcp.riskthinking.ai/mcp` and complete VELO OAuth; never request an API
key in chat. Inspect the connected tool list and schemas before calls. Use the
company or market search/detail tools to resolve the target, then the matching
climate-score and constituent/asset-score tools. Read
[references/playbook.md](references/playbook.md) for exact sequences. Prefer
bounded, sorted calls for decision-relevant concentrations; confirm scope before
exhaustive retrieval.

## Demo bootstrap

This live enterprise skill does not require local asset files. Use the authorized
MCP connection, or the SDK fallback, to search the requested company or index and discover
supported pathways and horizons, then ask the user to resolve ambiguity. If no
authorized connection is available, explain the prerequisite and stop. The
repository's synthetic VELO-shaped JSON is only for reconciliation smoke tests,
not a substitute for this assessment.

## Workflow

1. Resolve the company or market index. Show ambiguity and require selection rather than choosing silently.
2. Discover supported pathways and horizons.
3. Run `scripts/assess_company.py` with either `--company-id` or `--index-id`. Follow the method map in [references/playbook.md](references/playbook.md) when using equivalent MCP tools.
4. Collect total climate score, factor impacts/attribution, country concentration, asset-type concentration, and high-risk assets where authorized.
5. Compare pathways/horizons as separate scenario results. Never imply a scenario probability unless the platform supplies one.
6. Explain the enterprise lift over CRC: ownership/material assets, broader/finer hazards, multi-factor modelling, future scenarios, aggregation, and benchmarks.
7. Produce a diligence memo with evidence, coverage exceptions, concentrations, drivers, sensitivity, and actions.

## Safety

- Use read-only calls unless explicit authorization covers company creation or asset upload.
- Never reveal API keys or organization-private asset data beyond the authorized output.
- Do not turn climate scores into buy/sell, credit, or compliance conclusions without an owner-approved decision policy.
- Describe the CRC/VELO foundation relationship as directional and increasingly materialized, not as complete implementation parity.
