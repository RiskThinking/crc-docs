"""Write one self-contained HTML page that shows a locations GeoJSON on the crc-viz hazard map.

The company pipeline writes ``locations.geojson``. This turns it into a single
``index.html`` with the crc-viz browser bundle (script, styles and MapLibre
worker) and the data all inline. Open it by double-clicking, email it, or host
it anywhere. It needs a real browser tab (best served over http: add
``--serve`` to open a live link on localhost) and internet for the Carto basemap tiles.

The bundle is committed under ``assets/crc-viz`` (rebuild it from the npm package with
``npm run build`` in ``tools/crc-viz-bundle``). A copy of this script on its
own downloads it from GitHub. Then:

    uv run python tools/build_map_page.py pipeline_output/company/locations.geojson \\
        --output pipeline_output/company/map
"""

from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import os
import tempfile
import urllib.request
import webbrowser
import zlib
from pathlib import Path
from typing import Any

# Where a standalone copy of this script downloads the bundle from. Point
# CRC_VIZ_BASE_URL elsewhere (a release, a CDN) to use another build.
BUNDLE_URL = "https://raw.githubusercontent.com/RiskThinking/crc-docs/map-skill-test/assets/crc-viz"
BUNDLE_FILES = ("crc-viz.js", "crc-viz.css")
# Expected yearly damage per location, averaged over the early and late windows
# the pipeline uses (EARLY and LATE in pipelines/how_exposed_is_this_company.py).
DAMAGE_KEYS = ("total_early", "total_late")
HURRICANE_COLOURS = ["#fff7ec", "#fdd49e", "#fc8d59", "#d7301f", "#7f0000"]

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
  html, body {{ height: 100%; margin: 0; font-family: system-ui, sans-serif; }}
  #map {{ height: 100%; position: relative; z-index: 1; }}
</style>
</head>
<body>
<div id="fallback" style="position:fixed;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;color:#444;background:#f6f6f6">
  <p>This map needs a browser to run. If you only see this message, the preview panel is blocking scripts.<br>Download the file and open it in Chrome, Safari or Firefox.</p>
</div>
<div id="map"></div>
<script>
  // If the map cannot start (a sandboxed preview can block workers, requests or
  // WebGL), say why on the page instead of leaving it blank.
  (function () {{
    var problems = [];
    function show() {{
      var box = document.getElementById("map-problems");
      if (!box) {{
        box = document.createElement("pre");
        box.id = "map-problems";
        box.style.cssText = "position:fixed;left:8px;bottom:8px;right:8px;max-height:40%;overflow:auto;margin:0;padding:8px;background:#fff3f0;border:1px solid #cc5b38;color:#67000d;font:12px/1.4 monospace;white-space:pre-wrap;z-index:9999";
        document.body.appendChild(box);
      }}
      box.textContent = "Map problem. If this is a preview panel, download the file and open it in a browser.\\n" + problems.join("\\n");
    }}
    function add(text) {{ problems.push(text); show(); }}
    window.addEventListener("error", function (e) {{ add("error: " + e.message); }});
    window.addEventListener("unhandledrejection", function (e) {{ add("rejected: " + (e.reason && e.reason.message || e.reason)); }});
    document.addEventListener("securitypolicyviolation", function (e) {{ add("blocked by " + e.violatedDirective + ": " + String(e.blockedURI).slice(0, 80)); }});
    setTimeout(function () {{
      if (!document.querySelector(".maplibregl-canvas")) add("the map never started (page origin: " + location.origin + ")");
    }}, 6000);
  }})();
</script>
<script>{js}</script>
<script>
  const layers = {layers};
{boot}
</script>
</body>
</html>
"""


STATIC_BOOT = """  const data = {data};
  CrcViz.mountHazardMap(document.getElementById("map"), {{ source: data, layers }});"""

# The hosted viewer reads its locations from the link (#<data>): raw-deflate JSON,
# base64url, as {"k": [numeric keys], "r": [[lon, lat, city, value per key], ...]}.
# Every numeric field travels, so all of them are offered as colour fields.
HURRICANE_PLACEHOLDER = "__hurricanes__"
VIEWER_BOOT = """  const hint = document.getElementById("fallback");
  async function load() {{
    const text = location.hash.slice(1).replace(/-/g, "+").replace(/_/g, "/");
    if (!text) throw new Error("This page needs a map link with data after the # sign.");
    const bytes = Uint8Array.from(atob(text), function (c) {{ return c.charCodeAt(0); }});
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return JSON.parse(await new Response(stream).text());
  }}
  load().then(function (pack) {{
    const hurricanes = pack.k.find(function (k) {{ return k.indexOf("hurricanes_within_") === 0; }}) || "";
    const config = JSON.parse(JSON.stringify(layers).split("{placeholder}").join(hurricanes));
    const data = {{ type: "FeatureCollection", features: pack.r.map(function (r) {{
      const properties = {{ city: r[2] }};
      pack.k.forEach(function (k, i) {{ properties[k] = r[3 + i]; }});
      return {{ type: "Feature", geometry: {{ type: "Point", coordinates: [r[0], r[1]] }}, properties: properties }};
    }}) }};
    hint.remove();
    CrcViz.mountHazardMap(document.getElementById("map"), {{ source: data, layers: config }});
  }}).catch(function (e) {{ hint.textContent = "Could not read the map data: " + e.message; }});"""

LINK_URL = "https://riskthinking.github.io/crc-docs/map/"


def encode_link(geojson: dict[str, Any], base: str = LINK_URL) -> str:
    """A link to the hosted viewer with every location packed into the #fragment."""
    features = geojson.get("features") or []
    keys: list[str] = []
    for feature in features:
        for key, value in feature.get("properties", {}).items():
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if numeric and key not in keys and not key.endswith("_id"):
                keys.append(key)
    rows = []
    for feature in features:
        props = feature.get("properties", {})
        lon, lat = feature["geometry"]["coordinates"][:2]
        values = [
            round(props[key], 4)
            if isinstance(props.get(key), float)
            else props.get(key)
            for key in keys
        ]
        rows.append(
            [round(lon, 3), round(lat, 3), props.get("city") or props.get("name") or ""]
            + values
        )
    text = json.dumps({"k": keys, "r": rows}, separators=(",", ":"), ensure_ascii=False)
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = packer.compress(text.encode()) + packer.flush()
    return base + "#" + base64.urlsafe_b64encode(packed).decode().rstrip("=")


def decode_link(link: str) -> dict[str, Any]:
    text = link.split("#", 1)[1]
    packed = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    return json.loads(zlib.decompress(packed, -15))


def layer_config(geojson: dict[str, Any]) -> list[dict[str, Any]]:
    """Colour points by hurricane count, else by late-century damage."""
    features = geojson.get("features") or []
    props = features[0].get("properties", {}) if features else {}
    hurricanes = next((k for k in props if k.startswith("hurricanes_within_")), None)
    if hurricanes:
        return [
            {
                "id": "points",
                "visKey": hurricanes,
                "title": "Hurricanes within 50 km",
                "unit": "hurricanes",
                "colorScheme": HURRICANE_COLOURS,
                "radius": 6,
                "tooltip": {
                    "titleKey": "city",
                    "valueKeys": [hurricanes, *DAMAGE_KEYS],
                },
            }
        ]
    if "total_late" in props:
        return [
            {
                "id": "points",
                "visKey": "total_late",
                "title": "Expected yearly damage, 2070-2080",
                "unit": "% of value",
                "radius": 6,
                "tooltip": {
                    "titleKey": "city",
                    "valueKeys": list(DAMAGE_KEYS),
                },
            }
        ]
    return []


def find_bundle(explicit: Path | None = None, download: bool = True) -> Path | None:
    """Folder holding the crc-viz browser bundle, or None.

    Looks at ``explicit``, ``$CRC_VIZ_BROWSER``, the repository's
    ``assets/crc-viz`` and a sibling crc-viz checkout (``../crc-viz/dist/browser``).
    Otherwise downloads it from ``$CRC_VIZ_BASE_URL`` (default: BUNDLE_URL).
    """
    here = Path(__file__).resolve().parents[1]
    candidates = [
        explicit,
        Path(os.environ["CRC_VIZ_BROWSER"])
        if os.environ.get("CRC_VIZ_BROWSER")
        else None,
        here / "assets" / "crc-viz",
        Path("../crc-viz/dist/browser"),
    ]
    for folder in candidates:
        if folder and (folder / BUNDLE_FILES[0]).is_file():
            return folder
    if not download:
        return None
    base = os.environ.get("CRC_VIZ_BASE_URL", BUNDLE_URL).rstrip("/")
    folder = Path(tempfile.mkdtemp(prefix="crc-viz-"))
    try:
        for name in BUNDLE_FILES:
            with urllib.request.urlopen(f"{base}/{name}", timeout=60) as response:
                (folder / name).write_bytes(response.read())
    except OSError as error:
        print(f"Could not download the crc-viz bundle from {base}: {error}")
        return None
    return folder


def write_atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
    os.chmod(handle.name, 0o644)
    os.replace(handle.name, path)


def build(geojson_path: Path, viz: Path, output: Path, title: str) -> Path:
    if not (viz / "crc-viz.js").is_file():
        raise SystemExit(
            f"{viz}/crc-viz.js not found. Run `npm run build` in tools/crc-viz-bundle first."
        )
    geojson = json.loads(geojson_path.read_text())
    output.mkdir(parents=True, exist_ok=True)
    # "</" inside an inline script or style block would end it early.
    data = json.dumps(geojson, separators=(",", ":")).replace("</", "<\\/")
    js = (viz / "crc-viz.js").read_text().replace("</script", "<\\/script")
    css = (viz / "crc-viz.css").read_text().replace("</style", "<\\/style")
    page = PAGE.format(
        title=title,
        css=css,
        js=js,
        layers=json.dumps(layer_config(geojson), indent=2),
        boot=STATIC_BOOT.format(data=data),
    )
    write_atomic(output / "index.html", page)
    return output / "index.html"


def serve(folder: Path, port: int = 8000, open_browser: bool = True) -> None:
    """Serve ``folder`` on localhost, print the link and open it. Stops on Ctrl-C."""
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(folder)
    )
    server = None
    for candidate in range(port, port + 20):
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", candidate), handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit(f"No free port between {port} and {port + 19}.")
    url = f"http://localhost:{server.server_port}/index.html"
    print(f"Live map: {url}  (Ctrl-C to stop)", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_viewer(viz: Path, output: Path) -> Path:
    """Write the hosted viewer (for GitHub Pages) that draws the map from its link."""
    # layer_config looks for a key that starts with "hurricanes_within_".
    sample = {
        "features": [{"properties": {"hurricanes_within_" + HURRICANE_PLACEHOLDER: 0}}]
    }
    page = PAGE.format(
        title="Locations on the CRC hazard map",
        css=(viz / "crc-viz.css").read_text().replace("</style", "<\\/style"),
        js=(viz / "crc-viz.js").read_text().replace("</script", "<\\/script"),
        layers=json.dumps(layer_config(sample), indent=2),
        boot=VIEWER_BOOT.format(
            placeholder="hurricanes_within_" + HURRICANE_PLACEHOLDER
        ),
    )
    output.mkdir(parents=True, exist_ok=True)
    write_atomic(output / "index.html", page)
    return output / "index.html"


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("geojson", type=Path, nargs="?")
    parser.add_argument(
        "--viz",
        type=Path,
        help="folder with crc-viz.js and crc-viz.css (default: find or download)",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--link",
        action="store_true",
        help="print a link to the hosted viewer with the locations packed into it",
    )
    parser.add_argument(
        "--viewer",
        type=Path,
        metavar="FOLDER",
        help="write the hosted viewer page into FOLDER (publish it on GitHub Pages)",
    )
    parser.add_argument("--title", default="Locations on the CRC hazard map")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="after building, serve the page on localhost and open it in the browser",
    )
    parser.add_argument("--port", type=int, default=8000, help="first port to try")
    args = parser.parse_args(argv)
    if args.link:
        if not args.geojson:
            raise SystemExit("--link needs the locations.geojson path.")
        link = encode_link(json.loads(args.geojson.read_text()))
        print(f"Live map: {link}")
        return Path(link)
    viz = find_bundle(args.viz)
    if viz is None:
        raise SystemExit("No crc-viz bundle found or downloadable; see --viz.")
    if args.viewer:
        page = build_viewer(viz, args.viewer)
        print(f"Wrote {page}.")
        return page
    if not args.geojson or not args.output:
        raise SystemExit("Give the locations.geojson path and --output.")
    page = build(args.geojson, viz, args.output, args.title)
    print(f"Wrote {page}.")
    if args.serve:
        serve(args.output, args.port)
    return page


if __name__ == "__main__":
    main()
