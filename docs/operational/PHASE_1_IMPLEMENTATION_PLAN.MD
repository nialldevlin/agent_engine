  # PHASE_1_IMPLEMENTATION_PLAN.md

  ## Phase Summary

  Phase 1 establishes the foundational canonical data structures and validation 
  logic for Agent Engine. This phase replaces all legacy schema elements 
  (StageType, EdgeType, old TaskStatus) with the canonical kind+role model, 
  universal status model, and proper Task lineage tracking. It implements strict 
  manifest validation ensuring all projects conform to the canonical architecture 
  before execution begins.

  **Scope**: Schema definitions, validation logic, no runtime execution.

  **Success Criteria**: All manifests validate against canonical schemas; DAG 
  validator enforces all structural invariants; no legacy schema elements remain in
   public APIs.

  ---

  ## Requirements & Invariants

  ### Universal Constraints (from AGENT_ENGINE_SPEC)

  1. **Node Model**:
     - Every node has exactly one `kind` ∈ {`agent`, `deterministic`}
     - Every node has exactly one `role` ∈ {`start`, `linear`, `decision`, 
  `branch`, `split`, `merge`, `exit`}
     - `start` and `exit` roles are `deterministic` only
     - All other roles may be `agent` or `deterministic`

  2. **Edge Model**:
     - Edges are directed pairs `(from, to, label?)`
     - No EdgeType enum; routing semantics come from node roles only

  3. **Task Model**:
     - Tasks have separate lifecycle state and outcome status
     - Lifecycle: `pending | running | completed`
     - Status (universal): `success | failure | partial`
     - Tasks track lineage: `parent_task_id`, `lineage_type` ∈ {`root`, `clone`,
  `subtask`}
     - Tasks reference three memory layers explicitly

  4. **Status Propagation**:
     - All entities (nodes, tools, tasks) use the universal status model
     - Status must be set before reaching exit nodes

  5. **Context Model**:
     - Every node specifies exactly one of: `context_profile_id`, `"global"`, or
  `"none"`
     - Context profiles define: max_tokens, retrieval_policy, memory sources

  6. **DAG Invariants**:
     - Graph is acyclic
     - Exactly one start node marked `default_start: true`
     - Start nodes: 0 inbound, 1 outbound
     - Exit nodes: ≥1 inbound, 0 outbound
     - Linear nodes: 1 inbound, 1 outbound
     - Decision nodes: 1 inbound, ≥2 outbound
     - Branch nodes: 1 inbound, ≥2 outbound
     - Split nodes: 1 inbound, ≥1 outbound
     - Merge nodes: ≥2 inbound, 1 outbound (unless terminal)
     - All nodes reachable from start, all reach at least one exit

  ---

  ## LLM Implementation Plan

  ### TASK 1: Update Node Schema to Canonical Kind + Role Model

  **Goal**: Replace legacy `StageType` with canonical `kind` and `role` fields.

  **Files**:
  - `/home/ndev/agent_engine/src/agent_engine/schemas/stage.py`
  - `/home/ndev/agent_engine/src/agent_engine/schemas/workflow.py`

  **Actions**:

  1.1. **Remove Legacy Enums**:
     - Delete `StageType` enum entirely from `stage.py`
     - Delete `OnErrorPolicy` enum (replaced by simple boolean)

  1.2. **Create Canonical Enums**:
     - Add `NodeKind` enum with values: `AGENT = "agent"`, `DETERMINISTIC =
  "deterministic"`
     - Add `NodeRole` enum with values: `START = "start"`, `LINEAR = "linear"`,
  `DECISION = "decision"`, `BRANCH = "branch"`, `SPLIT = "split"`, `MERGE =
  "merge"`, `EXIT = "exit"`

  1.3. **Refactor Stage Class to Node**:
     - Rename `Stage` class to `Node`
     - Replace `type: StageType` with two fields:
       - `kind: NodeKind`
       - `role: NodeRole`
     - Replace `entrypoint: bool` with `default_start: bool` (only valid when `role
   == "start"`)
     - Replace `terminal: bool` logic with `role == "exit"` checks
     - Replace `agent_id: Optional[str]` logic:
       - Required when `kind == "agent"`
       - Must be None when `kind == "deterministic"`
     - Replace `tool_id: Optional[str]` with `tools: List[str]` (list of allowed
  tool IDs)
     - Replace `on_error: Dict[str, Any]` with `continue_on_failure: bool = False`
     - Keep: `stage_id` (rename to `node_id` later), `name`, `inputs_schema_id`,
  `outputs_schema_id`, `metadata`
     - Add: `context: str` (context profile ID, or literal "global" or "none")
     - Add for merge nodes: `merge: Optional[Dict[str, Any]]` with `strategy: str`
  subfield

  1.4. **Add Validation Method**:
     - Add `validate_node_invariants()` method that checks:
       - `start` and `exit` roles require `kind == "deterministic"`
       - `agent` kind requires non-null `agent_id`
       - `default_start == True` only when `role == "start"`
       - `merge` field only when `role == "merge"`

  **Invariants to Enforce**:
  - No `StageType` references remain
  - All nodes have both `kind` and `role`
  - Kind-role combinations respect constraints

  ---

  ### TASK 2: Update Edge Schema to Canonical Model

  **Goal**: Simplify edges to canonical `(from, to, label?)` model.

  **Files**:
  - `/home/ndev/agent_engine/src/agent_engine/schemas/workflow.py`

  **Actions**:

  2.1. **Remove Legacy EdgeType**:
     - Delete `EdgeType` enum
     - Remove `edge_type` field from `Edge` class

  2.2. **Canonical Edge Schema**:
     - Keep: `from_stage_id` (rename to `from_node_id` later), `to_stage_id`
  (rename to `to_node_id` later)
     - Keep: `condition: Optional[str]` (used by decision nodes)
     - Keep: `edge_id: Optional[str]`
     - Remove all references to NORMAL, CONDITIONAL, ERROR, FALLBACK

  2.3. **Update Edge Docstring**:
     - Document that routing semantics come from node roles, not edge types
     - Document that `condition` is used by decision nodes to select edges

  **Invariants to Enforce**:
  - No `EdgeType` references remain
  - Edges are simple directed pairs with optional label

  ---

  ### TASK 3: Update Task Schema with Canonical Lifecycle and Status

  **Goal**: Separate lifecycle state from outcome status; add lineage and memory
  refs.

  **Files**:
  - `/home/ndev/agent_engine/src/agent_engine/schemas/task.py`

  **Actions**:

  3.1. **Create Status Enums**:
     - Add `TaskLifecycle` enum: `PENDING = "pending"`, `RUNNING = "running"`,
  `COMPLETED = "completed"`
     - Add `UniversalStatus` enum: `SUCCESS = "success"`, `FAILURE = "failure"`,
  `PARTIAL = "partial"`

  3.2. **Update TaskStatus References**:
     - Replace `TaskStatus` with `TaskLifecycle` for the `status` field
     - Rename field from `status` to `lifecycle`

  3.3. **Add Universal Status Field**:
     - Add `status: UniversalStatus = UniversalStatus.SUCCESS` (default, can be
  changed during execution)

  3.4. **Add Lineage Fields**:
     - Add `parent_task_id: Optional[str] = None`
     - Add `lineage_type: str = "root"` (enum-like: "root", "clone", "subtask")
     - Add `lineage_metadata: Dict[str, Any] = Field(default_factory=dict)`

  3.5. **Add Memory References**:
     - Add `task_memory_ref: str` (required; use task_id as default)
     - Add `project_memory_ref: str` (required; must be provided at task creation)
     - Add `global_memory_ref: str` (required; must be provided at task creation)

  3.6. **Add Current Output Field**:
     - Add `current_output: Optional[Any] = None` (updated after each node
  execution)

  3.7. **Update Docstrings**:
     - Document lifecycle vs status distinction
     - Document lineage tracking for clones and subtasks
     - Document memory reference usage

  **Invariants to Enforce**:
  - `lifecycle` and `status` are distinct fields
  - Lineage tracking is explicit
  - Memory references are always present

  ---

  ### TASK 4: Create ContextProfile Schema

  **Goal**: Define canonical context profile schema for memory assembly.

  **Files**:
  - `/home/ndev/agent_engine/src/agent_engine/schemas/memory.py`

  **Actions**:

  4.1. **Create ContextProfileSource Schema**:
     ```python
     class ContextProfileSource(SchemaBase):
         store: str  # "task" | "project" | "global"
         tags: List[str] = Field(default_factory=list)

  4.2. Create ContextProfile Schema:
  class ContextProfile(SchemaBase):
      id: str
      max_tokens: int
      retrieval_policy: str  # "recency" | "semantic" | "hybrid"
      sources: List[ContextProfileSource]
      metadata: Dict[str, Any] = Field(default_factory=dict)

  4.3. Update Existing Memory Schemas:
  - Verify MemoryConfig, ContextItem, ContextPackage match canonical requirements
  - Ensure three-layer model (task/project/global) is clear

  4.4. Add Validation:
  - retrieval_policy must be one of: "recency", "semantic", "hybrid"
  - sources must contain at least one store
  - Each source store must be one of: "task", "project", "global"

  Invariants to Enforce:
  - Context profiles are explicit, named configurations
  - Retrieval policies are standardized
  - Three-layer memory model is enforced

  ---
  TASK 5: Update Tool Schemas for Canonical Permission Model

  Goal: Clarify tool capabilities vs node-level tool permissions.

  Files:
  - /home/ndev/agent_engine/src/agent_engine/schemas/tool.py

  Actions:

  5.1. Verify ToolDefinition Schema:
  - Ensure it has: tool_id, kind, name, description, inputs_schema_id,
  outputs_schema_id
  - Ensure it has capability fields: capabilities: List[ToolCapability]
  - Add if missing: allow_network: bool, allow_shell: bool, filesystem_root: 
  Optional[str]

  5.2. Update ToolCapability Enum:
  - Verify values match canonical: DETERMINISTIC_SAFE, WORKSPACE_MUTATION,
  EXTERNAL_NETWORK, EXPENSIVE

  5.3. Add Tool Permission Documentation:
  - Document that ToolDefinition defines what a tool CAN do
  - Document that Node.tools defines what a node MAY call
  - Document that both must be satisfied for tool invocation

  5.4. Verify ToolPlan Schema:
  - Ensure ToolPlan and ToolStep match canonical (already exist, verify structure)

  Invariants to Enforce:
  - Tool capabilities are defined per-tool
  - Node tool permissions are per-node whitelists
  - Both levels exist and are validated

  ---
  TASK 6: Update WorkflowGraph Schema

  Goal: Update workflow schema to reference canonical node and edge schemas.

  Files:
  - /home/ndev/agent_engine/src/agent_engine/schemas/workflow.py

  Actions:

  6.1. Update WorkflowGraph Fields:
  - Change stages: List to nodes: List[Node] (or List[str] for node IDs)
  - Keep edges: List[Edge]
  - Remove start_stage_ids, end_stage_ids (replaced by node-level default_start and
   role == "exit")
  - Keep workflow_id, invariants, metadata

  6.2. Update Docstrings:
  - Document that exactly one DAG per project
  - Document that start/exit nodes are determined by node roles
  - Reference canonical constraints

  Invariants to Enforce:
  - Workflow contains nodes and edges only
  - Start/exit are determined by node properties, not workflow-level lists

  ---
  TASK 7: Implement Canonical DAG Validation

  Goal: Replace old validation with canonical constraint enforcement.

  Files:
  - /home/ndev/agent_engine/src/agent_engine/schemas/workflow.py

  Actions:

  7.1. Rewrite validate_workflow_graph() Function:

  7.2. Structural Validation:
  - Extract all node IDs from workflow
  - Build adjacency list and inbound/outbound counts per node
  - Validate all edges reference existing nodes

  7.3. Acyclicity Check:
  - Implement DFS-based cycle detection
  - Raise error if any cycle found

  7.4. Node Role Constraints:
  - For each node, verify edge counts match role:
    - start: 0 inbound, 1 outbound
    - exit: ≥1 inbound, 0 outbound
    - linear: 1 inbound, 1 outbound
    - decision: 1 inbound, ≥2 outbound
    - branch: 1 inbound, ≥2 outbound
    - split: 1 inbound, ≥1 outbound
    - merge: ≥2 inbound, 1 outbound (unless role == "exit")

  7.5. Start Node Validation:
  - Find all nodes with role == "start"
  - Ensure exactly one has default_start == True
  - Raise error if zero or multiple default starts

  7.6. Exit Node Validation:
  - Find all nodes with role == "exit"
  - Ensure at least one exit node exists

  7.7. Reachability Validation:
  - Starting from default start node, compute reachable set via DFS
  - Ensure all nodes are reachable
  - Ensure at least one exit node is reachable from default start

  7.8. Kind-Role Constraint Validation:
  - For each node:
    - If role == "start" or role == "exit", ensure kind == "deterministic"
    - All other role-kind combinations are valid

  7.9. Context Field Validation:
  - For each node, ensure context is either:
    - A string matching a context profile ID (to be validated against memory.yaml
  later)
    - The literal string "global"
    - The literal string "none"

  Invariants to Enforce:
  - All canonical DAG invariants from AGENT_ENGINE_SPEC §3
  - No validation of non-canonical constraints (e.g., StageType, EdgeType)

  ---
  TASK 8: Update Schema Registry

  Goal: Register all canonical schemas; remove legacy schemas.

  Files:
  - /home/ndev/agent_engine/src/agent_engine/schemas/registry.py
  - /home/ndev/agent_engine/src/agent_engine/schemas/__init__.py

  Actions:

  8.1. Update Imports:
  - Import Node (renamed from Stage)
  - Import ContextProfile, ContextProfileSource
  - Import UniversalStatus, TaskLifecycle

  8.2. Update SCHEMA_REGISTRY:
  - Change "stage" to "node" → Node
  - Add "context_profile" → ContextProfile
  - Add "context_profile_source" → ContextProfileSource
  - Add "universal_status" → UniversalStatus
  - Add "task_lifecycle" → TaskLifecycle
  - Remove any deprecated pipeline schemas

  8.3. Update init.py Exports:
  - Export all canonical schemas
  - Remove legacy exports (Stage, StageType, EdgeType, TaskStatus)

  Invariants to Enforce:
  - All canonical schemas are registered
  - No legacy schemas are exported or registered

  ---
  TASK 9: Add Schema Validation Tests

  Goal: Verify all schemas validate correctly and enforce canonical invariants.

  Files:
  - Create /home/ndev/agent_engine/tests/test_schemas_canonical.py
  - Update existing schema tests to match canonical model

  Actions:

  9.1. Test Node Schema:
  - Valid nodes with all kind-role combinations
  - Invalid: start with kind == "agent"
  - Invalid: exit with kind == "agent"
  - Invalid: default_start == True with role != "start"
  - Invalid: missing required fields

  9.2. Test Edge Schema:
  - Valid edges with from/to/label
  - Validate edges reference valid node IDs (in integration test)

  9.3. Test Task Schema:
  - Valid task with lifecycle and status
  - Valid task with lineage fields for clone and subtask
  - Valid task with memory references
  - Verify current_output can be set and retrieved

  9.4. Test ContextProfile Schema:
  - Valid profile with all retrieval policies
  - Valid profile with different source combinations
  - Invalid: bad retrieval policy
  - Invalid: empty sources list

  9.5. Test DAG Validation:
  - Valid minimal DAG (one start, one linear, one exit)
  - Valid complex DAG (decision, branch, merge)
  - Invalid: no start node
  - Invalid: no exit node
  - Invalid: multiple default starts
  - Invalid: zero default starts
  - Invalid: cycle detected
  - Invalid: unreachable nodes
  - Invalid: wrong edge counts for roles
  - Invalid: start with kind == "agent"

  9.6. Test WorkflowGraph Schema:
  - Valid workflow with nodes and edges
  - Workflow validation calls DAG validator

  Invariants to Enforce:
  - All canonical schema constraints are tested
  - All invalid cases are caught and raise clear errors

  ---
  TASK 10: Update Documentation Comments

  Goal: Ensure all schema docstrings reference canonical docs.

  Files:
  - All schema files in /home/ndev/agent_engine/src/agent_engine/schemas/

  Actions:

  10.1. Add Canonical References:
  - Every schema class docstring should include a reference like:
    - "Per AGENT_ENGINE_SPEC §2.2 and AGENT_ENGINE_OVERVIEW §1.2"
  - Document which section of the canonical docs defines each schema

  10.2. Document Invariants:
  - For each schema, list its canonical invariants in the docstring
  - Example: Node docstring lists kind-role constraints

  10.3. Remove Legacy Documentation:
  - Remove references to pipelines, StageType, EdgeType
  - Remove references to non-canonical behaviors

  Invariants to Enforce:
  - All schemas trace back to canonical documents
  - No outdated documentation remains

  ---
  Acceptance Criteria

  Phase 1 is complete when:

  1. Schema Compliance:
    - ✅ All nodes use kind and role fields; no StageType references exist
    - ✅ All edges use canonical (from, to, label?) model; no EdgeType references
  exist
    - ✅ Task has separate lifecycle and status fields
    - ✅ Task has lineage fields: parent_task_id, lineage_type, lineage_metadata
    - ✅ Task has memory references: task_memory_ref, project_memory_ref,
  global_memory_ref
    - ✅ Task has current_output field
    - ✅ ContextProfile schema exists with canonical fields
  2. Validation Logic:
    - ✅ DAG validator enforces all canonical invariants from AGENT_ENGINE_SPEC §3
    - ✅ Exactly one default start node required
    - ✅ Acyclicity enforced
    - ✅ Reachability enforced
    - ✅ Role-specific edge counts enforced
    - ✅ Kind-role constraints enforced
  3. Test Coverage:
    - ✅ All valid schema cases pass validation
    - ✅ All invalid schema cases raise clear errors
    - ✅ DAG validator tests cover all constraint types
  4. Registry & Exports:
    - ✅ All canonical schemas registered in SCHEMA_REGISTRY
    - ✅ No legacy schemas exported
    - ✅ import agent_engine.schemas works without legacy references
  5. Documentation:
    - ✅ All schemas reference canonical documents in docstrings
    - ✅ No outdated documentation remains
  6. No Code Implementation:
    - ✅ This phase implements only schemas and validation logic
    - ✅ No runtime execution code (that's Phase 2+)

  ---
  Notes for Implementation

  File Naming Conventions

  - Consider renaming stage.py to node.py for clarity
  - Consider renaming field names: stage_id → node_id, from_stage_id →
  from_node_id, etc.
  - This can be a separate refactoring step after schema changes

  Backward Compatibility

  - Phase 1 is a breaking change for existing manifests
  - Document migration path from old schemas to new
  - Consider writing a migration script for existing test manifests

  Testing Strategy

  - Unit tests for each schema class
  - Integration tests for DAG validation
  - Ensure tests cover both positive and negative cases
  - Use clear error messages for validation failures

  Dependencies

  - Phase 0 must be complete (no pipeline references)
  - No dependencies on later phases
  - Schemas are pure data structures with validation logic only
