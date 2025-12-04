# PHASE 0 INTEGRATION PLAN

**Created:** 2025-12-03
**Status:** Ready for Implementation
**Phase:** 0C - Integration Implementation

---

## Executive Summary

Based on analysis of 24 legacy files, we're salvaging **8 high-value utility modules** that fill critical gaps in the current Agent Engine. These modules are generic, well-tested, and require minimal adaptation.

**Scope:** Phase 0C focuses on **utilities only** - no major architectural changes, no breaking changes to existing code.

**Effort Estimate:** 8-12 hours with parallel minion execution

---

## Approved Salvage List

### Category A: Copy As-Is (Trivial)

| # | Source | Target | Lines | Complexity | Changes |
|---|--------|--------|-------|------------|---------|
| 1 | `toolkit/token_utils.py` | `utils/token_utils.py` | 80 | TRIVIAL | None |
| 2 | `toolkit/text_analysis.py` | `utils/text_analysis.py` | 120 | TRIVIAL | None |
| 3 | `toolkit/version_utils.py` | `utils/version_utils.py` | 51 | TRIVIAL | None |

**Justification:** These are pure utility functions with no external dependencies. Zero Arthur-specific code detected.

### Category B: Extract & Adapt (Low Complexity)

| # | Source | Target | Lines | Complexity | Changes |
|---|--------|--------|-------|------------|---------|
| 4 | `toolkit/filesystem.py` | `utils/filesystem_safety.py` | ~150 | LOW | Extract validation functions only |
| 5 | `toolkit/json_io.py` | `utils/json_io.py` | 74 | LOW | Adapt error types |
| 6 | `toolkit/log_utils.py` | `utils/logging_utils.py` | 100 | LOW | Adapt return types |

**Justification:** Minimal adaptation required - mostly removing tool wrapper layer and adjusting return types.

### Category C: Refactor & Integrate (Medium Complexity)

| # | Source | Target | Lines | Complexity | Changes |
|---|--------|--------|-------|------------|---------|
| 7 | `toolkit/file_context.py` | `utils/file_context.py` | 250 | MEDIUM | Remove ArthurConfig, simplify |
| 8 | `toolkit/prompt_helpers.py` | `utils/prompt_builders.py` | 200 | MEDIUM | Adapt to SCHEMA_REGISTRY |

**Justification:** Requires refactoring dependencies but core logic is generic and valuable.

---

## Implementation Tasks

### Task 1: Create utils/ Module Structure

**Minion:** Infrastructure Setup Minion

**Actions:**
1. Create `/home/ndev/agent_engine/src/agent_engine/utils/` directory
2. Create `__init__.py` with exports
3. Update `/home/ndev/agent_engine/src/agent_engine/__init__.py` to export utils

**Files to create:**
```
src/agent_engine/utils/
├── __init__.py
├── token_utils.py
├── text_analysis.py
├── version_utils.py
├── filesystem_safety.py
├── json_io.py
├── logging_utils.py
├── file_context.py
└── prompt_builders.py
```

**Acceptance Criteria:**
- ✓ utils/ module exists
- ✓ All 8 files created (can be empty stubs initially)
- ✓ __init__.py exports all utilities
- ✓ No import errors

---

### Task 2: Copy Trivial Utilities

**Minion:** Copy Utilities Minion

**Actions:**

**2.1: token_utils.py**
- Source: `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/token_utils.py`
- Target: `/home/ndev/agent_engine/src/agent_engine/utils/token_utils.py`
- Changes: None (copy as-is)
- Functions: `estimate_tokens_rough()`, `estimate_tokens_messages()`, `estimate_prompt_tokens()`, `estimate_tokens()`, `CHARS_PER_TOKEN`

**2.2: text_analysis.py**
- Source: `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/text_analysis.py`
- Target: `/home/ndev/agent_engine/src/agent_engine/utils/text_analysis.py`
- Changes: None (copy as-is)
- Functions: `extract_keywords()`, `calculate_relevance_score()`, `STOP_WORDS`

**2.3: version_utils.py**
- Source: `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/version_utils.py`
- Target: `/home/ndev/agent_engine/src/agent_engine/utils/version_utils.py`
- Changes: None (copy as-is)
- Functions: `parse_version()`, `compare_versions()`, `is_compatible()`

**Acceptance Criteria:**
- ✓ Files copied with full content
- ✓ Imports work correctly
- ✓ Unit tests pass (create simple smoke tests)

---

### Task 3: Extract Filesystem Safety Utilities

**Minion:** Filesystem Safety Minion

**Source:** `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/filesystem.py`
**Target:** `/home/ndev/agent_engine/src/agent_engine/utils/filesystem_safety.py`

**Functions to Extract:**

1. **`validate_path_traversal(workspace_root: Path, target_path: str) -> Tuple[bool, Optional[str], Optional[Path]]`**
   - Extract from lines ~50-80
   - Keep validation logic intact
   - Return: (is_valid, error_message, resolved_path)

2. **`is_binary_file(path: Path) -> bool`**
   - Extract from lines ~100-130
   - Keep extension check + content sampling
   - Return: bool

3. **`resolve_safe_path(workspace_root: Path, rel_path: str) -> Tuple[bool, str, Optional[Path]]`**
   - Wrapper combining validation + resolution
   - Return: (is_safe, error_or_success_msg, resolved_path)

4. **Constants:**
   - `SKIP_EXTENSIONS` - Binary file extension set
   - `DEFAULT_MAX_READ_BYTES = 50_000`
   - `DEFAULT_MAX_WRITE_BYTES = 1_000_000`

**Changes Required:**
- Remove `ToolResult` wrappers
- Remove tool registration functions
- Keep pure validation/detection functions
- Add type hints if missing
- Update docstrings to reference Agent Engine

**Acceptance Criteria:**
- ✓ Path traversal attacks blocked (test: `../../etc/passwd`)
- ✓ Binary files detected correctly
- ✓ Symlink escapes prevented
- ✓ Unit tests pass

---

### Task 4: Adapt JSON I/O Helpers

**Minion:** JSON I/O Minion

**Source:** `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/json_io.py`
**Target:** `/home/ndev/agent_engine/src/agent_engine/utils/json_io.py`

**Functions to Adapt:**

1. **`read_json_safe(path: Path, default: Any = None) -> Tuple[Any, Optional[str]]`**
   - Source: `safe_read_json()`
   - Change return from `(value, JSONError)` to `(value, Optional[str])`
   - Keep fallback to default on error

2. **`write_json_safe(path: Path, data: Any, indent: int = 2) -> Tuple[bool, Optional[str]]`**
   - Source: `safe_write_json()`
   - Change return from `ToolResult` to `(success: bool, error: Optional[str])`
   - Keep directory creation logic

3. **`validate_json_structure(data: Any, required_keys: List[str]) -> Tuple[bool, List[str]]`**
   - Copy as-is
   - Return: (is_valid, missing_keys)

**Changes Required:**
- Remove `from toolkit.base import ToolResult, JSONError`
- Replace return types
- Keep all functional logic
- Update docstrings

**Acceptance Criteria:**
- ✓ Reads JSON with fallback
- ✓ Writes JSON with directory creation
- ✓ Validates structure correctly
- ✓ Unit tests pass

---

### Task 5: Adapt Logging Utilities

**Minion:** Logging Utils Minion

**Source:** `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/log_utils.py`
**Target:** `/home/ndev/agent_engine/src/agent_engine/utils/logging_utils.py`

**Functions to Adapt:**

1. **`auto_cleanup_empty_log(path: Path, check_fn: Callable) -> bool`**
   - Source: same name
   - Change return from `ToolResult` to `bool`

2. **`safe_append_log(path: Path, content: str, encoding: str = "utf-8") -> Tuple[bool, Optional[str]]`**
   - Source: same name
   - Change return from `ToolResult` to tuple
   - Keep directory creation logic

3. **`rotate_log_if_needed(path: Path, max_size: int, keep_count: int = 3) -> Tuple[bool, Optional[str], Dict[str, Any]]`**
   - Source: same name
   - Change return from `ToolResult` to tuple with metadata dict
   - Keep rotation logic (rename to .1, .2, etc.)

**Changes Required:**
- Remove `from toolkit.base import ToolResult`
- Simplify return types
- Keep all rotation/cleanup logic
- Update docstrings

**Acceptance Criteria:**
- ✓ Appends to log files safely
- ✓ Rotates when exceeding size
- ✓ Cleans up empty logs
- ✓ Unit tests pass

---

### Task 6: Refactor File Context Extraction

**Minion:** File Context Minion

**Source:** `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/file_context.py`
**Target:** `/home/ndev/agent_engine/src/agent_engine/utils/file_context.py`

**Classes to Refactor:**

1. **`FileRelevance` dataclass**
   - Copy as-is

2. **`FileContextExtractor` class**
   - Keep: `scan_workspace_files()`, `score_file_relevance()`, `extract_file_context()`
   - Remove: ArthurConfig dependency, embedding backend
   - Simplify: Mode-aware thresholds (use simple dict instead of config object)

**Changes Required:**
- Remove `from king_arthur_orchestrator.infra.config import ArthurConfig`
- Replace with simple mode dict:
  ```python
  MODE_THRESHOLDS = {
      "cheap": {"inline_max": 2000, "snippet_max": 5000},
      "balanced": {"inline_max": 10000, "snippet_max": 30000},
      "max_quality": {"inline_max": 50000, "snippet_max": 100000}
  }
  ```
- Remove embedding scoring (keep keyword-only)
- Update `extract_keywords()` import to use local `text_analysis.py`

**Acceptance Criteria:**
- ✓ Scans workspace files with filtering
- ✓ Scores relevance by keywords
- ✓ Extracts content in three modes (inline/snippet/summary)
- ✓ Respects mode-specific size thresholds
- ✓ Unit tests pass

---

### Task 7: Refactor Prompt Builders

**Minion:** Prompt Builders Minion

**Source:** `/home/ndev/king_arthurs_table/src/king_arthur_orchestrator/toolkit/prompt_helpers.py`
**Target:** `/home/ndev/agent_engine/src/agent_engine/utils/prompt_builders.py`

**Functions to Refactor:**

1. **`_resolve_ref(ref_path: str, full_schema: dict) -> dict`**
   - Copy as-is (JSON Schema $ref resolution)

2. **`_generate_json_skeleton(schema: dict, include_descriptions: bool, full_schema: dict) -> str`**
   - Copy as-is (generates example JSON from schema)

3. **`json_context(schema_id: str, include_full_schema: bool, include_skeleton: bool) -> str`**
   - Adapt schema loading:
     ```python
     # Old:
     contract = JsonContract.load(schema_id)
     # New:
     from agent_engine.schemas import SCHEMA_REGISTRY
     pydantic_model = SCHEMA_REGISTRY.get(schema_id)
     if not pydantic_model:
         return f"\n\nResponse must be valid JSON matching schema: {schema_id}"
     schema = pydantic_model.model_json_schema()
     ```
   - Keep all skeleton generation logic

4. **`json_only_instruction() -> str`**
   - Copy as-is

5. **`wrap_with_json_requirement(base_prompt: str, schema_id: str, mode: str) -> str`**
   - Adapt schema loading as above
   - Keep wrapping logic

6. **`validate_prompt_has_json_instruction(prompt: str) -> bool`**
   - Copy as-is

**Changes Required:**
- Remove `from king_arthur_orchestrator.json_engine.contracts import JsonContract`
- Add `from agent_engine.schemas import SCHEMA_REGISTRY`
- Replace all `JsonContract.load()` calls with `SCHEMA_REGISTRY.get()` + `model_json_schema()`
- Update docstrings to reference Pydantic models

**Acceptance Criteria:**
- ✓ Generates JSON skeletons from schemas
- ✓ Resolves $ref correctly
- ✓ Wraps prompts with JSON requirements
- ✓ Works with current SCHEMA_REGISTRY
- ✓ Unit tests pass

---

## Testing Strategy

### Unit Tests Required

**Create:** `/home/ndev/agent_engine/tests/utils/` directory

**Test Files:**

1. **`test_token_utils.py`** (Minion: Test Writer A)
   - Test estimate_tokens_rough() with various text lengths
   - Test estimate_tokens_messages() with different message formats
   - Test estimate_prompt_tokens() with system/messages/tools

2. **`test_text_analysis.py`** (Minion: Test Writer A)
   - Test extract_keywords() with stop words
   - Test calculate_relevance_score() with various inputs
   - Test keyword extraction from code vs natural language

3. **`test_version_utils.py`** (Minion: Test Writer A)
   - Test parse_version() with valid/invalid formats
   - Test compare_versions() all orderings
   - Test is_compatible() with major/minor matching

4. **`test_filesystem_safety.py`** (Minion: Test Writer B)
   - Test path traversal attacks (../, symlinks)
   - Test binary file detection
   - Test path resolution
   - Test workspace boundary enforcement

5. **`test_json_io.py`** (Minion: Test Writer B)
   - Test safe read with fallback
   - Test safe write with directory creation
   - Test structure validation
   - Test error handling (permissions, corrupt JSON)

6. **`test_logging_utils.py`** (Minion: Test Writer B)
   - Test log append
   - Test log rotation
   - Test empty log cleanup
   - Test edge cases (permissions, missing dirs)

7. **`test_file_context.py`** (Minion: Test Writer C)
   - Test workspace scanning
   - Test relevance scoring
   - Test extraction modes (inline/snippet/summary)
   - Test mode thresholds
   - Test skip patterns

8. **`test_prompt_builders.py`** (Minion: Test Writer C)
   - Test skeleton generation
   - Test $ref resolution
   - Test prompt wrapping
   - Test with real schemas (TaskSpec, ToolDefinition)

**Test Coverage Target:** >85% for all utility modules

---

## Integration with Current Codebase

### No Breaking Changes

**Guarantee:** All existing code continues to work without modification.

**Integration Points (Optional Enhancements):**

1. **ContextAssembler** can use `file_context.py` for file discovery
2. **AgentRuntime** can use `prompt_builders.py` for structured prompts
3. **ConfigLoader** can use `version_utils.py` for schema versioning
4. **Security** can use `filesystem_safety.py` for path validation
5. **Telemetry** can use `logging_utils.py` for event logging

**No Immediate Integration Required:** Utilities are standalone. Integration is future enhancement.

---

## Minion Assignments (Phase 0C)

### Parallel Track 1: Trivial Copies (2 hours)

**Minion A: Infrastructure + Trivial Copies**
- Task 1: Create utils/ structure
- Task 2.1: Copy token_utils.py
- Task 2.2: Copy text_analysis.py
- Task 2.3: Copy version_utils.py

### Parallel Track 2: Low Complexity Adaptations (3-4 hours)

**Minion B: Filesystem & JSON**
- Task 3: Extract filesystem_safety.py
- Task 4: Adapt json_io.py

**Minion C: Logging**
- Task 5: Adapt logging_utils.py

### Parallel Track 3: Medium Complexity Refactors (4-5 hours)

**Minion D: File Context**
- Task 6: Refactor file_context.py

**Minion E: Prompt Builders**
- Task 7: Refactor prompt_builders.py

### Parallel Track 4: Testing (3-4 hours)

**Minion F: Test Writer A**
- Tests for token_utils, text_analysis, version_utils

**Minion G: Test Writer B**
- Tests for filesystem_safety, json_io, logging_utils

**Minion H: Test Writer C**
- Tests for file_context, prompt_builders

---

## Success Criteria

**Phase 0C Complete When:**

- ✓ All 8 utility modules created in `src/agent_engine/utils/`
- ✓ All modules pass import tests
- ✓ All 8 test files created with >85% coverage
- ✓ All tests pass
- ✓ No breaking changes to existing code
- ✓ Documentation updated (docstrings in place)
- ✓ CHANGELOG.md updated with Phase 0C completion

---

## Deferred Items (Not Phase 0C)

These are valuable but deferred to future phases:

1. **JSON Engine Advanced** → Phase 2+ (research enhancement)
2. **Manifest Hygiene** → Phase 1 (quality-of-life)
3. **Override System** → Phase 1 (plugin layer)
4. **Built-in Tools** → Phase 1 (convenience layer)
5. **Semantic Memory** → Phase 2+ (advanced retrieval)
6. **Token Budget Manager** → Phase 2+ (optimization)
7. **Tool Registry with Consent** → Phase 1+ (complex feature)

**Rationale:** Core engine functions without these. They're enhancements, not requirements.

---

## Risk Assessment

**Low Risk:**
- Utilities are standalone
- No architectural changes
- No breaking changes
- All salvaged code is well-tested in production (King Arthur)

**Mitigation:**
- Parallel execution reduces calendar time
- Comprehensive tests catch integration issues
- Unit-first approach validates each module independently

---

## Timeline

**Sequential:** 14-18 hours
**Parallel (8 minions):** 5-6 hours calendar time

**Recommended:** Launch all 8 minions in parallel for maximum efficiency.

---

## Ready for Phase 0C Execution

**Command:** "Launch Phase 0C implementation" to start 8 minions in parallel.
