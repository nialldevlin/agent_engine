# **PHASE 0 IMPLEMENTATION PLAN**

## *Workspace Audit & Remediation*

**Version:** 1.0
**Date:** 2025-12-09
**Status:** Ready for Implementation

---

## **SECTION 1 — High-Level Summary**

### Purpose

Phase 0 brings the Agent Engine repository into exact alignment with the canonical architecture defined in:

- `docs/canonical/AGENT_ENGINE_OVERVIEW.md`
- `docs/canonical/AGENT_ENGINE_SPEC.md`
- `docs/canonical/PROJECT_INTEGRATION_SPEC.md`
- `docs/operational/PLAN_BUILD_AGENT_ENGINE.md`

This phase removes all legacy pipeline-era code, eliminates non-canonical routing concepts, and ensures the workspace is structurally ready for Phase 1 implementation.

### Constraints

- **DO NOT** write any new code or features
- **DO NOT** modify canonical documentation
- **DO NOT** invent new semantics or architecture
- **ONLY** remove, rename, or quarantine conflicting structures
- Preserve all work that aligns with canonical specs

### Goals

1. Remove all references to pipeline selection and multi-pipeline routing
2. Eliminate the separate `pipelines.yaml` manifest (DAG becomes sole routing definition)
3. Rename `pipeline_executor.py` to `dag_executor.py`
4. Consolidate `stages.yaml` into `workflow.yaml` per PROJECT_INTEGRATION_SPEC
5. Update all imports, tests, and code references to use DAG-only semantics
6. Ensure schema registry matches canonical manifest list exactly
7. Validate that `import agent_engine` works without legacy features

---

## **SECTION 2 — Implementation Requirements**

### Invariants (Must Satisfy)

Phase 0 must ensure the following invariants hold before Phase 1 begins:

#### **IR-1: DAG as Sole Routing Structure**
Per AGENT_ENGINE_OVERVIEW §2 and AGENT_ENGINE_SPEC §3.1:
- The DAG (`workflow.yaml`) is the **only** routing definition
- No pipeline selection logic exists
- No multi-pipeline configuration files exist
- Router does not choose between pipelines

#### **IR-2: Canonical Manifest Set**
Per PROJECT_INTEGRATION_SPEC §2:
- Required manifests: `workflow.yaml`, `agents.yaml`, `tools.yaml`, `memory.yaml`, `schemas/`
- Optional manifests: `plugins.yaml`
- **NO** `pipelines.yaml` file
- **NO** separate `stages.yaml` file (stages/nodes embedded in workflow.yaml)

#### **IR-3: Node Definition Location**
Per PROJECT_INTEGRATION_SPEC §3.1:
- All node definitions are embedded directly in `workflow.yaml`
- No separate stages manifest file exists

#### **IR-4: Schema Registry Alignment**
Per PROJECT_INTEGRATION_SPEC §3:
- Schema registry contains only canonical schemas
- **NO** "pipeline" schema registered
- Schemas include: workflow_graph, stage (node), edge, agent_definition, tool_definition, memory_config, task, etc.

#### **IR-5: Task Model Alignment**
Per AGENT_ENGINE_SPEC §2.1:
- Task contains normalized input, current output, history, metadata
- Task does **NOT** reference a `pipeline_id` (only workflow/DAG context)
- Task lineage tracks clones and subtasks, not pipelines

#### **IR-6: Executor Semantics**
Per AGENT_ENGINE_SPEC §3.1:
- Executor is named `DAGExecutor` or similar (not `PipelineExecutor`)
- Executor follows DAG edges deterministically
- No pipeline selection or pipeline-based routing exists

#### **IR-7: File and Module Naming**
- No file or module names reference "pipeline" unless they are removing pipelines
- Comments and docstrings do not describe pipeline semantics

#### **IR-8: Test Alignment**
- No tests reference pipeline selection
- No tests validate multi-pipeline routing
- Tests validate DAG-based execution only

---

## **SECTION 3 — Step-By-Step Implementation Plan**

Phase 0 implementation is divided into **Human Steps** (requiring judgment, review, or approval) and **LLM Steps** (safe, deterministic file operations).

---

### **3.1 Human Steps**

These steps require human review and approval before proceeding.

#### **H-1: Review and Approve Deletion of `pipelines.yaml`**

**Why:** Per PROJECT_INTEGRATION_SPEC §2, the canonical manifest set does not include `pipelines.yaml`. The DAG (`workflow.yaml`) is the sole routing definition.

**Action Required:**
1. Review the current `pipelines.yaml` file at:
   - `/home/ndev/agent_engine/configs/basic_llm_agent/pipelines.yaml`
2. Confirm that its contents can be safely removed (start/end nodes are redundant with workflow.yaml)
3. Approve deletion

**Expected Condition After Completion:**
- `pipelines.yaml` file does not exist in any config directory
- No code references `pipelines.yaml` loading

---

#### **H-2: Review and Approve Consolidation of `stages.yaml` into `workflow.yaml`**

**Why:** Per PROJECT_INTEGRATION_SPEC §3.1, node definitions must be embedded directly in `workflow.yaml`, not in a separate stages file.

**Action Required:**
1. Review current separation:
   - `/home/ndev/agent_engine/configs/basic_llm_agent/stages.yaml` (contains node definitions)
   - `/home/ndev/agent_engine/configs/basic_llm_agent/workflow.yaml` (contains edges and workflow structure)
2. Understand that nodes must be embedded in workflow.yaml per canonical spec
3. Approve consolidation plan

**Expected Condition After Completion:**
- All node/stage definitions are embedded in `workflow.yaml`
- `stages.yaml` file does not exist
- `workflow.yaml` contains both nodes and edges

---

#### **H-3: Review and Approve Renaming of Core Executor Module**

**Why:** Per AGENT_ENGINE_SPEC §3.1, the executor should reflect DAG-based routing semantics, not pipeline semantics.

**Action Required:**
1. Review current module:
   - `/home/ndev/agent_engine/src/agent_engine/runtime/pipeline_executor.py`
2. Approve renaming to:
   - `/home/ndev/agent_engine/src/agent_engine/runtime/dag_executor.py`
3. Approve renaming class `PipelineExecutor` to `DAGExecutor`

**Expected Condition After Completion:**
- Module is named `dag_executor.py`
- Class is named `DAGExecutor`
- All imports updated throughout codebase

---

#### **H-4: Review Breaking Changes to Public API**

**Why:** Removing `pipeline_id` from Task and removing pipeline selection affects the public Engine API.

**Action Required:**
1. Review current Engine API:
   - `Engine.from_config_dir()` expects "pipelines" as required manifest
   - `Engine.create_task()` calls `router.choose_pipeline()`
   - `Task` has `pipeline_id` field
2. Understand that these will be removed/changed
3. Approve API changes

**Expected Condition After Completion:**
- Engine no longer requires "pipelines" manifest
- Router does not have `choose_pipeline()` method
- Task does not have `pipeline_id` field
- DAG execution is started via explicit or default start node

---

#### **H-5: Review Test Changes and Approve Test Deletions**

**Why:** Tests validating pipeline selection and multi-pipeline routing must be removed or rewritten to validate DAG routing.

**Action Required:**
1. Review tests in:
   - `/home/ndev/agent_engine/tests/test_pipeline_dag_execution.py`
   - `/home/ndev/agent_engine/tests/test_config_loader_and_json_engine.py`
   - `/home/ndev/agent_engine/tests/test_runtime.py`
   - Other files with pipeline references
2. Identify tests that validate:
   - Pipeline selection logic
   - Multi-pipeline routing
   - Pipeline manifest loading
3. Approve rewriting or removing these tests

**Expected Condition After Completion:**
- No tests validate pipeline selection
- All tests validate DAG-based routing
- Test fixtures use workflow.yaml without pipelines.yaml

---

### **3.2 LLM Steps**

These steps can be safely executed by an LLM (Haiku or Qwen) after human approval of the relevant human steps.

---

#### **L-1: Delete `pipelines.yaml` File**

**Prerequisites:** H-1 approved

**Action:**
```bash
rm /home/ndev/agent_engine/configs/basic_llm_agent/pipelines.yaml
```

**Verification:**
```bash
! test -f /home/ndev/agent_engine/configs/basic_llm_agent/pipelines.yaml
```

**Expected Final Condition:**
- File does not exist

---

#### **L-2: Consolidate `stages.yaml` into `workflow.yaml`**

**Prerequisites:** H-2 approved

**Action:**
1. Read `/home/ndev/agent_engine/configs/basic_llm_agent/stages.yaml`
2. Read `/home/ndev/agent_engine/configs/basic_llm_agent/workflow.yaml`
3. Merge stage definitions into workflow.yaml under a `nodes:` or `stages:` field (use `nodes:` per canonical terminology)
4. Delete `stages.yaml`

**Expected Final Condition:**
- `workflow.yaml` contains both node definitions and edges
- `stages.yaml` does not exist
- Node definitions follow canonical Node schema from AGENT_ENGINE_SPEC §2.2

**Example Merged Structure:**
```yaml
workflow_id: basic_workflow
nodes:
  - id: user_input
    kind: agent
    role: start
    agent_id: orchestrator
    # ... other node fields
edges:
  - from: user_input
    to: gather_context
```

---

#### **L-3: Rename `pipeline_executor.py` to `dag_executor.py`**

**Prerequisites:** H-3 approved

**Action:**
1. Rename file:
   ```bash
   mv /home/ndev/agent_engine/src/agent_engine/runtime/pipeline_executor.py \
      /home/ndev/agent_engine/src/agent_engine/runtime/dag_executor.py
   ```
2. Open `dag_executor.py`
3. Rename class `PipelineExecutor` to `DAGExecutor`
4. Update docstrings to reference DAG instead of pipeline

**Expected Final Condition:**
- File is named `dag_executor.py`
- Class is named `DAGExecutor`
- No references to "pipeline" in class name or core logic

---

#### **L-4: Update `config_loader.py` to Remove Pipeline Loading**

**Prerequisites:** H-1, H-2 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/runtime/config_loader.py`

**Changes Required:**

1. **Remove pipeline loading logic:**
   - Remove lines 68-77 (pipeline loading block)
   - Remove `pipelines` field from `EngineConfig` dataclass (line 36)

2. **Update `_REQUIRED_MANIFESTS`:**
   - Remove "pipelines" from required manifest list
   - Change "stages" to be loaded as part of workflow (not separate)

3. **Remove pipeline validation:**
   - Remove lines 196-205 (`_validate_workflow` pipeline validation)
   - Remove `_reaches_end` helper function (lines 208-219) if only used for pipeline validation

4. **Update manifest loading:**
   - Ensure workflow.yaml loading includes embedded node definitions
   - Remove separate stages loading if nodes are now embedded in workflow

**Expected Final Condition:**
- No references to `pipelines` in config_loader.py
- `EngineConfig` does not have `pipelines` field
- Workflow validation does not reference pipelines
- Node definitions loaded from workflow.yaml directly

---

#### **L-5: Update `engine.py` to Remove Pipeline Selection**

**Prerequisites:** H-3, H-4 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/engine.py`

**Changes Required:**

1. **Update imports (line 10):**
   - Change: `from agent_engine.runtime.pipeline_executor import PipelineExecutor`
   - To: `from agent_engine.runtime.dag_executor import DAGExecutor`

2. **Remove "pipelines" from required manifests (line 26):**
   - Change: `_REQUIRED_MANIFESTS = ("agents", "tools", "stages", "workflow", "pipelines")`
   - To: `_REQUIRED_MANIFESTS = ("agents", "tools", "workflow")`
   - Note: "stages" removed because nodes are now in workflow.yaml

3. **Update constructor (lines 66-104):**
   - Remove `pipelines=config.pipelines` from Router initialization (line 88)
   - Rename `pipeline_executor` to `dag_executor` throughout
   - Rename class reference from `PipelineExecutor` to `DAGExecutor`

4. **Update `create_task` method (lines 106-128):**
   - Remove line 127: `pipeline = self.router.choose_pipeline(task_spec=task_spec)`
   - Remove `pipeline_id` parameter from task creation (line 128)
   - Task creation should not require pipeline_id

5. **Update `run_task` method (lines 130-134):**
   - Remove check for `task.pipeline_id` (lines 132-133)
   - Call `dag_executor.run(task)` without pipeline_id parameter

6. **Update internal references:**
   - Change all `self.pipeline_executor` to `self.dag_executor`

**Expected Final Condition:**
- No pipeline selection logic in Engine
- DAGExecutor used instead of PipelineExecutor
- Task creation does not involve pipeline_id
- Engine.from_config_dir() does not require pipelines.yaml

---

#### **L-6: Update `router.py` to Remove Pipeline Selection**

**Prerequisites:** H-4 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/runtime/router.py`

**Changes Required:**

1. **Remove pipelines from Router dataclass (line 11-15):**
   - Remove `pipelines: Dict[str, Pipeline]` field

2. **Remove `choose_pipeline` method (lines 17-22):**
   - Delete entire method

3. **Update `next_stage` method signature (line 24):**
   - Remove `pipeline: Pipeline` parameter
   - Method should determine next stage based on current_stage_id and workflow edges only

4. **Simplify routing logic:**
   - Router should use workflow.start_stage_ids if current_stage_id is None
   - Follow edges deterministically from current stage

**Expected Final Condition:**
- Router does not reference Pipeline class or pipeline selection
- Router initialization requires only: `workflow: WorkflowGraph, stages: Dict[str, Stage]`
- Routing is purely DAG-based

---

#### **L-7: Update `schemas/workflow.py` to Deprecate Pipeline Class**

**Prerequisites:** H-4 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/schemas/workflow.py`

**Changes Required:**

1. **Option A (Quarantine):**
   - Move `Pipeline` class definition to a comment block
   - Add deprecation notice: "# DEPRECATED: Pipeline class is not part of canonical architecture"
   - Keep Edge and WorkflowGraph classes

2. **Option B (Remove):**
   - Delete `Pipeline` class entirely (lines 90-123)
   - Update imports in other files that reference Pipeline

**Recommendation:** Use Option A (quarantine) initially to make reverting easier if issues arise.

**Expected Final Condition:**
- `Pipeline` class is not used in active code
- `WorkflowGraph` remains as the sole workflow definition

---

#### **L-8: Update `schemas/__init__.py` to Remove Pipeline Export**

**Prerequisites:** H-4 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/schemas/__init__.py`

**Changes Required:**

1. **Remove Pipeline from imports (line 40):**
   - Change: `from .workflow import Edge, EdgeType, Pipeline, WorkflowGraph`
   - To: `from .workflow import Edge, EdgeType, WorkflowGraph`

2. **Remove Pipeline from __all__ (line 96):**
   - Remove `"Pipeline",` from the export list

**Expected Final Condition:**
- Pipeline is not exported from agent_engine.schemas
- External code cannot import Pipeline

---

#### **L-9: Update `schemas/registry.py` to Remove Pipeline Schema**

**Prerequisites:** H-4 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/schemas/registry.py`

**Changes Required:**

1. **Remove Pipeline from imports (line 22):**
   - Change: `from .workflow import Edge, Pipeline, WorkflowGraph`
   - To: `from .workflow import Edge, WorkflowGraph`

2. **Remove pipeline schema registration (line 34):**
   - Delete: `"pipeline": Pipeline,`

**Expected Final Condition:**
- "pipeline" schema is not registered
- Schema registry contains only canonical schemas

---

#### **L-10: Update `schemas/task.py` to Remove `pipeline_id` Field**

**Prerequisites:** H-4 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/schemas/task.py`

**Changes Required:**

1. **Remove `pipeline_id` from Task schema (line 77):**
   - Delete: `pipeline_id: str`
   - Task routing should be implicit from workflow start node selection

2. **Update TaskManager if it references pipeline_id:**
   - Check `/home/ndev/agent_engine/src/agent_engine/runtime/task_manager.py`
   - Remove pipeline_id from `create_task` method

**Expected Final Condition:**
- Task does not have `pipeline_id` field
- Task creation does not require pipeline specification

---

#### **L-11: Update `dag_executor.py` to Remove Pipeline References**

**Prerequisites:** L-3 completed, H-4 approved

**File:** `/home/ndev/agent_engine/src/agent_engine/runtime/dag_executor.py`

**Changes Required:**

1. **Update `run` method signature (line 33):**
   - Change: `def run(self, task: Task, pipeline_id: str) -> Task:`
   - To: `def run(self, task: Task) -> Task:`

2. **Remove pipeline lookup (line 34):**
   - Delete: `pipeline = self.router.pipelines[pipeline_id]`

3. **Update routing calls:**
   - Change line 43: `next_stage_id = self.router.next_stage(current_stage_id, pipeline, decision=pending_decision)`
   - To: `next_stage_id = self.router.next_stage(current_stage_id, decision=pending_decision)`

4. **Update initialization logic:**
   - When current_stage_id is None, use `self.router.workflow.start_stage_ids[0]` or default start
   - Remove pipeline-based start node selection

5. **Remove fallback_end_stage_ids logic (lines 100-103):**
   - Fallback exits should be defined as error edges in the DAG, not in pipeline config

6. **Update docstring and comments:**
   - Replace "pipeline" with "DAG" or "workflow" throughout

**Expected Final Condition:**
- DAGExecutor runs tasks through the DAG without pipeline reference
- Start node determined from workflow.start_stage_ids
- No pipeline selection or pipeline-based routing

---

#### **L-12: Update Test Fixtures to Remove `pipelines.yaml`**

**Prerequisites:** H-5 approved

**Files:**
- `/home/ndev/agent_engine/tests/test_config_loader_and_json_engine.py`
- Any test helper that creates fixtures

**Changes Required:**

1. **Remove pipelines.yaml from test fixtures:**
   - Ensure test config directories do not include pipelines.yaml
   - Update test assertions that check for pipeline loading

2. **Update manifest validation tests:**
   - Remove tests that validate pipeline manifest schema
   - Remove tests that check pipeline reachability

**Expected Final Condition:**
- Test fixtures use only canonical manifests
- No test loads or validates pipelines.yaml

---

#### **L-13: Update or Remove Pipeline-Specific Tests**

**Prerequisites:** H-5 approved

**Files:**
- `/home/ndev/agent_engine/tests/test_pipeline_dag_execution.py`
- `/home/ndev/agent_engine/tests/test_runtime.py`
- Other test files with pipeline references

**Changes Required:**

**Option A (Rewrite):**
1. Rename `test_pipeline_dag_execution.py` to `test_dag_execution.py`
2. Rewrite tests to validate DAG routing without pipeline selection
3. Use workflow start nodes instead of pipeline start nodes

**Option B (Remove):**
1. Delete tests that cannot be meaningfully rewritten
2. Ensure core DAG execution is covered by other tests

**Expected Final Condition:**
- All tests validate DAG-based execution
- No tests reference pipeline selection or multi-pipeline routing
- Tests use canonical workflow structure

---

#### **L-14: Update `runtime/__init__.py` Exports**

**Prerequisites:** L-3, L-11 completed

**File:** `/home/ndev/agent_engine/src/agent_engine/runtime/__init__.py`

**Changes Required:**

1. **Update exports to use DAGExecutor:**
   - If PipelineExecutor was exported, change to DAGExecutor
   - Update any documentation strings

**Expected Final Condition:**
- Runtime module exports DAGExecutor, not PipelineExecutor

---

#### **L-15: Search and Replace All Remaining "pipeline" References**

**Prerequisites:** All L-1 through L-14 completed

**Action:**

1. **Search for remaining references:**
   ```bash
   grep -r "pipeline" /home/ndev/agent_engine/src --include="*.py" | grep -v ".pyc" | grep -v "__pycache__"
   ```

2. **Review each occurrence:**
   - Comments: Update to say "DAG" or "workflow"
   - Docstrings: Update terminology
   - Variable names: Rename if they refer to active code (not deprecated quarantined code)
   - Log messages: Update terminology

3. **Exceptions (do not change):**
   - Deprecation comments
   - Quarantined code blocks
   - Historical notes in docstrings that reference "pipeline-era"

**Expected Final Condition:**
- No active code references "pipeline" semantics
- Comments and docstrings use canonical terminology

---

#### **L-16: Update Example Configuration in `configs/basic_llm_agent/`**

**Prerequisites:** L-2 completed

**Files:**
- `/home/ndev/agent_engine/configs/basic_llm_agent/workflow.yaml`

**Changes Required:**

1. **Ensure workflow.yaml matches canonical structure:**
   - Has embedded node definitions (from consolidation in L-2)
   - Has `workflow_id` field
   - Has `nodes:` list with canonical node fields (id, kind, role, schema_in, schema_out, context, tools, etc.)
   - Has `edges:` list with canonical edge fields (from_stage_id, to_stage_id, condition, edge_type)
   - Has `start_stage_ids:` list (explicit entry points)
   - Has `end_stage_ids:` list (explicit exit points)

2. **Validate against PROJECT_INTEGRATION_SPEC §3.1:**
   - Node kind: "agent" or "deterministic"
   - Node role: one of "start", "linear", "decision", "branch", "split", "merge", "exit"
   - Edges reference valid node IDs

**Expected Final Condition:**
- Example config demonstrates canonical workflow structure
- No pipelines.yaml or stages.yaml files exist
- All routing defined in workflow.yaml

---

#### **L-17: Run Linter and Fix Import Errors**

**Prerequisites:** All L-1 through L-16 completed

**Action:**

1. **Run Python import checker:**
   ```bash
   python -c "import agent_engine; print('Success')"
   ```

2. **Run pytest to find import errors:**
   ```bash
   pytest /home/ndev/agent_engine/tests --collect-only
   ```

3. **Fix any remaining import errors:**
   - Update imports that still reference PipelineExecutor
   - Update imports that reference Pipeline schema

**Expected Final Condition:**
- `import agent_engine` succeeds without errors
- No import errors when collecting tests

---

#### **L-18: Validate Schema Registry Against Canonical Spec**

**Prerequisites:** L-9 completed

**Action:**

1. **Check SCHEMA_REGISTRY contents:**
   ```python
   from agent_engine.schemas import SCHEMA_REGISTRY
   print(sorted(SCHEMA_REGISTRY.keys()))
   ```

2. **Expected schemas (from PROJECT_INTEGRATION_SPEC):**
   - workflow_graph
   - stage (or node)
   - edge
   - agent_definition
   - tool_definition
   - memory_config
   - task_spec
   - task
   - tool_plan
   - tool_step
   - tool_call_record
   - context_item
   - context_request
   - context_package
   - event
   - override_spec
   - engine_error

3. **Ensure "pipeline" is NOT in registry**

**Expected Final Condition:**
- SCHEMA_REGISTRY matches canonical requirements
- No "pipeline" schema registered

---

## **SECTION 4 — Repository Completion Criteria**

Phase 0 is complete when all of the following conditions are verified:

### **CC-1: File Structure**
- [ ] `/configs/basic_llm_agent/pipelines.yaml` does not exist
- [ ] `/configs/basic_llm_agent/stages.yaml` does not exist
- [ ] `/configs/basic_llm_agent/workflow.yaml` exists and contains embedded node definitions
- [ ] `/src/agent_engine/runtime/dag_executor.py` exists
- [ ] `/src/agent_engine/runtime/pipeline_executor.py` does not exist

### **CC-2: Import Check**
- [ ] `python -c "import agent_engine"` succeeds without errors
- [ ] `python -c "from agent_engine import Engine"` succeeds
- [ ] `python -c "from agent_engine import Pipeline"` fails with ImportError (Pipeline not exported)

### **CC-3: Schema Registry**
- [ ] `agent_engine.schemas.SCHEMA_REGISTRY` does not contain "pipeline" key
- [ ] Schema registry contains "workflow_graph", "stage", "edge", "agent_definition", "tool_definition", "memory_config"

### **CC-4: Code References**
- [ ] No active code file contains class name `PipelineExecutor`
- [ ] No active code file contains `router.choose_pipeline()`
- [ ] No active code file contains `task.pipeline_id` as an active field (may exist in deprecated/quarantine blocks)
- [ ] `grep -r "pipelines.yaml" /home/ndev/agent_engine/src` returns no matches

### **CC-5: Engine API**
- [ ] `Engine._REQUIRED_MANIFESTS` does not include "pipelines"
- [ ] `Engine.__init__()` has `dag_executor` parameter, not `pipeline_executor`
- [ ] `Engine.create_task()` does not call `router.choose_pipeline()`

### **CC-6: Router Semantics**
- [ ] `Router` dataclass does not have `pipelines` field
- [ ] `Router.next_stage()` method does not accept `pipeline` parameter
- [ ] Router initialization signature: `Router(workflow: WorkflowGraph, stages: Dict[str, Stage])`

### **CC-7: Task Model**
- [ ] `Task` schema does not have `pipeline_id` as a required field
- [ ] Task creation does not require pipeline specification

### **CC-8: Test Alignment**
- [ ] No test file validates pipeline selection logic
- [ ] No test file loads `pipelines.yaml`
- [ ] Test fixtures use canonical manifest structure (workflow.yaml with embedded nodes)

### **CC-9: Example Configuration**
- [ ] Example config in `/configs/basic_llm_agent/` uses only canonical manifests
- [ ] `workflow.yaml` contains embedded nodes and edges
- [ ] No `pipelines.yaml` or `stages.yaml` in example config

### **CC-10: Documentation and Comments**
- [ ] Active code docstrings reference "DAG" and "workflow", not "pipeline"
- [ ] Comments in runtime modules reference canonical routing semantics

---

## **SECTION 5 — Execution Order**

The following execution order must be followed to minimize breakage:

### **Phase A: Human Review and Approval**
1. Complete H-1 through H-5 (all human review steps)
2. Document approvals

### **Phase B: File Operations**
1. L-1: Delete pipelines.yaml
2. L-2: Consolidate stages.yaml into workflow.yaml
3. L-3: Rename pipeline_executor.py to dag_executor.py

### **Phase C: Schema and Model Updates**
1. L-7: Deprecate Pipeline class
2. L-8: Remove Pipeline from schemas/__init__.py
3. L-9: Remove Pipeline from schema registry
4. L-10: Remove pipeline_id from Task schema

### **Phase D: Core Logic Updates**
1. L-4: Update config_loader.py
2. L-6: Update router.py
3. L-11: Update dag_executor.py
4. L-5: Update engine.py
5. L-14: Update runtime/__init__.py

### **Phase E: Test and Configuration Updates**
1. L-12: Update test fixtures
2. L-13: Update or remove pipeline-specific tests
3. L-16: Update example configuration

### **Phase F: Cleanup and Validation**
1. L-15: Search and replace remaining references
2. L-17: Run linter and fix import errors
3. L-18: Validate schema registry

### **Phase G: Final Verification**
1. Verify all completion criteria (CC-1 through CC-10)
2. Run full test suite
3. Confirm `import agent_engine` works
4. Document completion

---

## **SECTION 6 — Risk Mitigation**

### **Backup Strategy**

Before executing any LLM steps:

```bash
# Create backup branch
cd /home/ndev/agent_engine
git checkout -b backup-pre-phase-0
git add -A
git commit -m "Backup before Phase 0 remediation"
git checkout main
```

### **Incremental Validation**

After each phase (A through G):
1. Run `python -c "import agent_engine"` to check for import errors
2. Run basic smoke tests
3. Commit changes with descriptive message

### **Rollback Plan**

If Phase 0 cannot be completed:
```bash
git checkout backup-pre-phase-0
```

---

## **SECTION 7 — Post-Phase-0 Validation**

After completing all steps, run the following validation:

```bash
# Test 1: Import check
python -c "import agent_engine; from agent_engine import Engine; print('✓ Imports work')"

# Test 2: Schema registry check
python -c "from agent_engine.schemas import SCHEMA_REGISTRY; assert 'pipeline' not in SCHEMA_REGISTRY; print('✓ Schema registry clean')"

# Test 3: File structure check
! test -f /home/ndev/agent_engine/configs/basic_llm_agent/pipelines.yaml && echo "✓ pipelines.yaml removed"
! test -f /home/ndev/agent_engine/configs/basic_llm_agent/stages.yaml && echo "✓ stages.yaml removed"
test -f /home/ndev/agent_engine/src/agent_engine/runtime/dag_executor.py && echo "✓ dag_executor.py exists"

# Test 4: No pipeline references in active code
! grep -r "class PipelineExecutor" /home/ndev/agent_engine/src --include="*.py" && echo "✓ No PipelineExecutor class"

# Test 5: Run test suite
pytest /home/ndev/agent_engine/tests -v
```

---

## **END OF PHASE 0 IMPLEMENTATION PLAN**

---

### **✅ PHASE 0 STATUS: COMPLETE**

**Date:** 2025-12-09
**Status:** ✅ FULLY IMPLEMENTED AND VERIFIED

---

### **Completion Summary**

| Category | Count | Status |
|----------|-------|--------|
| Human Review Steps (H-1 to H-5) | 5 | ✅ APPROVED |
| LLM Implementation Steps (L-1 to L-18) | 18 | ✅ COMPLETED |
| Completion Criteria (CC-1 to CC-10) | 10 | ✅ VERIFIED |
| **Total** | **33** | **100% COMPLETE** |

---

### **Completion Details**

✅ **Phase A: Human Review** — All approvals received
✅ **Phase B: File Operations** — All file changes completed
✅ **Phase C: Schema Updates** — All schema changes completed
✅ **Phase D: Core Logic** — All code changes completed
✅ **Phase E: Tests** — All tests updated (384 passing)
✅ **Phase F: Cleanup** — All references cleaned
✅ **Phase G: Verification** — All criteria verified

---

### **Verification Results**

**CC-1: File Structure** ✅
- ✓ pipelines.yaml deleted
- ✓ stages.yaml deleted
- ✓ workflow.yaml exists with embedded stages
- ✓ dag_executor.py exists
- ✓ pipeline_executor.py deleted

**CC-2: Import Checks** ✅
- ✓ import agent_engine works
- ✓ from agent_engine import Engine works
- ✓ Pipeline not exported (as expected)

**CC-3: Schema Registry** ✅
- ✓ Pipeline schema not registered
- ✓ All canonical schemas present

**CC-4: Code References** ✅
- ✓ No PipelineExecutor class
- ✓ No router.choose_pipeline()
- ✓ No task.pipeline_id field
- ✓ No pipelines.yaml references

**CC-5: Engine API** ✅
- ✓ Engine._REQUIRED_MANIFESTS correct
- ✓ Uses dag_executor parameter
- ✓ No pipeline selection logic

**CC-6: Router Semantics** ✅
- ✓ DAG-based routing only
- ✓ No pipeline selection

**CC-7: Task Model** ✅
- ✓ No pipeline_id field

**CC-8: Test Alignment** ✅
- ✓ 384 tests passing
- ✓ No pipeline-specific tests

**CC-9: Example Configuration** ✅
- ✓ Canonical structure in configs/basic_llm_agent/

**CC-10: Documentation** ✅
- ✓ Active code uses DAG terminology

---

### **Canonical Architecture Reference**

- AGENT_ENGINE_OVERVIEW.md: ✓ Authoritative
- AGENT_ENGINE_SPEC.md: ✓ Authoritative
- PROJECT_INTEGRATION_SPEC.md: ✓ Authoritative
- PLAN_BUILD_AGENT_ENGINE.md: ✓ Authoritative
