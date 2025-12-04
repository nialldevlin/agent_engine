# PLAN_PHASE_0 — Salvage & Refactor Legacy Components

**Phase:** 0 - Legacy Salvage (from PLAN_BUILD_AGENT_ENGINE.md)
**Status:** Ready for Execution
**Objective:** Extract, rename, and refactor *generic, engine-agnostic* utilities from `legacy/king_arthur/` into proper Agent Engine modules.

**Design Principle:** Only salvage what is truly engine-agnostic. Arthur-specific logic, roles, and assumptions must be stripped or quarantined.

---

## Overview

We have 24 Python files in `legacy/king_arthur/src/king_arthur_orchestrator/`:

**Core (3 files):**
- manifest_hygiene.py
- override_manager.py
- override_parser.py

**JSON Engine (5 files):**
- __init__.py
- contracts.py
- gateway.py
- medic.py
- utils.py

**Toolkit (16 files):**
- context.py, file_context.py, text_analysis.py, token_utils.py
- filesystem.py, json_io.py, json_utils.py
- manifest_utils.py, registry.py, validation_utils.py, version_utils.py
- execution.py, log_utils.py, plan_validation.py, prompt_helpers.py, task_intent.py

**Current State (from audit):**
- ✓ No imports from legacy into core (quarantine intact)
- ✓ All 18 expected salvage files exist (+ 6 extras)
- ? Salvage work NOT yet done—files remain in legacy/ unchanged

---

## Execution Strategy

### Phase 0A: Parallel Analysis (6 Minions)
Each minion analyzes a salvage area, identifies Arthur-specific vs. engine-agnostic code, and produces a refactoring plan.

### Phase 0B: Sequential Integration (Me, Sonnet)
I review all refactoring plans, make decisions, and coordinate integration into `src/agent_engine/`.

### Phase 0C: Parallel Implementation (N Minions)
Minions execute the approved refactorings in parallel.

### Phase 0D: Validation (Me, Sonnet)
I verify integration, run tests, update documentation.

---

## Phase 0A: Analysis Minions (Parallel)

### Minion 1: JSON Engine Analyst
**Target Files:**
- `legacy/king_arthur/src/king_arthur_orchestrator/json_engine/*.py` (5 files)

**Task:**
1. Read all 5 json_engine files
2. Compare with current `src/agent_engine/json_engine.py` (already exists)
3. Identify:
   - What's already salvaged/reimplemented in current engine
   - What's Arthur-specific (error messages, role assumptions, etc.)
   - What's genuinely useful and missing from current implementation
4. For each useful piece:
   - Extract the function/class
   - List required changes to make it engine-agnostic
   - Suggest integration location in current engine

**Output:** JSON_ENGINE_REFACTOR_PLAN.md with:
- Inventory of legacy functions/classes
- Comparison matrix: legacy vs current implementation
- Recommended salvages with integration instructions
- Arthur-specific code to discard

---

### Minion 2: Manifest & Registry Analyst
**Target Files:**
- `legacy/.../core/manifest_hygiene.py`
- `legacy/.../toolkit/manifest_utils.py`
- `legacy/.../toolkit/registry.py`
- `legacy/.../toolkit/validation_utils.py`
- `legacy/.../toolkit/version_utils.py`

**Task:**
1. Read all 5 manifest-related files
2. Compare with current `src/agent_engine/config_loader.py` and `schemas/registry.py`
3. Identify:
   - Manifest loading patterns (YAML/JSON parsing, validation)
   - Registry patterns (schema lookup, versioning)
   - Hygiene checks (cross-references, DAG validation)
   - Arthur-specific manifest fields or assumptions
4. Extract useful utilities not present in current implementation

**Output:** MANIFEST_REFACTOR_PLAN.md with:
- Function-by-function analysis
- Integration targets (config_loader.py, schemas/registry.py, or new modules)
- Required changes to remove Arthur dependencies
- Test coverage recommendations

---

### Minion 3: Override System Analyst
**Target Files:**
- `legacy/.../core/override_manager.py`
- `legacy/.../core/override_parser.py`

**Task:**
1. Read both override files
2. Compare with current `src/agent_engine/schemas/override.py` (schema exists but no runtime implementation)
3. Identify:
   - How overrides are parsed (natural language → structured)
   - How overrides are applied (routing, memory, safety, verbosity, mode)
   - Arthur-specific override logic (roles, commands, etc.)
   - Generic override mechanics suitable for engine
4. Design integration into `src/agent_engine/runtime/overrides/` (currently empty)

**Output:** OVERRIDE_REFACTOR_PLAN.md with:
- Override parsing strategy (keep vs rewrite)
- Override application strategy (router integration, task manager hooks)
- Schema alignment check (OverrideSpec in schemas/override.py)
- Natural language → structured mapping examples

---

### Minion 4: Context & Memory Analyst
**Target Files:**
- `legacy/.../toolkit/context.py`
- `legacy/.../toolkit/file_context.py`
- `legacy/.../toolkit/text_analysis.py`
- `legacy/.../toolkit/token_utils.py`

**Task:**
1. Read all 4 context-related files
2. Compare with current `src/agent_engine/runtime/context.py` (ContextAssembler already implemented)
3. Compare with current memory stores (task_store.py, project_store.py, global_store.py)
4. Identify:
   - Context assembly patterns (file context, text chunking, token budgeting)
   - Utilities missing from current implementation
   - Arthur-specific context assumptions
5. Extract reusable utilities

**Output:** CONTEXT_REFACTOR_PLAN.md with:
- Utility inventory (token counting, text chunking, file context building)
- Integration targets (runtime/context.py, memory/backend.py, or new utilities/)
- Comparison: legacy patterns vs current ContextAssembler implementation
- Recommendations for enhancement vs replacement

---

### Minion 5: Tool Runtime Analyst
**Target Files:**
- `legacy/.../toolkit/filesystem.py`
- `legacy/.../toolkit/json_io.py`
- `legacy/.../toolkit/execution.py`
- `legacy/.../toolkit/plan_validation.py`

**Task:**
1. Read all 4 tool-related files
2. Compare with current `src/agent_engine/runtime/tool_runtime.py` and `security.py`
3. Identify:
   - File system operations (read, write, search patterns)
   - JSON I/O utilities
   - Execution sandboxing/permissions
   - Plan validation (ToolPlan schema enforcement)
   - Arthur-specific tool assumptions
4. Extract generic tool utilities

**Output:** TOOL_RUNTIME_REFACTOR_PLAN.md with:
- Tool utility inventory (fs ops, json ops, execution patterns)
- Security check alignment (compare with current security.py)
- Integration targets (tool_runtime.py, security.py, or new tool_utils/)
- Recommendations for current implementation enhancement

---

### Minion 6: Extra Utilities Analyst
**Target Files (not in original salvage list, but present):**
- `legacy/.../toolkit/json_utils.py`
- `legacy/.../toolkit/log_utils.py`
- `legacy/.../toolkit/prompt_helpers.py`
- `legacy/.../toolkit/task_intent.py`

**Task:**
1. Read all 4 extra utility files
2. Determine if they're:
   - Generic and useful for engine
   - Arthur-specific and should be quarantined
   - Redundant with current implementation
3. For each useful utility:
   - Extract function/class
   - Identify integration location
   - List required changes

**Output:** EXTRA_UTILS_ASSESSMENT.md with:
- File-by-file verdict: SALVAGE / QUARANTINE / REDUNDANT
- For SALVAGE items: integration plan
- For QUARANTINE items: reason (Arthur-specific, obsolete, etc.)

---

## Phase 0B: Decision & Coordination (Me, Sonnet)

After all 6 minions report:

1. **Review all refactoring plans** - Ensure consistency, no duplication
2. **Make final salvage decisions** - What gets integrated, what stays quarantined
3. **Assign integration priorities** - Critical utilities first, nice-to-haves later
4. **Design integration strategy** - Where each salvaged piece goes in current engine
5. **Create implementation tasks** - Specific refactoring instructions for Phase 0C minions

**Output:** PHASE_0_INTEGRATION_PLAN.md with:
- Final salvage list (approved functions/classes)
- Integration locations (which src/agent_engine/ modules)
- Implementation task breakdown for Phase 0C
- Testing requirements
- Documentation updates needed

---

## Phase 0C: Parallel Implementation (N Minions)

Based on Phase 0B decisions, spawn minions to:

### Minion A: JSON Engine Integration
- Integrate approved json_engine utilities into `src/agent_engine/json_engine.py`
- Remove Arthur-specific error messages
- Add tests for new functionality

### Minion B: Manifest Utilities Integration
- Integrate approved manifest/registry utilities into `config_loader.py` and `schemas/registry.py`
- Enhance validation logic
- Add manifest hygiene checks

### Minion C: Override System Implementation
- Create `src/agent_engine/runtime/overrides/` module structure
- Integrate override parsing logic
- Implement override application in router/task_manager
- Add tests

### Minion D: Context Utilities Integration
- Enhance `runtime/context.py` with salvaged utilities
- Add token budgeting improvements
- Integrate file context patterns

### Minion E: Tool Runtime Utilities Integration
- Enhance `runtime/tool_runtime.py` with salvaged utilities
- Integrate filesystem/json_io patterns
- Add security checks if missing

### Minion F: Extra Utilities Integration (if approved)
- Integrate any approved extra utilities
- Place in appropriate modules or create new utilities/ subpackage

**Each minion outputs:**
- Refactored code (clean, engine-agnostic)
- Tests for new functionality
- Documentation updates

---

## Phase 0D: Validation (Me, Sonnet)

1. **Code review** - Verify all integrations are clean, no Arthur leakage
2. **Run full test suite** - Ensure no regressions
3. **Update AUDIT_SUMMARY.md** - Document Phase 0 completion
4. **Update CHANGELOG.md** - Record salvaged utilities
5. **Verify quarantine** - Confirm legacy/ remains isolated

**Success Criteria:**
- ✓ All approved utilities integrated into `src/agent_engine/`
- ✓ No Arthur-specific logic in core engine
- ✓ All tests passing
- ✓ Legacy quarantine intact (no imports from legacy/)
- ✓ Documentation updated

---

## Tracking

### Phase 0A: Analysis
- [ ] Minion 1: JSON Engine analysis
- [ ] Minion 2: Manifest & Registry analysis
- [ ] Minion 3: Override System analysis
- [ ] Minion 4: Context & Memory analysis
- [ ] Minion 5: Tool Runtime analysis
- [ ] Minion 6: Extra Utilities analysis

### Phase 0B: Decision
- [ ] Review all analysis reports
- [ ] Make salvage decisions
- [ ] Create integration plan
- [ ] Break down implementation tasks

### Phase 0C: Implementation
- [ ] JSON Engine integration
- [ ] Manifest utilities integration
- [ ] Override system implementation
- [ ] Context utilities integration
- [ ] Tool runtime utilities integration
- [ ] Extra utilities integration (if any)

### Phase 0D: Validation
- [ ] Code review all integrations
- [ ] Run test suite
- [ ] Update documentation
- [ ] Verify quarantine

---

## Estimated Effort

**Phase 0A (Analysis):** 4-6 hours (parallel, ~1 hour per minion using Haiku)
**Phase 0B (Decision):** 2-3 hours (me, Sonnet)
**Phase 0C (Implementation):** 8-12 hours (parallel, ~2 hours per minion using Haiku)
**Phase 0D (Validation):** 2-3 hours (me, Sonnet)

**Total:** 16-24 hours → **6-10 hours calendar time** with parallelization

---

## Notes

1. **Conservative salvage** - When in doubt, leave it in legacy/. Only integrate what's clearly engine-agnostic.

2. **Testing required** - Every salvaged utility must have tests. No blind copy-paste.

3. **Current implementation wins** - If current engine already has a better implementation, don't replace it with legacy code. Only add genuinely missing functionality.

4. **No Arthur resurrection** - Strip all Arthur-specific roles, names, assumptions, error messages.

5. **Schema alignment** - Salvaged utilities must work with current schemas (Task, Stage, Agent, Tool, etc.), not legacy schemas.

---

## Ready to Execute

**Next Steps:**
1. Launch Phase 0A minions in parallel (6 minions)
2. Wait for analysis reports
3. I (Sonnet) review and create integration plan
4. Launch Phase 0C minions in parallel
5. I validate and document completion

**Start command:** Ready when you are! Say "execute phase 0" to begin.
