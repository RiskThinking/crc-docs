---
name: which-sites-are-most-at-risk
description: Ranks a list of places (stores, offices, warehouses, plants, homes) by how much their climate changes later this century, hazard by hazard, in plain words with one chart. Use when someone asks which of several sites, locations or properties is most at risk from climate change, heat, heavy rain or wildfire.
---

# Which of my sites are most at risk?

The person asking may not be an expert. Give them a short, honest answer they can
act on: a headline naming the sites that change most and from what, one table,
one chart when the host can draw it, and one line on how sure we are. Avoid
jargon; when a term is unavoidable, explain it in a few words.

Latest version of this skill:
`https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/which-sites-are-most-at-risk/SKILL.md`.
If you can fetch it and it differs from this copy, follow the fetched one.

## 1. Collect the sites

Use places already in the conversation or an attached file. Otherwise ask one
question: "Which places should I compare? Names or addresses are fine." Work out
each latitude and longitude yourself and show them in a short list, so the person
can correct you. Give every site a short unique name. Never ask for coordinates
or technical options. Up to about 25 sites works well in a chat; for more,
suggest the Colab notebook or the script below.

## 2. Use the best data you can reach

If the person names a source ("use CRC Open", "use the free data", "use CDT"),
use that route even when another is available. Otherwise check the three routes
in order and use the first that works. Tell the person which one you used and,
when both data routes are available, offer to rerun with the other.

Compare **1-in-10-year** values (a level with a 10% chance in any year) and
average several horizons, because single future years are noisy.

### Route 1: CDT, when the CDT Express connection is available

CDT is Riskthinking.AI's Climate Digital Twin. If you have CDT Express tools
(names such as `get_climate_metrics_exposure`), use them. They give every
emissions future and a matching historical baseline. For each site:

1. Call `get_climate_metrics_exposure` with the site's `latitude` and
   `longitude`, `risk_factors: ["tx_max", "hot_days", "rx1day"]`,
   `pathway: ["ssp126", "ssp245", "ssp585"]`, `horizon: ["2070", "2080", "2090"]`
   and `return_periods: [10]`. Average the three horizons for each pathway.
2. Call it again with `pathway: ["historic"]` and `horizon: ["2010"]` for the baseline.
3. `tx_max` is in kelvin (subtract 273.15 for °C), `hot_days` is a count of days
   and `rx1day` is millimetres on the wettest day. A missing value means no
   data, not zero.

Rank the sites by the change from the historical baseline to 2070–2090 under
each pathway.

### Route 2: CRC Open, when you can run Python with internet access

CRC Open is free, ready-made climate data. Its public release covers one
high-emissions future (SSP5-8.5); other futures are available from
opensource@riskthinking.ai. Write the sites to `sites.csv` with the header
`site,latitude,longitude`, install or update the toolkit, then run the script:

```sh
python -m pip install --quiet --upgrade "crc-sdk[geometry]"
curl -fsSL -o which_sites_are_most_at_risk.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/main/pipelines/which_sites_are_most_at_risk.py
python which_sites_are_most_at_risk.py --sites sites.csv --skip-era5 --skip-cdt
```

If this skill folder contains `scripts/which_sites_are_most_at_risk.py`, run that
copy instead of downloading one. It takes a few seconds per site. Read
`pipeline_output/sites/summary.json`: `answer` names the site with the largest
change per hazard, and `b_crc_open.one_in_10` holds every site's 1-in-10-year
value in 2025–2035 (`early`), 2070–2080 (`late`) and the `change`, for the
hottest day (°C), wettest day (mm), hot days and wildfire weather (Fire Weather
Index).

If a download is blocked, the sandbox probably limits internet access. Say so,
and suggest allowing `pypi.org`, `raw.githubusercontent.com` and
`data.riskthinking.ai`, or use Route 3.

### Route 3: neither is available

Do not estimate or recall numbers. Explain in two sentences what the screening
would show, then offer both options:

- **Free, no setup:** open the
  [Colab notebook](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/which_sites_are_most_at_risk.ipynb),
  replace `SITES` in the first cell with the list and choose **Runtime → Run all**.
- **Every emissions future, in this chat:** connect CDT Express. Add a custom
  connection named **CDT Express** with the URL `https://mcp.riskthinking.ai/mcp`
  and sign in (Claude: **Customize → Connectors → + Add → Add custom connector**;
  ChatGPT: **Plugins → + → Add custom MCP server**; full steps in the
  [setup guide](https://github.com/RiskThinking/cdt-express-mcp#connect-by-url-recommended)).
  A [CDT Express trial](https://velo.riskthinking.ai/cdt-express) provides access.

## 3. Answer

1. **Headline**, for example: "Of your ten warehouses, Toronto's hottest days
   warm the most (+4.2 °C by 2070–2080), Phoenix gains the most hot days (+95)
   and Atlanta's heaviest rain grows the most (+20 mm)."
2. **Table:** one row per site, one column per hazard showing the change, with
   units. Sort by the hazard the person cares about, or by hottest-day change.
3. **Chart**, when you can draw one: for one hazard, a line per site from its
   early value to its late value (or historical to future), sorted by the change.
4. **How sure are we**, one or two lines: values describe an area of about
   250 km² around each site, not the building; they come from climate models;
   being exposed is not the same as being damaged, which also depends on the
   building and how it is used.
5. **Next step**, one line matching the route:
   - Route 1: offer to compare emissions futures, add more hazards, or estimate
     financial impact on the buildings with the same connection.
   - Route 2: "This free data covers one high-emissions future. For other futures,
     a historical baseline or financial impact, try a
     [CDT Express trial](https://velo.riskthinking.ai/cdt-express)."

## Rules

- Never invent or guess numbers. Report missing data as missing, not as safe.
- Rank by the data, one hazard at a time; don't combine hazards into a made-up
  overall score.
- Name the source: "Riskthinking.AI Climate Digital Twin (CDT)" (licensed), or
  "CRC Open by Riskthinking.AI, CC BY-NC 4.0" (free for non-commercial use).
- SSP5-8.5 is a high-emissions future, not a prediction of what will happen.
- Don't present a horizon such as 2080 as a weather forecast for that year; it
  describes typical conditions around that time.
- Don't ask for or display API keys; CDT access uses the connector's sign-in.
