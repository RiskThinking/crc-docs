# Company and market diligence playbook

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
