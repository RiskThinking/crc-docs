# Climate Risk Commons

[![Join the community on Discord](https://img.shields.io/badge/Discord-Join%20the%20community-5865F2?logo=discord&logoColor=white)](https://discord.gg/quuhzr3wS4)

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
| **How hot will the hottest day get?** "Today's and future hottest days for my city, explained simply." Compares a weather station, free CRC Open curves and CDT. | [How hot will it get](.agents/skills/how-hot-will-it-get/SKILL.md), with CDT when connected<br>**Example:** `How hot will the hottest day get in Phoenix in the future?` | Same skill | [How hot will it get](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_hot_will_it_get.ipynb) | [Hottest-day answer](pipelines/how_hot_will_it_get.py) |
| **Screen mortgage collateral for river flooding.** "What are the 25-, 100- and 500-year depths at these properties?" | [Mortgage flood screen](.agents/skills/crc-screen-mortgage-flood/SKILL.md)<br>**Example:** `Use the crc-screen-mortgage-flood skill for Toronto, Canada.` | [Property climate underwriting](.agents/skills/velo-underwrite-property-climate/SKILL.md)<br>**Example:** `Use the velo-underwrite-property-climate skill for 392 Markham Street, Toronto.` | [JRC flood acquisition](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/jrc_global_flood_hazard.ipynb); [asset evaluation](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/asset_portfolio_evaluation.ipynb) | [Acquire flood](pipelines/jrc_flood_pipeline.py) → [screen assets](.agents/skills/crc-screen-mortgage-flood/scripts/screen_mortgage_flood.py) |
| **Estimate flood damage under an explicit curve.** "How would this approved depth-damage curve affect my insured properties?" | [Flood insurance loss](.agents/skills/crc-model-flood-insurance-loss/SKILL.md)<br>**Example:** `Use the crc-model-flood-insurance-loss skill with my attached portfolio and approved depth-damage curve.` | [Portfolio insurability triage](.agents/skills/velo-triage-portfolio-insurability/SKILL.md)<br>**Example:** `Use the velo-triage-portfolio-insurability skill for the company in my attached portfolio.` | [Event-aligned impacts](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/portfolio_impact.ipynb) | [Custom curve and assets](.agents/skills/crc-model-flood-insurance-loss/scripts/model_flood_loss.py); [fixture example](pipelines/portfolio_impact_pipeline.py) |
| **Review physical exposure across an asset portfolio.** "Which Frankfurt sites have flood or drought exposure, and where is coverage missing?" | [Asset portfolio assessment](.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md)<br>**Example:** `Use the crc-assess-asset-portfolio-risk skill for Frankfurt, with flood and drought.` | [Company or market-index assessment](.agents/skills/velo-assess-company-climate-risk/SKILL.md)<br>**Example:** `Use the velo-assess-company-climate-risk skill for the S&P 500.` | [Asset evaluation](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/asset_portfolio_evaluation.ipynb); [EDO drought](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/jrc_edo_drought_index.ipynb) | [Evaluate separate hazards](.agents/skills/crc-assess-asset-portfolio-risk/scripts/assess_asset_portfolio.py); [fixture evaluation](pipelines/asset_portfolio_pipeline.py); [acquire drought](pipelines/jrc_drought_pipeline.py) |
| **Screen agricultural sourcing areas.** "Which sampled corn and soybean areas near Ames overlap modeled flood?" | [Agricultural climate risk](.agents/skills/crc-assess-agricultural-climate-risk/SKILL.md)<br>**Example:** `Use the crc-assess-agricultural-climate-risk skill for corn and soybeans near Ames, Iowa.` | [Company assessment](.agents/skills/velo-assess-company-climate-risk/SKILL.md) when a company/supplier can be resolved; no crop-specific twin<br>**Example:** `Use the velo-assess-company-climate-risk skill for the supplier named in my sourcing assessment.` | [Crop and field exposure](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/agricultural_climate_risk.ipynb) | [Agricultural assessment](pipelines/agricultural_climate_pipeline.py) |
| **Map regional flood exposure.** "Where do modeled flood cells and candidate places overlap in the Rhine corridor?" | [Mortgage flood screen](.agents/skills/crc-screen-mortgage-flood/SKILL.md), acquisition reference<br>**Example:** `Use the crc-screen-mortgage-flood skill to guide a regional flood overlay in the Rhine corridor using the flood-by-province notebook.` | - | [Flood by province](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/flood_risk_by_province.ipynb) | [Flood/admin overlay](pipelines/flood_admin_pipeline.py); [covered Overture candidates](pipelines/overture_assets_pipeline.py) |
| **Build an open historical heat and rainfall baseline.** "How hot is a 1-in-10-year hottest day, and how wet a wettest day, at these cities?" | - | - | [ERA5 historical baseline](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/era5_historical_baseline.ipynb) | - |
| **Audit observed station heat and cold with ISD or its GHCNh successor.** "Which years are complete at Toronto Pearson, and what return levels follow from sampled temperatures?" | - | - | [NOAA ISD station extremes](notebooks/noaa_isd_station_extremes.ipynb) | [Station audit and fitting](pipelines/noaa_isd_pipeline.py), with `--source isd` or `--source ghcnh`, offline replay and fit diagnostics |
| **Inspect sea-level scenarios.** Compare NOAA 2022 station projections and source bounds relative to the 2005 baseline. Run from a local checkout. | - | - | [NOAA sea-level scenarios](notebooks/noaa_sea_level_scenarios.ipynb) | [NOAA sea-level scenario audit](pipelines/noaa_sea_level_pipeline.py) |
| **Inspect coastal extreme water levels.** Review NOAA annual exceedance levels, confidence bounds, datum and detrending context at a gauge. Run from a local checkout. | - | - | [NOAA extreme water levels](notebooks/noaa_extreme_water_levels.ipynb) | [NOAA coastal-level audit](pipelines/noaa_extreme_water_levels_pipeline.py) |
| **Inspect Canadian gauge flow and level.** Read HYDAT daily means, source symbols and checksummed snapshots; gauge level has an unspecified datum. Run from a local checkout. | - | - | [HYDAT daily observations](notebooks/hydat_daily_observations.ipynb) | [HYDAT daily gauge audit](pipelines/hydat_daily_pipeline.py) |
| **Inspect Canadian daily station observations.** Preserve GeoMet temperature, precipitation and quality flags; select a climate ID and replay cached source records. Run from a local checkout. | - | - | [ECCC daily observations](notebooks/eccc_daily_observations.ipynb) | [ECCC daily station audit](pipelines/eccc_daily_pipeline.py) |
| **Inspect gridded monthly rainfall.** Read CHIRPS v3 final monthly land pixels with checksummed source replay. Run from a local checkout. | - | - | [CHIRPS monthly rainfall](notebooks/chirps_monthly.ipynb) | [Monthly raster inspection](pipelines/chirps_monthly_pipeline.py) |
| **Inspect daily gauge streamflow.** Review USGS daily means, source status and missing days; discharge is not inundation depth. Run from a local checkout. | - | - | [USGS streamflow](notebooks/usgs_streamflow.ipynb) | [Daily streamflow inspection](pipelines/usgs_streamflow_pipeline.py) |
| **Inspect a tropical cyclone track.** NOAA IBTrACS observations retain agency fields and snapshot provenance; they do not represent asset winds or return-period curves. Run from a local checkout. | - | - | [IBTrACS tracks](notebooks/ibtracs_tracks.ipynb) | [Track inspection](pipelines/ibtracs_pipeline.py) |
| **Inspect Canadian design rainfall and release changes.** "How do 15-minute, 1-hour and 24-hour ECCC rates compare with a fitted curve?" Run from a local checkout. Current-release acquisition stages a provincial bundle. | - | - | [ECCC rainfall IDF](notebooks/eccc_rainfall_idf.ipynb) | [ECCC source audit and refitting](pipelines/eccc_idf_pipeline.py), with station IDs or repeated `--bounds` for area unions, published confidence limits and offline replay |
| **Screen a portfolio for extreme daily rainfall.** "How do Rx1day quantiles vary across sites and future horizons?" Uses the public 63-hazard CRC Open release with bounded acquisition and cache reuse. | - | - | [CRC Open rainfall screening](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/crc_open_hazards.ipynb), with saved chart previews | [CRC portfolio screening](pipelines/crc_open_pipeline.py), accepting CSV or Parquet assets and an optional ERA5 comparison |
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

## Packages and reference

This repository shows complete workflows. The packages document their own APIs
and data sources; start there for anything below the workflow level.

| Package | Covers | Docs |
|---|---|---|
| [crc-sdk](https://github.com/RiskThinking/crc-sdk) | Data sources, canonical hazard datasets, portfolio evaluation and impacts, fitting, bring your own data | [Index](https://github.com/RiskThinking/crc-sdk/tree/main/docs/README.md) · [data sources](https://github.com/RiskThinking/crc-sdk/tree/main/docs/README.md#data-sources) · [concepts](https://github.com/RiskThinking/crc-sdk/tree/main/docs/concepts.md) |
| [crc-framework](https://github.com/RiskThinking/crc-framework-rs) | Distributions, fitting, impact functions and contracts, risk metrics | [Index](https://github.com/RiskThinking/crc-framework-rs/tree/main/docs/README.md) · [Python API](https://github.com/RiskThinking/crc-framework-rs/tree/main/docs/python.md) · [impact contracts](https://github.com/RiskThinking/crc-framework-rs/tree/main/docs/impact-contracts.md) |

`uv.lock` pins the tested local environment. Colab notebooks pin their own
package versions in their setup cell.

Assessment guidance kept here:

- [Capability matrix](ai-playbooks/docs/capability-matrix.md): interpretation limits that matter in an assessment.
- [Gap backlog](ai-playbooks/docs/gap-backlog.md): workflow work that remains.
- [Product strategy](ai-playbooks/docs/product-strategy.md): why pair open and enterprise evidence.
- [Verification audit](ai-playbooks/docs/dogfood-verification.md): how the skills were last verified, and how to repeat it.
- [Agent entry point](AGENTS.md): canonical skill discovery.

CRC and VELO/CDT results require an explicit semantic crosswalk; this repository
does not claim that all enterprise computations already run on CRC.

## Community

Questions, ideas and show-and-tell are welcome on
[Discord](https://discord.gg/quuhzr3wS4). Report bugs and documentation gaps as
GitHub issues in [crc-docs](https://github.com/RiskThinking/crc-docs/issues),
[crc-sdk](https://github.com/RiskThinking/crc-sdk/issues) or
[crc-framework](https://github.com/RiskThinking/crc-framework-rs/issues).
