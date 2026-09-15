# Skill refresh contract

Every canonical `SKILL.md` contains a self-contained bootstrap so an installed
folder can find its source without repository-relative links working locally.
This is an instruction-driven check using the host's available tools, not a
background updater or a guarantee of network access.

## Resolve once, then keep the run consistent

1. Before an assessment's workflow or scripts execute, resolve the current
   `main` commit of **RiskThinking/crc-docs**. Use the GitHub API endpoint
   `https://api.github.com/repos/RiskThinking/crc-docs/commits/main`, a connected
   GitHub tool that returns the branch's full commit SHA, or a fresh Git remote
   query. Search snippets, a cached branch name and an installed folder's age
   do not establish the current revision.
2. Load `.agents/skills/<skill-name>/SKILL.md` at that SHA. Verify its frontmatter
   name matches the requested skill. Read this contract from the same revision.
   A renamed or missing skill is a source-resolution failure, not permission to
   substitute a similarly named skill from elsewhere.
3. Load required playbooks, scripts, notebooks and environment files at the
   **same SHA**. For raw files use
   `https://raw.githubusercontent.com/RiskThinking/crc-docs/<sha>/<path>`.
   Resolve relative Markdown links against the containing file's repository
   directory; code paths described as repository-relative start at the repo root.
   A fetched skill replaces the installed workflow for this run. Do not combine
   it with stale installed scripts or fetch dependencies from moving `main` URLs.
4. When execution needs a checkout, use a separate snapshot/work directory at
   that commit and the snapshot's `uv.lock` and setup instructions. Do not pull
   over a user's working tree, overwrite an installed skill, or upgrade a shared
   environment as part of freshness checking. A fetch does not grant additional
   permissions or override the user's instructions or the host's access controls.
5. Record the repository URL, skill name, full SHA, UTC check time and mode
   (`latest`, `pinned`, or `local-development`) in the run provenance. Retain
   runtime package versions separately. A short `Source: crc-docs@<short-sha>`
   note is sufficient in chat; preserve the full SHA in the report/manifest.

Reuse the resolved snapshot while continuing the same assessment, including
paired CRC/VELO work. Do not restart this check when the fetched skill repeats
its bootstrap instructions. Resolve again for a new assessment or explicit
refresh request. Finish an ongoing run at its selected revision even if `main`
changes in the meantime.

## Pins, offline use and failure

An explicit user-selected commit/tag takes precedence over `main`: resolve it
to a commit when possible and label the run `pinned`, never “latest.” A request
to develop or test local edits likewise uses that local copy and records its
base commit and dirty state; it must not discard those edits via remote refresh.

If source lookup, full-file retrieval or a required dependency fails, explain
what could not be verified and stop before assessment execution. The user may
provide access or explicitly choose a known offline/pinned copy. If already
authorized, use that copy and disclose that freshness is unverified. A partial
fetch, rate limit or missing tool must never silently become a successful check.
Source control applies to workflow code and instructions; the selected workflow
may still acquire JRC, Overture and other explicitly referenced external data.

## Installation boundary

Only copies containing the bootstrap can perform this check. Existing uploads
that predate it need a one-time replacement after these changes are published.
Fetching a new workflow for a run does not persistently update a ChatGPT/Claude
upload, its discovery description, UI metadata or permissions. Update the
installed package through the host's supported mechanism when those change.
