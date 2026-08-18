---
name: velo-triage-portfolio-insurability
description: Triage a company's physical-asset portfolio using VELO's uninsurable and stranded asset classifications under a selected pathway and horizon. Use for insurance portfolio review, renewal triage, climate concentration, high-risk asset lists, or the higher-calibre twin to a CRC flood damage assessment.
---

# VELO portfolio insurability triage

Use VELO classifications as platform signals, not as universal actuarial or underwriting policy.

## Guided intake

Treat `Use $velo-triage-portfolio-insurability` as a complete invocation. Reuse
a clear company from the conversation; otherwise ask only for the company name
or VELO company ID. Resolve candidates and supported pathways/horizons through
the authorized connection. Select an unambiguous company, show a short list when
identity is ambiguous, and recommend a relevant scenario or comparison rather
than asking the user for raw platform codes. Ask a follow-up only when identity,
scenario intent, or decision context is materially unclear. Valid advanced
inputs override defaults.

## Demo bootstrap

This live enterprise skill does not require local portfolio files. Use the
authorized MCP or SDK connection to resolve the requested company and discover
supported pathways and horizons. Ask the user to select among ambiguous matches.
If no authorized connection is available, explain the prerequisite and stop;
never present mocked classifications as live VELO results.

## Workflow

1. Resolve an existing company and confirm pathway/horizon from the connected API or MCP capability list.
2. Read [references/playbook.md](references/playbook.md) for the current SDK threshold semantics.
3. Run `scripts/triage_insurability.py` or equivalent read-only MCP tools.
4. Report uninsurable and stranded asset lists, counts, overlap, countries/types, available risk metrics, and scenario.
5. Pull factor impacts or aggregations when available to explain drivers and concentrations.
6. Separate the VELO platform classification from the insurer's appetite, pricing, wording, deductibles, reinsurance, and regulatory capital policy.
7. Reconcile with `$crc-model-flood-insurance-loss` only for aligned assets and flood-related evidence; use the comparison to show multi-hazard and enterprise-data lift.

## Safety

- Never expose credentials.
- Do not upload or alter organization assets without explicit authorization.
- Never bind, decline, price, or cancel coverage automatically.
- Treat missing assets or scores as coverage exceptions.
