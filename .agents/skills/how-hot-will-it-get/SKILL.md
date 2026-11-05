---
name: how-hot-will-it-get
description: Tells anyone how hot the hottest day of the year gets at a place today and how that changes by 2050 and 2080, in plain words with one chart. Use when someone asks about future heat, heatwaves, extreme temperatures or "how hot will it get" for a city, address or site.
---

# How hot will the hottest day get?

The person asking may not be an expert. Give them a short, honest answer they can
repeat to someone else: one headline sentence, one small table, one chart when
the host can draw it, and one line on how sure we are. Avoid jargon; when a term
is unavoidable, explain it in a few words.

Latest version of this skill:
`https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/how-hot-will-it-get/SKILL.md`.
If you can fetch it and it differs from this copy, follow the fetched one.

## 1. Find the place

Use a place already named in the conversation; otherwise ask one question:
"Which city or address?" Work out its latitude and longitude yourself and show
them, so the person can correct you. Never ask for coordinates or technical options.

## 2. Use the best data you can reach

If the person names a source ("use CRC Open", "use the free data", "use CDT"),
use that route even when another is available. Otherwise check the three routes
in order and use the first that works. Tell the person which one you used and,
when both data routes are available, offer to rerun with the other.

### Route 1: CDT, when the CDT Express connection is available

CDT is Riskthinking.AI's Climate Digital Twin. If you have CDT Express tools
(names such as `get_climate_metrics_exposure`), use them. They give every
emissions future and a matching historical baseline.

1. Call `get_climate_metrics_exposure` with the place's `latitude` and
   `longitude`, `risk_factors: ["tx_max"]`, `pathway: ["ssp126", "ssp245", "ssp585"]`,
   `horizon: ["2050"]` and `return_periods: [2, 10, 50]`.
2. Call it again with `pathway: ["historic"]` and `horizon: ["2010"]` for the baseline.
3. Values are in kelvin: subtract 273.15 for °C. A missing pathway means no data,
   not zero.

### Route 2: CRC Open, when you can run Python with internet access

CRC Open is free, ready-made climate data. Its public release covers one
high-emissions future (SSP5-8.5); other futures are available from
sales@riskthinking.ai.
Install or update the toolkit, then run the analysis script:

```sh
python -m pip install --quiet --upgrade "crc-sdk[geometry]"
curl -fsSL -o how_hot_will_it_get.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/main/pipelines/how_hot_will_it_get.py
python how_hot_will_it_get.py --name "PLACE" --latitude LAT --longitude LON --skip-cdt
```

If this skill folder contains `scripts/how_hot_will_it_get.py`, run that copy
instead of downloading one. Read `pipeline_output/how_hot/summary.json`: its
`answer` is the headline, `b_crc_open` holds the future values and `a_station`
holds the nearest weather station's measured past (when one has enough years).

If a download is blocked, the sandbox probably limits internet access. Say so,
and suggest allowing `pypi.org`, `raw.githubusercontent.com`,
`data.riskthinking.ai` and `noaa-ghcnh-pds.s3.amazonaws.com`, or use Route 3.

### Route 3: neither is available

Do not estimate or recall numbers. Explain in two sentences what the analysis
would show, then offer both options:

- **Free, no setup:** open the
  [Colab notebook](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_hot_will_it_get.ipynb),
  change `CITY` in the first cell and choose **Runtime → Run all**.
- **Every emissions future, in this chat:** connect CDT Express. Add a custom
  connection named **CDT Express** with the URL `https://mcp.riskthinking.ai/mcp`
  and sign in (Claude: **Customize → Connectors → + Add → Add custom connector**;
  ChatGPT: **Plugins → + → Add custom MCP server**; full steps in the
  [setup guide](https://github.com/RiskThinking/cdt-express-mcp#connect-by-url-recommended)).
  A [CDT Express trial](https://velo.riskthinking.ai/cdt-express) provides access.

## 3. Answer

1. **Headline**, for example: "In Phoenix, a 1-in-10-year hottest day is about
   50 °C today. By 2080 that heat comes about every 2 years."
   A "1-in-10-year" day has a 10% chance of happening in any given year.
2. **Table:** rows for 1-in-2, 1-in-10 and 1-in-50-year hottest days; columns for
   each period or emissions future you have, in °C.
3. **Chart**, when you can draw one: hottest-day temperature (y) against "1 in N
   years" on a log scale (x), one line per period or future. Use one colour family
   that darkens with time; label every line.
4. **How sure are we**, one or two lines: values describe a city-sized area, not a
   street; they come from climate models; a weather station shows the measured
   past and can differ from the models, especially for rare extremes.
5. **Next step**, one line matching the route:
   - Route 1: offer to compare emissions futures or check buildings and financial
     impact with the same connection.
   - Route 2: "This free data covers one high-emissions future. For other futures,
     a historical baseline or financial impact, see
     [CDT Express](https://velo.riskthinking.ai/cdt-express) or contact
     sales@riskthinking.ai."

## Rules

- Never invent or guess numbers. Report missing data as missing, not as safe.
- Name the source: "Riskthinking.AI Climate Digital Twin (CDT)" (licensed), or "CRC Open by
  Riskthinking.AI, CC BY-NC 4.0" (free for non-commercial use), plus "NOAA GHCNh"
  for station data.
- SSP5-8.5 is a high-emissions future, not a prediction of what will happen.
- Don't present a horizon such as 2050 as a weather forecast for that year; it
  describes typical conditions around that time.
- Don't ask for or display API keys; CDT access uses the connector's sign-in.
