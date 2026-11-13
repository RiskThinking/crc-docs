# crc-viz browser bundle

`crc-viz.js` and `crc-viz.css` are a browser build of the crc-viz hazard map, built from the
published npm package `@climateriskcommons/crc-viz@0.1.0-alpha.2`, with React, MapLibre and
the MapLibre worker bundled in. `tools/build_map_page.py` inlines them into one
self-contained HTML map.

Rebuild (after bumping the version in `tools/crc-viz-bundle/package.json`):

    cd tools/crc-viz-bundle && npm install && npm run build

The build writes both files here. The entry point (`mountHazardMap`, `unmountHazardMap`)
is `tools/crc-viz-bundle/entry.tsx`.
