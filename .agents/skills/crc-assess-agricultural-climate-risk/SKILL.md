---
name: crc-assess-agricultural-climate-risk
description: Assess bounded USDA crop-cover or global FTW field evidence against CRC canonical flood or drought hazards. Use for agricultural sourcing, crop exposure, field screening, and open climate-risk baselines; not for yield prediction, ownership, or a synthetic farm-risk score.
---

# CRC agricultural climate risk

Produce an auditable agricultural evidence layer and a separate per-hazard
evaluation. Never infer ownership, yield, production, or a combined risk score.

## Before each assessment: refresh from the canonical source

This installed copy is a bootstrap for `RiskThinking/crc-docs`. Before executing
an assessment, resolve `main` at
`https://api.github.com/repos/RiskThinking/crc-docs/commits/main` using an available
GitHub, web-fetch or Git tool. Record the returned full commit SHA, then load
`https://raw.githubusercontent.com/RiskThinking/crc-docs/<sha>/.agents/skills/crc-assess-agricultural-climate-risk/SKILL.md`
and its required linked files from that same commit. Follow that version for this
run; see its `ai-playbooks/docs/skill-refresh.md` for resolution and provenance.
Do this once per new assessment, not recursively when reading the fetched skill.
An explicit user-pinned revision or requested local development copy takes
precedence and must be labelled. If the commit or required files cannot be
verified, report the limitation and stop assessment execution; never silently
use an older installed copy. This refreshes the run, not the host's installation.

## Intake and source choice

Reuse a supplied geography, year, crops, hazard, and decision context. If the
target or decision is absent, ask: “Which sourcing area or agricultural region
should I assess, and what decision should the screen inform?” Resolve and show
a narrow WGS84 AOI.

- In CONUS, default to USDA CDL 30 m and the latest complete requested year.
  Use 10 m only for 2024–2025 when the added detail matters.
- Elsewhere, use FTW field boundaries for the requested ISO country and retain
  continuous confidence. State that crop type is unavailable.
- Default flood to EFAS in Europe and GloFAS elsewhere. Add EDO SMI only when
  drought is relevant and covered.

## Execution reference

Use the repository's [setup](../../../ai-playbooks/docs/setup.md) and
[capability matrix](../../../ai-playbooks/docs/capability-matrix.md) for the
tested package baseline and output contract. Run repository-relative commands
from the `crc-docs` root. Helpers produce intermediate data; complete the
reporting and interpretation steps below in the assistant workflow.

## Workflow

1. Read [the agricultural playbook](../../../ai-playbooks/agricultural-climate-risk.md).
2. Materialize each applicable hazard into its own canonical Parquet and read
   its embedded source, unit, semantics, pathway, horizon, tail, support, and
   H3 resolution.
3. Run `pipelines/agricultural_climate_pipeline.py` with a bounded AOI. Let the
   hazard metadata choose H3 resolution. The notebook twin is
   `notebooks/agricultural_climate_risk.ipynb`.
4. Preserve USDA year/class and sampled crop share, or FTW year/confidence/area.
   Preserve match status and missingness in each hazard evaluation.
5. Keep hazards with incompatible units, horizons, or semantics separate.
   Flag return-period extrapolation and low-confidence or missing agricultural
   coverage.

## Deliverable

Return the agricultural-units Parquet, one canonical evaluation Parquet per
hazard, map and summary Parquets, a PMTiles presentation artifact, and a
manifest with versions, filters, hashes, row counts, metadata, and warnings.
Show a map plus a per-crop or confidence-stratified exposure summary. Label
USDA crop share as sampled pixels—not acreage—and FTW polygons as
remote-sensing field units—not parcels or proof of ownership.
