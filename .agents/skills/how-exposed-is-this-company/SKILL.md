---
name: how-exposed-is-this-company
description: Tells investors, lenders and analysts how exposed a listed company is to physical climate risk (damage to its buildings from hurricanes, floods, heat and more), how that grows under different emissions futures and how it compares with peers in a market index, in plain words with one chart. Use when someone asks about a company's climate risk, which companies in an index or portfolio are most exposed, or how much climate damage a company's sites could face.
---

# How exposed is this company?

Latest version: `https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/how-exposed-is-this-company/SKILL.md`.
If it differs from this copy, follow the fetched one, unless you are inside a
crc-docs checkout: then this copy and the repo's `pipelines/` and `tools/` win.

The reader may not be an expert. Plain words, no jargon, no invented numbers.
Never ask for identifiers or technical options.

## Output: four sections, always in this order

1. **Interpretation**: one headline sentence, then at most three short bullets
   (what the numbers mean, how it grows, how it compares). Name the data route
   used.
2. **Table**: one row per metric or hazard; one column per future and horizon
   (or period).
3. **Chart**: a grouped column chart, one group per category.
   - Route 1: categories are the two futures, SSP2-4.5 and SSP5-8.5; each group
     has three bars, the horizons 2030, 2050 and 2090, showing expected impact
     (% of asset value).
   - Route 2: categories are wind, rain, heat and total; bars are 2023-2036 and
     2068-2081 expected yearly damage (% of building value).
   Use exactly these hex colours, light to dark (later is darker): Route 1's
   three bars `#fa9b75`, `#ef3b2c`, `#a50f15`; Route 2's two bars `#fa9b75`,
   `#cb181d`. No other colours.
   Label axes with units and title it with the company. The chart is required:
   never skip it. Use the host's chart tool if there is one. Otherwise draw it
   with Python (matplotlib), save the PNG, then render it inline: return the PNG
   itself as image content in the conversation. A file name, a download card or a
   markdown image link alone does not satisfy this. In ChatGPT Work Mode, call
   this with the chart's actual absolute path (the `image(...)` call is what
   returns the chart as image content):

       const chart = await tools.view_image({ path: "/absolute/path/to/chart.png" });
       image(chart.image_url);

   In Claude, display the image in the tool output. Under the inline chart add
   one link to the PNG (in ChatGPT `[Open the chart](sandbox:/mnt/data/<name>-chart.png)`;
   the sandbox opens it). If direct image output is unavailable, say so in one
   line and give that link alone.
4. **Map and files** (only when you have locations; see Map below):
   - the live map link, as the first bullet;
   - <name>-map.html: <short description> (plain text, no backticks, no link);
   - <name>-locations.geojson: <short description> (plain text, no backticks,
     no link).
   Do not add a line of file links anywhere, and do not link the file names. The
   only link in this block is the live map. End the reply with the two files
   attached as download cards (one per file, download button only): in ChatGPT
   attach the files from this run as you would attach a file to a message, with
   no link text before or after the cards. Always copy the files from this run
   into the downloads folder under fresh descriptive names (e.g.
   `apple-fl-map.html`) and attach those; never attach or link an earlier copy
   or a `chatgpt.com/library` URL.

Then close with two short lines: **How sure are we** (scores depend on which
assets are known and on damage functions, so they suit comparing companies and
futures; Route 2 uses an open map of one area's locations with equal values, not
the company's asset register) and **Next step** (see each route).

## Step 1: find the company

Use the company named in the conversation; else ask once: "Which company? A name
or ticker is fine." For an index or list, compare the companies instead.

## Step 2: get the data

If the person names a route ("use CRC Open", "use CDT"), use it. Otherwise use
the first that works: Route 1, then 2, then 3. Say which you used.

### Route 1: CDT (when `search_companies` and related CDT Express tools exist)

1. `search_companies` by `name` or `stock_ticker` (retry with `method: "fuzzy"`
   if empty; confirm ambiguous matches).
2. `get_company_climate_scores` with the `company_id`,
   `metric: ["expected_impact", "cvar_95", "dcr_score"]`, for `pathway` in
   `ssp245`, `ssp585` and `horizon` in `2030`, `2050`, `2090`.
3. Peers: `search_market_indexes` (the index named, else a well-known one that
   holds the company, e.g. S&P 500 or Dow Jones Industrial Average), then
   `get_market_index_companies_climate_scores` with `pathway: "ssp585"`,
   `horizon: "2050"`, the same metrics, `sort_by: "expected_impact"`. Report the
   company's rank.
4. Map: if `get_company_assets` returns coordinates, write them as
   `locations.geojson` (one point per asset, scores as numeric properties, a
   `name` or `city` property) and follow Map. No coordinates means no map: say so.

Scores are fractions; multiply by 100. **Expected impact** = average damage as a
share of asset value. **Tail risk** (`cvar_95`) = average damage in the worst 5%
of outcomes. **Downside likelihood** (`dcr_score`) = chance of more damage than
around 2010.

Next step: offer other companies, the riskiest assets, or other futures.

### Route 2: CRC Open (when you can run Python with internet)

Free data for one high-emissions future (SSP5-8.5), one area. It finds the
brand's locations on the open Overture map, counts past hurricanes within 50 km
(North Atlantic only) and estimates expected yearly damage from hurricane wind,
heavy rain and hot days.

1. Pick the area (the one asked, else the company's home state or region). Work
   out its bounding box `W S E N` and two-letter region code, and show them.
   Outside the USA also pass `--country` (three-letter code, e.g. `CAN`) so the
   hurricane damage function matches; outside the North Atlantic add
   `--skip-hurricanes`.
2. Install or update the toolkit and run (use `scripts/how_exposed_is_this_company.py`
   from this folder if present, or `pipelines/` in a checkout; else download):

```sh
python -m pip install --quiet --upgrade "crc-sdk>=1,<2"
curl -fsSL -o how_exposed_is_this_company.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/main/pipelines/how_exposed_is_this_company.py
python how_exposed_is_this_company.py --brand "BRAND" --bounds W S E N --region XX --skip-cdt
```

   The Overture query alone can take about two minutes, longer than some
   sandboxes allow a single command. Run it in the background
   (`nohup python ... > run.log 2>&1 &`), check `run.log` every 20 seconds until
   the `GeoJSON:` line appears, and keep the same `--output` folder so retries
   reuse the cached locations. If it still fails, say it failed and why; never
   quote numbers from a run you did not just complete. If no places are found, try other
   spellings of the brand.
3. Read `pipeline_output/company/summary.json`: `answer` is the headline;
   `a_public.hurricanes` is the share of locations with a hurricane within 50 km;
   `b_crc_open.average_expected_damage_pct` is the average location's expected
   yearly damage (% of building value) by hazard for 2023–2036 (`early`) and 2068–2081 (`late`).
4. Say the data has no historical baseline and covers SSP5-8.5 only; other
   futures: opensource@riskthinking.ai.

Next step: "This free data covers one high-emissions future and one area. For
the whole company, every future and peer rankings, try a
[CDT Express trial](https://velo.riskthinking.ai/cdt-express)."

### Route 3: neither available

Do not estimate or recall numbers. In two sentences say what the analysis would
show, then offer:

- **Free:** the
  [Colab notebook](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/main/notebooks/how_exposed_is_this_company.ipynb)
  (edit `BRAND`, `AREA`, `REGION` in the first cell, then Runtime → Run all).
- **Whole company, every future:** connect CDT Express, a custom connector
  named **CDT Express** at `https://mcp.riskthinking.ai/mcp` (Claude: Customize →
  Connectors → + Add → Add custom connector; ChatGPT: Plugins → + → Add custom
  MCP server; [setup guide](https://github.com/RiskThinking/cdt-express-mcp#connect-by-url-recommended);
  [trial](https://velo.riskthinking.ai/cdt-express)).

If downloads fail, the sandbox likely blocks the network: ask to allow
`pypi.org`, `raw.githubusercontent.com`, `data.riskthinking.ai`,
`stac.overturemaps.org`, `overturemaps-us-west-2.s3.amazonaws.com`,
`www.ncei.noaa.gov`, or use Route 3.

## Map (every route with locations; deliver all three without being asked)

The pipeline already builds these and prints `Live map:`, `Map:` and
`GeoJSON:` lines. If a line is missing, or the data came from Route 1, run
(inside a checkout use `tools/build_map_page.py`):

```sh
curl -fsSL -o build_map_page.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/main/tools/build_map_page.py
python build_map_page.py pipeline_output/company/locations.geojson --link
python build_map_page.py pipeline_output/company/locations.geojson \
  --output pipeline_output/company/map
```

Always use this script, never a map of your own; keep its Settings control
overlaid top-right (`controlsPlacement: "overlay-top-right"`).

1. **Live link.** Paste the pipeline's `- [Open the live map](...)` line
   unchanged as the first bullet of **Map and files**, in the answer text. Never
   shorten, retype or truncate it; if cut off, read `live_map_link.txt` next to
   the GeoJSON or attach `live_map.html`. Do not start a server or embed the map
   in the chat: it only works in a browser tab.
2. **Map file.** `pipeline_output/company/map/index.html` (about 3 MB): opens in
   Chrome, Safari or Firefox; needs internet for the basemap.
3. **GeoJSON.** `pipeline_output/company/locations.geojson`: one point per
   location with hurricane counts and expected-damage fields; also opens in
   QGIS, geojson.io or Kepler.gl.

In a sandbox the pipeline copies files to the downloads folder (`/mnt/data` in
ChatGPT, `/mnt/user-data/outputs` in Claude) and prints a `Download file:` line
for each. Attach those files from this run, as described in **Map and files**.
If you ran the commands without the pipeline, copy the files there yourself with
descriptive names (e.g. `walmart-fl-map.html`, `walmart-fl-locations.geojson`).
With no downloads folder, give plain-text paths and rely on the live link. Never
claim a map or file was provided if it was not.

## Rules

- Never invent or guess numbers; report missing data as missing, not as safe.
- Do not compare Route 1 scores with Route 2 damage; different hazards, assets
  and bases.
- Source line: "Riskthinking.AI Climate Digital Twin (CDT)" (licensed), or
  "CRC Open by Riskthinking.AI, CC BY-NC 4.0" plus "Overture Maps Foundation"
  and "NOAA IBTrACS" for Route 2.
- Overture places show where a brand operates, not what it owns.
- SSP5-8.5 is a high-emissions future, not a prediction. Not investment advice.
- Never ask for or show API keys; CDT uses the connector's sign-in.
