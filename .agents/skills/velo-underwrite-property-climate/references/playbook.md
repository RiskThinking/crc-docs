# Property underwriting playbook

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
