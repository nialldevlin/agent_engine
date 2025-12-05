
## SECTION 1 — OVERVIEW & SUMMARY (FOR HUMAN USER)

**Goal (Phase 3 — Workflow Graph & Pipeline Executor)**
Design and implement a robust workflow graph model and execution engine so that tasks can run through arbitrarily complex pipelines (agents, tools, decision/merge stages, error/fallback flows) with clear invariants, validation, and traceable execution.

**Current state (from repo + tests)**

* Graph & schema:

  * `WorkflowGraph`, `Stage`, `Edge`, `Pipeline`, `StageType`, `TaskMode`, `TaskSpec`, `TaskStatus` already exist in `src/agent_engine/schemas/...`.
  * Stages support at least AGENT and TOOL types, with `entrypoint` / `terminal` flags.
* Runtime:

  * `Router` in `src/agent_engine/runtime/router.py` can route between stages using a simple graph.
  * `PipelineExecutor` in `src/agent_engine/runtime/pipeline_executor.py` runs stages in order and returns a final `Task` with `stage_results` and `routing_trace`.
  * `AgentRuntime` and a tool runtime interface already exist.
* Tests:

  * `tests/test_runtime.py` contains `test_pipeline_executor_runs_through_stages`, which asserts a simple two-stage workflow (AGENT → TOOL) completes and the TOOL stage output matches expectations using `ToolRuntimeStub`.

**Assumptions, constraints, success criteria**

* You want the workflow model to remain **DAG-based** (no implicit cycles) but eventually support:

  * Decision stages
  * Merge stages
  * Transform / feedback / policy nodes
  * Error / fallback edges
* Backwards compatibility:

  * Existing `tests/test_runtime.py` must keep passing without modification.
  * Existing public schema fields should not break unless strictly necessary.
* Implementation must be:

  * Friendly to smaller coding models (Qwen2.5-Coder-7B): small steps, precise instructions, minimal cross-file edits per call.
  * Easy to validate via targeted tests (`pytest tests/test_runtime.py` and new, focused tests).

**Risks, unknowns, prerequisites**

* Potential schema drift between:

  * `WorkflowGraph` / `Pipeline` in schemas
  * How `Router` and `PipelineExecutor` actually interpret them.
* Adding more `StageType` values and new edge semantics can subtly break routing if invariants aren’t clearly defined and validated.
* You’ll want at least a minimal spec for:

  * Decision stages: what output structure / convention determines which outgoing edge to follow.
  * Merge stages: how multiple inputs are correlated and combined.
* Prerequisites:

  * Phase 1/2 config and schema basics are already in place.
  * Basic test infra is working (pytest configured and passing current tests).

Success here means:

* Graph definitions and validators can guarantee sane workflows.
* PipelineExecutor can:

  * Run a multi-stage pipeline with different stage types.
  * Handle errors via error/fallback edges when available.
  * Produce a clear, inspectable routing trace and per-stage results.
* New tests cover:

  * Validation failures for bad graphs.
  * Execution behavior for branching and error paths (at least minimal versions).

---

## SECTION 2 — PHASED IMPLEMENTATION PLAN WITH STEPS (FOR HUMAN USER)

We’ll treat this as **Phase 3** with sub-phases **3.A–3.D**.

### Phase 3.A — Graph & Stage Role Refinement

**Goal**
Extend the workflow graph model to support richer stage roles and edge semantics without breaking existing usages.

**Files to modify / create**

* Modify:

  * `@/src/agent_engine/schemas/workflow.py`
  * `@/src/agent_engine/schemas/stage.py`
* Possibly touch (schema imports/usage only):

  * `@/src/agent_engine/runtime/router.py`
  * `@/src/agent_engine/runtime/pipeline_executor.py`
  * `@/tests/test_runtime.py` (only if new required fields need default behavior, but try to avoid changes)

**Key changes**

* Extend `StageType` in `stage.py` to include:

  * `AGENT`, `TOOL` (existing)
  * `DECISION`, `MERGE`, `TRANSFORM`, `FEEDBACK` (new)
* Add optional **role** metadata to `Stage` (staying backward compatible):

  * e.g., boolean or Enum flags for `is_entry`, `is_terminal`, `is_error_handler`, `is_fallback`.
  * Keep existing `entrypoint` and `terminal` fields, but clarify in docstring how they relate to new roles.
* Add `EdgeType` to `workflow.py`:

  * `NORMAL`, `ERROR`, `FALLBACK`, `POLICY`.
  * Extend `Edge` to include `edge_type: EdgeType = EdgeType.NORMAL` (default normal).
* Document invariants in docstrings / comments:

  * `Edge.edge_type` defaults to NORMAL; existing tests must still pass with no changes.
  * Pipelines may use only NORMAL edges to stay “simple” if advanced features are unused.

**Invariants & constraints**

* All new fields must have **sensible defaults** so existing workflows/tests remain valid.
* `StageType` extension must not force existing stages to change type.
* `EdgeType` default is NORMAL, and any absent `edge_type` in serialized configs should deserialize as NORMAL.

**Edge cases**

* Pipelines that:

  * Use only AGENT/TOOL stages should behave exactly as before.
  * Have stages that are both `entrypoint=True` and `terminal=True` (degenerate single-stage pipeline) must still be allowed.
* Configs that don’t yet include new fields must still validate and operate.

**Phase 3.A Steps**

1. **Step 3.A.1 — [QWEN] Extend StageType and Stage roles**

   * Modify `@/src/agent_engine/schemas/stage.py` to:

     * Add new `StageType` values.
     * Add optional role metadata on `Stage` with defaults.

2. **Step 3.A.2 — [QWEN] Introduce EdgeType and extend Edge**

   * Modify `@/src/agent_engine/schemas/workflow.py` to:

     * Add `EdgeType` Enum.
     * Add `edge_type` field to `Edge` with default `EdgeType.NORMAL`.
     * Update docstrings and type hints.

3. **Step 3.A.3 — [HUMAN] Run tests and inspect for regressions**

   * Run `pytest tests/test_runtime.py`.
   * If failures occur, inspect error messages and adjust new defaults rather than changing test behavior, unless absolutely necessary.

---

### Phase 3.B — DAG Validator & Graph Integrity

**Goal**
Create a reusable validator that enforces DAG structure and basic integrity rules for workflows and pipelines.

**Files to modify / create**

* Create:

  * `@/src/agent_engine/runtime/graph_validator.py`
* Modify:

  * `@/src/agent_engine/runtime/router.py` (to optionally call the validator or accept validated graphs)
  * Potentially `@/src/agent_engine/config_loader.py` (if this is the natural place to validate graphs when loading configs)
* Tests:

  * `@/tests/test_graph_validator.py` (new)

**Key changes**

* Implement a `GraphValidator` (or free functions) with capabilities:

  1. **Cycle detection**

     * Given `WorkflowGraph` (`stages`, `edges`), detect cycles using DFS or Kahn’s algorithm.
     * Reject non-DAG graphs with a clear error.

  2. **Reachability & terminal coverage**

     * Ensure all `start_stage_ids` in a pipeline are valid and reachable.
     * Ensure all `end_stage_ids` are valid and reachable from at least one start.
     * Optionally ensure there is at least one terminal per pipeline.

  3. **Edge consistency**

     * Every `Edge.from_stage_id` and `Edge.to_stage_id` must reference existing stages.
     * If using `EdgeType.ERROR` or `EdgeType.FALLBACK`, ensure target stages exist.

* Provide a simple API, e.g.:

  ```python
  validate_workflow_graph(workflow: WorkflowGraph, pipelines: dict[str, Pipeline]) -> None
  ```

  or a `GraphValidator` class with a `validate(...)` method.

**Invariants & constraints**

* Validator must be **pure** (no side effects): raise exceptions or return a result object; don’t mutate graphs.
* It should be cheap enough to run on config load rather than per-task execution.
* Existing simple workflows (like `test_runtime`) must pass validation without requiring config changes.

**Edge cases**

* Workflow with isolated stages that are not referenced by any pipeline.
* Pipelines that reference stages not in `workflow.stages`.
* Pipelines with no explicit `end_stage_ids` (if allowed) — decide and document behavior.

**Phase 3.B Steps**

4. **Step 3.B.1 — [QWEN] Implement graph validator module**

   * Create `@/src/agent_engine/runtime/graph_validator.py` with:

     * Cycle detection.
     * Reachability checks.
     * Edge reference validation.
     * Clear exception types/messages.

5. **Step 3.B.2 — [QWEN] Integrate validation into config load / router creation**

   * Update either `@/src/agent_engine/config_loader.py` or `@/src/agent_engine/runtime/router.py` to:

     * Call `validate_workflow_graph(...)` when constructing router/pipeline structures.
     * Decide whether to validate once at load time or allow explicit “validate” API.

6. **Step 3.B.3 — [QWEN] Add focused tests for validator**

   * Create `@/tests/test_graph_validator.py` to cover:

     * Valid simple workflow (current runtime test topology).
     * Graph with cycle (expect failure).
     * Pipeline referencing missing stage (expect failure).
     * Pipeline with unreachable terminal (expect failure).

7. **Step 3.B.4 — [HUMAN] Run targeted tests**

   * Run:

     * `pytest tests/test_graph_validator.py`
     * `pytest tests/test_runtime.py`
   * If tests fail:

     * Adjust only the validator or its integration, not the business logic of the executor unless you explicitly decide to change semantics.

---

### Phase 3.C — Enhanced PipelineExecutor Behavior

**Goal**
Upgrade `PipelineExecutor` to handle richer stage types and edge behaviors while keeping simple pipelines unchanged.

**Files to modify / create**

* Modify:

  * `@/src/agent_engine/runtime/pipeline_executor.py`
  * `@/src/agent_engine/runtime/router.py` (if needed to support new edge types / next-stage logic)
* Possibly touch:

  * `@/src/agent_engine/runtime/agent_runtime.py`
  * Tool runtime implementation file (wherever the non-stub ToolRuntime lives)
* Tests:

  * `@/tests/test_runtime.py` (extend)
  * `@/tests/test_pipeline_executor_extended.py` (new)

**Key changes**

* Define execution semantics:

  * **Mode handling** (`TaskMode.ANALYSIS_ONLY`, EXECUTE, etc.):

    * Define how each mode affects:

      * Agent stages (can they call tools, write outputs, etc.).
      * Tool stages (are side effects allowed).
    * For now, at least ensure ANALYSIS_ONLY is supported and does not break existing behavior.

  * **StageType behavior (high-level)**:

    * `AGENT`: call into `AgentRuntime` with context/inputs; produce output for next stage.
    * `TOOL`: call ToolRuntime; produce tool output.
    * `DECISION`: returns some routing decision (e.g., a label or key) which router uses to select the next edge.
    * `MERGE`: combine multiple inbound results; must define how to track inbound branches (initially, you can support only single inbound for MVP and document that).
    * `TRANSFORM` / `FEEDBACK`: treat as pure functions over context/results for now.

  * **Error handling and fallback**:

    * When a stage raises or fails:

      * If there is an `EdgeType.ERROR` from that stage, follow it.
      * Else, if pipeline has `fallback_end_stage_ids`, end in a controlled “fallback complete” state.
      * Else, mark task as FAILED.

* Enhance `routing_trace` and `stage_results`:

  * Ensure each executed stage is recorded with:

    * Stage ID, type, status (SUCCESS / ERROR / SKIPPED).
    * Possibly brief metadata (e.g., which edge was taken).

**Invariants & constraints**

* If a workflow uses only AGENT/TOOL stages and NORMAL edges:

  * Execution behavior must be identical to current behavior.
* Executor must **not** modify the workflow graph; it only reads it and mutates the task state/results.
* `TaskStatus` semantics must stay consistent (COMPLETED/FAILED/etc.).

**Edge cases**

* Decision stage that produces an unknown branch key; router must handle “no matching edge” gracefully (fail or fallback).
* Workflows with multiple possible terminals; ensure routing_trace clearly shows which branch was taken.
* Errors thrown by either AgentRuntime or ToolRuntime.

**Phase 3.C Steps**

8. **Step 3.C.1 — [QWEN] Refine PipelineExecutor control flow**

   * Update `@/src/agent_engine/runtime/pipeline_executor.py` to:

     * Use a clear per-stage execution loop.
     * Handle TaskMode, StageType, and error/fallback routing at a high level.
     * Preserve existing behavior for the simple two-stage case.

9. **Step 3.C.2 — [QWEN] Extend runtime tests for executor**

   * Add or modify tests:

     * Extend `@/tests/test_runtime.py` or create `@/tests/test_pipeline_executor_extended.py` to:

       * Cover at least one DECISION → TOOL flow.
       * Cover error handling path using `EdgeType.ERROR` or pipeline `fallback_end_stage_ids`.

10. **Step 3.C.3 — [HUMAN] Validate executor behavior**

    * Run:

      * `pytest tests/test_runtime.py`
      * `pytest tests/test_pipeline_executor_extended.py`
    * Inspect routing traces:

      * Confirm stage order makes sense.
      * Confirm error/fallback paths act as expected.

---

### Phase 3.D — Stage Execution Library / Registry

**Goal**
Extract per-stage-type execution logic into a dedicated library so it’s easy to extend and test stage behaviors in isolation.

**Files to modify / create**

* Create:

  * `@/src/agent_engine/runtime/stage_library.py`
* Modify:

  * `@/src/agent_engine/runtime/pipeline_executor.py` (to delegate to stage library)
* Tests:

  * `@/tests/test_stage_library.py` (new)

**Key changes**

* Implement a small stage execution registry, e.g.:

  * A mapping `StageType → Callable`:

    * Signature could be something like:

      ```python
      def run_stage(
          task: Task,
          stage: Stage,
          context_package: ContextPackage,
          agent_runtime: AgentRuntime,
          tool_runtime: ToolRuntime,
      ) -> StageResult
      ```

  * Provide concrete functions:

    * `run_agent_stage(...)`
    * `run_tool_stage(...)`
    * `run_decision_stage(...)` (MVP: just return decision metadata; exact format can be simple)
    * `run_transform_stage(...)` (MVP: passthrough or simple transform hook)
    * etc.

* PipelineExecutor then:

  * Uses the registry to execute stages based on `stage.type`.
  * Simplifies its internal branching logic.

**Invariants & constraints**

* Stage library must be **stateless** and **deterministic** given inputs; all side effects go through `AgentRuntime` / `ToolRuntime`.
* Adding new StageTypes should only require:

  * Implementing a new function.
  * Registering it in one place.

**Edge cases**

* Unknown `StageType`: Stage library should raise a clear exception, caught by executor as an error case.
* Stage execution failures must propagate through the existing error/fallback mechanism.

**Phase 3.D Steps**

11. **Step 3.D.1 — [QWEN] Implement stage_library module**

    * Create `@/src/agent_engine/runtime/stage_library.py` with:

      * Execution functions per StageType (MVP versions).
      * Registry and a single `execute_stage(...)` entry point.

12. **Step 3.D.2 — [QWEN] Wire PipelineExecutor to stage_library**

    * Update `@/src/agent_engine/runtime/pipeline_executor.py` to:

      * Call `stage_library.execute_stage(...)` instead of hard-coding per-type logic.

13. **Step 3.D.3 — [QWEN] Add tests for stage_library**

    * Create `@/tests/test_stage_library.py`:

      * Use minimal fake/stub `Task`, `Stage`, `AgentRuntime`, and `ToolRuntime`.
      * Assert correct behavior for AGENT and TOOL stages at least.

14. **Step 3.D.4 — [HUMAN] Final validation for Phase 3**

    * Run full test suite or at least:

      * `pytest tests/test_graph_validator.py`
      * `pytest tests/test_runtime.py`
      * `pytest tests/test_pipeline_executor_extended.py`
      * `pytest tests/test_stage_library.py`
    * If failures appear, iterate:

      * Fix tests if the semantics have intentionally changed.
      * Otherwise, fix the implementation to align with intended semantics.

---

## SECTION 3 — QWEN IMPLEMENTATION PROMPTS (FOR CLINE ACT MODE)

Below: one prompt per [QWEN] step, ready to paste into Cline Act mode for Qwen2.5-Coder-7B.

---

### Qwen Prompt 1 (Phase 3.A, Step 3.A.1 — Extend StageType and Stage roles)

```text
You are assisting with Phase 3.A, Step 3.A.1 of the Agent Engine implementation plan.

Goal:
Extend the stage schema to support richer stage roles and new StageType values without breaking existing behavior.

Context:
- The project root is the repository containing @/src and @/tests.
- Stage schemas live in @/src/agent_engine/schemas/stage.py.
- Existing code uses StageType for AGENT and TOOL, and Stage has entrypoint/terminal fields.

Task:
1. In @/src/agent_engine/schemas/stage.py:
   - Extend StageType to include at least the following values in addition to existing ones:
     - DECISION, MERGE, TRANSFORM, FEEDBACK.
   - Add optional role metadata to the Stage model (either additional boolean flags or an Enum) to represent:
     - is_entry, is_terminal, is_error_handler, is_fallback (or similar names).
   - Ensure:
     - All new fields have sensible default values so existing code and tests do NOT break.
     - Existing entrypoint and terminal fields remain usable and are documented to show how they relate to the new role metadata.

2. Update type hints and docstrings to clearly describe:
   - The purpose of each StageType.
   - How role metadata is intended to be used (high-level only, no extra logic here).

Constraints:
- Do NOT modify any other files.
- Do NOT change existing public field names or semantics unless necessary for compatibility.
- Preserve all existing imports and usages as much as possible.

Output format:
- Return a unified diff (git-style) for @/src/agent_engine/schemas/stage.py only.
```

### Qwen Prompt 2 (Phase 3.A, Step 3.A.2 — Introduce EdgeType and extend Edge)

```text
You are assisting with Phase 3.A, Step 3.A.2 of the Agent Engine implementation plan.

Goal:
Extend the workflow edge schema to support edge types (normal, error, fallback, policy) while preserving existing behavior.

Context:
- Workflow schemas live in @/src/agent_engine/schemas/workflow.py.
- There is an Edge model and a WorkflowGraph model that reference stages by ID.
- Existing code assumes edges are "normal" without explicit types.

Task:
1. In @/src/agent_engine/schemas/workflow.py:
   - Introduce an EdgeType Enum with at least:
     - NORMAL, ERROR, FALLBACK, POLICY.
   - Extend the Edge model to include:
     - edge_type: EdgeType with a DEFAULT of EdgeType.NORMAL.
   - Update docstrings and type hints for Edge and WorkflowGraph to explain:
     - The meaning of each EdgeType.
     - That edge_type is optional in configs and defaults to NORMAL.

2. Ensure that:
   - Existing code that constructs Edge without edge_type still works and sees EdgeType.NORMAL.
   - No other modules break due to missing imports (add imports where needed).

Constraints:
- Do NOT modify any logic outside @/src/agent_engine/schemas/workflow.py.
- Preserve existing fields and behavior of WorkflowGraph and Edge as much as possible.

Output format:
- Return a unified diff (git-style) for @/src/agent_engine/schemas/workflow.py only.
```

### Qwen Prompt 3 (Phase 3.A, Step 3.A.3 — Run tests is HUMAN-only)

No Qwen prompt; this is a HUMAN step.

---

### Qwen Prompt 4 (Phase 3.B, Step 3.B.1 — Implement graph validator module)

```text
You are assisting with Phase 3.B, Step 3.B.1 of the Agent Engine implementation plan.

Goal:
Create a graph validator module that checks workflow and pipeline integrity (DAG structure, reachability, and edge consistency).

Context:
- Workflow and pipeline schemas live in:
  - @/src/agent_engine/schemas/workflow.py
  - @/src/agent_engine/schemas/stage.py
- Router and runtime live in:
  - @/src/agent_engine/runtime/router.py
  - @/src/agent_engine/runtime/pipeline_executor.py

Task:
1. Create a new module @/src/agent_engine/runtime/graph_validator.py.
2. In that module, implement a small API such as:
   - A function validate_workflow_graph(workflow: WorkflowGraph, pipelines: dict[str, Pipeline]) -> None
     OR
   - A GraphValidator class with a validate(...) method.
3. The validator must:
   - Detect cycles in the workflow graph (use DFS or Kahn’s algorithm).
   - Verify that all Edge.from_stage_id and Edge.to_stage_id reference existing stages.
   - For each Pipeline:
     - Ensure all start_stage_ids and end_stage_ids reference valid stages.
     - Ensure each end_stage_id is reachable from at least one start_stage_id.
4. On validation failure, raise a clear, specific exception type (you may define a custom exception in this module).

Constraints:
- Do NOT modify existing schemas in this step.
- Keep the validator pure (it must not mutate the workflow or pipelines).
- Do NOT wire the validator into router or config loading yet; just implement the module.

Output format:
- Return a unified diff (git-style) for the new file @/src/agent_engine/runtime/graph_validator.py.
```

### Qwen Prompt 5 (Phase 3.B, Step 3.B.2 — Integrate validation into config load / router)

```text
You are assisting with Phase 3.B, Step 3.B.2 of the Agent Engine implementation plan.

Goal:
Integrate the graph validator so workflows and pipelines are validated once when they are constructed or loaded.

Context:
- Graph validator API exists in @/src/agent_engine/runtime/graph_validator.py.
- Workflow and pipeline schemas live in @/src/agent_engine/schemas/workflow.py.
- Router and/or config loader create WorkflowGraph and Pipeline sets in:
  - @/src/agent_engine/runtime/router.py
  - @/src/agent_engine/config_loader.py (if present).

Task:
1. Identify the central place where WorkflowGraph and Pipelines are created or loaded:
   - Prefer @/src/agent_engine/config_loader.py if it exists.
   - Otherwise, use @/src/agent_engine/runtime/router.py where Router is instantiated.
2. Call the validator (e.g., validate_workflow_graph(...)) immediately after the workflow and pipeline data structures are constructed.
3. Ensure that:
   - Invalid graphs cause a clear failure early (on load/initialization), not at runtime.
   - Existing simple workflows still pass validation without requiring config changes.

Constraints:
- Limit changes to:
  - @/src/agent_engine/runtime/graph_validator.py (if minor tweaks needed)
  - @/src/agent_engine/runtime/router.py
  - @/src/agent_engine/config_loader.py (if present)
- Do NOT change tests in this step.
- Keep the integration minimal and clearly documented in docstrings or comments.

Output format:
- Return a unified diff (git-style) for any modified files:
  - @/src/agent_engine/runtime/graph_validator.py (if changed)
  - @/src/agent_engine/runtime/router.py
  - @/src/agent_engine/config_loader.py (if changed)
```

### Qwen Prompt 6 (Phase 3.B, Step 3.B.3 — Add tests for validator)

```text
You are assisting with Phase 3.B, Step 3.B.3 of the Agent Engine implementation plan.

Goal:
Add focused tests for the graph validator to cover valid and invalid workflow/pipeline configurations.

Context:
- Graph validator implemented in @/src/agent_engine/runtime/graph_validator.py.
- Workflow and pipeline schemas in @/src/agent_engine/schemas/workflow.py and @/src/agent_engine/schemas/stage.py.
- Runtime tests already exist in @/tests/test_runtime.py.

Task:
1. Create a new test file @/tests/test_graph_validator.py.
2. In this file, add tests that:
   - Construct a minimal, valid WorkflowGraph and Pipelines setup similar to the one in tests/test_runtime.py and assert that validate_workflow_graph(...) passes.
   - Construct a graph with a cycle and assert that validation raises the expected exception.
   - Construct a pipeline that references a missing stage and assert validation failure.
   - Construct a pipeline where an end_stage_id is unreachable from the start_stage_ids and assert validation failure.

Constraints:
- Use simple, in-memory WorkflowGraph and Pipeline instances (no config files).
- Do NOT modify existing tests in tests/test_runtime.py in this step.
- Keep tests concise and focused on validator behavior.

Output format:
- Return a unified diff (git-style) for @/tests/test_graph_validator.py only.
```

### Qwen Prompt 7 (Phase 3.B, Step 3.B.4 — HUMAN-only)

No Qwen prompt; this is a HUMAN step.

---

### Qwen Prompt 8 (Phase 3.C, Step 3.C.1 — Refine PipelineExecutor control flow)

```text
You are assisting with Phase 3.C, Step 3.C.1 of the Agent Engine implementation plan.

Goal:
Refine PipelineExecutor’s control flow to handle StageType, TaskMode, and error/fallback routing while preserving existing simple behavior.

Context:
- PipelineExecutor lives in @/src/agent_engine/runtime/pipeline_executor.py.
- Router lives in @/src/agent_engine/runtime/router.py and knows the workflow graph.
- StageType and EdgeType have been extended in:
  - @/src/agent_engine/schemas/stage.py
  - @/src/agent_engine/schemas/workflow.py
- test_pipeline_executor_runs_through_stages exists in @/tests/test_runtime.py and must keep passing.

Task:
1. In @/src/agent_engine/runtime/pipeline_executor.py:
   - Make the main execution loop explicitly:
     - Fetch current stage.
     - Execute stage based on its StageType and TaskMode.
     - Record stage result and routing decision.
     - Ask Router for the next stage, taking into account any error/fallback edges.
   - Ensure:
     - If only AGENT and TOOL stages with NORMAL edges are used, behavior matches current tests.
     - Errors in stage execution can be routed via error/fallback edges if present; otherwise, mark the task as FAILED.

2. Add or improve comments/docstrings explaining:
   - How TaskMode influences execution (at least ANALYSIS_ONLY vs default).
   - How error/fallback routing is expected to work at a high level.

Constraints:
- Do NOT modify tests in this step.
- Do NOT add new StageType behaviors here; you only need to make the control flow ready for later integration with the stage library.
- Keep changes localized to PipelineExecutor (and Router only if necessary for edge-type awareness).

Output format:
- Return a unified diff (git-style) for @/src/agent_engine/runtime/pipeline_executor.py (and @/src/agent_engine/runtime/router.py if modified).
```

### Qwen Prompt 9 (Phase 3.C, Step 3.C.2 — Extend runtime tests for executor)

```text
You are assisting with Phase 3.C, Step 3.C.2 of the Agent Engine implementation plan.

Goal:
Add tests that exercise the enhanced PipelineExecutor behavior, including basic branching and error handling.

Context:
- PipelineExecutor is in @/src/agent_engine/runtime/pipeline_executor.py.
- Existing runtime tests are in @/tests/test_runtime.py.
- StageType and EdgeType now support additional values, and the graph validator ensures integrity.

Task:
1. Either:
   - Extend @/tests/test_runtime.py with additional tests, OR
   - Create a new file @/tests/test_pipeline_executor_extended.py.
2. Add tests that:
   - Define a WorkflowGraph and Pipelines with at least one DECISION stage that routes to different TOOL stages based on some simple condition.
   - Verify that:
     - The correct branch is taken.
     - routing_trace and stage_results reflect the chosen path.
   - Define a case where a stage raises an error or returns a failure, with an ERROR-type edge to a fallback stage, and verify:
     - The executor follows the ERROR edge.
     - The final task status is COMPLETED or a domain-specific “completed with fallback,” per the existing TaskStatus semantics.

Constraints:
- Use simple stub AgentRuntime and ToolRuntime implementations within the tests.
- Do NOT break or rewrite existing tests unnecessarily; add new tests focused on the new behaviors.
- If you create a new test file, ensure pytest discovers it.

Output format:
- Return a unified diff (git-style) for the modified/created test files:
  - @/tests/test_runtime.py and/or @/tests/test_pipeline_executor_extended.py.
```

### Qwen Prompt 10 (Phase 3.C, Step 3.C.3 — HUMAN-only)

No Qwen prompt; this is a HUMAN step.

---

### Qwen Prompt 11 (Phase 3.D, Step 3.D.1 — Implement stage_library module)

```text
You are assisting with Phase 3.D, Step 3.D.1 of the Agent Engine implementation plan.

Goal:
Create a stage execution library that maps StageType to execution functions, so PipelineExecutor can delegate per-stage behavior.

Context:
- StageType and Stage schemas live in:
  - @/src/agent_engine/schemas/stage.py
- PipelineExecutor currently executes stages directly in:
  - @/src/agent_engine/runtime/pipeline_executor.py
- AgentRuntime and ToolRuntime are already defined in the runtime package.

Task:
1. Create a new module @/src/agent_engine/runtime/stage_library.py.
2. In this module:
   - Define a function execute_stage(task, stage, context_package, agent_runtime, tool_runtime) -> StageResult (or equivalent result structure used by PipelineExecutor).
   - Inside execute_stage, dispatch to specific functions based on stage.type:
     - run_agent_stage(...)
     - run_tool_stage(...)
     - (Optionally stub) run_decision_stage(...), run_transform_stage(...), etc.
   - For now, keep DECISION/MERGE/TRANSFORM behavior minimal (e.g., pass-through or simple placeholder) but clearly documented.

3. Ensure:
   - Stage library is stateless; it only uses inputs and runtime services.
   - Errors raised by these functions are propagated up to PipelineExecutor.

Constraints:
- Do NOT modify PipelineExecutor in this step.
- Do NOT modify tests in this step.
- Keep function signatures and imports clear and minimal.

Output format:
- Return a unified diff (git-style) for @/src/agent_engine/runtime/stage_library.py.
```

### Qwen Prompt 12 (Phase 3.D, Step 3.D.2 — Wire PipelineExecutor to stage_library)

```text
You are assisting with Phase 3.D, Step 3.D.2 of the Agent Engine implementation plan.

Goal:
Update PipelineExecutor to delegate per-stage execution to the new stage_library, simplifying its internal logic.

Context:
- stage_library module exists in @/src/agent_engine/runtime/stage_library.py with an execute_stage(...) function.
- PipelineExecutor is in @/src/agent_engine/runtime/pipeline_executor.py and currently contains per-stage-type logic.

Task:
1. In @/src/agent_engine/runtime/pipeline_executor.py:
   - Import execute_stage from @/src/agent_engine/runtime/stage_library.py.
   - Replace any inline per-stage-type execution logic with a call to execute_stage(...), passing:
     - task, stage, context_package, agent_runtime, tool_runtime (or the equivalent available in this module).
2. Ensure:
   - Existing tests (e.g., tests/test_runtime.py) still pass.
   - Routing, TaskStatus, routing_trace, and stage_results behavior remains the same for simple AGENT/TOOL pipelines.

Constraints:
- Do NOT modify stage_library in this step except for imports, if necessary.
- Do NOT change test files in this step.
- Keep the change minimal and focused on delegating execution.

Output format:
- Return a unified diff (git-style) for @/src/agent_engine/runtime/pipeline_executor.py.
```

### Qwen Prompt 13 (Phase 3.D, Step 3.D.3 — Add tests for stage_library)

```text
You are assisting with Phase 3.D, Step 3.D.3 of the Agent Engine implementation plan.

Goal:
Add tests for stage_library to verify basic AGENT and TOOL stage execution behavior using stubs.

Context:
- stage_library is implemented in @/src/agent_engine/runtime/stage_library.py.
- StageType, Stage, and Task are defined in schemas and runtime modules.
- AgentRuntime and ToolRuntime exist in runtime modules.

Task:
1. Create a new test file @/tests/test_stage_library.py.
2. In this file:
   - Define simple stub implementations of AgentRuntime and ToolRuntime that:
     - Record the calls they receive.
     - Return minimal, predictable results.
   - Construct minimal Task and Stage instances representing:
     - An AGENT stage.
     - A TOOL stage.
   - Call stage_library.execute_stage(...) for each case and assert:
     - The stub runtimes were called as expected.
     - The returned result object (or dict) contains the expected fields and values.

Constraints:
- Keep the test self-contained; do NOT depend on PipelineExecutor.
- Do NOT modify existing tests in other files.
- Make the tests robust but minimal.

Output format:
- Return a unified diff (git-style) for @/tests/test_stage_library.py.
```

### Qwen Prompt 14 (Phase 3.D, Step 3.D.4 — HUMAN-only)

No Qwen prompt; this is a HUMAN step.
