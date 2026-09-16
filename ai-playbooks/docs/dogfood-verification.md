# Verification and lineage audit

Verified on **2026-09-15** using the published **crc-sdk 0.7.1** and
**crc-framework 0.2.5** wheels, with **velo-sdk 0.0.20** for SDK fallback tests.
The environment was resolved from PyPI, not sibling editable checkouts.
`pyproject.toml` requires SDK `>=0.7.1,<0.8`; `uv.lock` pins the tested versions.

## What passed

| Check | Evidence | Scope |
|---|---|---|
| Seven-skill harness | All seven routes pass with varied targets/scenarios | Real CRC fixture computations; VELO API doubles; comparison inventory only |
| Pipeline regressions | Six tests pass | FTW publication/manifest, null agricultural hazard values, flood/drought null summaries |
| Fixture pipelines | Asset evaluation, impact, portfolio risk and multi-scenario pipelines pass | Real framework/SDK computations against checked-in Cologne data |
| All nine notebooks | Full execution with 22 figures, each containing interactive Plotly data and PNG fallback; static HTML exports and visual checks pass | Five fixture notebooks plus live JRC flood, EDO drought, regional/admin and USDA agricultural notebooks; saved outputs are checked in |
| Standalone notebook setup | Six full runs outside the checkout (five fixture notebooks and agriculture), plus setup/import checks for the other three | Fresh Python environment initially containing only a notebook kernel; pinned resource downloads, repeatable setup, pip-installed PMTiles tools and Colab renderer MIME checks pass |
| Live open bootstrap | EFAS 3.1.1; Overture 2026-08-19.0; 280 canonical rows, 21 H3 cells, 10 candidates | Mortgage, loss and portfolio each produce 10 rows; comparison JSON is synthetic and inventory-only |
| Live agricultural pipeline | USDA CDL 2025 corn/soy and GloFAS 2.1.2; 21 agricultural units, 17 matched and 4 outside coverage; map, summary and manifest written | Real bounded acquisition/evaluation; PMTiles skipped |
| Static lineage checks | Local Markdown links, Python/notebook syntax, SDK/framework notebook imports and CLI help | Checks file/API references; does not execute every remote notebook |

The live bootstrap used bounds `6.95,50.93,6.97,50.95` and produced schema-1.2
canonical data. Package versions must be recorded independently of embedded
`creation_version`: this run's metadata reported `0.2.0` despite the installed
SDK being 0.7.1. Preserve the source metadata as returned and record the runtime
package versions separately; do not silently rewrite provenance.

## Reproduce

Run from the repository root:

```shell
uv sync --locked --extra velo
uv run --extra velo python ai-playbooks/examples/dogfood/verify_skills.py \
  --report pipeline_output/verification/skills.json
uv run --with pytest python -m pytest -q
./ai-playbooks/examples/run-open-demo.sh \
  efas 6.95 50.93 6.97 50.95 pipeline_output/verification/live-open
```

Use `python -m pytest` so the repository root is on the import path. The harness
uses an isolated temporary directory; live outputs remain in the gitignored
`pipeline_output/verification/` directory. Executed offline notebooks were saved
there too. The subsequent full notebook refresh saved successful executions
directly into all nine checked-in notebooks, with package versions and execution
time in each notebook's `crc_preview` metadata.

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

## Corrections from this audit

- Replaced repeated route tables with the README's problem-to-skill-to-code map;
  notebooks link back to their skill and setup instructions.
- Removed old SDK 0.3.0 installation instructions and upgraded the locked packages.
- Verified the agricultural skill's playbook link and documented its GloFAS default,
  one-hazard-per-run interface and H3-only evaluation precision.
- Updated canonical schema, impact-registry and direct MCP asset-scoring claims.
- Fixed flood/drought CLI summaries that assumed all curve values were numeric;
  agricultural map summaries now label matched null values separately from
  locations outside coverage.
- Distinguished helpers' data outputs from the full report an assistant assembles.

## Validation limits

Live VELO permissions, response schemas, pagination and available data were not
revalidated: enterprise tests use API doubles. The synthetic comparison fixture
does not establish target or metric equivalence. FTW remote acquisition remains
unverified; its publication path uses local regression inputs. The notebook
refresh executed the live EDO, regional/admin and USDA examples, including PMTiles
exports. EDO initially timed out during acquisition; completed annual-minimum
files were validated and the remaining years fetched before a successful full
1995–2025 run. Remote availability and runtime still depend on source services.

Notebook previews were checked locally through their embedded PNGs and static
HTML exports. Colab setup was tested in a clean local runtime outside the
checkout, not in a hosted Google Colab session. Notebook links resolve the
published `main` branch, so new setup cells become available there after these
changes are pushed. The [setup guide](setup.md#python-environment) includes the command to refresh them.

The [problem map](../../README.md#choose-a-problem) records whether a notebook is
a workflow twin or a reference building block. [Setup](setup.md) explains output
locations and prerequisites; [capabilities](capability-matrix.md) records semantic
limits.
