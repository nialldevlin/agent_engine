# Agent Engine

Agent Engine is a manifest-driven framework for building multi-agent LLM systems. It turns YAML/JSON manifests into a runnable orchestration runtime with schemas, routing, memory, tool safety, and telemetry baked in, so apps stay declarative and testable.

## Quickstart

1. **Install deps (needs network)**  
   `make install`
2. **Run tests**  
   `make test`
3. **Lint/format/typecheck**  
   `make lint` · `make format` · `make typecheck`

## Run the minimal example

- With Claude: `ANTHROPIC_API_KEY=... python3 run_example.py "Make a dino game"`
- Without Claude: `python3 run_example.py "Make a dino game"` (uses a mock LLM to show the flow)

The script builds a single-stage pipeline, calls the agent runtime, and prints the stage output. Extend it with your manifests/tool handlers/LLM client as needed.

## Configure your own project

1. Define manifests (YAML/JSON) for agents, tools, stages, workflow, pipelines, and memory under a `configs/` folder.
2. Load them with `config_loader.load_engine_config(...)` to get an `EngineConfig`.
3. Provide tool handlers (or LLM peasants) to `ToolRuntime`, and an LLM client to `AgentRuntime`.
4. Create a `TaskSpec`, let `Router` pick a pipeline, and execute via `PipelineExecutor` or the `run_task` helper.

## Documentation

- Architecture: `docs/canonical/AGENT_ENGINE_OVERVIEW.md` (authoritative).
- Research basis: `docs/canonical/RESEARCH.md` and `docs/canonical/RESEARCH_UPDATED.md` (context, memory, routing, JSON).
- Plans: `docs/operational/PLAN_AGENT_ENGINE_CODEX.md` (implementation checklist) and `docs/operational/PLAN_AGENT_ENGINE.md` (phase steps).
