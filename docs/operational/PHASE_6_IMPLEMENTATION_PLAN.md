# Phase 6 Implementation Plan: Memory & Context v1

**Status:** READY FOR IMPLEMENTATION (Steps 1-11)
**Date Created:** 2025-12-10
**Phase Goal:** Implement memory stores and context assembler

---

## Overview

Phase 6 implements the canonical memory and context system per:
- AGENT_ENGINE_SPEC §4 (Context & Memory Semantics)
- AGENT_ENGINE_OVERVIEW §1.5 (Context Assembly)
- PROJECT_INTEGRATION_SPEC §3.4 (memory.yaml)

Memory v1 provides:
- **Three-tier memory architecture**: task-local, project-wide, global
- **Context Profiles**: Deterministic context slices per node
- **Retrieval Policies**: Recency-based deterministic retrieval (v1 only, no semantic/hybrid)
- **Token Budgeting**: HEAD/TAIL compression for context size management
- **Context Assembly**: Per-node context gathering integrated into node execution

---

## Existing State (from Phases 2-5)

### Already Implemented
1. **Memory Schema** (`src/agent_engine/schemas/memory.py`):
   - `ContextProfile`: Profile definition with id, max_tokens, retrieval_policy, sources
   - `ContextProfileSource`: Memory layer specification (task/project/global)
   - `ContextItem`, `ContextRequest`, `ContextPackage`: Context data structures
   - `MemoryStoreConfig`, `CompressionPolicy`, `ContextPolicy`: Configuration schemas

2. **Memory Stores Stubs** (`src/agent_engine/memory_stores.py`):
   - `MemoryStore`: Basic stub interface with get/put methods
   - `initialize_memory_stores()`: Creates default stores (task, project, global)
   - `initialize_context_profiles()`: Creates default profiles from config

3. **Runtime Memory Modules** (`src/agent_engine/runtime/memory/`):
   - `backend.py`: Abstract MemoryBackend + InMemoryBackend implementation
   - `task_store.py`: TaskMemoryStore for task-local context
   - `project_store.py`: ProjectMemoryStore for project-scoped context
   - `global_store.py`: GlobalMemoryStore for cross-project context

4. **ContextAssembler** (`src/agent_engine/runtime/context.py`):
   - Multi-tier context building with budget allocation
   - Item selection with HEAD/TAIL preservation
   - Task cleanup and metadata extraction

5. **Node Executor Integration** (`src/agent_engine/runtime/node_executor.py`):
   - Context assembly stage in node lifecycle (Step 2)
   - Context metadata recording in StageExecutionRecord

### Already Passing Tests
- 571 tests passing (580 existing from Phases 1-5 + memory stubs)
- Phase 3, 4, 5 tests all passing

---

## Phase 6 Implementation Steps

### Step 1: Enhance Memory Store Backend Implementation

**File:** `src/agent_engine/runtime/memory/backend.py`

**Current State:** Abstract MemoryBackend with InMemoryBackend stub

**Changes Required:**
1. Implement `InMemoryBackend` methods fully:
   - `put(item_id: str, item: Any)`: Store item with timestamp
   - `get(item_id: str) -> Optional[Any]`: Retrieve item by ID
   - `query(filters: Dict[str, Any], limit: int) -> List[ContextItem]`: Query items
   - `list_all() -> List[ContextItem]`: Get all items
   - `clear()`: Clear all items
   - `remove(item_id: str)`: Remove specific item

2. Add internal structure:
   - `items: Dict[str, ContextItem]`: Storage dictionary
   - `timestamps: Dict[str, str]`: Item timestamps

**Test Coverage (new tests):**
- Test put/get round-trip
- Test query with empty filters
- Test list_all returns correct count
- Test clear removes all items
- Test remove removes specific item
- Test timestamps are preserved

---

### Step 2: Implement TaskMemoryStore

**File:** `src/agent_engine/runtime/memory/task_store.py`

**Current State:** Stub with basic structure

**Changes Required:**
1. Implement full TaskMemoryStore class:
   - `task_id: str`: Identifier for this task's memory
   - `backend: MemoryBackend`: Item storage
   - `created_at: str`: Timestamp of creation

2. Implement methods:
   - `put(item: ContextItem)`: Add item to task memory
   - `get(item_id: str) -> Optional[ContextItem]`: Retrieve item
   - `list_all() -> List[ContextItem]`: Get all items (for context assembly)
   - `query(filters: Dict[str, Any], limit: int) -> List[ContextItem]`: Query with filters
   - `clear()`: Clear task memory on completion

3. Enforce invariants:
   - Items must have timestamps
   - Each item must be unique by item_id
   - Memory should not exceed reasonable limits (soft limit, no hard error)

**Test Coverage (new tests):**
- Test task memory isolation (different tasks have separate stores)
- Test put/list_all round-trip
- Test clear removes all items
- Test query with tag filters

---

### Step 3: Implement ProjectMemoryStore

**File:** `src/agent_engine/runtime/memory/project_store.py`

**Current State:** Stub with basic structure

**Changes Required:**
1. Implement full ProjectMemoryStore class:
   - `project_id: str`: Identifier for this project
   - `backend: MemoryBackend`: Item storage
   - `created_at: str`: Timestamp of creation
   - `last_accessed: str`: Last access timestamp

2. Implement methods:
   - `put(item: ContextItem)`: Add item to project memory
   - `get(item_id: str) -> Optional[ContextItem]`: Retrieve item
   - `list_all() -> List[ContextItem]`: Get all items
   - `query(filters: Dict[str, Any], limit: int) -> List[ContextItem]`: Query with filters
   - `access()`: Update last_accessed timestamp (call on every context assembly)

3. Enforce invariants:
   - Items must have timestamps
   - Each item must be unique by item_id
   - Items from any task within project are accessible

**Test Coverage (new tests):**
- Test project memory isolation (different projects have separate stores)
- Test put/list_all round-trip
- Test query returns items from multiple tasks
- Test access timestamp updates

---

### Step 4: Implement GlobalMemoryStore

**File:** `src/agent_engine/runtime/memory/global_store.py`

**Current State:** Stub with basic structure

**Changes Required:**
1. Implement full GlobalMemoryStore class:
   - `backend: MemoryBackend`: Item storage
   - `created_at: str`: Timestamp of creation

2. Implement methods:
   - `put(item: ContextItem)`: Add item to global memory
   - `get(item_id: str) -> Optional[ContextItem]`: Retrieve item
   - `list_all() -> List[ContextItem]`: Get all items
   - `query(filters: Dict[str, Any], limit: int) -> List[ContextItem]`: Query with filters

3. Enforce invariants:
   - Items must have timestamps
   - Each item must be unique by item_id
   - Shared across all projects and tasks

**Test Coverage (new tests):**
- Test global memory shared across tasks
- Test global memory shared across projects
- Test put/list_all round-trip
- Test query with tag filters

---

### Step 5: Enhance ContextAssembler - Profile Validation

**File:** `src/agent_engine/runtime/context.py`

**Current State:** ContextAssembler exists with build_context method

**Changes Required:**
1. Add method to validate and resolve context profiles:
   - `resolve_context_profile(context_spec: str, profiles: Dict[str, ContextProfile]) -> Optional[ContextProfile]`
   - Handle three cases:
     - If context_spec is "none" → return None
     - If context_spec is "global" → return built-in global profile
     - If context_spec is profile ID → return profile from dict or raise error
   - If profile references non-existent memory source → raise error

2. Add method for context profile validation:
   - `validate_context_profile(profile: ContextProfile) -> None`
   - Verify all sources reference valid memory layers (task/project/global)
   - Verify max_tokens > 0
   - Verify retrieval_policy is "recency" (v1 only)

**Test Coverage (new tests):**
- Test resolve "none" returns None
- Test resolve "global" returns global profile
- Test resolve profile ID returns correct profile
- Test resolve invalid profile ID raises error
- Test invalid retrieval_policy raises error
- Test invalid memory source raises error

---

### Step 6: Enhance ContextAssembler - Context Building

**File:** `src/agent_engine/runtime/context.py`

**Current State:** Basic build_context implementation

**Changes Required:**
1. Enhance context assembly to use profiles:
   - `build_context(task: Task, profile: Optional[ContextProfile]) -> ContextPackage`
   - If profile is None → return empty ContextPackage
   - If profile is specified:
     - Initialize from each source's memory layer
     - Collect all items from specified sources
     - Apply tag filtering per source
     - Sort by timestamp (recency policy - v1 only)
     - Apply HEAD/TAIL compression if configured
     - Select items until token budget exhausted
     - Return ContextPackage with metadata

2. Add helper method for item filtering:
   - `_filter_items_by_tags(items: List[ContextItem], tags: List[str]) -> List[ContextItem]`
   - If no tags specified → return all items
   - If tags specified → return items matching any tag

3. Add helper method for token budgeting:
   - `_select_within_token_budget(items: List[ContextItem], budget: int) -> List[ContextItem]`
   - Apply budget allocation across sources
   - Apply HEAD/TAIL compression if configured
   - Select items in order until budget exhausted

**Test Coverage (new tests):**
- Test build_context with None profile returns empty package
- Test build_context with profile assembles correct items
- Test tag filtering works correctly
- Test token budget is respected
- Test HEAD/TAIL compression preserves edges
- Test compression_ratio calculation

---

### Step 7: Integrate Context Assembly into Node Execution

**File:** `src/agent_engine/runtime/node_executor.py`

**Current State:** Context assembly stage exists but uses stubs

**Changes Required:**
1. Update NodeExecutor._execute_node to properly assemble context:
   - Call `context_assembler.resolve_context_profile()` to get profile
   - If profile not None:
     - Call `context_assembler.build_context(task, profile)`
     - Pass context to agent or deterministic handler
     - Record context metadata in StageExecutionRecord
   - If profile is None:
     - Pass empty/default context

2. Update agent_runtime.run_agent_stage() signature:
   - Add `context: Optional[ContextPackage]` parameter
   - Inject context into LLM prompt if provided

3. Update deterministic_registry methods:
   - Add `context: Optional[ContextPackage]` parameter to all operations
   - Available for custom logic but optional

**Test Coverage (new tests):**
- Test context assembly called for each node
- Test correct profile used per node
- Test context passed to agent
- Test empty context for "none" nodes
- Test context metadata recorded in history

---

### Step 8: Memory Write Operations

**File:** `src/agent_engine/runtime/node_executor.py` and task flow

**Current State:** Memory stores exist but no write operations

**Changes Required:**
1. Add method to write context items after node execution:
   - When node completes, optionally write output to memory
   - `write_to_memory(task: Task, node: Node, output: Any, memory_stores: Dict)`
   - If node has `write_to_memory` configuration:
     - Create ContextItem from output
     - Determine target store (task/project/global)
     - Write item to appropriate store

2. Update node execution flow:
   - After validation but before routing, check `write_to_memory` flag
   - Write output to specified memory layer

**Minimal v1 Implementation:**
- No configuration required (write operations optional)
- If specified, write node output as ContextItem to specified layer
- Node must have explicit `write_to_memory: {store: "task"|"project"|"global", tags: [...]}` in config

**Test Coverage (new tests):**
- Test write to task memory
- Test write to project memory
- Test write to global memory
- Test items appear in next node's context assembly

---

### Step 9: Context Profile Configuration Loading

**File:** `src/agent_engine/manifest_loader.py` and `src/agent_engine/engine.py`

**Current State:** Basic loading in memory_stores.py

**Changes Required:**
1. Update manifest_loader to properly parse memory.yaml:
   - Load context_profiles section
   - Validate each profile has required fields
   - Create ContextProfile objects
   - Store in engine.context_profiles dict

2. Update Engine.from_config_dir():
   - Pass loaded context_profiles to ContextAssembler
   - Pass memory_stores to ContextAssembler
   - Initialize task_stores and project_stores dicts

3. Update node execution to resolve profiles:
   - When executing node, call `context_assembler.resolve_context_profile(node.context)`
   - Handle "none", "global", and profile ID cases

**Test Coverage (new tests):**
- Test memory.yaml loads correctly
- Test profiles registered and accessible
- Test invalid profile references raise errors
- Test default profile creation when memory.yaml absent

---

### Step 10: Write Tests for Memory & Context

**File:** `tests/test_phase6_memory_context.py` (NEW)

**Test Categories:**

#### Backend Tests (5 tests)
- Test InMemoryBackend put/get round-trip
- Test list_all returns all items
- Test query with filters
- Test clear removes items
- Test remove removes item

#### TaskMemoryStore Tests (8 tests)
- Test task memory isolation
- Test put/list_all round-trip
- Test clear on completion
- Test query with tag filters
- Test multiple items per task
- Test timestamp preservation
- Test item overwrite
- Test concurrent task stores

#### ProjectMemoryStore Tests (8 tests)
- Test project memory isolation
- Test put/list_all round-trip
- Test cross-task visibility within project
- Test query returns correct items
- Test access timestamp updates
- Test multiple projects isolated
- Test timestamp preservation
- Test item overwrite

#### GlobalMemoryStore Tests (8 tests)
- Test global memory shared across all
- Test put/list_all round-trip
- Test query with tag filters
- Test cross-task visibility
- Test cross-project visibility
- Test timestamp preservation
- Test item overwrite
- Test scale with many items

#### ContextAssembler Tests (15 tests)
- Test profile resolution (none/global/profile_id)
- Test build_context with None profile returns empty
- Test build_context with profile assembles items
- Test tag filtering
- Test token budget respected
- Test HEAD/TAIL compression
- Test compression_ratio calculation
- Test multi-source context assembly
- Test budget allocation across sources
- Test item ordering (recency)
- Test profile validation
- Test invalid profile raises error
- Test max_tokens validation
- Test retrieval_policy validation
- Test memory source validation

#### Integration Tests (6 tests)
- Test context assembly in node execution
- Test context passed to agent
- Test context metadata in history
- Test multiple nodes each get correct context
- Test context updates across task execution
- Test memory cleanup on task completion

---

### Step 11: Run Full Test Suite and Fix Failures

**File:** All test files

**Changes Required:**
1. Run `python3 -m pytest tests/ -v`
2. Fix any failures related to:
   - Memory store interfaces
   - Context assembly
   - Profile resolution
   - History recording with context
3. Ensure all 580+ existing tests still pass
4. Ensure all 30+ new Phase 6 tests pass
5. Total: 610+ tests passing

**Success Criteria:**
- All tests pass
- No regressions from Phases 1-5
- Memory deterministic (recency-based ordering)
- Context assembly per-node correct
- Token budgeting enforced
- HEAD/TAIL compression functional

---

## Implementation Order

Execute steps sequentially:
1. ✅ Backend (supports all three store types)
2. ✅ TaskMemoryStore (task-local context)
3. ✅ ProjectMemoryStore (project-wide context)
4. ✅ GlobalMemoryStore (cross-project context)
5. ✅ Profile validation (resolve + validate methods)
6. ✅ Context building (enhanced per profiles)
7. ✅ Integration with NodeExecutor
8. ✅ Memory write operations (optional)
9. ✅ Profile configuration loading
10. ✅ Comprehensive test suite
11. ✅ Run and fix all tests

---

## Key Invariants (Canonical Constraints)

1. **Memory Isolation**: Task memory is per-task, project memory is per-project, global is shared
2. **Deterministic Retrieval**: v1 uses recency (timestamp) only, no semantic/hybrid
3. **Token Budgeting**: Context size never exceeds profile's max_tokens budget
4. **Context Read-Only**: Context passed to nodes must be read-only (no mutations)
5. **Profile Resolution**: Each node has exactly one of: profile ID, "global", or "none"
6. **No Implicit Behavior**: All context assembly driven by explicit profile configuration
7. **Complete History**: All context used recorded in StageExecutionRecord for replay

---

## Non-Goals (Phase 6 v1)

These are explicitly NOT implemented in Phase 6:
- Semantic/hybrid retrieval (future semantic search)
- Embedding generation/storage (future ML features)
- Multi-profile per node
- Dynamic profile selection
- Context mutation/updates by nodes
- Distributed memory backends
- Persistence across process restarts (in-memory only v1)

All of these are in **Future Work**.

---

## Acceptance Criteria

✅ Phase 6 is complete when:
- All three memory store types fully implemented
- ContextAssembler properly validates and resolves profiles
- Context assembly per-node integration complete
- Token budgeting enforced with HEAD/TAIL compression
- Deterministic recency-based retrieval working
- All 610+ tests passing (580 existing + 30 new)
- No regressions from Phases 1-5
- Memory v1 deterministic and repeatable
- History complete with context metadata

---

# END OF PHASE_6_IMPLEMENTATION_PLAN.md
