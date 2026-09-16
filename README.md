# Climate Risk Commons

Use an AI skill to guide a climate-risk assessment, or open its notebook and
Python pipeline to inspect and run the analysis yourself. **CRC** provides open,
reproducible hazard and risk workflows. **VELO/CDT** adds enterprise asset,
company and scenario evidence through an authenticated service.

**Set the source once per chat**, then copy any example from the table:

```text
Use skills from https://github.com/RiskThinking/crc-docs. Before each new
assessment, load the latest skill and its linked files from the same commit.
If you cannot verify the source, tell me before running the assessment.
```

The skill guides the remaining inputs. [Setup](ai-playbooks/docs/setup.md) covers
AI connections and Python installation; no AI tool is required to run the code.
Installed skills include this freshness check; older installations need a one-time
update. [How refresh works](ai-playbooks/docs/setup.md#keeping-installed-skills-current).

## Choose a problem

Skills link to their instructions and include copyable example prompts. You can
also start with just `Use the <skill-name> skill.` and let the assistant guide
the inputs. Notebooks explain the methods; pipelines run
them headlessly. "Reference" means a related building block, not an end-to-end
implementation of the paired enterprise skill. VELO/CDT skills use live MCP
calls or their linked SDK scripts; there are no enterprise notebook twins here.

| Problem | Skill (CRC) | Skill (VELO/CDT) | Notebook | Pipeline |
|---|---|---|---|---|
| **Screen mortgage collateral for river flooding.** "What are the 25-, 100- and 500-year depths at these properties?" | [Mortgage flood screen](.agents/skills/crc-screen-mortgage-flood/SKILL.md)<br>**Example:** `Use the crc-screen-mortgage-flood skill for Toronto, Canada.` | [Property climate underwriting](.agents/skills/velo-underwrite-property-climate/SKILL.md)<br>**Example:** `Use the velo-underwrite-property-climate skill for 392 Markham Street, Toronto.` | [JRC flood acquisition](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/jrc_global_flood_hazard.ipynb); [asset evaluation](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/asset_portfolio_evaluation.ipynb) | [Acquire flood](pipelines/jrc_flood_pipeline.py) → [screen assets](.agents/skills/crc-screen-mortgage-flood/scripts/screen_mortgage_flood.py) |
| **Estimate flood damage under an explicit curve.** "How would this approved depth-damage curve affect my insured properties?" | [Flood insurance loss](.agents/skills/crc-model-flood-insurance-loss/SKILL.md)<br>**Example:** `Use the crc-model-flood-insurance-loss skill with my attached portfolio and approved depth-damage curve.` | [Portfolio insurability triage](.agents/skills/velo-triage-portfolio-insurability/SKILL.md)<br>**Example:** `Use the velo-triage-portfolio-insurability skill for the company in my attached portfolio.` | [Event-aligned impacts](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/portfolio_impact.ipynb) | [Custom curve and assets](.agents/skills/crc-model-flood-insurance-loss/scripts/model_flood_loss.py); [fixture example](pipelines/portfolio_impact_pipeline.py) |
| **Review physical exposure across an asset portfolio.** "Which Frankfurt sites have flood or drought exposure, and where is coverage missing?" | [Asset portfolio assessment](.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md)<br>**Example:** `Use the crc-assess-asset-portfolio-risk skill for Frankfurt, with flood and drought.` | [Company or market-index assessment](.agents/skills/velo-assess-company-climate-risk/SKILL.md)<br>**Example:** `Use the velo-assess-company-climate-risk skill for the S&P 500.` | [Asset evaluation](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/asset_portfolio_evaluation.ipynb); [EDO drought](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/jrc_edo_drought_index.ipynb) | [Evaluate separate hazards](.agents/skills/crc-assess-asset-portfolio-risk/scripts/assess_asset_portfolio.py); [fixture evaluation](pipelines/asset_portfolio_pipeline.py); [acquire drought](pipelines/jrc_drought_pipeline.py) |
| **Screen agricultural sourcing areas.** "Which sampled corn and soybean areas near Ames overlap modeled flood?" | [Agricultural climate risk](.agents/skills/crc-assess-agricultural-climate-risk/SKILL.md)<br>**Example:** `Use the crc-assess-agricultural-climate-risk skill for corn and soybeans near Ames, Iowa.` | [Company assessment](.agents/skills/velo-assess-company-climate-risk/SKILL.md) when a company/supplier can be resolved; no crop-specific twin<br>**Example:** `Use the velo-assess-company-climate-risk skill for the supplier named in my sourcing assessment.` | [Crop and field exposure](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/agricultural_climate_risk.ipynb) | [Agricultural assessment](pipelines/agricultural_climate_pipeline.py) |
| **Map regional flood exposure.** "Where do modeled flood cells and candidate places overlap in the Rhine corridor?" | [Mortgage flood screen](.agents/skills/crc-screen-mortgage-flood/SKILL.md), acquisition reference<br>**Example:** `Use the crc-screen-mortgage-flood skill to guide a regional flood overlay in the Rhine corridor using the flood-by-province notebook.` | - | [Flood by province](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/flood_risk_by_province.ipynb) | [Flood/admin overlay](pipelines/flood_admin_pipeline.py); [covered Overture candidates](pipelines/overture_assets_pipeline.py) |
| **Understand portfolio tail loss.** "What VaR/CVaR follows from these explicit binary outcomes and independence assumptions?" | [Asset portfolio assessment](.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md), advanced reference<br>**Example:** `Use the crc-assess-asset-portfolio-risk skill to explain the portfolio-risk notebook and its binary-outcome assumptions.` | [Company assessment](.agents/skills/velo-assess-company-climate-risk/SKILL.md), different model/metrics<br>**Example:** `Use the velo-assess-company-climate-risk skill to review tail-risk metrics for the company in my assessment.` | [Portfolio risk metrics](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/portfolio_risk_metrics.ipynb) | [Risk and attribution](pipelines/portfolio_risk_pipeline.py) |
| **Explore sensitivity to a changed hazard tail.** "What changes if the fitted tail scale rises by 10%?" | [Asset portfolio assessment](.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md), sensitivity reference<br>**Example:** `Use the crc-assess-asset-portfolio-risk skill to explore a 10% tail-scale stress using the multi-scenario notebook.` | -; local stresses are not enterprise climate projections | [Multi-scenario comparison](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/multi_scenario_portfolio.ipynb) | [Local tail stresses](pipelines/multi_scenario_pipeline.py) |
| **Understand a fitted flood curve.** "How does a dry-event probability combine with positive flood depth?" | [Mortgage flood screen](.agents/skills/crc-screen-mortgage-flood/SKILL.md), methods reference<br>**Example:** `Use the crc-screen-mortgage-flood skill to explain the hurdle-distribution primer.` | - | [Hurdle-distribution primer](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/hurdle_fit_primer.ipynb) | - |
| **Reconcile open and enterprise results.** "What can each assessment tell us about the same real target?" | [Compare CRC and VELO](.agents/skills/compare-crc-velo-assessments/SKILL.md)<br>**Example:** `Use the compare-crc-velo-assessments skill with the CRC and VELO results in this conversation.` | Same comparison skill; run the relevant enterprise skill first | - | [Artifact inventory](.agents/skills/compare-crc-velo-assessments/scripts/inventory_assessments.py), followed by the skill's semantic comparison |

## Run a notebook

Open a notebook from the table in Colab and choose **Runtime → Run all**. No
clone, API key or GPU is required. The first run installs dependencies and may
take several minutes; saved outputs are already visible on GitHub.

Prefer a local environment? Use Python 3.12+:

```shell
uv sync --locked
uv run jupyter lab notebooks/
```

For a small fixture-based run from the repository root:

```shell
uv run python pipelines/asset_portfolio_pipeline.py
```

For live JRC flood acquisition and Overture candidate discovery:

```shell
./ai-playbooks/examples/run-open-demo.sh
```

The portfolio learning track uses checked-in Cologne fixtures. The spatial and
agricultural examples acquire remote data and may take several minutes.
See [setup and output files](ai-playbooks/docs/setup.md#live-open-demonstration)
for prerequisites, changing geography and caching.

## Read the results correctly

A completed AI assessment should include a concise results table, relevant charts
and a map when locations are available, backed by downloadable data and provenance.
The helper scripts produce intermediate data; the skill directs the assistant to
assemble the final report. Missing evidence must remain visible.

- Overture places are candidate locations, not proof of ownership, collateral or
  portfolio membership. Crop cover and predicted field boundaries likewise do
  not establish yield, ownership or financial exposure.
- Flood depth, damage ratio and portfolio loss are different quantities. A
  historical JRC result is not a future climate scenario. Keep incompatible
  hazards and metrics separate.
- Null or unmatched locations are not zero risk. Check source support, units,
  curve treatment, spatial precision and extrapolation before interpreting values.
- Use approved assets, vulnerability curves and aggregation assumptions for
  decision-facing work. Illustrative curves and local tail stresses teach methods.

## Capabilities and verification

The current reproducible baseline is **crc-sdk 0.7.1 / crc-framework 0.2.5**,
verified against the published packages. See [verification results and limits](ai-playbooks/docs/dogfood-verification.md).
The SDK handles source access, canonical hazard data and spatial/portfolio
workflows; the framework provides distributions, fitting, impacts and risk metrics.

- [Capability matrix](ai-playbooks/docs/capability-matrix.md): supported surfaces and interpretation limits.
- [Gap backlog](ai-playbooks/docs/gap-backlog.md): remaining workflow work, distinct from available primitives.
- [Product strategy](ai-playbooks/docs/product-strategy.md): why pair open and enterprise evidence.
- [Agent entry point](AGENTS.md): canonical skill discovery.

CRC and VELO/CDT results require an explicit semantic crosswalk; this repository
does not claim that all enterprise computations already run on CRC.
