# PLAN_SONNET_MINION: Research-Driven Architectural Enhancements

**Lead:** Sonnet (architecture & integration)
**Workers:** Haiku Minions (focused implementation)
**Focus:** Complex, research-driven features requiring architectural design and careful integration

**Date:** 2025-12-03
**Last Updated:** 2025-12-03
**Based on:** RESEARCH.md implementation checklists + current codebase analysis

---

## 🎯 EXECUTION STATUS

### ✅ COMPLETED
- **Phase 1: Multi-Tier Memory Architecture** (100% complete)
  - All 6 tasks (1.1-1.6) implemented and tested
  - 99 new tests added (123 total tests passing)
  - Design: `docs/design/MEMORY_ARCHITECTURE.md`
  - Implementation: `src/agent_engine/runtime/memory/` (backend, task_store, project_store, global_store)
  - Integration: Updated `ContextAssembler` with backward compatibility
  - Tests: `tests/test_context_integration.py` (10 integration tests passing)

- **Phase 2.1: Context Profiles Design** (Design complete, implementation pending)
  - Design: `docs/design/CONTEXT_PROFILES.md`

### 🚧 IN PROGRESS
- **Phase 2: Context Retrieval Policies** (20% complete - design done, implementation pending)

### 📋 NEXT STEPS
1. **Phase 2.2-2.5**: Implement Context Profiles (Minions 5-7, ~3 hours)
   - Task 2.2: Implement ContextProfile Schema
   - Task 2.3: Implement Context Retrieval Policies
   - Task 2.4: Integrate Profiles into ContextAssembler (Sonnet)
   - Task 2.5: Create Default Profiles
   - Task 2.6: Context paging/compression telemetry

2. **Phase 3**: Telemetry-Based Routing (~5-7 hours)
3. **Phase 4**: Fallback Matrix (~4-5 hours, can run in parallel)
4. **Phase 6-8**: Advanced features (~20-24 hours)
5. **Phase 9**: Telemetry/UX/Cost instrumentation (~4-6 hours, parallel with Codex Category F)

---

## Overview

This plan implements **research-driven enhancements** from RESEARCH.md that require:
- Architectural decisions and design
- Integration across multiple subsystems
- Careful consideration of research findings
- Complex logic and state management

These tasks are **best suited for Sonnet + Haiku Minions** rather than Codex because they require deep understanding of the research context and architectural implications.

> **Scope note:** Context-profile work and “agent challenger” evolution described below are prospective research items; they are not part of the current Agent Engine runtime and must remain explicitly gated until implemented.

**Can run in PARALLEL with PLAN_CODEX.md**

> **King Arthur Integration Note:** All lift-and-integrate work for `legacy/king_arthur/` components (JSON engine, toolkit, overrides, manifest hygiene) is now tracked in `legacy/king_arthur/INTEGRATION_PLAN.md`. Keep this plan focused on research-driven architectural work; coordinate with the integration plan before taking any King Arthur tasks.

---

## Current State: Research Implementation Gap Analysis

### ✅ Already Implemented (Good Foundation)
- ContextItem, ContextFingerprint, ContextPackage schemas
- ToolPlan, ToolCapability, ToolRiskLevel
- FailureSignature and EngineError schemas
- AgentManifest with evolution parameters
- Basic template_version tracking
- Basic HEAD/TAIL context preservation
- Budget-aware context assembly

### ❌ Missing Research-Driven Features (This Plan)

**TIER 1 - Critical Enhancements (RESEARCH.md §1-4):**
1. Multi-tier memory stores (task/project/global) - RESEARCH §1.2
2. Context retrieval policies (agent-aware, task-aware) - RESEARCH §2.1
3. Agent-specific context profiles - RESEARCH §2.2
4. Router with telemetry-based selection - RESEARCH §4.1
5. Fallback matrix implementation - RESEARCH §4.2
6. Context paging/compression telemetry & debug trace - RESEARCH §§1.1-1.3

**TIER 2 - Advanced Features (RESEARCH.md §3, 6-7):**
7. ReAct-style internal reasoning support - RESEARCH §3.2
8. Post-mortem analyst for root cause - RESEARCH §7.2
9. Evolution system integration - RESEARCH §6.1
10. Global vs project memory namespaces - RESEARCH §8.2
11. UX/cost/carbon telemetry scaffolding - RESEARCH §9, Appendix A.5-A.6

---

## Phase 1: Multi-Tier Memory Architecture (RESEARCH §1.2) ✅ COMPLETE

**Goal:** Implement MemGPT-style memory hierarchy with task/project/global tiers

**Status:** ✅ All 6 tasks complete, 99 new tests added, 123 total tests passing

### Task 1.1: Design Memory Store Architecture ✅ COMPLETE
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §1.2, §8.2
**Deliverable:** Design document + interface definitions

**Design Requirements:**
- Separate stores for: `task`, `project/<project_id>`, `global`
- Each store implements common `MemoryBackend` interface
- Paging policies for moving data between tiers
- Clear write/read APIs with scope enforcement

**Sonnet Decides:**
- Storage backend (in-memory for now, pluggable for future)
- Paging policies (when to promote task → project, project → global)
- Namespace structure for project isolation
- Migration path from legacy single-tier context store (completed)

**Output:** ✅ `docs/design/MEMORY_ARCHITECTURE.md` (created)

### Task 1.2: Implement Memory Backend Interface ✅ COMPLETE
**Assignee:** Minion 1 (Haiku)
**Files:**
- `src/agent_engine/runtime/memory/__init__.py` (new)
- `src/agent_engine/runtime/memory/backend.py` (new)

**Implementation:**
```python
# Interface based on Sonnet's design
class MemoryBackend(Protocol):
    def add(self, item: ContextItem) -> None: ...
    def query(self, filters: dict, limit: int) -> List[ContextItem]: ...
    def delete(self, item_id: str) -> bool: ...
    def list_all(self) -> List[ContextItem]: ...
```

**Tests:** ✅ `tests/test_memory_backend.py` (34 tests passing)

### Task 1.3: Implement TaskMemoryStore ✅ COMPLETE
**Assignee:** Minion 2 (Haiku)
**Files:** `src/agent_engine/runtime/memory/task_store.py`

**Features:**
- Ephemeral storage per task (cleared when task completes)
- Fast access for current task context
- Automatic cleanup after task completion

**Tests:** ✅ `tests/test_task_store.py` (18 tests passing)

### Task 1.4: Implement ProjectMemoryStore ✅ COMPLETE
**Assignee:** Minion 3 (Haiku)
**Files:** `src/agent_engine/runtime/memory/project_store.py`

**Features:**
- Namespaced by project_id
- Persistent across tasks within same project
- Design decisions, conventions, important failures
- TTL or size-based eviction

**Tests:** ✅ `tests/test_project_store.py` (24 tests passing)

### Task 1.5: Implement GlobalMemoryStore ✅ COMPLETE
**Assignee:** Minion 4 (Haiku)
**Files:** `src/agent_engine/runtime/memory/global_store.py`

**Features:**
- User preferences and styles
- Cross-project patterns
- Careful write permissions (confirmation required)
- Long-term persistence

**Tests:** ✅ `tests/test_global_store.py` (23 tests passing)

### Task 1.6: Integrate Memory Tiers into ContextAssembler ✅ COMPLETE
**Assignee:** Sonnet (Integration)
**Files:** `src/agent_engine/runtime/context.py`

**Changes:**
- Replace single-tier context store with multi-tier architecture (complete)
- Query all three tiers based on ContextRequest
- Implement paging policies (prefer task > project > global)
- Budget allocation across tiers

**Tests:** ✅ `tests/test_context_integration.py` (10 integration tests passing)

**Estimated Effort:** Phase 1 = 6-8 hours (can parallelize 1.2-1.5)
**Actual Effort:** ~6 hours (parallelized 1.2-1.5 with 4 minions)

---

## Phase 2: Context Retrieval Policies (RESEARCH §2.1, §2.2) 🚧 IN PROGRESS

**Goal:** Implement agent-aware, task-aware context retrieval

**Status:** 20% complete (Task 2.1 design done, tasks 2.2-2.5 pending)

### Task 2.1: Design Context Profiles System ✅ COMPLETE
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §2.1, §2.2
**Deliverable:** `docs/design/CONTEXT_PROFILES.md`

**Design Requirements:**
- ContextProfile per agent role (Implementer, Analyst, Strategist, Assistant)
- Profiles specify: preferred context types, retrieval biases, budget allocation
- Examples:
  - Implementers: code + tests + minimal conversation
  - Strategist: summaries + decisions + preferences, no raw code
  - Analysts: specific domain focus (JSON repair, review, etc.)

**Sonnet Decides:**
- Profile schema structure
- How profiles integrate with ContextRequest
- Default profiles for each role
- Override mechanism for custom profiles

**Output:** ✅ `docs/design/CONTEXT_PROFILES.md` (created)

### Task 2.2: Implement ContextProfile Schema ⏳ NEXT
**Assignee:** Minion 5 (Haiku)
**Files:** `src/agent_engine/schemas/memory.py`

**Add:**
```python
class ContextProfile(SchemaBase):
    profile_id: str
    role: AgentRole
    preferred_sources: List[str]  # ['code', 'tests', 'decisions']
    budget_allocation: Dict[str, float]  # {'code': 0.6, 'history': 0.3, 'decisions': 0.1}
    retrieval_bias: Dict[str, float]  # importance multipliers per source
    max_history_turns: int
```

### Task 2.3: Implement Context Retrieval Policies
**Assignee:** Minion 6 (Haiku)
**Files:**
- `src/agent_engine/runtime/memory/retrieval_policy.py` (new)

**Implementation:**
- `RetrievalPolicy` class with scoring functions
- Task-aware retrieval (bias toward mentioned files/paths)
- Recency + importance + relevance scoring
- Budget-aware selection with profile guidance

**Tests:** Scoring and selection for different profiles

### Task 2.4: Integrate Profiles into ContextAssembler
**Assignee:** Sonnet (Integration)
**Files:**
- `src/agent_engine/runtime/context.py`
- `src/agent_engine/runtime/agent_runtime.py`

**Changes:**
- ContextRequest includes agent_profile
- ContextAssembler uses profile for retrieval decisions
- Different context packages for Implementer vs Strategist vs Analyst

**Tests:** Profile-based context retrieval

### Task 2.5: Create Default Profiles
**Assignee:** Minion 7 (Haiku)
**Files:** `configs/context_profiles/` (new directory)

**Create:**
- `agent_default.yaml`
- `analyst_default.yaml`
- `strategist_default.yaml`
- `assistant_default.yaml`

### Task 2.6: Context Paging & Compression Telemetry (Head/Tail Debug)
**Assignee:** Sonnet (Integration)
**Files:** `src/agent_engine/runtime/context.py`, `agent_engine/telemetry.py`

**Add:**
- Emit telemetry on selected vs dropped items (head/tail preserved, middle compressed).
- Record `compression_ratio`, policy mode, and reasons for drops; expose debug flag to print trace.
- Tests: assert telemetry events/logs include paging decisions; regression fixture for HEAD/TAIL preservation.

**Estimated Effort:** Phase 2 = 4-6 hours (tasks 2.2-2.3 can parallelize)

---

## Phase 3: Router with Telemetry-Based Selection (RESEARCH §4.1)

**Goal:** Implement MoA-style routing with telemetry and fitness scoring

### Task 3.1: Design Routing Architecture
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §4.1, MoA patterns
**Deliverable:** `docs/design/ROUTING_ARCHITECTURE.md`

**Design Requirements:**
- Router considers: task features, agent fitness scores, context fingerprints
- Support for primary + backup agent selection
- Confidence scores for routing decisions
- Telemetry-driven fitness tracking per agent

**Sonnet Decides:**
- Fitness scoring algorithm
- When to use primary vs backup routing
- How context fingerprints inform routing
- Confidence thresholds for fallback

### Task 3.2: Enhance ContextFingerprint Usage
**Assignee:** Minion 8 (Haiku)
**Files:** `src/agent_engine/schemas/memory.py`

**Enhance ContextFingerprint:**
- Add fingerprint computation from TaskSpec + context
- Hash key file paths, tags, mode
- Include complexity estimate

**Add utility functions:**
```python
def compute_fingerprint(task: Task, context: ContextPackage) -> ContextFingerprint
def fingerprint_similarity(fp1: ContextFingerprint, fp2: ContextFingerprint) -> float
```

### Task 3.3: Implement Agent Fitness Tracking
**Assignee:** Minion 9 (Haiku)
**Files:** `src/agent_engine/evolution.py`

**Enhance evolution.py:**
- Track per-agent success/failure by fingerprint region
- Compute fitness scores: `success_rate * complexity_handled`
- Store historical performance
- Expose `get_fitness(agent_id, fingerprint) -> float`

**Tests:** Fitness tracking and retrieval

### Task 3.4: Enhance Router with Telemetry Selection
**Assignee:** Minion 10 (Haiku)
**Files:** `src/agent_engine/runtime/router.py`

**Add to Router:**
- `choose_agent(task_spec, fingerprint, agents_available) -> (primary, backups, confidence)`
- Query fitness scores from evolution module
- Consider task features + fingerprint similarity
- Return confidence score (0.0-1.0)

**Logic:**
- If confidence < threshold, include backup agents
- Log routing decision with reasoning

**Tests:** Routing decisions with various fitness scenarios

### Task 3.5: Integration and Telemetry
**Assignee:** Sonnet (Integration)
**Files:**
- `src/agent_engine/runtime/pipeline_executor.py`
- `src/agent_engine/telemetry.py`

**Changes:**
- Compute fingerprint before routing
- Log routing decision + fingerprint to telemetry
- Log task outcome with fingerprint for fitness updates
- Wire fitness updates into evolution module

**Tests:** End-to-end routing with fitness tracking

**Estimated Effort:** Phase 3 = 5-7 hours (tasks 3.2-3.4 can parallelize)

---

## Phase 4: Fallback Matrix (RESEARCH §4.2)

**Goal:** Implement structured failure handling with fallback policies

### Task 4.1: Design Fallback Matrix
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §4.2
**Deliverable:** `docs/design/FALLBACK_MATRIX.md`

**Design Requirements:**
- Map each FailureCode → recommended actions
- Actions: retry, switch_agent, escalate, ask_user
- Configurable per-stage, per-mode
- Telemetry for fallback effectiveness

**Sonnet Decides:**
- Default fallback matrix structure
- When to retry vs switch vs escalate
- Maximum retry counts per failure type
- User escalation triggers

### Task 4.2: Implement Fallback Policy Schema
**Assignee:** Minion 11 (Haiku)
**Files:** `src/agent_engine/schemas/errors.py`

**Add:**
```python
class FallbackAction(str, Enum):
    RETRY = "retry"
    SWITCH_AGENT = "switch_agent"
    ESCALATE = "escalate"
    ASK_USER = "ask_user"
    FAIL = "fail"

class FallbackPolicy(SchemaBase):
    failure_code: FailureCode
    max_retries: int
    actions: List[FallbackAction]
    switch_to_agent_role: Optional[AgentRole]
```

### Task 4.3: Implement Fallback Matrix Handler
**Assignee:** Minion 12 (Haiku)
**Files:** `src/agent_engine/runtime/fallback.py` (new)

**Implementation:**
- `FallbackHandler` class
- Load fallback matrix from config
- `handle_failure(failure: FailureSignature, task: Task) -> FallbackAction`
- Track retry counts per failure type
- Log fallback decisions to telemetry

**Tests:** Fallback decision logic

### Task 4.4: Integrate Fallback into PipelineExecutor
**Assignee:** Sonnet (Integration)
**Files:** `src/agent_engine/runtime/pipeline_executor.py`

**Changes:**
- Catch stage failures
- Consult FallbackHandler
- Execute fallback actions:
  - Retry: re-run stage with same agent
  - Switch: router selects backup agent
  - Escalate: move to escalation stage or ask user
- Log fallback paths taken

**Tests:** End-to-end fallback scenarios

### Task 4.5: Create Default Fallback Configs
**Assignee:** Minion 13 (Haiku)
**Files:** `configs/fallback_matrix.yaml` (new)

**Define defaults:**
```yaml
fallbacks:
  - failure_code: json_error
    max_retries: 2
    actions: [retry, switch_agent]
  - failure_code: tool_failure
    max_retries: 1
    actions: [retry, escalate]
  - failure_code: context_miss
    max_retries: 0
    actions: [ask_user]
```

**Estimated Effort:** Phase 4 = 4-5 hours (tasks 4.2-4.3 can parallelize)

---

## Phase 5: Override Parser (RESEARCH §8.1)

*Delegated.* Override parser, manager, and manifest hygiene work now live in `legacy/king_arthur/INTEGRATION_PLAN.md`. Follow that plan for all King Arthur lift tasks; do not implement override work inside this document. Remove this section entirely once the integration plan lands.

---

## Phase 6: Post-Mortem Analyst (RESEARCH §7.2)

**Goal:** Automated root-cause analysis for failures

### Task 6.1: Design Post-Mortem System
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §7.2
**Deliverable:** `docs/design/POST_MORTEM.md`

**Design Requirements:**
- Trigger post-mortem on significant failures
- Analyze: plan, tool logs, context, errors
- Output: root-cause summary + tags
- Store for evolution and debugging

**Sonnet Decides:**
- When to trigger post-mortem (always? only severe failures?)
- What data to include in analysis
- Tag taxonomy for root causes
- How to surface post-mortems to developers

### Task 6.2: Implement Post-Mortem Analyst
**Assignee:** Minion 17 (Haiku)
**Files:** `src/agent_engine/runtime/post_mortem.py` (new)

**Implementation:**
- `PostMortemAnalyst` class
- Takes: Task, stage outputs, errors, tool logs
- Uses small LLM to analyze
- Returns: `PostMortemReport` with summary + tags

```python
class PostMortemReport(SchemaBase):
    task_id: str
    root_cause: str
    tags: List[str]  # ['bad_plan', 'context_miss', 'tool_failure']
    recommendations: List[str]
    severity: Severity
```

**Tests:** Mock post-mortem analysis

### Task 6.3: Integrate Post-Mortem into Pipeline
**Assignee:** Sonnet (Integration)
**Files:** `src/agent_engine/runtime/pipeline_executor.py`

**Changes:**
- Trigger post-mortem on failure
- Store report in telemetry
- Optional: surface to user in CLI/UI

**Tests:** Post-mortem triggered on failures

### Task 6.4: Add Post-Mortem Analytics
**Assignee:** Minion 18 (Haiku)
**Files:** `src/agent_engine/telemetry.py`

**Add:**
- Aggregate post-mortem tags
- Identify common failure patterns
- Surface trends for debugging

**Tests:** Tag aggregation and trend analysis

**Estimated Effort:** Phase 6 = 3-4 hours (linear, post-mortem depends on integration)

---

## Phase 7: Evolution System Integration (RESEARCH §6.1)

**Goal:** Wire evolution into routing and enable agent challengers

### Task 7.1: Design Evolution System
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §6.1
**Deliverable:** `docs/design/EVOLUTION_SYSTEM.md`

**Design Requirements:**
- Spawn challenger agents with mutated manifests
- Route fraction of tasks to challengers
- Score challengers vs incumbents
- Promote or retire based on performance

**Sonnet Decides:**
- Mutation strategy for AgentManifest parameters
- Challenger spawn frequency
- Evaluation period and criteria
- Promotion/retirement thresholds

### Task 7.2: Implement Implementer Challenger System
**Assignee:** Minion 19 (Haiku)
**Files:** `src/agent_engine/evolution.py`

**Enhance:**
- `spawn_challenger(base_agent: AgentDefinition) -> AgentDefinition`
- Mutate manifest parameters (reasoning_steps, tool_bias, verbosity, tests_emphasis)
- Track lineage (parent agent ID)

**Tests:** Challenger spawning with valid mutations

### Task 7.3: Implement Challenger Routing
**Assignee:** Minion 20 (Haiku)
**Files:** `src/agent_engine/runtime/router.py`

**Add:**
- `challenger_fraction` config (e.g., 10% of tasks to challengers)
- Randomly select challengers for routing
- Ensure balanced evaluation

**Tests:** Challenger routing distribution

### Task 7.4: Implement Promotion/Retirement Logic
**Assignee:** Minion 21 (Haiku)
**Files:** `src/agent_engine/evolution.py`

**Add:**
- `evaluate_challengers()` - compare fitness scores
- Promote successful challengers to primary pool
- Retire underperforming agents (with safeguards)
- Preserve lineage for analysis

**Tests:** Promotion and retirement decisions

### Task 7.5: Integration and Configuration
**Assignee:** Sonnet (Integration)
**Files:**
- `src/agent_engine/runtime/pipeline_executor.py`
- `configs/evolution.yaml` (new)

**Add config:**
```yaml
evolution:
  enabled: true
  challenger_fraction: 0.1
  evaluation_period_tasks: 100
  promotion_threshold: 1.2  # 20% better than incumbent
  min_tasks_for_promotion: 20
```

**Tests:** End-to-end evolution cycle

**Estimated Effort:** Phase 7 = 5-6 hours (tasks 7.2-7.4 can partially parallelize)

---

## Phase 8: ReAct-Style Internal Reasoning (RESEARCH §3.2)

**Goal:** Support internal reason-act-observe loops within agents

### Task 8.1: Design ReAct Support
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §3.2
**Deliverable:** `docs/design/REACT_SUPPORT.md`

**Design Requirements:**
- Agents can perform mini reason-act cycles internally
- Hard cap on internal loops (e.g., 3 cycles)
- Expose only final structured output to pipeline
- Log internal reasoning for debugging

**Sonnet Decides:**
- How to structure internal ReAct loops
- Cap on iterations
- When to use ReAct (implement mode only? always?)
- How to prevent infinite loops

### Task 8.2: Implement ReAct Loop Handler
**Assignee:** Minion 22 (Haiku)
**Files:** `src/agent_engine/runtime/react_handler.py` (new)

**Implementation:**
- `ReActHandler` class
- Manages internal loops: reason → act → observe → adjust
- Enforces iteration limits
- Collects intermediate observations

**Tests:** ReAct loop execution with cap

### Task 8.3: Integrate ReAct into AgentRuntime
**Assignee:** Sonnet (Integration)
**Files:** `src/agent_engine/runtime/agent_runtime.py`

**Changes:**
- Optional ReAct mode for agents
- Pass intermediate tool results back to agent
- Log internal iterations
- Return final structured output only

**Tests:** AgentRuntime with ReAct loops

**Estimated Effort:** Phase 8 = 3-4 hours (linear, requires careful design)

---

## Phase 9: Telemetry, UX/Cost Instrumentation (RESEARCH §9, Appendix A.5-A.6)

**Goal:** Add telemetry scaffolding for UX signals and cost/energy proxies; align with carbon-aware scheduling research.

### Task 9.1: Cost/Latency/Energy Proxies in Telemetry
- Capture model size, token counts, and simple latency/throughput metrics per task/agent call.
- Store per-call cost/energy proxies in telemetry payloads for offline reporting.

### Task 9.2: UX Metrics Instrumentation
- Add fields for override usage, interruption count, retry counts, and acceptance/skip rates (where applicable).
- Wire hooks so frontends/CLIs can submit UX feedback without blocking pipeline.

### Task 9.3: Carbon/Cost Reporting Schema
- Define lightweight schema for carbon/cost reports; document how to aggregate per-session footprints.
- Add toggles for “low-cost/low-carbon” modes that select smaller models or skip parallelism when allowed.

### Task 9.4: Integration with Routing/Compression Signals
- Expose compression ratios, paging decisions, and routing fingerprints to the same telemetry stream for holistic analysis.
- Ensure compatibility with Codex Category F template/telemetry work.

**Estimated Effort:** Phase 9 = 4-6 hours (independent, can run parallel with Codex Category F)

---

## Summary: Sonnet + Minion Task Matrix

| Phase | Tasks | Parallelizable? | Estimated Effort | Dependencies |
|-------|-------|-----------------|------------------|--------------|
| **Phase 1: Multi-Tier Memory** | 6 tasks (1.1-1.6) | Tasks 1.2-1.5 parallel | 6-8 hours | None |
| **Phase 2: Context Profiles** | 6 tasks (2.1-2.6) | Tasks 2.2-2.3 parallel | 5-7 hours | Phase 1 complete |
| **Phase 3: Telemetry Routing** | 5 tasks (3.1-3.5) | Tasks 3.2-3.4 parallel | 5-7 hours | Phase 2 for profiles |
| **Phase 4: Fallback Matrix** | 5 tasks (4.1-4.5) | Tasks 4.2-4.3 parallel | 4-5 hours | None (independent) |
| **Phase 5: Override Parser** | _Tracked in `legacy/king_arthur/INTEGRATION_PLAN.md`_ | See integration plan | — | — |
| **Phase 6: Post-Mortem** | 4 tasks (6.1-6.4) | Linear | 3-4 hours | None (independent) |
| **Phase 7: Evolution** | 5 tasks (7.1-7.5) | Tasks 7.2-7.4 parallel | 5-6 hours | Phase 3 for routing |
| **Phase 8: ReAct Support** | 3 tasks (8.1-8.3) | Linear | 3-4 hours | None (independent) |
| **Phase 9: Telemetry/UX/Cost** | 4 tasks (9.1-9.4) | Tasks 9.1-9.3 parallel | 4-6 hours | None (independent) |

**Total Estimated Effort:** 38-52 hours
**With Maximum Parallelization:** ~22-27 hours (Sonnet + 22 Haiku minions)

---

## Execution Strategy

### Week 1: Core Infrastructure
- **Phase 1** (Multi-Tier Memory) - CRITICAL PATH
- **Phase 4** (Fallback Matrix) - PARALLEL with Phase 1
- **Phase 6** (Post-Mortem) - PARALLEL with Phase 1

### Week 2: Intelligence & Routing
- **Phase 2** (Context Profiles) - depends on Phase 1
- **Phase 3** (Telemetry Routing) - depends on Phase 2

### Week 3: Advanced Features
- **Phase 7** (Evolution) - depends on Phase 3
- **Phase 8** (ReAct Support) - PARALLEL with Phase 7

### Week 4: Telemetry + UX/Cost Instrumentation
- **Phase 9** (Telemetry/UX/Cost) - independent, align with Codex Category F

---

## Integration with PLAN_CODEX.md

**These plans CAN RUN IN PARALLEL:**

**Sonnet + Minions focus on:**
- Architectural complexity
- Research-driven design
- Cross-subsystem integration
- Complex state management

**Codex focuses on (see PLAN_CODEX.md):**
- Systematic code patterns
- Documentation generation
- Test suite expansion
- Well-defined algorithms
- Refactoring existing code

**Coordination Points:**
- Both plans update schemas → coordinate schema changes
- Both touch runtime modules → use feature branches
- Regular sync meetings between Sonnet and Codex outputs

---

## Success Criteria

### Phase 1-2 Complete:
✅ Multi-tier memory working with task/project/global isolation
✅ Context retrieval adapts to agent roles (Implementer vs Strategist)
✅ Tests demonstrate profile-based context assembly

### Phase 3-4 Complete:
✅ Router selects agents based on fitness scores
✅ Fallback matrix handles failures gracefully
✅ Telemetry shows routing decisions and fallback paths

### Phase 6 Complete:
✅ Post-mortems generated for failures
✅ Post-mortem system integrated and logged in telemetry

### Phase 7-8 Complete:
✅ Challenger agents spawn and compete
✅ Evolution cycle promotes successful variants
✅ ReAct loops work for complex reasoning tasks

### ALL PHASES COMPLETE:
✅ Full research-driven feature set implemented
✅ All RESEARCH.md implementation checklists ✅
✅ Production-ready Agent Engine with advanced capabilities

---

**End of PLAN_SONNET_MINION.md**

Next: Create PLAN_CODEX.md for parallel systematic implementation work.
