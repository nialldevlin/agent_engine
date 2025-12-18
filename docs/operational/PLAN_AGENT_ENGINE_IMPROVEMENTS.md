# PLAN_AGENT_ENGINE_IMPROVEMENTS.md

Status: draft  
Owner: Claude Sonnet (PLAN MODE)  
Source of truth: `help_chatbot` test log shared in the user report.

## Goals
- Close the observability, timeout, and progress gaps uncovered by the 70-second RAG run so the framework can surface live tool state and finish faster.
- Provide concrete workstreams for telemetry, tool defaults, streaming I/O, instrumentation, cancellation, and adaptive heuristics prioritized by the user data.
- Keep changes aligned with existing tool_runtime/telemetry contracts so Haiku (or another implementer) can follow Sonnet’s detailed implementation brief.

## Workstream 1: Tool Timeout Visibility & Feedback (Priority: HIGH)
- Review `tool_runtime.py` around `self._execute_with_timeout` (current call at line ~215) to understand how handler execution is wrapped today.
- Extend `telemetry.py` with a `tool_progress` event that records `task_id`, `node_id`, `tool_id`, a percentage, and a human-friendly message so the inspector/LLM can display live updates.
- Replace `_execute_with_timeout` with `_execute_with_timeout_and_progress` (or similar) that:
  * Accepts optional callbacks for progress reports from handlers.
  * Emits a `tool_progress` event every 5 seconds for tools running longer than 60 seconds, including elapsed time/timeout threshold.
  * Includes reporting hooks so the tool runtime can say “search_codebase running (15s/60s limit)” without waiting for completion.
- Ensure the timeout infrastructure still converts `TimeoutError`→`EngineError` and that telemetry/data stores capture both the signal and any partial results produced by the handler.

## Workstream 2: Configurable Tool Timeout Defaults (Priority: MEDIUM)
- Source `tool_runtime.Timeout` default logic (currently `timeout = tool_config.get("timeout", getattr(tool_def, 'timeout', None))`) and document missing timeouts.
- Extend `tools.yaml` (or `config/tools*.yaml`) with declarative hints: `timeout`, `timeout_action` (warn/abort/extend), and `long_running`.
- When a tool lacks an explicit timeout, log/warn via telemetry and apply a configurable default (e.g., 300s) rather than letting it run indefinitely.
- Respect `timeout_action` semantics by either warning, aborting immediately, or extending the deadline, and ensure documentation/tooling explains the choices.

## Workstream 3: Streaming & Progressive Tool Results (Priority: MEDIUM)
- Update `tool_runtime` so handlers can return generators/async iterators that emit dictionaries with `type` (`progress`, `partial`, `final`) and optional payloads.
- Ensure `ToolRuntime` forwards `partial` messages immediately to the LLM client (via telemetry/artifacts) instead of buffering until completion.
- Document the streaming contract in docs (README or new subsection) so future tool authors know how to emit incremental data.
- Add regression tests or a sample RAG tool handler that yields partial READMEs/ripgrep results to prove perceived latency shrinks from ~70s to ~15s.

## Workstream 4: Tool Execution Metrics Dashboard (Priority: LOW)
- Introduce `engine.get_tool_performance_stats()` (or similar getter in `engine.py`/`inspector.py`) that aggregates telemetry metrics per tool: counts, averages, percentiles, slowest call, and timeout/failure tallies.
- Leverage the existing `metrics_collector` (see `telemetry.py:280-302`) but add aggregation recipes for counters/timers and expose them via the inspector API and/or telemetry snapshots.
- Document how to read the dashboard so developers can understand which tools, like the RAG indexer, need optimization.

## Workstream 5: Tool Cancellation / Interruption Support (Priority: LOW)
- Introduce a cancellation token/event (e.g., `CancellableToolExecution`) that threads or async calls can poll to stop long-running work before timeout.
- Wire the new token into `tool_runtime`: pass it to handler factories and expose a mechanism for the engine/inspector to request cancellation mid-flight.
- Ensure `TimeoutError` handling detects cancellations vs. hard timeouts and surfaces partial results if available.
- Provide guidance for tools to honor cancellation requests (e.g., check `cancel_requested.is_set()` at natural checkpoints).

## Workstream 6: Adaptive Timeout Recommendations (Priority: LOW)
- Add a helper in `tool_runtime.py` (or a config-driven module) that estimates timeout recommendations per tool based on inputs such as `workspace_root` file count.
- Seed heuristics for `search_codebase`: 3 minutes for >1000 files, 60s for >100, and 30s otherwise; default to 300s for unknown tools.
- Emit telemetry warnings when actual runs exceed the recommendation to help future tuning without relying solely on manual observation.
- Document the recommendation hints so developers understand why the engine suggests a longer timer.

## Execution Guidance for Claude Sonnet
- Use `docs/internal/phase_plan_prompt_webgpt.txt` as the template when generating the detailed implementation steps for Haiku.
- Each step must reference explicit files (`telemetry.py`, `tool_runtime.py`, `tools.yaml`, `engine.py`, etc.), mention verification steps (re-run `help_chatbot` scenario or regression tests), and keep semantics aligned with the canonical docs.
- Provide enough detail so Haiku can implement every bullet without further clarification: include expected new functions, config entries, telemetry events, and user-visible messages.

## Verification & Follow-up
- Re-run the `help_chatbot` test suite to confirm progress telemetry appears, configurable timeouts are applied, and streaming partial results reach the client.
- Validate new telemetry/metrics APIs via unit tests that exercise `tool_progress`, partial result forwarding, and cancellation paths.
- After implementation, update this plan’s status, add checkmarks for completed line items, and add a summary of outcomes to `docs/CHANGELOG.md` before retiring the plan.
