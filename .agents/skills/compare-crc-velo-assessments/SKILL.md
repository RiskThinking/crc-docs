---
name: compare-crc-velo-assessments
description: Reconcile an open CRC climate-risk assessment with its VELO/CDT enterprise twin and explain the capability lift without treating unlike metrics as equivalent. Use when comparing outputs, preparing a paired demo, creating a sales-engineering memo, validating CRC-to-VELO synergy, or identifying product/data gaps exposed by both runs.
---

# Compare CRC and VELO assessments

Make the open/proprietary relationship credible by preserving both provenance and non-equivalence.

## Before each assessment: refresh from the canonical source

This installed copy is a bootstrap for `RiskThinking/crc-docs`. Before executing
an assessment, resolve `main` at
`https://api.github.com/repos/RiskThinking/crc-docs/commits/main` using an available
GitHub, web-fetch or Git tool. Record the returned full commit SHA, then load
`https://raw.githubusercontent.com/RiskThinking/crc-docs/<sha>/.agents/skills/compare-crc-velo-assessments/SKILL.md`
and its required linked files from that same commit. Follow that version for this
run; see its `ai-playbooks/docs/skill-refresh.md` for resolution and provenance.
Do this once per new assessment, not recursively when reading the fetched skill.
An explicit user-pinned revision or requested local development copy takes
precedence and must be labelled. If the commit or required files cannot be
verified, report the limitation and stop assessment execution; never silently
use an older installed copy. This refreshes the run, not the host's installation.

## Guided intake

Treat naming this skill in plain language, or any platform selector
(`$compare-crc-velo-assessments`, `/compare-crc-velo-assessments`,
`@compare-crc-velo-assessments`), as a complete invocation. First look
for one CRC result and one VELO/CDT result already identified in the conversation
or attached files. If the pair is unambiguous, proceed without another question.
Otherwise ask the user to identify or attach the two results; if one side does
not exist, recommend the appropriate twin skill. Infer the semantic crosswalk
from metadata and report uncertainty instead of asking a non-expert to specify
alignment fields or comparison classes. Advanced users may provide explicit
artifacts, alignment constraints, or decision criteria, which override inferred
defaults when valid.

## Demo bootstrap

For a zero-credential file-handling smoke test, first run
`ai-playbooks/examples/run-open-demo.sh` to create the Overture/JRC CRC output,
then inventory its `pipeline_output/ai-playbooks/flood-loss.parquet` beside
`ai-playbooks/examples/velo-company-example.json`. Label the JSON synthetic and
do not imply that the targets align or that the exercise demonstrates live VELO
capability. A decision-grade paired comparison requires CRC and VELO outputs for
the same real target, with aligned dimensions documented below.

## Execution reference

Use the repository's [setup](../../../ai-playbooks/docs/setup.md) and
[capability matrix](../../../ai-playbooks/docs/capability-matrix.md) for the
tested package baseline and output contract. Run repository-relative commands
from the `crc-docs` root. Helpers produce intermediate data; complete the
reporting and interpretation steps below in the assistant workflow.

## Workflow

1. Inventory both artifacts and run `scripts/inventory_assessments.py` when CRC Parquet and VELO JSON are available.
2. Read [references/crosswalk.md](references/crosswalk.md) and create an alignment table for asset/entity, hazard/factor, pathway, horizon, metric, unit, spatial precision, and source version.
3. Classify every comparison as:
   - **Directly comparable**: same business object and metric semantics.
   - **Directionally comparable**: related decision signal with material method differences.
   - **Capability lift only**: available on one side and not reducible to the other.
   - **Not comparable**: alignment or semantics fail.
4. Explain divergences using coverage, resolution, asset identity, hazards, scenario, vulnerability functions, probability conventions, and aggregation before discussing numerical difference.
5. Produce a paired decision memo: what CRC establishes, what VELO/CDT adds, whether the decision changes, and what evidence remains missing.
6. Add newly observed workflow issues to `ai-playbooks/docs/gap-backlog.md` with a reproducible example and suggested acceptance test, assigned to the CRC or VELO/CDT side.

## Deliverable bundle

Retain both untouched source artifacts and produce a machine-readable alignment
table containing the crosswalk fields, comparison class, differences, and
coverage notes. Export it as CSV and Parquet or JSON, create matched-asset
GeoJSON when both sides contain compatible locations, and write a self-contained
HTML decision report with a provenance manifest. In the response, show a compact
table of the most decision-relevant aligned and non-aligned findings. Include:

- side-by-side metric/coverage charts and a comparison-class count chart; and
- a matched-asset map showing only direct or directional spatial comparisons,
  with unmatched and capability-lift-only evidence visibly distinct.

Never plot unlike values on a shared quantitative scale. Keep all reconciliation
rows downloadable, disclose any visible top-N selection, and omit the map with a
clear explanation when spatial identity cannot be aligned rather than forcing a
misleading visualization.

## Messaging guardrails

- Do not position CRC as intentionally crippled. Position it as transparent, extensible infrastructure and reproducible baseline.
- Do not imply every VELO/CDT result is currently computed by CRC. State that CRC is the target open foundation and integration is increasingly being materialized.
- Do not claim causation from score differences.
- Do not hide nulls, unmatched assets, warnings, or scenario mismatch.
