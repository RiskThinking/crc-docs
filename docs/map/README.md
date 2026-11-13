# Hosted map viewer

`index.html` is the crc-viz hazard map with no data inside. It reads its locations
from the link (`#<data>`, raw-deflate JSON, base64url) that
`tools/build_map_page.py --link` prints, so one published page serves every map.
Rebuild it after updating `assets/crc-viz`:

    uv run python tools/build_map_page.py --viewer docs/map

Publish with GitHub Pages: Settings > Pages > deploy from branch, folder `/docs`.
