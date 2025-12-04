Here’s a pre-build audit plan you can drop in as `docs/operational/PLAN_AUDIT_AGENT_ENGINE.md` and follow before running the new build plan.

It’s focused on:

* Aligning **everything** to `AGENT_ENGINE_OVERVIEW.md`
* Classifying what’s **core engine vs example vs legacy**
* Killing or quarantining out-of-scope junk
* Making sure **tests are real tests**, not `pass`-stubs

---

# PLAN_AUDIT_AGENT_ENGINE

*Pre-build audit & cleanup for Agent Engine*

## 0. Goal & Scope

**Goal:**
Before implementing any new features, audit the repo to:

1. Ensure everything aligns with **AGENT_ENGINE_OVERVIEW.md** (canonical architecture).
2. Ensure **PLAN_BUILD_AGENT_ENGINE** is the roadmap and existing code fits into it.
3. Remove or quarantine anything that doesn’t belong in Agent Engine core.
4. Review all tests; delete or replace meaningless ones.
5. Produce a clear inventory of what already exists vs what still needs to be built.

**In scope (must be engine-aligned):**

* `src/agent_engine/**`
* `schemas/**`
* `configs/basic_llm_agent/**`
* `tests/**`
* `docs/canonical/AGENT_ENGINE_OVERVIEW.md`, `docs/canonical/RESEARCH.md` (canonical documentation - source of truth and research)
* `docs/operational/PLAN_BUILD_AGENT_ENGINE.md`
* `examples/**` (as examples only)
* `legacy/king_arthur/**` (must stay quarantined)

---

## 1. Lock Canonical References

1.1 Re-read **AGENT_ENGINE_OVERVIEW.md**

* Treat this as the **single source of truth** for architecture, components, and responsibilities.

1.2 Re-read **PLAN_BUILD_AGENT_ENGINE.md**

* Confirm it reflects the latest architecture from the overview.
* If anything in PLAN_BUILD_AGENT_ENGINE contradicts the overview, **update the plan**, not the overview.

1.3 Define classification labels to use during audit:

* `CORE_ENGINE` – belongs in `src/agent_engine/**`, directly supports the overview.
* `EXAMPLE_APP` – usage demos under `examples/**` and `configs/basic_llm_agent/**`.
* `LEGACY` – anything in `legacy/**` or Arthur-specific that should not influence Engine.
* `TO_REMOVE` – junk, placeholders, or out-of-scope code/tests that should be deleted.
* `TO_DECIDE` – ambiguous items to revisit at the end.

---

## 2. Documentation & Plans Audit

**Targets:**

* `docs/DOCUMENTATION_RULES.md`
* `docs/CHANGELOG.md`
* `docs/operational/README.md`
* `docs/operational/PLAN_BUILD_AGENT_ENGINE.md`
* Top-level `README.md`
* `schemas/SCHEMAS_OVERVIEW.md`

2.1 Check for contamination
For each doc:

* Flag any mention of:

  * Arthur-specific architecture as if it were current.
  * Legacy pipelines, roles, or behaviors not in the overview.
  * “Magic features” not specified in the overview (e.g., auto-evolution baked into core).

Classify each such passage as `TO_REMOVE` or `LEGACY_NOTE` (historical reference only).

2.2 Ensure docs describe **Agent Engine**, not “a particular app”

* `AGENT_ENGINE_OVERVIEW.md`: describes core engine only → OK.
* `PLAN_BUILD_AGENT_ENGINE.md`: must be clearly about **engine modules**, not about a specific “basic_llm_agent” app.
* `README.md`: confirm it introduces Agent Engine as a framework, not just the basic_llm_agent example.

2.3 Update or mark docs

* For each contaminated or off-scope section:

  * Either update the wording to match current architecture *or* mark it explicitly as `LEGACY`/historical and move to a legacy notes section if needed.
* Ensure `SCHEMAS_OVERVIEW.md` outlines the schema surfaces the build plan expects (agents, tools, workflows, tasks, memory, events, errors).

---

## 3. Configs & Example App Audit

**Targets:**

* `configs/basic_llm_agent/**`
* `examples/basic_llm_agent/**`

3.1 Verify they are **examples**, not core

* Check `configs/basic_llm_agent/*.yaml`:

  * Confirm they match the schema assumptions from `src/agent_engine/schemas/**`.
  * Confirm they represent a valid but **non-special** use of the engine (no weird shortcuts baked into schemas just for this example).

* Check `examples/basic_llm_agent/cli.py`:

  * Confirm it calls into core engine modules as a client, not as a place where “secret core logic” lives.

3.2 Align naming and semantics

* Ensure config keys (agent, tool, workflow, stage names) match the patterns in `schemas/**` and `AGENT_ENGINE_OVERVIEW`.
* If configs rely on fields/surfaces that are no longer part of the overview, mark them for update and tag the fields as `TO_REMOVE` or “example-only extension.”

3.3 Classify

* Mark `configs/basic_llm_agent/**` and `examples/basic_llm_agent/**` as `EXAMPLE_APP` in your notes.
* Any engine-ish logic hiding here should be moved into `src/agent_engine/**` in the build phase, not live permanently in `examples`.

---

## 4. Core Engine Code Audit (`src/agent_engine`)

**Targets:**

* `src/agent_engine/config_loader.py`
* `src/agent_engine/evolution.py`
* `src/agent_engine/json_engine.py`
* `src/agent_engine/patterns/**`
* `src/agent_engine/plugins/**`
* `src/agent_engine/runtime/**`
* `src/agent_engine/schemas/**`
* `src/agent_engine/security.py`
* `src/agent_engine/telemetry.py`
* `src/agent_engine/__init__.py`

For each module/file, answer:

> 1. Does this file directly support the architecture in AGENT_ENGINE_OVERVIEW?
> 2. Does anything in here hard-code a **pattern**, **app logic**, or **advanced behavior** that belongs in plugins/patterns instead?
> 3. Is the naming and API consistent with `schemas/**` and the build plan?

4.1 `schemas/**` audit

* Verify models cover:

  * Agent, Tool, Workflow, Stage, Task, Memory, Event, Errors, Registry, Overrides.
* Flag any schema fields that:

  * Are not mentioned in the overview.
  * Exist solely to support a specific example or pattern.
* Mark them as `TO_REMOVE`, `EXAMPLE_ONLY`, or `ADVANCED_PLUGIN`.

4.2 `runtime/**` audit

* `agent_runtime.py`, `tool_runtime.py`, `llm_client.py`, `pipeline_executor.py`, `router.py`, `task_manager.py`, `runtime/context.py`, `runtime/memory/**`:

For each:

* Ensure it describes **generic engine behavior**, not a specific usage pattern.
* Flag any code that:

  * Hard-codes committee/supervisor logic.
  * Assumes a particular pipeline shape beyond the DAG model.
  * Mixes app-specific decisions into core.

Classify:

* `CORE_ENGINE` – belongs here.
* `ADVANCED_PATTERN` – should move under `patterns/` later.
* `TO_REMOVE` – if it’s legacy or unused.

4.3 `patterns/**` audit

* `committee.py`, `supervisor.py`:

Ensure:

* These are **optional patterns** that depend only on core APIs.
* No other core module imports them directly.
* They can be cleanly disabled without breaking engine.

Classify them as `PATTERN_LIBRARY` (good) or refactor as needed.

4.4 `evolution.py` and `plugins/**`

* Confirm:

  * `evolution.py` is plugin-ish (optional), not required for engine to run.
  * `plugins/manager.py` implements generic plugin mechanics, not app-specific logic.

If `evolution.py` is too tightly coupled, mark it as `ADVANCED_PLUGIN` and plan to refactor in the build plan.

4.5 `security.py`, `telemetry.py`, `config_loader.py`, `json_engine.py`

* Ensure each aligns strictly with:

  * Security model in the overview.
  * Telemetry/Event Bus design.
  * Config/manifest loading and schema validation design.
  * JSON Engine responsibilities from RESEARCH and overview.

Flag anything that:

* Re-implements Arthur behavior.
* Expects configs not in `configs/basic_llm_agent` or schema definitions.
* Hardcodes logic that should be configuration or plugin-based.

---

## 5. Legacy Salvage & Containment Audit

**Targets:**

* `legacy/king_arthur/**`

5.1 Verify quarantine

* Confirm **no code under `src/agent_engine/**` imports from `legacy/king_arthur/**`.
* If it does, mark that import as `TO_REMOVE` or “to be replaced with proper engine module.”

5.2 Confirm salvage list

* Verify only these are allowed to be used as references for future refactors:

  * `core/manifest_hygiene.py`
  * `core/override_manager.py`
  * `core/override_parser.py`
  * `json_engine/*`
  * `toolkit/context.py`
  * `toolkit/file_context.py`
  * `toolkit/text_analysis.py`
  * `toolkit/token_utils.py`
  * `toolkit/filesystem.py`
  * `toolkit/json_io.py`
  * `toolkit/manifest_utils.py`
  * `toolkit/registry.py`
  * `toolkit/validation_utils.py`
  * `toolkit/version_utils.py`

Everything else in `legacy/` = historical reference only.

---

## 6. Tests Audit – Are These Real Tests?

**Targets:**

* `tests/**`

For **each** test file:

6.1 Categorize coverage

* Which engine components does it exercise?

  * config_loader/json_engine
  * schemas
  * runtime (agent, tool, pipeline, router)
  * memory stores
  * plugins/patterns
  * example basic_llm_agent

6.2 Detect fake tests

* Look for:

  * `pass` only tests
  * tests with no assertions
  * tests that only import modules and do nothing
  * tests that assert trivial things that never fail (`assert True`)

Mark such tests `TO_REMOVE` or `PLACEHOLDER`.

6.3 Check alignment with overview

* Does the test:

  * Assert behavior that matches AGENT_ENGINE_OVERVIEW?
  * Depend on legacy/Arthur semantics?
  * Expect patterns that should now be optional plugins?

If a test enforces legacy behavior, mark it as `TO_REMOVE` or `TO_REWRITE` in the build phase.

6.4 Create a test inventory
For each test file, create a row in a simple table (even just in a note):

* `file`
* `what_it_tests`
* `status` = {OK, PLACEHOLDER, LEGACY_BEHAVIOR, BROKEN, TO_REWRITE}

---

## 7. Inventory & Gap Analysis

7.1 Make a “Current State” summary

* For each major engine area:

  * Config & schemas
  * Workflow graph & executor
  * Runtime (agents, tools, tasks)
  * Memory & context
  * Telemetry & plugins
  * Security
  * Patterns
  * Example app

Note:

* What exists and seems solid (`CORE_ENGINE_OK`)
* What exists but is misaligned (`TO_REWRITE`)
* What is missing entirely (`TODO_NEW`)

7.2 Cross-check against PLAN_BUILD_AGENT_ENGINE

* For each phase in the build plan, map:

  * “Already built & aligned”
  * “Built but misaligned → refactor”
  * “Not built yet”

7.3 Decide fates for `TO_REMOVE` items

* Make a short list:

  * Files/sections to delete
  * Files to move to `legacy/`
  * Tests to remove or fully rewrite

---

## 8. Cleanup Pass (No New Features)

8.1 Apply **mechanical** changes only

* Delete clearly useless tests (`pass`-only, no assertions) and mark them in CHANGELOG.
* Remove or move obviously out-of-scope files (e.g., stray app-layer logic in core).
* Update docs that are obviously wrong / stale.

8.2 Do **not** implement new features here

* No new runtime behavior
* No new patterns
* No new plugins
  This phase is **audit + cleanup**, not build.

8.3 Run the full test suite

* Confirm it still runs.
* Expect failures where tests were asserting legacy or misaligned behavior → note these as targets for the build plan.

---

## 9. Output Artifacts

By the end of this audit phase, you should have:

1. Updated **PLAN_BUILD_AGENT_ENGINE.md** if needed.
2. A short **AUDIT_SUMMARY.md** (in `docs/operational/`) with:

   * Core engine status by component
   * Files/tests marked for removal or rewrite
   * Confirmed example-only components
3. A cleaned test suite with no pure placeholders.
4. A repo where **everything that remains is either:**

   * valid engine-core,
   * clearly marked example app, or
   * quarantined legacy.
