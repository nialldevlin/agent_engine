# Agent Engine Implementation Plans

**Date:** 2025-12-04
**Status:** Active — Phases 0–2 complete; ready for Phase 3

---

## Overview

This repository has completed the foundational work for the Agent Engine and is ready to move into workflow/pipeline implementation (Phase 3). The core schemas, config loader, task persistence, and utility libraries are implemented and verified.

**Current State:**
- ✅ Phases 0, 1, and 2 completed and verified
- ✅ Project virtual environment and VS Code workspace files created
- ✅ 360 tests passing (full test suite)
- ✅ Task persistence (checkpointing, load, listing, metadata) implemented
- ⚠️ Remaining work: Phase 3 (Workflow Graph & Pipeline Executor) and onward

---

## Plans (summary)

- **PLAN_BUILD_AGENT_ENGINE.md** — Master implementation plan. Phases 0–2 are complete. Phase 3 (Workflow Graph & Pipeline Executor) is next.
- **PHASE_2_IMPLEMENTATION_PLAN.md** — Task persistence & resumability. COMPLETED and verified.
- **PHASE_2_SCHEMAS_OVERVIEW.md** — Schemas reference for Phase 2. Present and in sync with code.

Other planning artifacts and guides (Cline prompts, extraction summaries) are available in `docs/operational/` for audit and reference.

---

## Parallel Execution Strategy

Both plans can run **simultaneously** for maximum efficiency:

### Week 1: Foundations
**Codex:** Category A (Fix Example) - 3 hrs
**Sonnet:** Phase 1 (Memory) + Phase 4 (Fallback) - 10-13 hrs
**Result:** Working example + memory architecture

### Week 2: Intelligence & Docs
**Codex (Codex Max):** Category B (Docs) - 2-3 hrs ✨
**Sonnet:** Phase 2 (Context) + Phase 3 (Routing) - 9-13 hrs
**Result:** Complete docs + intelligent routing

### Week 3: Advanced Features
**Codex (Codex Max):** Categories C & D - 7-9 hrs ✨
**Sonnet:** Phase 6 (Post-Mortem) + King Arthur integration follow-ups - 7-10 hrs
**Result:** Algorithms + tests + post-mortem system + KA lift

### Week 4: Polish & Evolution
**Codex (Codex Max):** Category E (Refactoring) - 2-4 hrs ✨
**Sonnet:** Phase 7 (Evolution) + Phase 8 (ReAct) - 8-10 hrs
**Result:** Production-ready + evolution

**Total Time:**
- Sequential: ~58-79 hours
- Parallel: ~3-4 weeks calendar time
- With Codex Max optimization: ~47-64 hours actual work

---

## Coverage Verification

### Critical Production Requirements ✅

**Working Example:**
- ✅ PLAN_CODEX Category A: Fixes all bugs, adds review stage, creates E2E test

**Complete Documentation:**
- ✅ PLAN_CODEX Category B: API reference, config reference, examples, getting started

**Production Hardening:**
- ✅ PLAN_CODEX Category E: Error handling, structured outputs, CI/CD
- ✅ PLAN_SONNET Phase 4: Fallback matrix
- ✅ PLAN_CODEX Category D: Comprehensive tests

**Research-Driven Features:**
- ✅ PLAN_SONNET Phase 1: Multi-tier memory (RESEARCH §1.2)
- ✅ PLAN_SONNET Phase 2: Context profiles (RESEARCH §2.1, §2.2)
- ✅ PLAN_SONNET Phase 3: Telemetry routing (RESEARCH §4.1)
- ✅ PLAN_CODEX Category C: Compression (RESEARCH §1.3)
- ✅ PLAN_CODEX Category C: Templates (RESEARCH §5.1)
- ✅ PLAN_CODEX Category C: JSON repair (RESEARCH §7.1)
- ✅ KA Integration Plan: JSON/toolkit overrides + hygiene (RESEARCH §8.1)
- ✅ PLAN_SONNET Phase 6: Post-mortem (RESEARCH §7.2)
- ✅ PLAN_SONNET Phase 7: Evolution (RESEARCH §6.1)
- ✅ PLAN_SONNET Phase 8: ReAct (RESEARCH §3.2)

**Advanced Features:**
- ✅ PLAN_CODEX Category D: Benchmarks (RESEARCH §6.2)
- ✅ PLAN_CODEX Category D: Security tests

### Nothing Missing ✅

All requirements from the original unified plan are captured:
- Example fixes → PLAN_CODEX Category A
- Documentation → PLAN_CODEX Category B
- Production hardening → PLAN_CODEX Category E + PLAN_SONNET Phase 4
- Research features → Both plans comprehensively
- Tests → PLAN_CODEX Category D
- Advanced patterns → PLAN_SONNET Phases 6-8 + KA Integration Plan

---

## Codex Max ROI Analysis

**High-Value Tasks for Codex Max (Use Codex Max):**
1. **API Reference** - 2 hrs → 30 min (4x speedup)
2. **Config Reference** - 2 hrs → 30 min (4x speedup)
3. **Prompt Compression** - 3-4 hrs → 1 hr (3x speedup)
4. **Error Handling** - 2-3 hrs → 1 hr (2-3x speedup)
5. **Test Generation** - 6-8 hrs → 3-4 hrs (2x speedup)

**Total Savings: ~15 hours (45% reduction)**

**Use Standard Codex or Haiku:**
- Small bug fixes (too small for Max)
- Example-specific docs (needs context)
- Integration work (Sonnet handles)

---

## Success Criteria

### Phase 1 Complete (Example Working):
✅ Example runs with all 8 stages (including review)
✅ No schema errors
✅ No security gate errors
✅ E2E test passing

### Phase 2 Complete (Documentation):
✅ Complete API reference
✅ Complete config reference
✅ Example fully documented
✅ New developers can use the engine

### Phase 3 Complete (Production Ready):
✅ Multi-tier memory operational
✅ Intelligent routing with fitness
✅ Fallback matrix handling failures
✅ Test coverage >80%
✅ CI/CD validating all PRs

### Phase 4 Complete (Advanced Features):
✅ Override system working
✅ Post-mortems generated
✅ Evolution cycle active
✅ All RESEARCH.md checklists implemented

---

## Getting Started

1. **Review both plans:**
   - [PLAN_SONNET_MINION.md](./PLAN_SONNET_MINION.md) for architecture work
   - [PLAN_CODEX.md](./PLAN_CODEX.md) for systematic work

2. **Choose execution mode:**
   - **Parallel** (recommended): Run both plans simultaneously
   - **Sequential**: Complete PLAN_CODEX first, then PLAN_SONNET
   - **Custom**: Pick specific tasks from either plan

3. **Start with PLAN_CODEX Category A** (URGENT):
   - Fixes example bugs in ~3 hours
   - Unblocks user adoption
   - Enables testing other features

4. **Use Codex Max strategically:**
   - Documentation tasks (Category B)
   - Algorithm implementation (Category C)
   - Test generation (Category D)
   - Systematic refactoring (Category E)

---

## Coordination

**Both plans can run in parallel safely.**

**Potential conflicts:**
- Both touch schemas → use feature branches
- Both touch runtime → clear module boundaries
- Sync on major changes before merge

**Integration points:**
- Codex provides docs for Sonnet's features
- Codex provides tests for Sonnet's implementations
- Regular integration testing

---

## Archive & Completed Work

Completed plans and verification artifacts have been recorded under `docs/operational/`:

- `PHASE_2_IMPLEMENTATION_PLAN.md` — COMPLETED
- `EXTRACTION_SUMMARY.md` — Completed extraction & verification
- `PLAN_BUILD_AGENT_ENGINE.md` — Master plan annotated with completion marks through Phase 2

**Next Active Work:**
- Implement **Phase 3 — Workflow Graph & Pipeline Executor**

---

**Ready to execute Phase 3!** 🚀
