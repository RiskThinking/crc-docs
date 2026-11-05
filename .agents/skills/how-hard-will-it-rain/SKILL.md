---
name: how-hard-will-it-rain
description: Tells anyone how much rain can fall in one day at a place and how that changes later this century, in plain words with one chart. Use when someone asks about heavy rain, downpours, cloudbursts, rainstorms, flash-flood rain or "how hard will it rain" for a city, address or site.
---

# How hard will it rain?

The person asking may not be an expert. Give them a short, honest answer they can
repeat to someone else: one headline sentence, one small table, one chart when
the host can draw it, and one line on how sure we are. Avoid jargon; when a term
is unavoidable, explain it in a few words.

Latest version of this skill:
`https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/how-hard-will-it-rain/SKILL.md`.
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

Rain is noisy: a single future year can be unusually wet or dry. Always average
several horizons (as below) and lead with the **1-in-10-year** wettest day;
rarer values such as 1-in-100 are much less certain.

### Route 1: CDT, when the CDT Express connection is available

CDT is Riskthinking.AI's Climate Digital Twin. If you have CDT Express tools
(names such as `get_climate_metrics_exposure`), use them. They give every
emissions future and a matching historical baseline.

1. Call `get_climate_metrics_exposure` with the place's `latitude` and
   `longitude`, `risk_factors: ["rx1day"]`, `pathway: ["ssp126", "ssp245", "ssp585"]`,
   `horizon: ["2070", "2080", "2090"]` and `return_periods: [2, 10, 25]`.
   Average the three horizons for each pathway.
2. Call it again with `pathway: ["historic"]` and `horizon: ["2010"]` for the baseline.
3. Values are millimetres of rain on the year's wettest day. A missing pathway
   means no data, not zero.

### Route 2: CRC Open, when you can run Python with internet access

CRC Open is free, ready-made climate data. Its public release covers one
high-emissions future (SSP5-8.5); other futures are available from
sales@riskthinking.ai. Install or update the toolkit, then run the analysis script:

```sh
python -m pip install --quiet --upgrade "crc-sdk[geometry]"
curl -fsSL -o how_hard_will_it_rain.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/main/pipelines/how_hard_will_it_rain.py
python how_hard_will_it_rain.py --name "PLACE" --latitude LAT --longitude LON --skip-era5 --skip-cdt
```

If this skill folder contains `scripts/how_hard_will_it_rain.py`, run that copy
instead of downloading one. Read `pipeline_output/how_hard_rain/summary.json`:
its `answer` is the headline and `b_crc_open` holds the values for three windows
of years (each an average of several horizons).

`--skip-era5` keeps the run under a minute. Only if the person wants the
recorded past too, install `"crc-sdk[zarr,netcdf,geometry]"` and drop that flag
(about 8 minutes); then `a_era5` holds the ERA5 record, which is on a coarse
grid and understates local downpours.

If a download is blocked, the sandbox probably limits internet access. Say so,
and suggest allowing `pypi.org`, `raw.githubusercontent.com` and
`data.riskthinking.ai` (plus `storage.googleapis.com` for ERA5), or use Route 3.

### Route 3: neither is available

Do not estimate or recall numbers. Explain in two sentences what the analysis
would show, then offer both options:

- **Free, no setup:** open the
  [Colab notebook](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_hard_will_it_rain.ipynb),
  change `CITY` in the first cell and choose **Runtime → Run all**.
- **Every emissions future, in this chat:** connect CDT Express. Add a custom
  connection named **CDT Express** with the URL `https://mcp.riskthinking.ai/mcp`
  and sign in (Claude: **Customize → Connectors → + Add → Add custom connector**;
  ChatGPT: **Plugins → + → Add custom MCP server**; full steps in the
  [setup guide](https://github.com/RiskThinking/cdt-express-mcp#connect-by-url-recommended)).
  A [CDT Express trial](https://velo.riskthinking.ai/cdt-express) provides access.

## 3. Answer

1. **Headline**, for example: "In Toronto, a 1-in-10-year wettest day brings
   about 51 mm of rain early this century. By 2070–2090 that much rain falls
   about every 4 years." A "1-in-10-year" day has a 10% chance of happening in
   any given year.
2. **Table:** rows for 1-in-2, 1-in-10 and 1-in-25-year wettest days; columns for
   each window of years or emissions future you have, in mm.
3. **Chart**, when you can draw one: a bar chart of the 1-in-10-year wettest day
   for each window or future, labelled in mm. Use one colour family that darkens
   with time, or one distinct colour per emissions future.
4. **How sure are we**, one or two lines: values describe an area of about
   250 km², not a street; they come from climate models; rarer days are less
   certain, which is why we lead with 1-in-10.
5. **Next step**, one line matching the route:
   - Route 1: offer to compare with other hazards (river or coastal flooding) or
     check buildings and financial impact with the same connection.
   - Route 2: "This free data covers one high-emissions future. For other futures,
     a historical baseline or financial impact, see
     [CDT Express](https://velo.riskthinking.ai/cdt-express) or contact
     sales@riskthinking.ai."

## Rules

- Never invent or guess numbers. Report missing data as missing, not as safe.
- Name the source: "Riskthinking.AI Climate Digital Twin (CDT)" (licensed), or
  "CRC Open by Riskthinking.AI, CC BY-NC 4.0" (free for non-commercial use), plus
  "ERA5, Copernicus" when used.
- Heavy rain is not flooding: whether a street floods also depends on drains,
  ground and rivers. Point to a flood question for that.
- SSP5-8.5 is a high-emissions future, not a prediction of what will happen.
- Don't present a horizon such as 2080 as a weather forecast for that year; it
  describes typical conditions around that time.
- Don't ask for or display API keys; CDT access uses the connector's sign-in.
