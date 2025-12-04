# Agent Engine Integration Plan (JSON, Toolkit, Overrides, Manifest Hygiene)

Goal: integrate the retained King Arthur modules into Agent Engine without inheriting brittle wiring. Prefer re-implementing thin glue layers inside Agent Engine over keeping questionable or tightly-coupled code. Use the plan below as a checklist before moving any file out of `legacy/king_arthur/`.

## Guiding Principles
- **Namespace cleanly**: port semantics into `agent_engine.*` packages; avoid runtime imports back to `king_arthur_orchestrator`.
- **Rewrite brittle glue**: where a module references missing helpers (e.g., `toolkit.workspace`, `infra.config`), re-create minimal Agent Engine equivalents instead of shimming to the old ones.
- **Schema-first orchestration**: treat JSON contracts as the single source of truth for stage IO; upgrade/extend schemas as needed rather than ad-hoc patches.
- **Tool safety parity**: enforce consent, workspace boundaries, and deterministic execution through Agent Engine’s own registries before exposing any toolkit tool.
- **Telemetry + tests**: add regression tests + validations in Agent Engine for every imported component (schemas, filesystem ops, plan validators, overrides).
- **Audit thoroughly**: before and after each integration milestone run `rg -n "king_arthur" src/ tests/ docs/` (and similar searches like `rg -n "Arthur"`) to catch lingering namespace references or assumptions.

## Workstream Breakdown

### 0. Pre-flight & Tracking
1. Catalog every file in `legacy/king_arthur/` and map it to an Agent Engine destination; document this mapping in a new design note (e.g., `docs/design/PORTED_KING_ARTHUR_COMPONENTS.md`) so reviewers can audit the moves without touching canonical docs.
2. Add a living checklist (PR-linked) that tracks which modules are ported, rewritten, or superseded. Update it whenever a component moves so future contributors know what remains in `legacy/king_arthur/`.
3. Maintain the `INTEGRATION_PLAN.md` status section whenever significant scope changes occur.

### 1. JSON Engine + Schemas
1. Replicate the schema tree under `agent_engine/json_engine/schemas` and register it inside Agent Engine’s packaging config.
2. Rewrite imports in `gateway.py`, `contracts.py`, `utils.py`, and `medic.py` to point at `agent_engine` modules.
3. Replace Arthur-specific dependencies:
   - Swap `ClaudeClient` usage for Agent Engine’s LLM clients; expose a backend interface that can wrap Anthropic, OpenAI, or mock clients.
   - Rebuild `ArthurCostMode` as `EngineCostMode` that matches Agent Engine modes.
4. Add Agent Engine telemetry hooks (JSON parse metrics, schema IDs) before executing fallback logic.
5. Create unit tests covering constrained generation fallback flow, JSONMedic deterministic repairs, and schema validation errors.

### 2. Toolkit (filesystem, execution, registry, plan validation, task intent, helpers)
1. Migrate deterministic tools into `agent_engine/toolkit/` preserving consent policies but rewriting the base `Tool`/`ToolResult` types to Agent Engine’s definitions.
2. Review each helper for missing deps (e.g., `toolkit.workspace`, `infra.models.ExecutionPlan`). Prefer building new minimal replacements inside Agent Engine instead of copying the entire Arthur stacks.
3. For filesystem + execution modules:
   - Implement the outstanding TODOs (shebang + chmod for new python files, undo metadata) before exposing writes.
   - Update dangerous-command patterns and consent prompts to align with Agent Engine’s CLI UX.
4. For `registry.py`, wire it into Agent Engine’s tool runtime: integrate with consent manager, logging, and Router instrumentation.
5. Add tests for: path traversal prevention, binary detection, bash safety, plan validation (including failure cases), and task intent edge cases.

### 3. Overrides (manager + parser)
1. Place the override manager/parser inside `agent_engine/core/overrides/`.
2. Adapt storage paths (`.arthur/...`) to Agent Engine’s config directories and update serialization format if needed.
3. Extend parser configuration to read from Agent Engine settings; re-implement any missing config loaders rather than importing Arthur configs.
4. Add tests to ensure overrides persist per-scope, survive restarts, and reject malformed directives.

### 4. Manifest Hygiene
1. Relocate `manifest_hygiene.py` under `agent_engine/core/manifest_hygiene.py`.
2. Replace dependencies on `round_table` helpers with Agent Engine’s manifest loader; if equivalent APIs do not exist, build new loader functions with clearer typing.
3. Review hygiene checks and remove/replace any Arthur-only categories; extend checks with Agent Engine-specific constraints (workflow DAG hints, schema alignment, consent docs).
4. Wire hygiene audits into CI (e.g., a `make manifest-hygiene` target) and ensure failures block merges.

### 5. Dependency + Import Cleanup
1. After relocating code, run `rg 'king_arthur_orchestrator' -n` to confirm no stale imports remain.
2. Update `pyproject.toml` / packaging to include the new packages and ensure `jsonschema` (if missing) is declared as a dependency.
3. Re-run `make lint test typecheck`; fix any typing gaps introduced by the new modules.

### 6. Validation & Rollout
1. Add golden-path tests for the JSON gateway + toolkit functions.
2. Instrument telemetry to confirm schema IDs, tool consent decisions, and override usage are being logged as expected.
3. Create integration notes in a new operational/design doc (e.g., `docs/operational/PLAN_KA_INTEGRATION_NOTES.md` and/or `docs/design/AGENT_ENGINE_JSON_TOOLKIT.md`) summarizing behavior changes so canonical docs can be updated later in a focused review.
