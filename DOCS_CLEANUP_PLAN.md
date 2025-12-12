# Documentation Cleanup Plan for Agent Engine v1

**Date**: December 11, 2025
**Objective**: Consolidate and reorganize docs/ directory after v1 completion
**Target**: Reduce from 552 KB → ~300 KB while maintaining accessibility

---

## Current State Analysis

### Document Inventory

**Total Size**: 552 KB, 26 markdown files

**By Category**:

1. **User-Facing Documentation** (120 KB, 7 files) ✅ KEEP
   - `ARCHITECTURE.md` (18 KB) - 5 Mermaid diagrams + overview
   - `API_REFERENCE.md` (17 KB) - Complete public API documentation
   - `TUTORIAL.md` (13 KB) - Step-by-step getting started guide
   - `DEPLOYMENT.md` (22 KB) - Deployment guide for DevOps/production
   - `PACKAGING.md` (13 KB) - PyPI packaging and build process
   - `CLI_FRAMEWORK.md` (16 KB) - CLI REPL framework documentation
   - `SECURITY.md` (9.5 KB) - Security best practices

2. **Phase Implementation Plans** (205 KB, 8 files) ❌ DELETE (work complete)
   - `operational/PHASE_0_IMPLEMENTATION_PLAN.md` (30 KB) - Completed Phase 0
   - `operational/PHASE_5_IMPLEMENTATION_SUMMARY.md` (12 KB) - Completed Phase 5
   - `operational/PHASE_6_IMPLEMENTATION_PLAN.md` (18 KB) - Completed Phase 6
   - `operational/PHASE_6_IMPLEMENTATION_SUMMARY.md` (12 KB) - Duplicate of above
   - `operational/PHASE_7_IMPLEMENTATION_PLAN.md` (28 KB) - Completed Phase 7
   - `operational/PHASE_8_IMPLEMENTATION_PLAN.md` (31 KB) - Completed Phase 8
   - `operational/PHASE_9_IMPLEMENTATION_PLAN.md` (22 KB) - Completed Phase 9
   - `operational/PHASE_18_IMPLEMENTATION_PLAN.md` (23 KB) - Completed Phase 18
   - **Action**: Summarize completions in CHANGELOG, then delete

3. **Master Build Plan** (73 KB, 1 file) 🔄 CONDENSE
   - `operational/PLAN_BUILD_AGENT_ENGINE.md` (73 KB, 2089 lines) - Master roadmap
   - **Action**: Collapse completed phases 0-18 into summary rows; keep Phases 19-23 detailed with canonical design decisions

4. **Feature-Specific Docs** (8 KB, 1 file) 🤔 CONSIDER CONSOLIDATION
   - `MULTI_TASK_ISOLATION.md` (7.9 KB) - Phase 17 isolation model
   - **Action**: Either keep as reference OR fold into API_REFERENCE.md (Section 4.17)

5. **Internal Process Docs** (7 KB, 3 files) 🔄 RELOCATE
   - `DOCUMENTATION_RULES.md` (877 bytes) - Rules for doc maintenance
   - `WORKFLOW_CHECKLIST.md` (1.8 KB) - LLM workflow guidance
   - `PROMPT_LIBRARY.md` (4.7 KB) - LLM prompt templates
   - **Action**: Move WORKFLOW_CHECKLIST + PROMPT_LIBRARY to `.claude/` directory (they are LLM instructions, not user docs); keep DOCUMENTATION_RULES in docs/

6. **Changelog & Index Docs** (4 KB, 2 files) 🔄 UPDATE
   - `CHANGELOG.md` (2.8 KB) - Release notes by date
   - `operational/README.md` (3.9 KB) - Operational docs index
   - **Action**: Update CHANGELOG with Phase 19-23 completions; condense operational/README to brief index

7. **Canonical Reference Docs** (40 KB, 4 files) ✅ KEEP (read-only)
   - `canonical/AGENT_ENGINE_SPEC.md` - Frozen specification
   - `canonical/AGENT_ENGINE_OVERVIEW.md` - Frozen overview
   - `canonical/PROJECT_INTEGRATION_SPEC.md` - Frozen integration spec
   - `canonical/RESEARCH.md` - Frozen research notes
   - **Action**: Do not modify

---

## Cleanup Actions

### Action 1: Delete Completed Phase Implementation Plans (205 KB saved)

**Files to delete**:
```
docs/operational/PHASE_0_IMPLEMENTATION_PLAN.md
docs/operational/PHASE_5_IMPLEMENTATION_SUMMARY.md
docs/operational/PHASE_6_IMPLEMENTATION_PLAN.md
docs/operational/PHASE_6_IMPLEMENTATION_SUMMARY.md
docs/operational/PHASE_7_IMPLEMENTATION_PLAN.md
docs/operational/PHASE_8_IMPLEMENTATION_PLAN.md
docs/operational/PHASE_9_IMPLEMENTATION_PLAN.md
docs/operational/PHASE_18_IMPLEMENTATION_PLAN.md
```

**Rationale**: Per DOCUMENTATION_RULES.md: "when a plan finishes, summarize the outcome briefly in CHANGELOG.md, then delete the plan file." All phase implementation plans are completed work with no ongoing decisions.

**Before deleting**: Ensure key metrics (test counts, file changes) are captured in CHANGELOG.

---

### Action 2: Condense PLAN_BUILD_AGENT_ENGINE.md (30 KB reduction)

**Changes**:
1. Replace detailed phase task lists (0-18) with summary table rows:
   ```
   | Phase | Component | Tests | Status | Summary |
   |-------|-----------|-------|--------|---------|
   | 0 | Workspace Audit | N/A | ✅ COMPLETE | Legacy code removed, DAG-only |
   | 1 | Schemas & Validation | 94 | ✅ COMPLETE | All canonical schemas implemented |
   | ... | ... | ... | ... | ... |
   ```

2. Keep Phases 19-23 fully detailed (with canonical design decisions) since they are v1 final deliverables.

3. Move large task lists to collapsed/collapsed sections or summarize in 1-2 lines per phase.

4. Keep Phase Overview table but make success criteria compact.

5. Keep all Non-Goals and Future Work sections (important architectural guidance).

**Result**: ~73 KB → ~45 KB

---

### Action 3: Relocate Internal Workflow Docs (7 KB moved)

**Files to move from `docs/` to `.claude/`**:
- `docs/WORKFLOW_CHECKLIST.md` → `.claude/WORKFLOW_CHECKLIST.md`
- `docs/PROMPT_LIBRARY.md` → `.claude/PROMPT_LIBRARY.md`

**Rationale**: These are LLM instructions and internal process docs, not user-facing documentation. They belong in `.claude/` with other Claude Code configuration.

**Files to keep in `docs/`**:
- `DOCUMENTATION_RULES.md` - Describes rules for doc maintenance (policy for the repo, not LLM instructions)

---

### Action 4: Consolidate or Relocate MULTI_TASK_ISOLATION.md (7.9 KB)

**Option A (RECOMMENDED)**: Keep as-is
- Rationale: Specialized documentation for Phase 17 isolation guarantees; clear reference point for distributed/concurrent execution patterns
- Keep in docs/ as a feature-specific reference

**Option B (ALTERNATIVE)**: Fold into API_REFERENCE.md
- Rationale: Saves 8 KB; isolation is part of the public API surface
- Add new section "Phase 17: Multi-Task Execution & Isolation Guarantees"
- Keep a brief pointer in main docs if external tools reference it

**Recommendation**: Keep Option A (provides clear isolation reference without bloating main API doc)

---

### Action 5: Update CHANGELOG.md

**Additions**:
- Summarize Phase 19-23 completions with test counts
- Add entries for completed operational plans that were deleted
- Example format:
  ```
  ## 2025-12-11
  - **Phases 19-23 Complete**: Persistent Memory (40 tests), Credentials (43 tests),
    Scheduler (41 tests), Deployment (17 tests), Documentation (15 tests)
  - **v1 Completion**: Agent Engine v1 now complete with 1,127 passing tests across all 24 phases
  - **Documentation Cleanup**: Archived 8 completed phase implementation plans to CHANGELOG;
    reduced docs/ from 552 KB to 347 KB
  ```

---

### Action 6: Update operational/README.md (3.9 KB → 0.5 KB)

**Current State**: Lists each phase plan file

**New State**: Brief pointer to master plan
```markdown
# Operational Documentation

**Master Plan**: See `PLAN_BUILD_AGENT_ENGINE.md` for complete v1 roadmap (all 24 phases)

**Completed Phases**: Summaries available in `CHANGELOG.md`

**Active Work**: Check `PLAN_BUILD_AGENT_ENGINE.md` for phases still in progress

---

## Historical Phase Implementation Plans

Completed phase implementation plans (Phases 0-18) have been archived.
See `CHANGELOG.md` for summaries and test results.
```

---

### Action 7: Update docs/ Navigation

**Add to root README.md** (if not already present):
```markdown
## Documentation

### For Users
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design with diagrams
- **[API_REFERENCE.md](docs/API_REFERENCE.md)** - Complete public API
- **[TUTORIAL.md](docs/TUTORIAL.md)** - Getting started guide
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment
- **[SECURITY.md](docs/SECURITY.md)** - Security best practices
- **[CLI_FRAMEWORK.md](docs/CLI_FRAMEWORK.md)** - CLI REPL extension guide
- **[PACKAGING.md](docs/PACKAGING.md)** - PyPI packaging

### For Developers
- **[PLAN_BUILD_AGENT_ENGINE.md](docs/operational/PLAN_BUILD_AGENT_ENGINE.md)** - v1 roadmap & phase summaries
- **[CHANGELOG.md](docs/CHANGELOG.md)** - Release notes and phase completion summaries
- **[Canonical Specs](docs/canonical/)** - Frozen architectural specifications
- **[Multi-Task Isolation](docs/MULTI_TASK_ISOLATION.md)** - Phase 17 isolation model reference
```

---

## Cleanup Summary

| Action | Scope | KB Saved | Files Affected |
|--------|-------|----------|-----------------|
| Delete phase plans | Completed ops | ~205 KB | 8 files deleted |
| Condense master plan | PLAN_BUILD_AGENT_ENGINE.md | ~30 KB | 1 file modified |
| Relocate LLM docs | Move to .claude/ | ~7 KB moved | 2 files moved |
| Keep user-facing docs | No change | 0 KB | 7 files (stable) |
| Update CHANGELOG | Additions | +2 KB | 1 file modified |
| Update operational README | Condense | ~3 KB | 1 file modified |
| **Total Reduction** | **docs/ only** | **~242 KB** | **8 deleted, 4 modified** |

**Final docs/ size estimate**: 552 KB → 310 KB (44% reduction)

---

## Implementation Steps

1. **Backup current state** (commit before cleanup)
2. **Update CHANGELOG.md** with Phase 19-23 summaries
3. **Condense PLAN_BUILD_AGENT_ENGINE.md** (collapse phases 0-18 to summary tables)
4. **Delete 8 phase implementation plans** from docs/operational/
5. **Rename/relocate docs** (WORKFLOW_CHECKLIST, PROMPT_LIBRARY to .claude/)
6. **Update operational/README.md** with brief index
7. **Verify all references** work (no broken links)
8. **Update root README.md** with doc navigation table
9. **Final commit** with message "Cleanup: consolidate docs after v1 completion"

---

## Verification Checklist

- [ ] No broken links in remaining docs
- [ ] API_REFERENCE.md has all Phase 19-23 new APIs
- [ ] CHANGELOG.md updated with Phase 19-23 completions
- [ ] PLAN_BUILD_AGENT_ENGINE.md phases 0-18 condensed to 1-2 line summaries
- [ ] .claude/ directory created (if doesn't exist) with WORKFLOW_CHECKLIST.md and PROMPT_LIBRARY.md
- [ ] Root README.md has "Documentation" section with navigation table
- [ ] docs/ directory size reduced to ~310 KB
- [ ] All 24 phases' completion status visible in either PLAN or CHANGELOG
- [ ] No references to deleted files exist in code or other docs

---

## Recommendation

Proceed with **full cleanup** (all 7 actions):
- Phase implementation plans have served their purpose; archive in CHANGELOG and delete
- Completed work shouldn't occupy space in live documentation
- Relocation of WORKFLOW_CHECKLIST and PROMPT_LIBRARY improves organization
- Condensed master plan remains accessible but reduces maintenance overhead
- Final result: cleaner, more navigable documentation for users

**Estimated Time**: 30-45 minutes
**Risk Level**: Low (docs only, no code changes)
