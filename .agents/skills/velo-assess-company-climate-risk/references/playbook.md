# Company and market diligence playbook

## Remote CDT Express MCP route

Prefer the OAuth-connected server at `https://mcp.riskthinking.ai/mcp`. Inspect
its current tool schemas before choosing scenario values or fields.

For a company:

1. Resolve identity with `search_companies` and `get_company`.
2. Retrieve the total with `get_company_climate_scores`.
3. Retrieve owned assets with `get_company_assets` or, only when justified,
   `get_all_company_assets`.
4. Use `get_asset_climate_scores` on a bounded decision-relevant asset set for
   drivers and concentrations. Preserve excluded and failed assets as coverage
   exceptions.

For a market index:

1. Resolve it with `search_market_indexes` and `get_market_index`.
2. Retrieve the total with `get_market_index_climate_scores`.
3. Use `get_market_index_companies_climate_scores` and
   `get_market_index_assets_climate_scores` with sorting and limits to identify
   concentrations; use their `get_all_...` counterparts only for a justified
   exhaustive export.

Use `get_metrics_definition` when explaining unfamiliar score fields. Complete
VELO OAuth and never request `CDT_API_KEY` in chat. If a needed factor,
aggregation, or high-risk classification is not exposed by the connected MCP
version, state the gap and use the SDK route only when locally configured and
authorized.

## Local SDK fallback

In `crc-docs`, install the optional client with `uv sync --extra velo`, then run the bundled script through `uv run python`.

## Company method map (`velo-sdk==0.0.20`)

- Resolve: `search_companies`, `get_company`.
- Assets: `list_company_assets`.
- Total: `get_company_climate_scores`.
- Drivers: `get_company_impact_scores`.
- Asset detail: `list_company_asset_climate_scores`, `list_company_asset_impact_scores`.
- Concentration: aggregate company asset climate/impact scores by country or asset type.
- High-risk lists: `list_uninsurable_company_assets`, `list_stranded_company_assets`.

## Market-index method map

Use the parallel `client.markets` methods: index lookup/list/search, companies, total climate and impact scores, asset detail, and country/asset-type aggregations.

## Diligence memo

1. Entity/index identity and asset snapshot.
2. Scenario and horizon.
3. Total metrics.
4. Factor attribution.
5. Geographic and asset-type concentrations.
6. Tail-risk/high-risk assets.
7. Coverage and identity exceptions.
8. Comparison with open CRC evidence.
9. Decision implications and additional diligence.
