# Setup and running examples

[Choose a problem](../../README.md#choose-a-problem) before loading a skill.
The canonical `SKILL.md` owns the guided workflow; its references explain domain
assumptions, and its scripts implement individual steps. Repository-relative
commands run from the repository root, even when a skill is installed elsewhere.
Fetch or clone this repository when a skill needs those files; fetching one
`SKILL.md` does not fetch its dependencies.

## AI setup

Use plain language: `Use the crc-screen-mortgage-flood skill for Toronto, Canada.`
Make the repository available to your assistant through a checkout or repository
connector. Skill selectors and automatic discovery depend on the host tool;
plain-language invocation still requires access to the skill files.

With a browsing-only assistant, ask it to fetch:

```text
https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/crc-screen-mortgage-flood/SKILL.md
```

Ask it to follow the skill and fetch its referenced files as needed. Execution
also requires a Python environment; a browsing-only chat cannot run pipelines.

For VELO/CDT, connect [CDT Express MCP](https://github.com/RiskThinking/cdt-express-mcp)
at `https://mcp.riskthinking.ai/mcp`, complete VELO OAuth, and enable the tools.
[.mcp.json](../../.mcp.json) supplies the project configuration. Discover current
tool schemas and available scenarios at runtime. Do not paste credentials into
chat. `uv sync --extra velo` installs the optional, pinned local SDK fallback;
its capabilities differ from those exposed by MCP.

### Platform discovery

- Canonical skills: [`.agents/skills`](../../.agents/skills), with OpenAI metadata in each `agents/openai.yaml`.
- Claude Code: [`.claude/skills`](../../.claude/skills) links to those same definitions; [`CLAUDE.md`](../../CLAUDE.md) imports the agent entry point.
- Other file-aware assistants: start with [`AGENTS.md`](../../AGENTS.md), or explicitly load the desired skill.
- Chat-only tools: use the raw-file route above or install a custom skill using the host's supported mechanism. Project MCP configuration is not automatically available in a hosted chat.

## Keeping installed skills current

Install a copy containing the refresh bootstrap once. On each new assessment,
the assistant checks `RiskThinking/crc-docs` for the latest `main` commit and
loads the skill plus required references/scripts from that one revision. The
[refresh contract](skill-refresh.md) defines source resolution, pinned/offline
runs and provenance. A failed freshness check stops execution rather than
silently falling back to an old installation.

This refreshes instructions **for the run**; it does not rewrite the installed
package. Older installations need a one-time replacement after the bootstrap
is published. Discovery descriptions and permissions still belong to the
installed package and may require later updates through the host.

The host must expose GitHub, URL-fetch or Git access and permit execution where
needed. Claude documents that network access varies by product and settings;
its API skill container has no network access ([runtime constraints](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)).
OpenAI's API supports explicitly uploaded immutable skill versions
([version API](https://developers.openai.com/api/reference/cli/resources/skills/subresources/versions/methods/create));
that API is not evidence that a ChatGPT upload automatically follows GitHub.
We therefore do not promise unconditional auto-update on either chat platform.

## Run notebooks in Colab

The [notebook links in the problem table](../../README.md#choose-a-problem) open
Google Colab. Connect a standard Python runtime (no GPU required), then choose
**Runtime → Run all**. The first code cell installs the notebook's SDK extras,
plotting packages and, where needed, the `tippecanoe` binaries. It checks PNG
rendering and downloads Chrome if no compatible browser is available.
If an already imported package changes, follow the cell's restart instruction
and run all cells again.

Each notebook works without a repository checkout. Its setup downloads only the
required fixtures or pipeline script from a fixed `crc-docs` commit and checks
their SHA-256 hashes. SDK/framework versions are pinned in that same cell.
A local checkout uses its own files, so edits remain testable. Live source data
still comes from the providers named in the notebook and is cached separately.

Colab runtimes are temporary: download results from the Files panel before the
runtime is deleted. The setup cell prints the working directory; caches live
under its `data/` folder, PMTiles under `artifacts/`, and other exported results
under the sibling `pipeline_output/` folder. Standalone files are inside
`.crc-docs/`; enable **Show hidden files** in the Files panel if needed.
Saved figures remain visible in
[GitHub previews](../../notebooks/); interactive charts require running the notebook.
Colab does not share installed libraries or runtime files with a notebook, which
is why setup runs inside each one ([Colab FAQ](https://research.google.com/colaboratory/faq.html)).

## Python environment

```shell
uv sync --locked
uv run jupyter lab notebooks/
uv run python pipelines/asset_portfolio_pipeline.py
```

Use Python 3.12+. Notebook setup locates the checkout and selects its
`notebooks/` working directory automatically. The lockfile records the tested
local environment; standalone notebooks declare their own dependencies.
`crc-sdk` supplies data access, canonicalization and workflows; `crc-framework` supplies numerical
distributions, fitting, impacts and risk metrics. The SDK re-exports core APIs.

Standalone pipeline PMTiles export requires `tippecanoe` on PATH (and `tile-join`
for merging); the notebooks that export tiles install these binaries themselves.
Use a pipeline's `--skip-pmtiles` option when available to omit that export.
Plotly PNG output requires Kaleido and compatible Chrome; notebook setup checks
and provisions them.
Each notebook includes a short viewing guide and saves Plotly interactive data
alongside a PNG in the same output. Compatible notebook viewers display the
interactive figure; GitHub uses the static image without executing JavaScript.
Saved outputs are a snapshot of the recorded execution, not live data.

To refresh all saved notebook outputs from the repository root:

```shell
uv run jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=3600 notebooks/*.ipynb
```

Run this with network access; the notebook setup cells install their prerequisites.
The remote hazard notebooks rebuild canonical curves with the installed SDK
while reusing validated source caches. Save successful outputs before committing;
every Plotly figure should contain both `application/vnd.plotly.v1+json` and
`image/png` MIME data. PMTiles exports remain downloadable companion files.

## Live open demonstration

```shell
./ai-playbooks/examples/run-open-demo.sh
```

The runner acquires JRC EFAS for a small Cologne area, selects Overture Places
inside modeled source geometry, and runs mortgage, loss, portfolio and artifact
inventory helpers. Network access is required on the first run. Change source,
WGS84 bounds (west, south, east, north), and output directory together:

```shell
./ai-playbooks/examples/run-open-demo.sh \
  glofas -79.42 43.63 -79.36 43.68 \
  pipeline_output/ai-playbooks-toronto
```

Default outputs under `pipeline_output/ai-playbooks/`:

| File | Contents |
|---|---|
| `jrc_depths_by_cell.parquet` | Canonical flood curves and source/scenario metadata |
| `overture-assets.csv` | Candidate locations, release, confidence and attribution |
| `mortgage-flood.parquet` | Return-period depths at candidate coordinates |
| `flood-loss.parquet` | Event-aligned damage ratios from an illustrative curve |
| `portfolio/flood.parquet` | Per-location flood evaluation |
| `comparison-inventory.json` | File inventory against synthetic VELO-shaped JSON; no live or target-aligned comparison |

These helpers do not generate the skill's complete charts, maps, HTML report or
reconciliation memo. The assistant assembles those from the preserved outputs.
Use authorized assets and an approved damage curve for decision-facing work.
Generated caches and outputs in `notebooks/data/` and `pipeline_output/` are ignored
by Git. Retain the resolved source release and metadata; `latest` source selection
does not automatically refresh an existing notebook canonical file. Use a new
output path or explicitly rebuild it after changing the source, area or fit policy.
