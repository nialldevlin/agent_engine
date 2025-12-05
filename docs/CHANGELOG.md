# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# Changelog

## 2025-12-04
- Repository: closed out operational Phase 0–2 artifacts and consolidated active plans.
- Deleted redundant operational plan and phase documents to reduce maintenance and surface current plan (`PLAN_BUILD_AGENT_ENGINE.md` now acts as master with phases closed through Phase 2).
- Verified and committed Task persistence work (checkpointing, load, list, metadata) and added VS Code workspace settings; full test suite passing (360 tests).

## 2025-12-03
- Added documentation rules and cleaned obsolete operational archives to reduce maintenance overhead.
- Captured King Arthur integration planning guidance in `legacy/king_arthur/INTEGRATION_PLAN.md` and pointed Sonnet plan at it.
- Cleaned canonical and operational docs (standardized headings, updated plan summaries, referenced doc rules).

- Closed PLAN_CODEX after completion (see repo history for details) and removed outdated GETTING_STARTED and architecture pointer docs to prevent stale guidance.
- Replaced legacy knight roles with neutral agent manifests, removed ContextStore fallback, and quarantined the King Arthur lift under `legacy/king_arthur/`.
