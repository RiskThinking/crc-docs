# Property underwriting playbook

## Remote CDT Express MCP route

Prefer the OAuth-connected server at `https://mcp.riskthinking.ai/mcp` for a
chat-native run:

1. Inspect the available tools and their schemas; supported scenario values are
   defined there and can change by server version.
2. Call `search_assets` for a name/address, or `get_asset` for a known ID.
3. Call `get_asset_climate_scores` for the chosen pathway and horizon.
4. When location-level factor evidence is needed and supported, use
   `get_climate_metrics_exposure`, `get_climate_metrics_impact`,
   `get_climate_metrics_probability_adjusted_impact`, or the corresponding
   distribution tool. Use `get_metrics_definition` before explaining unfamiliar
   metrics.
5. Preserve tool names, inputs, returned metadata, nulls, and errors in the
   evidence memo. Never equate a location metric with an asset score without a
   documented semantic match.

Complete the server's VELO OAuth flow. Never request or place `CDT_API_KEY` in a
prompt. If the connected server does not expose a required capability, state the
gap and use the SDK route below only when locally configured and authorized.

## Local SDK fallback

In `crc-docs`, install the optional client with `uv sync --extra velo`, then run the bundled script through `uv run python`.

## Read-only route in velo-sdk 0.0.20

1. Search or get the asset.
2. Resolve its owner with `client.assets.get_asset_owner(asset_id)`.
3. Read `client.companies.list_company_asset_climate_scores(owner.id, pathway, horizon)` and select the matching `asset_id`.
4. Read `client.companies.list_company_asset_impact_scores(...)` and select the same asset.

This indirection is a product gap. Prefer a direct asset-score MCP/API helper when one is explicitly available.

## Evidence fields

- Asset ID, name, address, coordinates, type, value/materiality fields when authorized.
- Owner/company ID and identity.
- Pathway and horizon.
- DCR, expected impact, VaR/CVaR levels returned.
- Factor/index impacts and attribution returned.
- Data generation timestamp/status when returned.
- Missing data, ambiguity, and coverage limits.

## Enterprise lift to demonstrate

Show broader hazard coverage, future scenario distribution, asset resolution, proprietary ownership/materiality, multi-factor effects, and enterprise risk metrics. Phrase these as additional evidence, not as proof that the open baseline was wrong.
