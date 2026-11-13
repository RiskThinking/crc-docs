# Agent guide

crc-docs answers everyday climate-risk questions three ways: free public data,
CRC Open and CDT (Riskthinking.AI's Climate Digital Twin). Each question has a
skill, a notebook and a pipeline. Claude Code loads this file through
`@AGENTS.md` in [CLAUDE.md](CLAUDE.md); other agentic tools read it directly.
A short index for language models is in [llms.txt](llms.txt).

## Skills

One `SKILL.md` per question under [`.agents/skills/`](.agents/skills):

| Question | Skill |
|---|---|
| How hot will the hottest day get? | [how-hot-will-it-get](.agents/skills/how-hot-will-it-get/SKILL.md) |
| How hard will it rain? | [how-hard-will-it-rain](.agents/skills/how-hard-will-it-rain/SKILL.md) |
| Which of my sites are most at risk? | [which-sites-are-most-at-risk](.agents/skills/which-sites-are-most-at-risk/SKILL.md) |
| Will my farm get drier? | [will-my-farm-get-drier](.agents/skills/will-my-farm-get-drier/SKILL.md) |
| How exposed is this company? | [how-exposed-is-this-company](.agents/skills/how-exposed-is-this-company/SKILL.md) |

Each skill picks its data route in this order unless the person names one:
CDT through the CDT Express MCP server ([`.mcp.json`](.mcp.json),
`https://mcp.riskthinking.ai/mcp`), then CRC Open through the matching pipeline,
then the Colab notebook. Hosts without repository access can fetch a skill from
`https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/<name>/SKILL.md`.
CI also packages every skill as an uploadable zip (`tools/package_skills.py`).

## Layout

- `notebooks/<question>.ipynb`: the explained answer, A → B → C, with saved
  chart previews. `notebooks/climate_risk_curves_primer.ipynb` teaches the
  concepts.
- `notebooks/sources/`: tours of individual public data sources.
- `pipelines/<question>.py`: the headless answer; writes `summary.json`
  (the company pipeline also writes `locations.geojson` for the crc-viz map).
  Other files in `pipelines/` back the source notebooks.
- `tools/build_map_page.py`: turns `locations.geojson` into one self-contained HTML file on the
  crc-viz hazard map (bundle built from the npm package in `tools/crc-viz-bundle`; see its docstring).
- `tests/`: offline checks, plus live runs behind `CRC_DOCS_LIVE=1`.

## Checks

```sh
uv sync --locked --extra velo
uv run pytest -q
uv run ruff check pipelines tests tools && uv run ruff format --check pipelines tests tools
CRC_DOCS_LIVE=1 uv run pytest -q tests/test_live.py   # downloads data
```

## Rules

- Notebooks keep sequential execution counts and a PNG preview for every chart.
  Set `CRC_DOCS_CI=1` for small runs and `CRC_NOTEBOOK_STATIC_PREVIEW=1` to save
  previews. `metadata.crc_docs` controls CI (`ci`, `timeout_seconds`,
  `cdt_outputs`).
- Saved CDT outputs stay small and aggregated. Never commit API keys; CDT code
  reads `RISKTHINKING_API_KEY`.
- CDT REST takes the singular `risk_factor` parameter; MCP tools take arrays.
- CRC Open has no historical baseline and covers SSP5-8.5; say so wherever its
  results appear.
- Write outputs atomically (temporary file, then `os.replace`).
- Docs, code and commit messages are in English.
