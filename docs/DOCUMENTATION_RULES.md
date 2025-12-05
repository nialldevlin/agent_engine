# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# Documentation Rules

- **Plan naming**: every operational plan lives in `docs/operational/PLAN_<plan_name>.md`. Use uppercase snake case for `<plan_name>`.
- **Progress tracking**: update plan task lists with ✅ checkmarks as milestones complete. Keep partial status visible until the entire plan is done.
- **Closing plans**: when a plan finishes, summarize the outcome briefly in `docs/CHANGELOG.md`, then delete the plan file from `docs/operational/`.
- **Canonical protection**: files under `docs/canonical/` are read-only unless the user explicitly approves edits (exception: `docs/canonical/ARCHITECTURE_OVERVIEW_POINTER.md`).
- **Doc hygiene**: prefer concise, purpose-built docs over archives; before adding new documentation, remove or consolidate any obsolete copies to limit bloat.
