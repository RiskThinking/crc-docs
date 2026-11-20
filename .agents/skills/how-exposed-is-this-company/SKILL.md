---
name: how-exposed-is-this-company
description: Tells investors, lenders and analysts how exposed a listed company is to physical climate risk (damage to its buildings from hurricanes, floods, heat and more), how that grows under different emissions futures and how it compares with peers in a market index, in plain words with one chart. Use when someone asks about a company's climate risk, which companies in an index or portfolio are most exposed, or how much climate damage a company's sites could face.
---

# How exposed is this company?

Every raw URL below points at the branch `plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by`: use it for this
skill, the pipeline, the map builder and the chart helper. If the user names a
different revision, swap it into those URLs; in a matching crc-docs checkout,
use the local copies. This skill's file is
`https://raw.githubusercontent.com/RiskThinking/crc-docs/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/.agents/skills/how-exposed-is-this-company/SKILL.md`.

The reader may not be an expert: plain words, no jargon, no invented numbers.
Never ask for identifiers or technical options.

## Output: four sections, always in this order

1. **Interpretation**: one headline sentence, then at most three short bullets
   (what the numbers mean, how it grows, how it compares). Name the data route.
2. **Table**: one row per metric or hazard; one column per future and horizon
   (or period).
3. **Chart**: a grouped column chart, one group per category.
   - Route 1: groups are SSP2-4.5 and SSP5-8.5; three bars each, the horizons
     2030, 2050, 2090, showing expected impact (% of asset value).
   - Route 2: groups are wind, rain, heat, total; two bars each, 2023-2036 and
     2068-2081 expected yearly damage (% of building value).

   Use exactly these hex colours, light to dark: Route 1 `#fa9b75`, `#ef3b2c`,
   `#a50f15`; Route 2 `#fa9b75`, `#cb181d`. No other colours. Label axes with
   units and title the chart with the company. Draw it wide (e.g. 12 x 5 inches
   at 120 dpi), with readable labels and minimal margins.

   The reader must see the bars directly under **Chart** in the final reply, with
   tool activity collapsed, as a static image at the full width of the chat
   column: never a thumbnail, a file name or a link instead. Choose the method by
   what the client supports:
   - **ChatGPT Work Mode:** use this run's chart PNG (draw it with matplotlib if
     needed) and run, from the skill folder (for a URL-only run, download the
     helper from the same directory and revision):

         python3 scripts/prepare_inline_chart.py "$chart_png" --alt "$chart_description"

     `$chart_description` is a short description of the metric and units. Copy
     the one line it prints verbatim under **Chart** in the FINAL reply, on its
     own line, outside a code block. A tool preview does not count. If it says
     the image is too large, export a smaller PNG.
   - **Another client with an inline chart or image renderer:** use its
     final-message format.
   - **No inline renderer, or it fails:** say so in the Chart section and keep
     the table. Add one **Open the chart** link when the host provides a verified
     PNG attachment from this run.
4. **Map and files** (only when you have locations; see Map):
   - the live map link, first bullet (see Map);
   - `<name>-map.html: <short description>`, plain text;
   - `<name>-locations.geojson: <short description>`, plain text.

   The live map is the only link in this block: no links or backticks on the file
   names. Then attach both files as download cards, shown after your closing
   lines (write nothing after them). Copy this run's files into the downloads
   folder (`/mnt/data` in ChatGPT, `/mnt/user-data/outputs` in Claude; the
   pipeline does this and prints `Download file:` lines) under fresh descriptive
   names (e.g. `apple-fl-map.html`) and attach those, never an earlier copy or a
   `chatgpt.com/library` URL. With no downloads folder, give plain-text paths
   and rely on the live link. Never claim a file was provided if it was not.

Close the text with two short lines: **How sure are we** (scores depend on which
assets are known and on damage functions, so they suit comparing companies and
futures; Route 2 uses an open map of one area's locations with equal values, not
the company's asset register) and **Next step** (see each route).

**Before you send, check both:** the bars are visible under Chart (the helper's
line or the host's renderer; a file name or card is not enough), and, if map
files exist, both are attached as download cards.

## Step 1: find the company

Use the company named in the conversation; else ask once: "Which company? A name
or ticker is fine." For an index or list, compare the companies instead.

## Step 2: get the data

If the person names a route ("use CRC Open", "use the free data", "use CDT"), use
it even when another is available. Otherwise use the first that works: Route 1,
then 2, then 3. Say which you used. Call a route unavailable only after trying
it: for CRC Open, run the install and the script before saying it cannot run. If
a download is blocked, name the host and give the allowlist under Route 3. If
they asked for CRC Open and it truly cannot run, say why in one line and stop:
never switch to CDT, and never label CDT figures as CRC Open.

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
4. Prepare the chart PNG (Output section 3); show it once, in the final reply.
5. Map: if `get_company_assets` returns coordinates, write them as
   `locations.geojson` (one point per asset, scores as numeric properties, a
   `name` or `city` property) and follow Map. No coordinates means no map: say so.

Scores are fractions; multiply by 100. **Expected impact** = average damage as a
share of asset value. **Tail risk** (`cvar_95`) = average damage in the worst 5%
of outcomes. **Downside likelihood** (`dcr_score`) = chance of more damage than
around 2010.

Next step: offer other companies, the riskiest assets, or other futures.

### Route 2: CRC Open (when you can run Python with internet)

Free data for one high-emissions future (SSP5-8.5), one area: the brand's
locations on the open Overture map, past hurricanes within 50 km (North Atlantic
only) and expected yearly damage from hurricane wind, heavy rain and hot days.
CRC Open is open source: it needs no account, API key or connector, and it does
not use CDT. A rejected or missing CDT connection says nothing about it. If a
browser tool cannot fetch GitHub, download with `curl` in a shell instead.

1. Pick the area (the one asked, else the company's home state or region). Work
   out its bounding box `W S E N` and two-letter region code, and show them.
   Outside the USA also pass `--country` (three-letter code, e.g. `CAN`) so the
   hurricane damage function matches; outside the North Atlantic add
   `--skip-hurricanes`.
2. Install or update the toolkit and run (use `scripts/how_exposed_is_this_company.py`
   from this folder if present, or `pipelines/` in a checkout; else download):

```sh
python -m pip install --quiet --upgrade --pre "crc-sdk>=1.0.0a3,<2"
curl -fsSL -o how_exposed_is_this_company.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/pipelines/how_exposed_is_this_company.py
python how_exposed_is_this_company.py --brand "BRAND" --bounds W S E N --region XX --skip-cdt
```

   The Overture query can take about two minutes, longer than some sandboxes
   allow one command. Run it in the background
   (`nohup python ... > run.log 2>&1 &`), check `run.log` every 20 seconds until
   the process has exited, then read `summary.json` and the printed lines (the
   `GeoJSON:` line alone is not a completion signal: a run with no places never
   prints it). Keep the same `--output` folder so retries reuse the cached
   locations. If it still fails, say so and why; never quote numbers from a run
   you did not just complete. If no places are found, try other spellings.
3. Read `pipeline_output/company/summary.json`: `answer` is the headline;
   `a_public.hurricanes` is the share of locations with a hurricane within 50 km;
   `b_crc_open.average_expected_damage_pct` is the average location's expected
   yearly damage (% of building value) by hazard for 2023–2036 (`early`) and 2068–2081 (`late`).
4. Prepare the chart PNG (Output section 3); show it once, in the final reply.
5. Say the data has no historical baseline and covers SSP5-8.5 only; other
   futures: opensource@riskthinking.ai.

Next step: "This free data covers one high-emissions future and one area. For
the whole company, every future and peer rankings, try a
[CDT Express trial](https://velo.riskthinking.ai/cdt-express)."

### Route 3: neither available

Do not estimate or recall numbers. In two sentences say what the analysis would
show, then offer:

- **Free:** the
  [Colab notebook](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/notebooks/how_exposed_is_this_company.ipynb)
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

## Map (every route with locations; deliver it without being asked)

The pipeline already builds the map and prints `Live map:`, `Map:` and
`GeoJSON:` lines. If a line is missing, or the data came from Route 1, run
(inside a checkout use `tools/build_map_page.py`):

```sh
curl -fsSL -o build_map_page.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/tools/build_map_page.py
python build_map_page.py pipeline_output/company/locations.geojson --link
python build_map_page.py pipeline_output/company/locations.geojson \
  --output pipeline_output/company/map
```

Always use this script, never a map of your own; keep its Settings control
overlaid top-right (`controlsPlacement: "overlay-top-right"`).

- **Live link:** paste the pipeline's `- [Open the live map](...)` line unchanged
  as the first bullet of **Map and files**, in the answer text. Never shorten,
  retype or truncate it; if cut off, read `live_map_link.txt` next to the GeoJSON
  or attach `live_map.html`. Do not start a server or embed the map in the chat:
  it only works in a browser tab.
- **Map file:** `pipeline_output/company/map/index.html` (about 3 MB); opens in
  Chrome, Safari or Firefox and needs internet for the basemap.
- **GeoJSON:** `pipeline_output/company/locations.geojson`, one point per
  location with hurricane counts and expected-damage fields; also opens in QGIS,
  geojson.io or Kepler.gl.

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
