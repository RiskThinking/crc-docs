# AI skill dogfood verification

Verified locally on 2026-08-18 with `crc-sdk==0.3.0`, `crc-framework==0.2.0`, and `velo-sdk==0.0.20`.

Run the repeatable offline suite from the repository root:

```shell
uv run --extra velo python ai-playbooks/examples/dogfood/verify_skills.py
```

The harness creates an isolated temporary directory and removes its generated assessments when it exits. CRC tests execute the real package workflows against checked-in or synthetic canonical hazard data. VELO tests execute the real bundled scripts against deterministic API doubles; they verify routing, target selection, scenario propagation, result shaping, and missing-equivalence guardrails without requiring credentials or calling a live service.

The deterministic harness intentionally retains small offline regression data;
it is not the user-facing open bootstrap. The public playbooks use live Overture
candidate discovery and JRC acquisition through
`ai-playbooks/examples/run-open-demo.sh`.

## Target-flexibility results

| Skill | Target A | Target B | Result |
|---|---|---|---|
| `crc-screen-mortgage-flood` | EFAS / Cologne AOI | GloFAS / Toronto AOI | Pass: source and geographic bounds changed independently |
| `crc-model-flood-insurance-loss` | Historical/1980, one warehouse, 25/100-year periods | Synthetic-stress/2050, two assets, 50/500-year periods | Pass: a two-scenario fixture was filtered to exactly the requested pathway/horizon in each run |
| `crc-assess-asset-portfolio-risk` | One-asset flood book | Two-asset flood + synthetic drought book | Pass: portfolio size and hazard set changed |
| `velo-underwrite-property-climate` | Asset ID, Cologne warehouse, SSP2-4.5/2050 | Search-resolved Toronto plant, SSP5-8.5/2070 | Pass with API double: identity route, geography, scenario, owner, and scores changed |
| `velo-triage-portfolio-insurability` | Company A, SSP2-4.5/2050 | Company B, SSP5-8.5/2070 | Pass with API double: company/scenario changed and classifications followed the selected company |
| `velo-assess-company-climate-risk` | Single company | Market index | Pass with API double after adding explicit `--company-id` / `--index-id` routing |
| `compare-crc-velo-assessments` | Flood/property assessment pair | Drought/market-index assessment pair | Pass: both CRC and VELO artifact shapes changed while non-equivalence remained explicit |

## Findings and corrections

Dogfooding found one material flexibility gap: `velo-assess-company-climate-risk` described company and market-index analysis, but its script accepted only `--company-id`. The script now supports mutually exclusive `--company-id` and `--index-id` targets and dispatches to the corresponding VELO SDK methods.

Review found that `crc-model-flood-insurance-loss` did not select pathway and
horizon before return-period evaluation. Its CLI now requires both values, and a
regression case constructs a two-scenario flood file and verifies that each run
contains only its selected scenario.

## What this verifies

- Skill instructions and scripts do not hard-code one company, asset, geography, pathway, horizon, portfolio size, return-period set, or damage curve.
- CRC scripts execute real local computations and preserve explicit hazard/scenario metadata.
- VELO scripts select and propagate different targets correctly at the SDK boundary.
- The comparison skill tolerates different enterprise artifact shapes without claiming metric equivalence.

## Live open-bootstrap verification

The networked Cologne bootstrap was also verified on 2026-08-18 for bounds
`6.95,50.93,6.97,50.95`. It resolved JRC EFAS release `3.1.1`, materialized 280
canonical curve rows across 21 covered H3 cells, resolved Overture Places release
`2026-07-22.0`, selected five candidates inside JRC source geometry, and produced
five-row mortgage, flood-loss, and portfolio evaluations. This verifies the
acquisition seam; it does not turn those Overture candidates into a real business
portfolio.

## Remaining live-system validation

The API-double tests do not prove live VELO permissions, latency, pagination behavior, data availability, or server response compatibility. Before release, run the three VELO skills against an authorized sandbox using at least two real targets and record redacted response-schema fixtures. Do not use production mutation endpoints for this check.
