# Insurability triage playbook

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
