# PLAN_SONNET_MINION: Research-Driven Architectural Enhancements

**Lead:** Sonnet (architecture & integration)
**Workers:** Haiku Minions (focused implementation)
**Focus:** Complex, research-driven features requiring architectural design and careful integration

**Date:** 2025-12-03
**Based on:** RESEARCH.md implementation checklists + current codebase analysis

---

## Overview

This plan implements **research-driven enhancements** from RESEARCH.md that require:
- Architectural decisions and design
- Integration across multiple subsystems
- Careful consideration of research findings
- Complex logic and state management

These tasks are **best suited for Sonnet + Haiku Minions** rather than Codex because they require deep understanding of the research context and architectural implications.

**Can run in PARALLEL with PLAN_CODEX.md**

---

## Current State: Research Implementation Gap Analysis

### ✅ Already Implemented (Good Foundation)
- ContextItem, ContextFingerprint, ContextPackage schemas
- ToolPlan, ToolCapability, ToolRiskLevel
- FailureSignature and EngineError schemas
- KnightManifest with evolution parameters
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
6. Override parser for natural language - RESEARCH §8.1

**TIER 2 - Advanced Features (RESEARCH.md §3, 6-7):**
7. ReAct-style internal reasoning support - RESEARCH §3.2
8. Post-mortem squire for root cause - RESEARCH §7.2
9. Evolution system integration - RESEARCH §6.1
10. Global vs project memory namespaces - RESEARCH §8.2

---

## Phase 1: Multi-Tier Memory Architecture (RESEARCH §1.2)

**Goal:** Implement MemGPT-style memory hierarchy with task/project/global tiers

### Task 1.1: Design Memory Store Architecture
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
- Migration path from current single ContextStore

**Output:** `docs/design/MEMORY_ARCHITECTURE.md`

### Task 1.2: Implement Memory Backend Interface
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

**Tests:** `tests/test_memory_backend.py`

### Task 1.3: Implement TaskMemoryStore
**Assignee:** Minion 2 (Haiku)
**Files:** `src/agent_engine/runtime/memory/task_store.py`

**Features:**
- Ephemeral storage per task (cleared when task completes)
- Fast access for current task context
- Automatic cleanup after task completion

**Tests:** Task memory isolation and cleanup

### Task 1.4: Implement ProjectMemoryStore
**Assignee:** Minion 3 (Haiku)
**Files:** `src/agent_engine/runtime/memory/project_store.py`

**Features:**
- Namespaced by project_id
- Persistent across tasks within same project
- Design decisions, conventions, important failures
- TTL or size-based eviction

**Tests:** Project isolation, persistence across tasks

### Task 1.5: Implement GlobalMemoryStore
**Assignee:** Minion 4 (Haiku)
**Files:** `src/agent_engine/runtime/memory/global_store.py`

**Features:**
- User preferences and styles
- Cross-project patterns
- Careful write permissions (confirmation required)
- Long-term persistence

**Tests:** Global preference persistence, cross-project access

### Task 1.6: Integrate Memory Tiers into ContextAssembler
**Assignee:** Sonnet (Integration)
**Files:** `src/agent_engine/runtime/context.py`

**Changes:**
- Replace single `ContextStore` with multi-tier architecture
- Query all three tiers based on ContextRequest
- Implement paging policies (prefer task > project > global)
- Budget allocation across tiers

**Tests:** End-to-end context assembly from multiple tiers

**Estimated Effort:** Phase 1 = 6-8 hours (can parallelize 1.2-1.5)

---

## Phase 2: Context Retrieval Policies (RESEARCH §2.1, §2.2)

**Goal:** Implement agent-aware, task-aware context retrieval

### Task 2.1: Design Context Profiles System
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §2.1, §2.2
**Deliverable:** `docs/design/CONTEXT_PROFILES.md`

**Design Requirements:**
- ContextProfile per agent role (Knight, Squire, Royalty, Peasant)
- Profiles specify: preferred context types, retrieval biases, budget allocation
- Examples:
  - Knights: code + tests + minimal conversation
  - Royalty: summaries + decisions + preferences, no raw code
  - Squires: specific domain focus (JSON repair, review, etc.)

**Sonnet Decides:**
- Profile schema structure
- How profiles integrate with ContextRequest
- Default profiles for each role
- Override mechanism for custom profiles

### Task 2.2: Implement ContextProfile Schema
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
- Different context packages for Knight vs Royalty vs Squire

**Tests:** Profile-based context retrieval

### Task 2.5: Create Default Profiles
**Assignee:** Minion 7 (Haiku)
**Files:** `configs/context_profiles/` (new directory)

**Create:**
- `knight_default.yaml`
- `squire_default.yaml`
- `royalty_default.yaml`
- `peasant_default.yaml`

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

**Goal:** Parse natural language directives into structured overrides

### Task 5.1: Design Override System
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §8.1
**Deliverable:** `docs/design/OVERRIDE_SYSTEM.md`

**Design Requirements:**
- Parse natural language → OverrideSpec
- Override types: routing, memory, tool, pattern, mode
- Scopes: global, project, pipeline, stage, agent
- Confirmation flows for dangerous overrides

**Examples:**
- "remember this for all projects" → global memory write
- "be more concise" → verbosity override
- "analysis only" → mode override
- "use knight X for file edits" → routing override

**Sonnet Decides:**
- Override parser approach (LLM squire vs patterns)
- Confirmation thresholds
- Override persistence and expiration
- Conflict resolution between overrides

### Task 5.2: Implement Override Parser Squire
**Assignee:** Minion 14 (Haiku)
**Files:** `src/agent_engine/runtime/override_parser.py` (new)

**Implementation:**
- `OverrideParser` class
- Use small LLM (or pattern matching for MVP)
- Parse text → OverrideSpec with kind, scope, target, payload
- Return confidence score

**Input:** Natural language directive
**Output:** OverrideSpec or None

**Tests:** Parse common override patterns

### Task 5.3: Implement Override Manager
**Assignee:** Minion 15 (Haiku)
**Files:** `src/agent_engine/runtime/override_manager.py` (new)

**Implementation:**
- Store active overrides (in-memory + optional persistence)
- Apply overrides to task/pipeline/stage execution
- Expiration and cleanup
- Conflict resolution (more specific wins)

**API:**
```python
class OverrideManager:
    def add_override(self, spec: OverrideSpec) -> bool
    def get_overrides(self, scope: str, target: str) -> List[OverrideSpec]
    def clear_overrides(self, scope: str) -> None
```

**Tests:** Override storage, retrieval, conflict resolution

### Task 5.4: Integrate Overrides into Pipeline
**Assignee:** Sonnet (Integration)
**Files:**
- `src/agent_engine/runtime/pipeline_executor.py`
- `src/agent_engine/runtime/router.py`

**Changes:**
- Check for overrides before routing
- Apply mode/tool/agent overrides
- Log override usage to telemetry

**Tests:** End-to-end override application

### Task 5.5: Add Confirmation Flows
**Assignee:** Minion 16 (Haiku)
**Files:** `src/agent_engine/runtime/override_parser.py`

**Add:**
- Risk scoring for overrides
- Confirmation prompts for high-risk overrides
- User feedback integration

**High-risk triggers:**
- Global scope modifications
- Security policy changes
- Agent retirement

**Estimated Effort:** Phase 5 = 4-6 hours (tasks 5.2-5.3 can parallelize)

---

## Phase 6: Post-Mortem Squire (RESEARCH §7.2)

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

### Task 6.2: Implement Post-Mortem Squire
**Assignee:** Minion 17 (Haiku)
**Files:** `src/agent_engine/runtime/post_mortem.py` (new)

**Implementation:**
- `PostMortemSquire` class
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

**Goal:** Wire evolution into routing and enable knight challengers

### Task 7.1: Design Evolution System
**Assignee:** Sonnet (Design)
**References:** RESEARCH.md §6.1
**Deliverable:** `docs/design/EVOLUTION_SYSTEM.md`

**Design Requirements:**
- Spawn challenger knights with mutated manifests
- Route fraction of tasks to challengers
- Score challengers vs incumbents
- Promote or retire based on performance

**Sonnet Decides:**
- Mutation strategy for KnightManifest parameters
- Challenger spawn frequency
- Evaluation period and criteria
- Promotion/retirement thresholds

### Task 7.2: Implement Knight Challenger System
**Assignee:** Minion 19 (Haiku)
**Files:** `src/agent_engine/evolution.py`

**Enhance:**
- `spawn_challenger(base_knight: AgentDefinition) -> AgentDefinition`
- Mutate manifest parameters (reasoning_steps, tool_bias, verbosity, tests_emphasis)
- Track lineage (parent knight ID)

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
- Retire underperforming knights (with safeguards)
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
- Optional ReAct mode for knights
- Pass intermediate tool results back to agent
- Log internal iterations
- Return final structured output only

**Tests:** AgentRuntime with ReAct loops

**Estimated Effort:** Phase 8 = 3-4 hours (linear, requires careful design)

---

## Summary: Sonnet + Minion Task Matrix

| Phase | Tasks | Parallelizable? | Estimated Effort | Dependencies |
|-------|-------|-----------------|------------------|--------------|
| **Phase 1: Multi-Tier Memory** | 6 tasks (1.1-1.6) | Tasks 1.2-1.5 parallel | 6-8 hours | None |
| **Phase 2: Context Profiles** | 5 tasks (2.1-2.5) | Tasks 2.2-2.3 parallel | 4-6 hours | Phase 1 complete |
| **Phase 3: Telemetry Routing** | 5 tasks (3.1-3.5) | Tasks 3.2-3.4 parallel | 5-7 hours | Phase 2 for profiles |
| **Phase 4: Fallback Matrix** | 5 tasks (4.1-4.5) | Tasks 4.2-4.3 parallel | 4-5 hours | None (independent) |
| **Phase 5: Override Parser** | 5 tasks (5.1-5.5) | Tasks 5.2-5.3 parallel | 4-6 hours | Phase 1 for memory writes |
| **Phase 6: Post-Mortem** | 4 tasks (6.1-6.4) | Linear | 3-4 hours | None (independent) |
| **Phase 7: Evolution** | 5 tasks (7.1-7.5) | Tasks 7.2-7.4 parallel | 5-6 hours | Phase 3 for routing |
| **Phase 8: ReAct Support** | 3 tasks (8.1-8.3) | Linear | 3-4 hours | None (independent) |

**Total Estimated Effort:** 34-46 hours
**With Maximum Parallelization:** ~20-25 hours (Sonnet + 22 Haiku minions)

---

## Execution Strategy

### Week 1: Core Infrastructure
- **Phase 1** (Multi-Tier Memory) - CRITICAL PATH
- **Phase 4** (Fallback Matrix) - PARALLEL with Phase 1
- **Phase 6** (Post-Mortem) - PARALLEL with Phase 1

### Week 2: Intelligence & Routing
- **Phase 2** (Context Profiles) - depends on Phase 1
- **Phase 3** (Telemetry Routing) - depends on Phase 2
- **Phase 5** (Override Parser) - depends on Phase 1

### Week 3: Advanced Features
- **Phase 7** (Evolution) - depends on Phase 3
- **Phase 8** (ReAct Support) - PARALLEL with Phase 7

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
✅ Context retrieval adapts to agent roles (Knight vs Royalty)
✅ Tests demonstrate profile-based context assembly

### Phase 3-4 Complete:
✅ Router selects agents based on fitness scores
✅ Fallback matrix handles failures gracefully
✅ Telemetry shows routing decisions and fallback paths

### Phase 5-6 Complete:
✅ Natural language overrides parsed and applied
✅ Post-mortems generated for failures
✅ Override and post-mortem systems integrated

### Phase 7-8 Complete:
✅ Challenger knights spawn and compete
✅ Evolution cycle promotes successful variants
✅ ReAct loops work for complex reasoning tasks

### ALL PHASES COMPLETE:
✅ Full research-driven feature set implemented
✅ All RESEARCH.md implementation checklists ✅
✅ Production-ready Agent Engine with advanced capabilities

---

**End of PLAN_SONNET_MINION.md**

Next: Create PLAN_CODEX.md for parallel systematic implementation work.
