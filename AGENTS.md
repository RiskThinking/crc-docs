# Agent entry point

Canonical skill definitions live under [`.agents/skills/`](.agents/skills), one
`SKILL.md` per skill. This file exists so agentic tools that auto-read
`AGENTS.md` (Codex, Cursor, Aider, Amp, and similar) discover the skills
without any manual linking step. Claude Code loads this file through
`@AGENTS.md` in the root [`CLAUDE.md`](CLAUDE.md). claude.ai has no automatic
repository discovery; see README.md's "Platform discovery" section.

## Skills

| Skill | Definition |
|---|---|
| crc-screen-mortgage-flood | [.agents/skills/crc-screen-mortgage-flood/SKILL.md](.agents/skills/crc-screen-mortgage-flood/SKILL.md) |
| crc-model-flood-insurance-loss | [.agents/skills/crc-model-flood-insurance-loss/SKILL.md](.agents/skills/crc-model-flood-insurance-loss/SKILL.md) |
| crc-assess-asset-portfolio-risk | [.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md](.agents/skills/crc-assess-asset-portfolio-risk/SKILL.md) |
| velo-underwrite-property-climate | [.agents/skills/velo-underwrite-property-climate/SKILL.md](.agents/skills/velo-underwrite-property-climate/SKILL.md) |
| velo-triage-portfolio-insurability | [.agents/skills/velo-triage-portfolio-insurability/SKILL.md](.agents/skills/velo-triage-portfolio-insurability/SKILL.md) |
| velo-assess-company-climate-risk | [.agents/skills/velo-assess-company-climate-risk/SKILL.md](.agents/skills/velo-assess-company-climate-risk/SKILL.md) |
| compare-crc-velo-assessments | [.agents/skills/compare-crc-velo-assessments/SKILL.md](.agents/skills/compare-crc-velo-assessments/SKILL.md) |

## Invoking a skill

Say the skill by name in plain language — e.g. "Use the
crc-screen-mortgage-flood skill for Toronto, Canada." Every skill accepts
this. Platform selectors are equivalent shortcuts, not requirements: Codex
`$skill-name`, ChatGPT `@skill-name`, Claude Code `/skill-name`.

## If this repository is not mounted or linked in your tool

Some chat surfaces (e.g. a bare "refer to this GitHub URL" prompt with no
repository connector) cannot read files just because a URL was mentioned. If
your tool has any URL-fetch or browsing capability, fetch the raw skill file
directly and follow it as your operating instructions for the rest of the
conversation:

```
https://raw.githubusercontent.com/RiskThinking/crc-docs/main/.agents/skills/<skill-name>/SKILL.md
```

For enterprise (VELO/CDT) skills, also connect the CDT Express MCP server at
`https://mcp.riskthinking.ai/mcp` — see [`.mcp.json`](.mcp.json) and README.md.

See [README.md](README.md) for the full walkthrough, enterprise MCP setup,
and per-platform discovery notes.
