# Insurability triage playbook

## Remote CDT Express MCP route

Prefer the OAuth-connected server at `https://mcp.riskthinking.ai/mcp` for a
chat-native run:

1. Inspect the available tools and schemas, then resolve the company with
   `search_companies` and `get_company`.
2. Obtain the company's assets with `get_company_assets`; use
   `get_all_company_assets` only when an exhaustive run is appropriate.
3. Call `get_asset_climate_scores` for each in-scope asset under one supported
   pathway and horizon. Confirm scope before a large fan-out.
4. Apply the documented VELO thresholds below to returned `cvar_95` values;
   preserve nulls and failed calls as coverage exceptions.
5. Use `get_company_climate_scores` for portfolio context, not as a substitute
   for asset classification.

Complete the server's VELO OAuth flow and never request `CDT_API_KEY` in chat.
If the connected MCP version cannot return the required asset metric or
portfolio scope, report the gap and use the SDK route only when locally
configured and authorized.

## Local SDK fallback

In `crc-docs`, install the optional client with `uv sync --extra velo`, then run the bundled script through `uv run python`.

In `velo-sdk==0.0.20`, company helpers describe:

- “uninsurable” assets as those with `cvar_95 >= 0.35`;
- “stranded” assets as those with `cvar_95 >= 0.75`.

These are VELO definitions. Quote the thresholds and scenario with every result; do not generalize them into legal, regulatory, or carrier-wide definitions.

## Triage output

1. Company, pathway, and horizon.
2. Total assets assessed when available.
3. Uninsurable count and asset details.
4. Stranded count and asset details.
5. Overlap and concentrations by country/type.
6. Factor drivers when available.
7. Coverage exceptions and missing data.
8. Human review queue and additional evidence required.
