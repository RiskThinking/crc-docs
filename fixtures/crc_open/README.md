# CRC SSP585 fixtures

Release `ssp585-fixture-2026-10-08-v2` contains **63 hazards**, **47,013 rows**
in 546 Parquet files. Data and catalogue total about **6.79 MB**; the largest
Parquet file is 14,255 bytes. These are geographic samples for SDK examples,
with coverage recorded in `_CATALOG.json`.

## Coverage and interpretation

The release contains literal `ssp585` rows for 59 climate-index hazards,
inundation, cyclone, coastal flood (`cflood`) and river flood (`rflood`).
There are no historic or other-scenario rows. SSP5-8.5 is an emissions scenario,
not a probability assigned to future emissions.

Coastal and river flood use scenario-compatible SSP585-labelled curves rather
than independently fitted SSP585 projections. Their geographic samples use
native r7 cells near the published cities.

Climate indices use native r5 cells around Toronto, Phoenix, London, Dhaka,
Singapore, Nairobi, São Paulo and Sydney: each city's centre cell and six
neighbours where available. Inundation uses native r7, selecting up to seven
available source cells within 50 km of a city when exact cells are absent.
Its sampled coverage is near London, Dhaka and Singapore. Use the catalogue's
actual cells and horizons; missing coverage is not zero risk.

Most climate-index horizons run from 2025 to 2090. Inundation has sparse horizons
through 2100. Cyclone includes the upstream 2010 and 2025–2100 labels, which
broadcast identical time/scenario-independent pooled curves. They are **not
SSP585-specific projections**, and the 2010 label is not a historical baseline.
Cyclone's ensemble scenario remains unspecified. Inundation's probability
semantics also remain unspecified. The SDK warns about both interpretations.

Curves retain the source values and fitting provenance. Climate indices declare
`annual_value_distribution` semantics and pooled ensembles. Pooled curves do not
represent per-model ensemble spread, and H3 indexing does not add asset-scale
scientific information. Temporal window lengths are unspecified in the source.
No-data rows are retained rather than converted to zero.

The catalogue and embedded Parquet metadata carry release terms, source
checksums and attribution to Riskthinking.AI bias-corrected climate distributions.
The SDK's software licence does not determine the data licence. The CRC Open
dataset is licensed under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)
(`CC-BY-NC-4.0`): attribution is required, and commercial use needs a separate
licence. `_CATALOG.json` and the Parquet metadata record that licence.
`_SUCCESS` contains the SHA256 of `_CATALOG.json`; partition digests cover exact
file bytes. Completed release IDs are immutable.

## Public dataset examples

The [portfolio pipeline](../../pipelines/crc_open_pipeline.py) and
[notebook](../../notebooks/crc_open_hazards.ipynb) use the public CRC Open release
`ssp585-global-2026-10-20-v1` by default, with **crc-sdk 0.8.1 or later**.
They screen three illustrative Toronto locations across 2030, 2050 and 2080,
inspect acquisition size and cell matches, and reuse verified local caches.
The notebook includes executed tables and chart images for GitHub preview.

```bash
uv sync
uv run python pipelines/crc_open_pipeline.py
```

For your own asset CSV or Parquet, provide a bounded acquisition area:

```bash
uv run python pipelines/crc_open_pipeline.py \
  --assets assets.csv --bounds -79.52 43.60 -79.25 43.78
```

## Inspect the sampled release

The checked-in samples are retained for release inspection. The current SDK
workflow examples use the public release above. Inspect fixture coverage directly
from its catalogue:

```python
import json
from pathlib import Path

root = Path("fixtures/crc_open/ssp585-fixture-2026-10-08-v2")
catalog = json.loads((root / "_CATALOG.json").read_text())
for partition in catalog["hazards"]["rx1day"]["partitions"]:
    print(partition["h3_r0"], partition["rows"], partition["path"])
```

The public adapter accepts another canonical catalogue using `source=` and a
pinned `release=`. Materialized hazards retain their scientific metadata, units
and native resolution. Missing coverage is not zero risk.

## Compare a historical baseline

Pass a canonical ERA5 historical Rx1day file with `--era5-rx1day`. The
[ERA5 historical baseline notebook](../../notebooks/era5_historical_baseline.ipynb)
shows how to generate one. Compare return values at the same asset locations;
the sources differ in resolution, pooling and bias correction, so the difference
cannot be attributed only to climate change. The fixture contains no historical
baseline.
