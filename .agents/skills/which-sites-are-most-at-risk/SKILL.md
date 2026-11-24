---
name: which-sites-are-most-at-risk
description: Ranks a list of places (stores, offices, warehouses, plants, homes) by how much their climate changes later this century, hazard by hazard, in plain words with one chart. Use when someone asks which of several sites, locations or properties is most at risk from climate change, heat, heavy rain or wildfire.
---

# Which of my sites are most at risk?

Every raw URL below points at the branch `plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by`: use it for this
skill, the pipeline, the map builder and the chart helper. If the user names a
different revision, swap it into those URLs; in a matching crc-docs checkout,
use the local copies. This skill's file is
`https://raw.githubusercontent.com/RiskThinking/crc-docs/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/.agents/skills/which-sites-are-most-at-risk/SKILL.md`.

The reader may not be an expert: plain words, no jargon, no invented numbers.
Never ask for coordinates or technical options.

## Output: four sections, always in this order

Every reply has all four, including when the conversation already holds results
for these sites: then reuse the numbers, but still draw this reply's chart with
the helper, get the live link (below) and copy the files into the downloads
folder. Never answer with links to earlier files or a link in place of the chart.

1. **Interpretation**: one headline sentence naming the sites that change most
   and from what (e.g. "Toronto's hottest days warm the most, +4.2 °C by
   2070-2080; Phoenix gains the most hot days"), then at most three short
   bullets. Name the data route.
2. **Table**: the 3 sites with the largest change in each of the four hazards
   (see Chart), combined (a site that leads two hazards appears once), and no
   other sites. Sort the rows by the hazard asked about, else hottest day. One
   short-headed column per hazard, all four, showing every row's change with
   units, so it fits the chat column. **Bold** the highest value in each column.
   Say how many sites you ran. Write the table in the reply: never offer or link
   a table file (the GeoJSON holds every value).
3. **Chart**: one wide image with one panel per hazard, always these four:
   hottest day (°C), hot days (days per year), wettest day (mm) and wildfire
   weather (Fire Weather Index, points); leave out only a hazard the run has no
   data for, and say so. Each panel is a
   horizontal bar chart with one bar per site showing the change from the
   earlier period to the later one, sorted largest first, so the top bar is the
   most exposed site for that hazard. Sort each panel on its own. Print the value
   at the end of each bar; use the site names as labels.
   - Route 1: change from the baseline to SSP5-8.5 averaged over 2070-2090.
   - Route 2: change from 2023-2036 to 2068-2081.

   Colour each bar by the size of its change, interpolating in RGB between two
   colours from `IMPACT_RISK_COLOURS` (`assets/impact_risk_colours.json`):
   `#fa9b75` at the panel's smallest change and `#a50f15` at its largest, with
   t = (value - min) / (max - min) per panel (all bars `#ef3b2c` if they are
   equal; in matplotlib, `LinearSegmentedColormap.from_list` with those two
   colours). No other colours. A panel's title names the hazard and units, and
   the figure's title says the periods compared.
   Put the panels side by side, each with its own site labels, in a figure about
   15 inches wide at 120 dpi and about 0.35 inches per site plus 1.5 (at least 4)
   tall, with readable labels and minimal margins. With more than 10 sites, show
   the 10 largest changes per panel and say so in the title.

   The reader must see the chart directly under **Chart** in the final reply, with
   tool activity collapsed, as a static image at the full width of the chat
   column: never a thumbnail, a file name or a link instead. Choose the method by
   what the client supports:
   - **ChatGPT Work Mode:** use this run's chart PNG (draw it with matplotlib if
     needed) and run, from the skill folder (for a URL-only run, download the
     helper from the same directory and revision):

         python3 scripts/prepare_inline_chart.py "$chart_png" --alt "$chart_description"

     `$chart_description` is a short description of the hazard and units. Copy
     the one line it prints verbatim under **Chart** in the FINAL reply, on its
     own line, outside a code block. A tool preview does not count. If it says
     the image is too large, export a smaller PNG.
   - **Another client with an inline chart or image renderer:** use its
     final-message format.
   - **No inline renderer, or it fails:** say so in the Chart section and keep
     the table. Add one **Open the chart** link when the host provides a verified
     PNG attachment from this run.
4. **Map and files** (whenever you have sites; see Map): three bullets, live
   link first:
   - the pipeline's `- [Open the live map](...)` line, unchanged (from the bare
     URL in `live_map_link.txt`, write `- [Open the live map](URL)`); it is the
     only link in the block;
   - `<name>-map.html: <short description>`, plain text;
   - `<name>-locations.geojson: <short description>`, plain text;
   - `<name>-chart.png: <short description>`, plain text.

   `<name>` is fresh and descriptive for this run, e.g. `apple-ca-rerun` (company,
   area, and a word that differs from any earlier run in the conversation): never
   the pipeline's generic `sites-` names, which an earlier run may already have
   used. No links or backticks on file names.

   Copy this run's map (`pipeline_output/sites/map/index.html`), GeoJSON and
   chart PNG into the downloads folder (`/mnt/data` in ChatGPT,
   `/mnt/user-data/outputs` in Claude) under those three names, then attach
   exactly those three files as download cards, shown after your closing lines
   (write nothing after them). Never attach `live_map.html`, an earlier copy or a
   `chatgpt.com/library` URL, and never write sandbox links. With no downloads
   folder, give plain-text paths and rely on the live link. Never claim a file
   was provided if it was not.

Close the text with two short lines: **How sure are we** (values describe an area
of about 250 km² around each site, not the building, and come from climate
models; exposed is not the same as damaged) and **Next step** (see each route).

**Before you send, check:** the first bullet under Map and files is the full live
map link; the panels are visible under Chart (the helper's
line or the host's renderer; a file name or card is not enough), and, if map
files exist, the map, GeoJSON and chart PNG are attached as download cards.

## Step 1: collect the sites

Use every place already in the conversation or an attached file; else ask once:
"Which places should I compare? Names or addresses are fine." If the person
names a company or brand without a list, get its real locations (the company's
own store or office directory, or the how-exposed-is-this-company skill's
open-map lookup) and map all of them. Never invent, sample or trim sites; if you
can only get some, say how many and from where. Work out each latitude and
longitude yourself, show a short list (or the count, for more than 25) so the
person can correct you, and give every site a short unique name. The map takes
every site; only the table and chart show the leaders. For more than about 100
sites, suggest the Colab notebook.

## Step 2: get the data

If the person names a route ("use CRC Open", "use the free data", "use CDT"), use
it even when another is available. Otherwise use the first that works: Route 1,
then 2, then 3. Say which you used. Call a route unavailable only after trying
it: for CRC Open, run the install and the script before saying it cannot run. If
a download is blocked, name the host and give the allowlist under Route 3. If
they asked for CRC Open and it truly cannot run, say why in one line and stop:
never switch to CDT, and never label CDT figures as CRC Open.

Compare **1-in-10-year** values (a level with a 10% chance in any year), averaging
several horizons because single future years are noisy.

### Route 1: CDT (when CDT Express tools such as `get_climate_metrics_exposure` exist)

For each site:

1. `get_climate_metrics_exposure` with `latitude`, `longitude`,
   `risk_factors: ["tx_max", "hot_days", "rx1day"]`,
   `pathway: ["ssp126", "ssp245", "ssp585"]`, `horizon: ["2070", "2080", "2090"]`,
   `return_periods: [10]`. Average the horizons per pathway.
2. Again with `pathway: ["historic"]`, `horizon: ["2010"]` for the baseline.
3. `tx_max` is in kelvin (subtract 273.15 for °C), `hot_days` is days and `rx1day`
   is mm on the wettest day. A missing value is no data, not zero.

Rank by the change from the baseline to 2070-2090. Then write `sites.geojson`:
one point per site with a `title` property (name, plus city when known) and
numeric `tx_max_change`, `hot_days_change`, `rx1day_change` (SSP5-8.5 minus
baseline, in °C, days, mm), plus `<hazard>_<pathway>_change` for the other
pathways. Any absolute `tx_max` in the file must be in °C, never kelvin. Leave
out values CDT did not return. Then follow Map.

Next step: offer other emissions futures, more hazards, or financial impact on
the buildings with the same connection.

### Route 2: CRC Open (when you can run Python with internet)

Free data for one high-emissions future (SSP5-8.5); other futures:
opensource@riskthinking.ai. CRC Open is open source: it needs no account, API
key or connector, and it does not use CDT. A rejected or missing CDT connection
says nothing about it. If a browser tool cannot fetch GitHub, download with
`curl` in a shell instead.

Write the sites to `sites.csv` with the header `site,latitude,longitude` (add
`city` if known), then run (use `scripts/which_sites_are_most_at_risk.py` from
this folder if present, or `pipelines/` in a checkout; else download):

```sh
python -m pip install --quiet --upgrade --pre "crc-sdk>=1.0.0a3,<2"
curl -fsSL -o which_sites_are_most_at_risk.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/pipelines/which_sites_are_most_at_risk.py
python which_sites_are_most_at_risk.py --sites sites.csv --skip-era5 --skip-cdt
```

It takes several minutes. Read `pipeline_output/sites/summary.json`:
`answer` names the site with the largest change per hazard, and
`b_crc_open.one_in_10` holds every site's 1-in-10-year value in 2023–2036
(`early`), 2068–2081 (`late`) and the `change`, for the hottest day (°C), wettest
day (mm), hot days and wildfire weather (Fire Weather Index). The run also writes
`pipeline_output/sites/sites.geojson` (fields such as `tx_max_2025_2035`,
`tx_max_change`, the same for `rx1day`, `hot_days`, `fwi`). Then follow Map.

Next step: "This free data covers one high-emissions future. For other futures,
a historical baseline or financial impact, try a
[CDT Express trial](https://velo.riskthinking.ai/cdt-express)."

### Route 3: neither available

Do not estimate or recall numbers. In two sentences say what the screening would
show, then offer:

- **Free:** the
  [Colab notebook](https://colab.research.google.com/github/RiskThinking/crc-docs/blob/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/notebooks/which_sites_are_most_at_risk.ipynb)
  (replace `SITES` in the first cell, then Runtime → Run all).
- **Every future, in this chat:** connect CDT Express, a custom connector named
  **CDT Express** at `https://mcp.riskthinking.ai/mcp` (Claude: Customize →
  Connectors → + Add → Add custom connector; ChatGPT: Plugins → + → Add custom
  MCP server; [setup guide](https://github.com/RiskThinking/cdt-express-mcp#connect-by-url-recommended);
  [trial](https://velo.riskthinking.ai/cdt-express)).

If downloads fail, the sandbox likely blocks the network: ask to allow
`pypi.org`, `raw.githubusercontent.com`, `data.riskthinking.ai`, or use Route 3.

## Map (every route with sites; deliver it without being asked)

The Route 2 pipeline already builds the map and prints `Live map:`, `Map:` and
`GeoJSON:` lines. If a line is missing, or the data came from Route 1, run
(inside a checkout use `tools/build_map_page.py`):

```sh
curl -fsSL -o build_map_page.py \
  https://raw.githubusercontent.com/RiskThinking/crc-docs/plat-2408-crc-docs-fix-map-not-being-prepared-from-skills-by/tools/build_map_page.py
python build_map_page.py pipeline_output/sites/sites.geojson --link
python build_map_page.py pipeline_output/sites/sites.geojson \
  --output pipeline_output/sites/map --title "Sites on the CRC map"
```

Always use this script, never a map of your own; keep its Settings control
overlaid top-right. No coordinates means no map: say so.

- **Live link:** paste the pipeline's `- [Open the live map](...)` line unchanged
  as the first bullet of **Map and files**, in the answer text. Never shorten,
  retype or truncate it; if cut off, read it from `live_map_link.txt` next to the
  GeoJSON. Never attach `live_map.html`. Do not start a server or embed the map in the chat:
  it only works in a browser tab.
- **Map file:** `pipeline_output/sites/map/index.html` (about 3 MB); opens in
  Chrome, Safari or Firefox and needs internet for the basemap.
- **GeoJSON:** `pipeline_output/sites/sites.geojson`, one point per site with its
  values; also opens in QGIS, geojson.io or Kepler.gl.

## Rules

- Never invent or guess numbers; report missing data as missing, not as safe.
- Rank by the data, one hazard at a time; no made-up overall score.
- Source line: "Riskthinking.AI Climate Digital Twin (CDT)" (licensed), or
  "CRC Open by Riskthinking.AI, CC BY-NC 4.0" (free for non-commercial use).
- SSP5-8.5 is a high-emissions future, not a prediction. A horizon such as 2080
  is typical conditions around then, not a forecast for that year.
- Never ask for or show API keys; CDT uses the connector's sign-in.
