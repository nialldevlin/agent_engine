## SECTION 1 — Minimal Overview

* **Goal:** Implement a DAG-based workflow engine by (1) introducing explicit graph representation + validator, and (2) upgrading the `PipelineExecutor` to execute DAG workflows with stage roles, decision/merge behavior, and basic failure/telemetry handling.
* **Key components/files:**

  * Schemas:
 
    * `src/agent_engine/schemas/stage.py`
    * `src/agent_engine/schemas/workflow.py`
    * `src/agent_engine/schemas/task.py`, `src/agent_engine/schemas/tool.py`, `src/agent_engine/schemas/errors.py`
  * Runtime:

    * `src/agent_engine/runtime/pipeline_executor.py`
    * `src/agent_engine/runtime/router.py`
    * `src/agent_engine/runtime/task_manager.py`
    * `src/agent_engine/runtime/context.py`
  * Telemetry / errors:

    * `src/agent_engine/telemetry.py` (or equivalent)
    * `src/agent_engine/schemas/errors.py`
* **Constraints:**

  * Don’t break existing basic example (`configs/basic_llm_agent/`).
  * Keep changes incremental: first wire DAG + validator, then upgrade executor, then tests.
  * No concurrency or fancy ToolPlan rollback yet; just lay hooks where needed.
* **Dependencies / risks:**

  * Existing tests may assume linear execution; you’ll need to expand, not replace.
  * Schema changes can cascade; make all new fields optional with explicit sane defaults and add tests to verify backward compatibility (existing manifests must continue to validate).

---

## SECTION 2 — Phased Implementation Plan

### Phase 3.1 — Graph Representation & Stage Roles

**Goal:** Introduce explicit DAG structure and stage roles/types in schemas while keeping backward compat where possible.

**Files to modify:**

* `src/agent_engine/schemas/stage.py`
* `src/agent_engine/schemas/workflow.py`
* `tests/test_schemas_models.py`

**Main changes:**

 * Note: the codebase already defines a `StageType` enum (see `src/agent_engine/schemas/stage.py`) with values such as `AGENT`, `TOOL`, `DECISION`, `MERGE`, `TRANSFORM`.

 * Prefer re-using the existing `StageType` rather than adding a new `StageRole` enum.

 * The existing `Stage` model already includes `entrypoint` and `terminal` boolean flags; do not add a new `role_alias` field. Reuse the existing `StageType` enum for stage classification.
* Define graph-level models in `workflow.py` (if not already present) for:

  * `Edge` (fields: `from_stage_id: str`, `to_stage_id: str`, `condition: Optional[str]`) — use explicit field names and types.
  * `WorkflowGraph` / `Pipeline` structure referencing stages + edges.

**Invariants:**

* Existing `Stage` usage should still work. All added fields must be optional with sane defaults and unit tests must confirm existing example configs still validate.
* Don’t rename or remove existing fields unless you also adjust all references/tests.

**Required tests:**

* Extend `tests/test_schemas_models.py` to cover:

  * Creating stages with roles.
  * Creating a small workflow graph with edges.

**Steps:**

1. **Step 3.1.1 — [QWEN] Add StageRole + role fields** — ✅ Completed

  * File: `src/agent_engine/schemas/stage.py`
   * Change:

     * Add `class StageRole(str, Enum): TRANSFORM = "transform"; DECISION = "decision"; MERGE = "merge"`
     * Add `role: StageRole = Field(default=StageRole.TRANSFORM)` to `Stage`.
     * Keep `entrypoint` and `terminal` fields as-is.
   * Constraints:

    * Don’t modify other classes or logic.
    * Return a unified diff for the modified files only. Apply the diff to the workspace.

2. **Step 3.1.2 — [QWEN] Define Edge/WorkflowGraph schemas** — ✅ Completed

  * File: `src/agent_engine/schemas/workflow.py`
   * Change:

    * The repository already contains `Edge` and `WorkflowGraph` models. Do not rename existing fields. Add the following optional fields to `Edge` (explicitly):

      - `edge_id: Optional[str] = None`
      - `edge_type: Optional[str] = None`

      Ensure `WorkflowGraph.stages` remains a `List[str]` of stage IDs.
   * Constraints:

    * Don’t break existing types/exports; add new models or extend existing ones carefully.
    * Return a unified diff for the modified files only. Apply the diff to the workspace.

3. **Step 3.1.3 — [QWEN] Update schema tests** — ✅ Completed

  * File: `tests/test_schemas_models.py`
   * Change:

     * Add tests that construct stages with explicit `role`.
     * Add tests for creating a simple graph with a couple of stages and edges.
   * Constraints:

     * Don’t delete or drastically change existing tests.
     * Return a unified diff for the modified files only. Apply the diff to the workspace.

4. **Step 3.1.4 — [HUMAN] Run schema tests** — ✅ Completed

   * Command: `pytest tests/test_schemas_models.py`
   * If failures: inspect, adjust field defaults or imports, rerun.

---

### Phase 3.2 — DAG Validator

**Goal:** Add a validator that checks DAG properties (no cycles, all nodes reachable, allowed transitions) using the schema from Phase 3.1.

**Files to modify/create:**

* `src/agent_engine/schemas/workflow.py` (or a new `validator.py` under schemas)
* `tests/test_schemas_models.py` or a new `tests/test_dag_validator.py`

**Main changes:**

* Implement a function or class, e.g. `validate_workflow_graph(graph: WorkflowGraph)`, that:

  * Ensures no cycles.
  * Ensures all stages are reachable from at least one entry stage and can reach at least one terminal stage.
  * Enforces allowed transitions based on `StageRole` / `StageType`.

**Invariants:**

* Validation should be pure (no I/O).
* Raise consistent error types (use your existing `EngineError`/`ValidationError` schema if present).

**Steps:**

1. **Step 3.2.1 — [QWEN] Add DAG validator** — ✅ Completed

  * File: `src/agent_engine/schemas/workflow.py` (or new file)
   * Change:

     * Implement `def validate_workflow_graph(graph: WorkflowGraph) -> None:` with basic cycle + reachability + type-based transition checks.
   * Constraints:

     * No logging or side effects; pure function.
     * Don’t modify unrelated models.

2. **Step 3.2.2 — [QWEN] Add DAG validator tests (explicit requirements)** — ✅ Completed

  * File to create: `tests/test_dag_validator.py`
  * What to implement:

    - Create a test class or module with three test functions:
      1. `test_valid_acyclic_graph_passes`: Create a small acyclic workflow graph (2–3 stages, edges with no cycles). Call `validate_workflow_graph` and assert that no exception is raised.
      2. `test_graph_with_cycle_fails`: Create a workflow graph with a cycle (e.g., A→B→A). Call `validate_workflow_graph` and assert that it raises a validation error (ValueError, EngineError, or similar).
      3. `test_unreachable_node_fails`: Create a graph where at least one stage cannot be reached from any entrypoint, or cannot reach any terminal. Call `validate_workflow_graph` and assert that it raises a validation error.
    - Each test must:
      - Construct the graph using the `WorkflowGraph` and `Edge` models from `src/agent_engine/schemas/workflow.py`.
      - Use minimal, in-memory data (no file I/O).
      - Assert the correct error type and message for failures.
      - Use clear stage IDs and edge definitions so the graph structure is obvious.
    - Do not import unused modules; keep the test file minimal and focused.
    - After implementing, run the test file with:

      ```powershell
      .\.venv\Scripts\python.exe -m pytest tests/test_dag_validator.py -q
      ```

    - If any test fails, inspect the error and fix only the test or validator logic as needed.

3. **Step 3.2.3 — [HUMAN] Run tests** — ✅ Completed

   * Command: `pytest tests/test_dag_validator.py`
   * Fix as needed.

---

### Phase 3.3 — Stage Pipelines & stage_library

**Goal:** Extract explicit pipelines for each stage role/type (agent, tool, decision, merge) into a `stage_library.py`, leaving `PipelineExecutor` to orchestrate, not micromanage internals.

**Files to modify/create:**

* `src/agent_engine/runtime/pipeline_executor.py`
* New: `src/agent_engine/runtime/stage_library.py`
* `src/agent_engine/runtime/router.py`
* Tests: `tests/test_runtime.py`, `tests/test_plugins_and_patterns.py` (as needed)

**Main changes:**

* Create functions like:

  * `run_agent_stage(...)`
  * `run_tool_stage(...)`
  * `run_decision_stage(...)`
  * `run_merge_stage(...)`
* Each function:

  * Accepts `task`, `stage`, context, runtime dependencies.
  * Emits basic telemetry events (or delegates).
  * Calls `TaskManager.save_checkpoint()` after writing results.

**Invariants:**

* Preserve existing public API of `PipelineExecutor` where possible.
* Don’t break current `basic_llm_agent` example.

**Steps:**

1. **Step 3.3.1 — [QWEN] Create stage_library module**

  * File: new `src/agent_engine/runtime/stage_library.py`
   * Change:

     * Define stubs for `run_agent_stage`, `run_tool_stage`, `run_decision_stage`, `run_merge_stage` with clear docstrings and TODOs.
   * Constraints:

     * No heavy implementation yet; just structure and signatures.
     * Imports only what’s needed.

2. **Step 3.3.2 — [QWEN] Refactor PipelineExecutor to call stage_library**

  * File: `src/agent_engine/runtime/pipeline_executor.py`
   * Change:

     * Replace inline stage-specific logic with calls to the new functions based on `StageType`/`StageRole`.
   * Constraints:

     * Keep behavior of existing linear execution as close as possible.
     * Don’t introduce concurrency yet.

3. **Step 3.3.3 — [HUMAN] Run runtime tests**

   * Command: `pytest tests/test_runtime.py`
   * Fix regressions.

---

### Phase 3.4 — Enhanced Pipeline Executor (Checkpoints, Routing, Telemetry v1)

**Goal:** Upgrade the executor to respect DAG edges, call the Router for decisions, and emit basic telemetry around stage start/finish.

**Files to modify:**

* `src/agent_engine/runtime/pipeline_executor.py`
* `src/agent_engine/runtime/router.py`
* `src/agent_engine/runtime/task_manager.py`
* `src/agent_engine/telemetry.py` (or equivalent)

**Main changes:**

* Executor:

  * Walk graph using `WorkflowGraph` + `Edge`s instead of a simple list.
  * At each stage:

    * emit `stage_started`
    * invoke appropriate stage pipeline
    * save checkpoint
    * emit `stage_finished`
  * For decision stages:

    * persist decision artifact
    * the existing `Router.next_stage(...)` performs simple condition matching. For determinism, add a concrete method on `Router` with the signature `resolve_edge(self, task, stage, decision_output, edges) -> str` that implements this policy (see Step 3.4.3).
* Router:

  * Ensure there is a `resolve_edge(...)` stub that takes a decision output and edge conditions (edge schema from Phase 3.1/3.2).

**Steps:**

1. **Step 3.4.1 — [QWEN] Add simple graph-walk loop**

  * File: `src/agent_engine/runtime/pipeline_executor.py`
   * Change:

     * Introduce a small helper to traverse from entry → terminal using `WorkflowGraph` and `Edge`s.
   * Constraints:

    * Maintain backward compatibility: if a `Pipeline` or `WorkflowGraph` contains stage IDs but no edges, fall back to the existing linear traversal behavior implemented today.

2. **Step 3.4.2 — [QWEN] Inject checkpoint + telemetry calls**

  * File: `src/agent_engine/runtime/pipeline_executor.py`
   * Change:

     * Around each stage execution, call `TaskManager.save_checkpoint()` and emit `stage_started`/`stage_finished` via your telemetry bus.
   * Constraints:

     * Don’t alter existing telemetry fields; extend minimally.

3. **Step 3.4.3 — [QWEN] Add `Router.resolve_edge` deterministic API**

   * File: `src/agent_engine/runtime/router.py`
   * Change:

     * Add a method with this exact signature:

       `def resolve_edge(self, task, stage, decision_output: dict, edges: list) -> str:`

       Implementation policy (deterministic):
       - If `decision_output` contains a key `condition`, `route`, or `next`, use its value (first present in that order) as `cond` and return the `to_stage_id` of the first `edge` where `edge.condition == cond` or `edge.to_stage_id == cond`.
       - If no condition matches and `len(edges) == 1`, return `edges[0].to_stage_id`.
       - If multiple edges exist and none match, return `edges[0].to_stage_id` as the deterministic default.

   * Constraints:

     * The method must be deterministic and have no side effects; it must return a `to_stage_id` string or raise a `ValueError` if `edges` is empty.

4. **Step 3.4.4 — [HUMAN] Run integration tests**

   * Command: `pytest tests/test_runtime.py tests/test_basic_llm_agent_example.py`
   * Fix breakages incrementally.

---

### Phase 3.5 — Minimal Tests for DAG Execution

**Goal:** Add focused tests to prove DAG execution and decision routing work.

**Files:**

* New: `tests/test_pipeline_dag_execution.py`

**Steps:**

1. **Step 3.5.1 — [QWEN] Add DAG execution tests**

  * File: `tests/test_pipeline_dag_execution.py`
   * Change:

     * Add a small workflow with transform → decision → branches → merge, using simple stub stages or mocks.
     * Assert that stages run in the expected order and that routing happens correctly.
   * Constraints:

     * Use mocks or lightweight adapters; don’t depend on real LLM calls.

2. **Step 3.5.2 — [HUMAN] Run tests**

   * Command: `pytest tests/test_pipeline_dag_execution.py`
   * Iterate as needed.
