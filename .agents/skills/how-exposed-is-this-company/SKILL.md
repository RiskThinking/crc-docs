---
name: how-exposed-is-this-company
description: Tells investors, lenders and analysts how exposed a listed company is to physical climate risk (damage to its buildings from hurricanes, floods, heat and more), how that grows under different emissions futures and how it compares with peers in a market index, in plain words with one chart. Use when someone asks about a company's climate risk, which companies in an index or portfolio are most exposed, or how much climate damage a company's sites could face.
---

# How exposed is this company?

The person asking may not be an expert. Give them a short, honest answer they can
repeat to someone else: one headline sentence, one small table, one chart when
the host can draw it, and one line on how sure we are. Avoid jargon; when a term
is unavoidable, explain it in a few words.

Latest version of this skill:
`https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/how-exposed-is-this-company/SKILL.md`.
If you can fetch it and it differs from this copy, follow the fetched one.

## 1. Find the company

Use a company already named in the conversation; otherwise ask one question:
"Which company? A name or ticker is fine." If the person asks about an index or
a list of companies, compare them instead. Never ask for identifiers or
technical options.

## 2. Use the best data you can reach

If the person names a source ("use CRC Open", "use the free data", "use CDT"),
use that route even when another is available. Otherwise check the three routes
in order and use the first that works. Tell the person which one you used.

### Route 1: CDT, when the CDT Express connection is available

CDT is Riskthinking.AI's Climate Digital Twin. If you have CDT Express tools
(names such as `search_companies`), use them. CDT already knows the assets of
thousands of listed companies worldwide.

1. Call `search_companies` with the company `name` (or `stock_ticker`); if a
   strict search finds nothing, retry with `method: "fuzzy"`. Confirm the match
   with the person when the name is ambiguous.
2. Call `get_company_climate_scores` with its `company_id` and
   `metric: ["expected_impact", "cvar_95", "dcr_score"]` for each `pathway` in
   `ssp245` and `ssp585` and each `horizon` in `2030`, `2050` and `2090`.
3. For peers, find an index the person names (or a well-known one that includes
   the company, such as the Dow Jones Industrial Average or S&P 500) with
   `search_market_indexes`, then call
   `get_market_index_companies_climate_scores` with its `index_id`,
   `pathway: "ssp585"`, `horizon: "2050"`,
   `metric: ["expected_impact", "cvar_95", "dcr_score"]` and
   `sort_by: "expected_impact"`. Report the company's rank.

Scores are fractions; multiply by 100 for percent. **Expected impact** is the
average damage as a share of tangible asset value; **tail risk** (`cvar_95`) is
the average damage in the worst 5% of outcomes; **downside likelihood**
(`dcr_score`) is the chance of more damage than around 2010. Compare SSP2-4.5
with SSP5-8.5 for company totals.

### Route 2: CRC Open, when you can run Python with internet access

CRC Open is free, ready-made climate data. Its public release covers one
high-emissions future (SSP5-8.5); other futures are available from
opensource@riskthinking.ai. This route finds the company's locations in one area
on the open Overture map (by brand name), counts past hurricanes near them
(North Atlantic only) and estimates expected yearly damage from hurricane wind,
heavy rain and hot days with open damage functions.

Pick an area: the one the person asks about, otherwise the company's home state
or region. Work out its bounding box (`min_lon min_lat max_lon max_lat`) and
two-letter region code yourself and show them. Then install or update the
toolkit and run the script:

```sh
python -m pip install --quiet --upgrade "crc-sdk[geometry]"
curl -fsSL -o how_exposed_is_this_company.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/main/pipelines/how_exposed_is_this_company.py
python how_exposed_is_this_company.py --brand "BRAND" --bounds W S E N --region XX --skip-cdt
```

If this skill folder contains `scripts/how_exposed_is_this_company.py`, run that
copy instead of downloading one. It takes one to two minutes for a state. Add
`--skip-hurricanes` outside the North Atlantic. If no places are found, try the
brand's spelling on its storefronts. Read `pipeline_output/company/summary.json`:
`answer` is the headline; `a_public.hurricanes` holds the share of locations a
hurricane passed within 50 km of; `b_crc_open.average_expected_damage_pct`
holds the average location's expected yearly damage (% of building value) by
hazard for 2025–2035 (`early`) and 2070–2080 (`late`).

If a download is blocked, the sandbox probably limits internet access. Say so,
and suggest allowing `pypi.org`, `raw.githubusercontent.com`,
`data.riskthinking.ai`, `stac.overturemaps.org`, `overturemaps-us-west-2.s3.amazonaws.com`
and `www.ncei.noaa.gov`, or use Route 3.

### Route 3: neither is available

Do not estimate or recall numbers. Explain in two sentences what the analysis
would show, then offer both options:

- **Free, no setup:** open the
  [Colab notebook](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_exposed_is_this_company.ipynb),
  change `BRAND`, `AREA` and `REGION` in the first cell and choose **Runtime → Run all**.
- **The whole company, every emissions future, in this chat:** connect CDT
  Express. Add a custom connection named **CDT Express** with the URL
  `https://mcp.riskthinking.ai/mcp` and sign in (Claude: **Customize →
  Connectors → + Add → Add custom connector**; ChatGPT: **Plugins → + → Add
  custom MCP server**; full steps in the
  [setup guide](https://github.com/RiskThinking/cdt-express-mcp#connect-by-url-recommended)).
  A [CDT Express trial](https://velo.riskthinking.ai/cdt-express) provides access.

## 3. Answer

1. **Headline**, for example: "Across all its assets, CDT puts Walmart's expected
   climate damage at about 12% of asset value by 2050 under high emissions
   (11% under a middle path), 14th of the 30 Dow companies." Or for Route 2:
   "Since 1990 a hurricane passed within 50 km of 81% of Walmart's Florida
   stores; the average store's expected yearly damage roughly doubles, from
   0.8% to 1.6% of its value, by 2070–2080, mostly from heat."
2. **Table:** rows for each score (or hazard), columns for each future and
   horizon (or period).
3. **Chart**, when you can draw one: expected impact by horizon, one line per
   future; or the index ranked by expected impact with the company highlighted.
4. **How sure are we**, one or two lines: scores depend on which assets are
   known and on damage functions, so they are best for comparing companies and
   futures; Route 2 uses an open map of one area's locations with equal values,
   not the company's own asset register.
5. **Next step**, one line matching the route:
   - Route 1: offer to compare with other companies, look at the riskiest
     assets, or switch emissions futures.
   - Route 2: "This free data covers one high-emissions future and one area.
     For the whole company, every future and peer rankings, try a
     [CDT Express trial](https://velo.riskthinking.ai/cdt-express)."

## Rules

- Never invent or guess numbers. Report missing data as missing, not as safe.
- Don't compare Route 1 scores with Route 2 damage numbers; they use different
  hazards, assets and bases.
- Name the source: "Riskthinking.AI Climate Digital Twin (CDT)" (licensed), or
  "CRC Open by Riskthinking.AI, CC BY-NC 4.0" (free for non-commercial use),
  plus "Overture Maps Foundation" and "NOAA IBTrACS" for Route 2.
- Overture places show where a brand operates, not what the company owns.
- This is not investment advice.
- SSP5-8.5 is a high-emissions future, not a prediction of what will happen.
- Don't ask for or display API keys; CDT access uses the connector's sign-in.
