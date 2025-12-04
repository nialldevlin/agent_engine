# UNIFIED PRODUCTION PLAN: Agent Engine to Production Ready

**Goal:** Complete the Agent Engine implementation and deliver a production-ready framework with one fully working example demonstrating an interpretation → decomposition → planning → review → execution workflow graph.

**Status Date:** 2025-12-03

---

## Executive Summary

The Agent Engine is **~85% complete**:
- ✅ All core schemas implemented (Task, Stage, Workflow, Agent, Tool, Memory, Event, Override)
- ✅ Runtime modules complete (TaskManager, PipelineExecutor, Router, Context, AgentRuntime, ToolRuntime)
- ✅ Config loader, JSON Engine, Security, Telemetry, Evolution stubs
- ✅ Plugin system and patterns (Committee, Supervisor)
- ✅ Comprehensive test suite (23 tests passing)
- ✅ Basic LLM agent example with manifests
- ⚠️ Example has minor issues (schema errors, security gate blocking execution)
- ❌ Missing: Documentation completeness, advanced examples, production hardening

**Remaining Work:** ~15% to achieve production-ready status with one polished example

---

## Current State Analysis

### ✅ COMPLETED (from all three plans)

**Phase 1-2: Project Structure & Schemas**
- ✅ Python project layout (pyproject.toml, src/, tests/, examples/, docs/)
- ✅ All schema models (task.py, stage.py, workflow.py, agent.py, tool.py, memory.py, event.py, override.py)
- ✅ Schema validation and registry
- ✅ Comprehensive schema tests

**Phase 3: Config & Validation**
- ✅ Config loader for YAML/JSON manifests
- ✅ JSON Engine with validation and repair
- ✅ DAG validation (cycle detection, reachability)
- ✅ Security permission skeleton
- ✅ Config loader tests

**Phase 4: Runtime Core**
- ✅ TaskManager (create, update, record results/errors)
- ✅ PipelineExecutor (orchestrate stage execution)
- ✅ Router (pipeline selection, stage transitions, decision routing)
- ✅ ContextAssembler and memory backends
- ✅ Runtime integration tests

**Phase 5: Agent & Tool Execution**
- ✅ AgentRuntime (prompt building, LLM integration, schema enforcement)
- ✅ ToolRuntime (tool execution, permission checks)
- ✅ LLM client interface with Mock, Anthropic, and Ollama adapters
- ✅ Plugin manager with hook system
- ✅ Committee and Supervisor pattern implementations
- ✅ Agent/Tool runtime tests

**Phase 6: Observability**
- ✅ TelemetryBus for event emission
- ✅ Evolution module (stub for scoring/feedback)
- ✅ Basic plugin examples

**Phase 7: Example**
- ✅ basic_llm_agent example with linear workflow
- ✅ Complete manifest set (agents.yaml, tools.yaml, workflow.yaml, pipelines.yaml, memory.yaml, stages.yaml)
- ✅ CLI runner script

### ⚠️ NEEDS FIXING (Critical for Production)

**Example Issues:**
1. Schema error: "Unknown schema 'gather_context_output'" in gather_context stage
2. Security gate blocking: "Workspace mutation not permitted" in execution stage
3. Missing: README.md for the example
4. Missing: Example doesn't demonstrate the full interpretation → decomposition → planning → **review** → execution flow (review stage is missing)

**Documentation Gaps:**
1. docs/canonical/API_REFERENCE.md is incomplete
2. docs/canonical/CONFIG_REFERENCE.md is incomplete
3. docs/GETTING_STARTED_AGENT_ENGINE.md needs validation
4. Example-specific documentation missing

**Production Hardening:**
1. Error handling completeness
2. Security policy enforcement (currently stub)
3. Evolution/scoring integration (currently stub)
4. Advanced routing features (fallbacks, overrides)
5. CI/CD pipeline (basic structure exists in .github/, needs validation)

---

## UNIFIED IMPLEMENTATION PLAN

### Phase A: Fix Example & Add Review Stage (CRITICAL PATH)
**Goal:** Get one fully working example demonstrating the complete workflow with review stage

**Serial Tasks (must be done in order):**

#### A1. Fix Schema Registration Issue
- **Assignee:** Minion 1 (Haiku)
- **Task:** Debug and fix "Unknown schema 'gather_context_output'" error
- **Files:**
  - `src/agent_engine/schemas/registry.py`
  - `configs/basic_llm_agent/stages.yaml`
- **Acceptance:** gather_context stage completes without schema error

#### A2. Fix Security Gate for Execution Stage
- **Assignee:** Minion 2 (Haiku)
- **Task:** Update security config to allow read-only execution in the example
- **Files:**
  - `src/agent_engine/security.py`
  - `configs/basic_llm_agent/*.yaml` (add security.yaml if missing)
  - `examples/basic_llm_agent/cli.py`
- **Acceptance:** execution stage runs and produces output without "Workspace mutation not permitted" error

#### A3. Add Review Stage to Workflow
- **Assignee:** Minion 3 (Haiku)
- **Task:** Add review stage between execution and results
- **Files:**
  - `configs/basic_llm_agent/workflow.yaml`
  - `configs/basic_llm_agent/stages.yaml`
  - `configs/basic_llm_agent/agents.yaml` (add reviewer agent)
  - `examples/basic_llm_agent/cli.py` (update ExampleLLMClient to handle review stage)
- **Acceptance:** Pipeline runs: user_input → gather_context → interpretation → decomposition → planning → execution → **review** → results

#### A4. End-to-End Integration Test
- **Assignee:** Sonnet (Review & Verify)
- **Task:** Create comprehensive integration test for the full example
- **Files:**
  - `tests/test_basic_llm_agent_e2e.py` (new)
- **Acceptance:** Test runs complete workflow with all stages, validates outputs

**Estimated Effort:** A1-A3 can partially run in parallel (3 Minions), A4 is serial
**Completion Criteria:** `python3 -m examples.basic_llm_agent.cli "analyze project structure"` produces clean output through all 8 stages

---

### Phase B: Documentation & Developer Experience (PARALLEL)
**Goal:** Complete documentation for production readiness

**Parallel Tasks (can run simultaneously):**

#### B1. Example Documentation
- **Assignee:** Minion 4 (Haiku)
- **Task:** Write comprehensive README for basic_llm_agent example
- **Files:**
  - `examples/basic_llm_agent/README.md` (new)
- **Content:**
  - What the example demonstrates
  - How to run it
  - How each stage works
  - How to extend/customize
  - Manifest structure explanation
- **Acceptance:** A new developer can understand and run the example from README alone

#### B2. API Reference Completion
- **Assignee:** Minion 5 (Haiku)
- **Task:** Complete API_REFERENCE.md with all public classes and functions
- **Files:**
  - `docs/canonical/API_REFERENCE.md`
- **Content:**
  - All schemas with field descriptions
  - All runtime classes with method signatures
  - Config loader usage
  - LLM client interface
  - Plugin system hooks
- **Acceptance:** Comprehensive reference for all public APIs

#### B3. Config Reference Completion
- **Assignee:** Minion 6 (Haiku)
- **Task:** Complete CONFIG_REFERENCE.md with manifest format documentation
- **Files:**
  - `docs/canonical/CONFIG_REFERENCE.md`
- **Content:**
  - agents.yaml format and fields
  - tools.yaml format and fields
  - workflow.yaml (stages, edges)
  - pipelines.yaml format
  - memory.yaml configuration
  - security.yaml permissions
  - Complete examples for each
- **Acceptance:** A user can write manifests from scratch using this doc

#### B4. Getting Started Guide Validation
- **Assignee:** Minion 7 (Haiku)
- **Task:** Review and enhance GETTING_STARTED_AGENT_ENGINE.md
- **Files:**
  - `docs/GETTING_STARTED_AGENT_ENGINE.md`
- **Content:**
  - Installation steps
  - Running the example
  - Creating a new project
  - Common patterns
  - Troubleshooting
- **Acceptance:** Follow the guide from scratch on a clean system

**Estimated Effort:** All B tasks can run in parallel (4 Minions)
**Completion Criteria:** Complete, accurate documentation exists for all aspects of the engine

---

### Phase C: Production Hardening (PARALLEL)
**Goal:** Harden the engine for production use

**Parallel Tasks (can run simultaneously):**

#### C1. Enhanced Error Handling
- **Assignee:** Minion 8 (Haiku)
- **Task:** Add comprehensive error handling and recovery
- **Files:**
  - `src/agent_engine/runtime/pipeline_executor.py`
  - `src/agent_engine/runtime/agent_runtime.py`
  - `src/agent_engine/runtime/tool_runtime.py`
  - `src/agent_engine/schemas/errors.py`
- **Changes:**
  - Graceful degradation on stage failures
  - Detailed error context in FailureSignature
  - Retry logic configuration
  - Fallback stage support
- **Tests:** Add error recovery tests
- **Acceptance:** Pipeline handles errors gracefully with fallbacks

#### C2. Security Policy Enforcement
- **Assignee:** Minion 9 (Haiku)
- **Task:** Implement full security policy system
- **Files:**
  - `src/agent_engine/security.py`
  - Add security.yaml to example manifests
- **Changes:**
  - Tool capability enforcement (filesystem, network, shell)
  - Mode-based restrictions (analysis_only, safe_mode)
  - Per-agent tool whitelists
  - Detailed permission audit logs
- **Tests:** Add security enforcement tests
- **Acceptance:** Security policies are fully enforced and auditable

#### C3. Advanced Routing Features
- **Assignee:** Minion 10 (Haiku)
- **Task:** Enhance router with advanced features from research
- **Files:**
  - `src/agent_engine/runtime/router.py`
  - `src/agent_engine/schemas/override.py`
- **Changes:**
  - User override support
  - Agent fallback selection on errors
  - Evolution score integration for agent selection
  - Routing trace with detailed reasoning
- **Tests:** Add routing decision tests
- **Acceptance:** Router supports overrides, fallbacks, and evolution-based selection

#### C4. Evolution & Scoring Integration
- **Assignee:** Minion 11 (Haiku)
- **Task:** Wire evolution module into router and telemetry
- **Files:**
  - `src/agent_engine/evolution.py`
  - `src/agent_engine/runtime/router.py`
  - `src/agent_engine/telemetry.py`
- **Changes:**
  - Collect success/failure metrics per agent
  - Compute simple fitness scores
  - Router queries scores for agent selection
  - Telemetry emits performance events
- **Tests:** Add evolution scoring tests
- **Acceptance:** Router selects agents based on historical performance

**Estimated Effort:** All C tasks can run in parallel (4 Minions), but some have dependencies (C4 depends on C3)
**Completion Criteria:** Production-grade error handling, security, routing, and evolution

---

### Phase D: Additional Examples & Advanced Features (OPTIONAL)
**Goal:** Provide more examples and advanced patterns

**Optional Tasks (for future enhancement):**

#### D1. Committee Pattern Example
- **Assignee:** Minion 12 (Haiku)
- **Task:** Create committee pattern example
- **Files:**
  - `examples/committee_decision/` (new directory)
  - Complete manifest set
  - CLI runner
  - README.md
- **Demonstrates:** Multiple agents working in parallel with merge stage

#### D2. Supervisor Pattern Example
- **Assignee:** Minion 13 (Haiku)
- **Task:** Create supervisor pattern example
- **Files:**
  - `examples/supervisor_review/` (new directory)
  - Complete manifest set
  - CLI runner
  - README.md
- **Demonstrates:** Worker-supervisor review cycle

#### D3. Tool-Heavy Example
- **Assignee:** Minion 14 (Haiku)
- **Task:** Create example with extensive tool usage
- **Files:**
  - `examples/tool_agent/` (new directory)
- **Demonstrates:** File operations, search, transformations via tools

#### D4. CI/CD Pipeline
- **Assignee:** Minion 15 (Haiku)
- **Task:** Set up comprehensive CI/CD
- **Files:**
  - `.github/workflows/` (enhance existing)
- **Includes:**
  - Tests on multiple Python versions
  - Linting (ruff, mypy)
  - Coverage reporting
  - Automated releases

**Estimated Effort:** Each D task is independent and can run in parallel
**Completion Criteria:** Multiple examples demonstrating different patterns

---

## EXECUTION STRATEGY

### Recommended Approach: Sonnet + Minion Swarm

**Phase A (Critical Path):**
1. Sonnet spawns Minions 1, 2, 3 in parallel for A1, A2, A3
2. Sonnet reviews all outputs, integrates changes
3. Sonnet performs A4 (integration test)
4. **Checkpoint:** Working example with full workflow

**Phase B (Parallel Documentation):**
1. Sonnet spawns Minions 4, 5, 6, 7 in parallel for B1, B2, B3, B4
2. Sonnet reviews for accuracy and completeness
3. **Checkpoint:** Complete documentation

**Phase C (Parallel Hardening):**
1. Sonnet spawns Minions 8, 9, 10 in parallel for C1, C2, C3
2. Minion 11 starts C4 after C3 completes
3. Sonnet reviews, ensures integration
4. **Checkpoint:** Production-ready engine

**Phase D (Optional, Future Work):**
1. Can be deferred to post-production
2. Each task is independent

---

## GPT CODEX / CODEX MAX RECOMMENDATIONS

**Where Codex/Codex Max Can Help:**

### High-Value Codex Tasks (Large, Mechanical Work):

1. **B2: API Reference Completion**
   - Codex excels at: Extracting all public APIs, generating structured documentation
   - Suggested model: Codex Max
   - Estimated speedup: 5x faster than manual documentation

2. **B3: Config Reference Completion**
   - Codex excels at: Schema documentation, YAML examples generation
   - Suggested model: Codex Max
   - Estimated speedup: 4x faster

3. **C1: Enhanced Error Handling**
   - Codex excels at: Systematic error handling patterns across multiple files
   - Suggested model: Codex Max
   - Estimated speedup: 3x faster with better coverage

4. **D4: CI/CD Pipeline**
   - Codex excels at: GitHub Actions configuration, standard CI patterns
   - Suggested model: Standard Codex
   - Estimated speedup: 3x faster

### Keep with Haiku Minions (Small, Focused Tasks):

1. **A1, A2, A3:** Small bug fixes and additions (Haiku is sufficient and cheaper)
2. **B1, B4:** Example-specific docs (requires context, Haiku is better)
3. **C2, C3, C4:** Complex logic requiring research references (Sonnet oversight needed)

### Summary:
- **Use Codex Max for:** B2, B3, C1, D4 (large-scale documentation and systematic code patterns)
- **Use Haiku Minions for:** A-tasks, B1, B4, C2, C3, C4 (focused work requiring oversight)
- **Sonnet always reviews and integrates all outputs**

**Estimated overall speedup with Codex Max:** ~30% reduction in total time for Phases B and C

---

## SUCCESS CRITERIA

### Minimum Viable Production (MVP):
✅ All Phase A tasks complete (working example with review stage)
✅ All Phase B tasks complete (comprehensive documentation)
✅ Core Phase C tasks complete (C1, C2 at minimum)

### Full Production Ready:
✅ All Phase A, B, C tasks complete
✅ Example runs cleanly end-to-end
✅ All tests pass (target: >30 tests with >85% coverage)
✅ Documentation allows new developers to use the engine
✅ Security and error handling are production-grade
✅ CI/CD validates all PRs

### Post-Production Enhancement:
✅ Phase D tasks complete
✅ Multiple examples demonstrating different patterns
✅ Advanced features (evolution, complex routing) fully validated

---

## TASK ASSIGNMENT MATRIX

| Phase | Task | Assignee | Can Parallelize? | Codex Recommended? | Estimated Effort |
|-------|------|----------|------------------|-------------------|------------------|
| A1 | Fix schema registration | Minion 1 (Haiku) | Yes (with A2,A3) | No | 30 min |
| A2 | Fix security gate | Minion 2 (Haiku) | Yes (with A1,A3) | No | 30 min |
| A3 | Add review stage | Minion 3 (Haiku) | Yes (with A1,A2) | No | 45 min |
| A4 | E2E integration test | Sonnet | No (after A1-3) | No | 30 min |
| B1 | Example README | Minion 4 (Haiku) | Yes (all B tasks) | No | 45 min |
| B2 | API reference | Minion 5 (Haiku) | Yes (all B tasks) | **Yes (Codex Max)** | 2 hrs → 30 min |
| B3 | Config reference | Minion 6 (Haiku) | Yes (all B tasks) | **Yes (Codex Max)** | 2 hrs → 30 min |
| B4 | Getting started review | Minion 7 (Haiku) | Yes (all B tasks) | No | 30 min |
| C1 | Error handling | Minion 8 (Haiku) | Yes (all C tasks) | **Yes (Codex Max)** | 2 hrs → 45 min |
| C2 | Security enforcement | Minion 9 (Haiku) | Yes (all C tasks) | No | 1.5 hrs |
| C3 | Advanced routing | Minion 10 (Haiku) | Yes (all C tasks) | No | 1.5 hrs |
| C4 | Evolution integration | Minion 11 (Haiku) | No (after C3) | No | 1 hr |
| D1-D4 | Optional examples | Minions 12-15 | Yes (all D tasks) | Yes for D4 | 2-4 hrs each |

**Total Critical Path Time (Serial):**
- With Haiku only: ~6-7 hours
- With Codex Max for B2, B3, C1: ~4-5 hours
- Maximum parallelization: ~2-3 hours with 11 agents running in swarm

---

## NEXT STEPS

### Immediate Actions (Sonnet):
1. Review and approve this unified plan
2. Spawn Minions 1, 2, 3 for Phase A tasks
3. Monitor progress and integrate changes
4. Run A4 integration test to validate

### Week 1 Target:
- ✅ Phase A complete (working example)
- ✅ Phase B complete (documentation)

### Week 2 Target:
- ✅ Phase C complete (production hardening)
- ✅ Full production ready status achieved

### Future:
- Phase D tasks as needed
- Community examples
- Advanced patterns

---

## APPENDIX: File Checklist

### Files to Create:
- [ ] `examples/basic_llm_agent/README.md`
- [ ] `tests/test_basic_llm_agent_e2e.py`
- [ ] `configs/basic_llm_agent/security.yaml` (if missing)

### Files to Update:
- [ ] `src/agent_engine/schemas/registry.py` (A1)
- [ ] `src/agent_engine/security.py` (A2, C2)
- [ ] `configs/basic_llm_agent/workflow.yaml` (A3)
- [ ] `configs/basic_llm_agent/stages.yaml` (A3)
- [ ] `configs/basic_llm_agent/agents.yaml` (A3)
- [ ] `examples/basic_llm_agent/cli.py` (A2, A3)
- [ ] `docs/canonical/API_REFERENCE.md` (B2)
- [ ] `docs/canonical/CONFIG_REFERENCE.md` (B3)
- [ ] `docs/GETTING_STARTED_AGENT_ENGINE.md` (B4)
- [ ] `src/agent_engine/runtime/pipeline_executor.py` (C1)
- [ ] `src/agent_engine/runtime/agent_runtime.py` (C1)
- [ ] `src/agent_engine/runtime/tool_runtime.py` (C1)
- [ ] `src/agent_engine/schemas/errors.py` (C1)
- [ ] `src/agent_engine/runtime/router.py` (C3, C4)
- [ ] `src/agent_engine/evolution.py` (C4)
- [ ] `src/agent_engine/telemetry.py` (C4)

### Files Needing Tests:
- [ ] Error handling tests (C1)
- [ ] Security enforcement tests (C2)
- [ ] Routing decision tests (C3)
- [ ] Evolution scoring tests (C4)

---

**End of Unified Production Plan**

This plan supersedes:
- `PLAN_AGENT_ENGINE.md`
- `PLAN_AGENT_ENGINE_CODEX.md`
- `PLAN_AGENT_ENGINE_SONNET_MINIONS.md`

All three previous plans have been consolidated into this single, actionable, production-focused roadmap.
