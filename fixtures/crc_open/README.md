# CRC SSP585 fixtures

Release `ssp585-fixture-2026-10-08-v2` contains **61 hazards**, **46,213 rows**
in 540 Parquet files. Data and catalogue total about **4.12 MB**; the largest
Parquet file is 8,003 bytes. These are geographic samples for SDK examples,
with coverage recorded in `_CATALOG.json`.

## Coverage and interpretation

The release contains literal `ssp585` rows for 59 climate-index hazards,
inundation and cyclone. `cflood` and `rflood` are excluded because their source
uses `Hot House`, `NDC` and `RT3` rather than SSP585. There are no historic or
other-scenario rows. SSP5-8.5 is an emissions scenario, not a probability assigned
to future emissions.

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
The SDK's software licence does not determine the data licence.
`_SUCCESS` contains the SHA256 of `_CATALOG.json`; partition digests cover exact
file bytes. Completed release IDs are immutable.

## Run the example

Requires **crc-sdk 0.8.0a3 or later**, supplied by this repository's dependencies:

```bash
uv sync
uv run python pipelines/crc_open_pipeline.py
```

The pipeline evaluates 2050 Rx1day at Toronto using the checked-in fixtures.
The paired [notebook](../../notebooks/crc_open_hazards.ipynb) explores catalogue
coverage, city return-value curves and horizon labels with the same SDK workflow.
Pass an HTTP root with `--fixtures` to read remotely:

```bash
uv run python pipelines/crc_open_pipeline.py \
  --fixtures https://raw.githubusercontent.com/RiskThinking/crc-docs/main/fixtures/crc_open
```

The SDK uses that HTTP root by default. For reproducibility, replace `main` with
an immutable commit SHA. `source=` and `fixtures=` also accept directories
containing release directories.

```python
from crc_sdk.workflows import HazardDataset

plan = (
    HazardDataset.crc_open(release="ssp585-fixture-2026-10-08-v2")
    .for_area((-79.5, 43.5, -79.2, 43.8))
    .hazards(["rx1day"])
    .horizons([2050])
    .cache("pipeline_output/crc_open/cache", mode="reuse")
)
plan.prefetch()
dataset = plan.materialize("pipeline_output/crc_open/rx1day.parquet")
```

`materialize_all(directory)` returns separate `HazardDataset`s to preserve each
hazard's units, tail and native resolution. `reuse`, `refresh` and `offline` use
verified persistent caches; `stream` verifies temporary downloads. Unsupported
selections and areas without coverage raise clear errors. Fixture warnings occur
at execution, while plan construction and `explain()` perform no I/O.

## Compare a historical baseline

Pass a canonical ERA5 historical Rx1day file with `--era5-rx1day`. The
[ERA5 historical baseline notebook](../../notebooks/era5_historical_baseline.ipynb)
shows how to generate one. Compare return values at the same asset locations;
the sources differ in resolution, pooling and bias correction, so the difference
cannot be attributed only to climate change. The fixture contains no historical
baseline.
