# ✅ **PHASE 2 IMPLEMENTATION BRIEF — Task Persistence & Resumability**

**Executor:** Qwen2.5-Coder-7B (Act Mode)
**Planner:** Claude Sonnet (Plan Mode)
**Scope:** Implement missing persistence logic in the Task system

---

# **SECTION 1 — OVERVIEW & SUMMARY (HUMAN-READABLE)**

Phase 2 adds **persistent, file-backed task storage** so that any running workflow can be:

* checkpointed
* restored after crashes
* inspected afterward
* enumerated for project history

The schema layer, config loader, and validation system are already complete.
Qwen only needs to modify:

* `src/agent_engine/schemas/task.py`
* `src/agent_engine/runtime/task_manager.py`

The deliverables are:

* JSON-safe task serialization (`to_dict` / `from_dict`)
* Checkpoint save/load
* Task listing
* Metadata inspection
* Minimal, deterministic directory convention under `.agent_engine/tasks/`

This brief ensures that Qwen implements only what is required, without modifying unrelated engine components.

---

# **SECTION 2 — PHASED IMPLEMENTATION PLAN (HUMAN-READABLE)**

## **Phase 2.1 — Add Serialization to Task Schema**

Modify `src/agent_engine/schemas/task.py` by adding:

* `to_dict()` → uses `model_dump(mode="json")`
* `from_dict()` → classmethod using `model_validate()`

This enables all downstream persistence logic.

**Success Conditions:**

* Round-trip serialization is lossless
* No modifications to existing fields or structure

---

## **Phase 2.2 — Introduce Project ID Extraction Helper**

Modify `src/agent_engine/runtime/task_manager.py`:

* Add `_extract_project_id(task_id)` above `TaskManager`
* Follows naming convention: `task-{spec_id}-{uuid}`
* Falls back to `"default"` on malformed IDs

**Success Conditions:**

* Correct handling of multi-segment spec IDs
* No filesystem-unsafe output

---

## **Phase 2.3 — Implement save_checkpoint()**

Add method to `TaskManager`:

* Serializes task
* Ensures directory exists
* Writes JSON file
* Returns `EngineError` rather than raising exceptions

**Success Conditions:**

* Writes valid JSON
* Handles missing task gracefully
* Includes file path in error details

---

## **Phase 2.4 — Implement load_checkpoint()**

Add method to `TaskManager`:

* Reads/validates the file
* Reconstructs Task using `from_dict()`
* Returns `(Task, None)` or `(None, EngineError)`

**Success Conditions:**

* Proper error codes: JSON, VALIDATION, UNKNOWN
* Restores into `self.tasks` dict

---

## **Phase 2.5 — Implement list_tasks()**

Add method to list all tasks for a project:

* Returns empty list if project directory does not exist
* Returns sorted task IDs

**Success Conditions:**

* No errors for missing directories
* Must not modify filesystem

---

## **Phase 2.6 — Implement get_task_metadata()**

Add lightweight metadata extractor:

* Reads JSON
* Returns only: `task_id`, `status`, `pipeline_id`, `created_at`, `updated_at`

**Success Conditions:**

* Does not deserialize entire Task
* Handles corrupt JSON gracefully

---

## **Phase 2.7 — Add Test Suite**

Create: `tests/test_task_persistence.py`

Include tests for:

* round-trip serialization
* correct directory creation
* missing file cases
* corrupt JSON
* listing tasks
* metadata extraction
* project ID parsing

---

# **SECTION 3 — QWEN IMPLEMENTATION PROMPTS (COPY-PASTE INTO ACT MODE)**

Each of these prompts is **one Act-Mode job**. Do them in order.

---

## **🧩 Prompt 1 — Implement Task Serialization**

```
Context:
- @/src/agent_engine/schemas/task.py
- @/docs/operational/PHASE_2_TASK_PERSISTENCE_BRIEF.md

Task:
Implement Task.to_dict() and Task.from_dict() exactly as specified in Section 2.1 of the brief.

Requirements:
- Use model_dump(mode="json") for serialization.
- Use model_validate() for deserialization.
- Do not modify any other parts of the schema or add dependencies.

Output:
- A unified diff modifying only src/agent_engine/schemas/task.py
```

---

## **🧩 Prompt 2 — Add Project ID Extraction Helper**

```
Context:
- @/src/agent_engine/runtime/task_manager.py
- @/docs/operational/PHASE_2_TASK_PERSISTENCE_BRIEF.md

Task:
Add the _extract_project_id(task_id) helper function before the TaskManager class, per Section 2.2.

Output:
- A unified diff modifying only src/agent_engine/runtime/task_manager.py
```

---

## **🧩 Prompt 3 — Implement save_checkpoint()**

```
Context:
- @/src/agent_engine/runtime/task_manager.py
- @/docs/operational/PHASE_2_TASK_PERSISTENCE_BRIEF.md

Task:
Implement save_checkpoint() with full error handling logic from Section 2.3.

Output:
- A unified diff modifying only src/agent_engine/runtime/task_manager.py
```

---

## **🧩 Prompt 4 — Implement load_checkpoint()**

```
Context:
- @/src/agent_engine/runtime/task_manager.py
- @/docs/operational/PHASE_2_TASK_PERSISTENCE_BRIEF.md

Task:
Implement load_checkpoint() exactly as specified in Section 2.4.

Output:
- A unified diff modifying only src/agent_engine/runtime/task_manager.py
```

---

## **🧩 Prompt 5 — Implement list_tasks()**

```
Context:
- @/src/agent_engine/runtime/task_manager.py
- @/docs/operational/PHASE_2_TASK_PERSISTENCE_BRIEF.md

Task:
Implement list_tasks() from Section 2.5.

Output:
- A unified diff modifying only src/agent_engine/runtime/task_manager.py
```

---

## **🧩 Prompt 6 — Implement get_task_metadata()**

```
Context:
- @/src/agent_engine/runtime/task_manager.py
- @/docs/operational/PHASE_2_TASK_PERSISTENCE_BRIEF.md

Task:
Add get_task_metadata() as defined in Section 2.6, returning only the required metadata fields.

Output:
- A unified diff modifying only src/agent_engine/runtime/task_manager.py
```

---

## **🧩 Prompt 7 — Create Persistence Test Suite**

```
Context:
- @/tests/
- @/docs/operational/PHASE_2_TASK_PERSISTENCE_BRIEF.md

Task:
Create tests/test_task_persistence.py implementing all tests described in Section 2.7.

Output:
- A diff creating tests/test_task_persistence.py
```
