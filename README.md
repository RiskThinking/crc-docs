# Climate Risk Commons

[![Join the community on Discord](https://img.shields.io/badge/Discord-Join%20the%20community-5865F2?logo=discord&logoColor=white)](https://discord.gg/quuhzr3wS4)

Answers to everyday climate-risk questions, three ways each: with free public
data, with **CRC Open** (free, ready-made climate curves for 63 hazards
worldwide), and with Riskthinking.AI's **Climate Digital Twin (CDT)**. Every
answer comes as an AI skill you can ask in one sentence, a notebook that
explains it, and a pipeline that runs it.

## Pick a question

| Question | Ask an AI | Explore | Run at scale |
|---|---|---|---|
| **How hot will the hottest day get?** | `How hot will the hottest day get in my city in the future?` · [skill](.agents/skills/how-hot-will-it-get/SKILL.md) | [Preview](notebooks/how_hot_will_it_get.ipynb) · [Open in Colab](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_hot_will_it_get.ipynb) | [Pipeline](pipelines/how_hot_will_it_get.py) |
| **How hard will it rain?** | `How much rain can fall in one day where I live, and is it getting worse?` · [skill](.agents/skills/how-hard-will-it-rain/SKILL.md) | [Preview](notebooks/how_hard_will_it_rain.ipynb) · [Open in Colab](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_hard_will_it_rain.ipynb) | [Pipeline](pipelines/how_hard_will_it_rain.py) |
| **Which of my sites are most at risk?** | `Which of my stores is most at risk from climate change?` · [skill](.agents/skills/which-sites-are-most-at-risk/SKILL.md) | [Preview](notebooks/which_sites_are_most_at_risk.ipynb) · [Open in Colab](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/which_sites_are_most_at_risk.ipynb) | [Pipeline](pipelines/which_sites_are_most_at_risk.py) |
| **Will my farm get drier?** | `Will my farm get less rain and longer dry spells in the future?` · [skill](.agents/skills/will-my-farm-get-drier/SKILL.md) | [Preview](notebooks/will_my_farm_get_drier.ipynb) · [Open in Colab](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/will_my_farm_get_drier.ipynb) | [Pipeline](pipelines/will_my_farm_get_drier.py) |
| **How exposed is this company?** | `How exposed is Walmart to climate change?` · [skill](.agents/skills/how-exposed-is-this-company/SKILL.md) | [Preview](notebooks/how_exposed_is_this_company.ipynb) · [Open in Colab](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_exposed_is_this_company.ipynb) | [Pipeline](pipelines/how_exposed_is_this_company.py) |

New to return periods and risk curves? Start with the five-minute primer:
[Preview](notebooks/climate_risk_curves_primer.ipynb) ·
[Open in Colab](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/climate_risk_curves_primer.ipynb).

## Three ways in

- **Ask an AI assistant.** Install a skill (or paste its link) in Claude, ChatGPT
  or a coding agent and ask the one-sentence question. The skill uses CDT when
  the [CDT Express connector](https://github.com/RiskThinking/cdt-express-mcp) is
  available, otherwise CRC Open through Python, otherwise it points you to the
  notebook. Say "use CRC Open" or "use CDT" to steer explicitly.
- **Open a notebook.** If opened in Colab, choose **Runtime → Run all**. No
  account is needed for the free parts. Saved charts are visible on GitHub.
- **Run a pipeline.** Clone this repo, `uv sync --locked`, then `uv run python pipelines/<name>.py --help`.
  Each writes a `summary.json` with a plain-language answer and full provenance.

## What each data route gives you

| | Free public data | CRC Open | CDT |
|---|---|---|---|
| Past | ✅ | ➖ | ✅ modelled baseline |
| Future, 2025–2100 | ❌ | ✅ | ✅ |
| Emissions pathways | ❌ | SSP5-8.5 ([others on request](mailto:opensource@riskthinking.ai)) | All, plus warming levels |
| Hazards | One per source | 63, same format | 63, same format |
| Impact functions, entities (e.g. companies and assets) | ❌ | Bring your own | ✅ |
| Cost | Free | Free for non-commercial use (CC BY-NC 4.0) | [Trial](https://velo.riskthinking.ai/cdt-express), then licence |

## Appendix: data-source notebooks

Hands-on tours of individual public sources through crc-sdk (ERA5, NOAA
stations, JRC flood and drought, CMIP6, ECCC, USGS, HYDAT, CHIRPS, IBTrACS, NOAA
sea level and water levels, USDA and Fields of The World cropland, and flood
risk by province) are in [notebooks/sources](notebooks/sources/).

## Packages

| Package | Covers |
|---|---|
| [crc-sdk](https://github.com/RiskThinking/crc-sdk) | Data sources, canonical hazard curves, portfolio evaluation, impacts, fitting |
| [crc-framework](https://github.com/RiskThinking/crc-framework-rs) | Distributions, fitting, impact functions, risk metrics |
| [cdt-express-mcp](https://github.com/RiskThinking/cdt-express-mcp) | Connect CDT to Claude, ChatGPT and other AI assistants |

Machine-readable index for AI agents: [llms.txt](llms.txt) · [AGENTS.md](AGENTS.md).

## Community

Questions and ideas are welcome on [Discord](https://discord.gg/quuhzr3wS4).
Report problems as GitHub issues in
[crc-docs](https://github.com/RiskThinking/crc-docs/issues),
[crc-sdk](https://github.com/RiskThinking/crc-sdk/issues) or
[crc-framework](https://github.com/RiskThinking/crc-framework-rs/issues).

- More CRC Open data, such as other emissions futures, and contributions:
  [opensource@riskthinking.ai](mailto:opensource@riskthinking.ai)
- Research access: [academic@riskthinking.ai](mailto:academic@riskthinking.ai)
- Every pathway, a historical baseline, impacts and company data:
  [CDT Express trial](https://velo.riskthinking.ai/cdt-express)
