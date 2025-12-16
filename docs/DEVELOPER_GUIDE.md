# Developer Guide

Practical, end-to-end instructions for building projects with Agent Engine using the canonical specifications.

## 1. Prerequisites
- Python 3.10+ and `make` (or Windows Makefile/windows batch)
- Anthropic/OpenAI/other provider API keys (set via environment variables or files)
- Read the canonical sources for semantics: `docs/canonical/AGENT_ENGINE_SPEC.md`, `docs/canonical/AGENT_ENGINE_OVERVIEW.md`, `docs/canonical/PROJECT_INTEGRATION_SPEC.md`

## 2. Install & Environment
```bash
make install          # creates .venv and installs agent_engine[dev]
source .venv/bin/activate
# Windows: build.bat install && .venv\Scripts\activate
```
Manual equivalent: `python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]`

## 3. Project Scaffold (canonical manifests)
```
my_project/
├── workflow.yaml        # required DAG (one per project)
├── agents.yaml          # required agent definitions
├── tools.yaml           # required tool definitions
├── memory.yaml          # optional memory/context profiles
├── plugins.yaml         # optional observer plugins
├── schemas/             # optional JSON/YAML schemas
└── cli_profiles.yaml    # optional CLI profiles
```
See `docs/canonical/PROJECT_INTEGRATION_SPEC.md` for field-level rules.

## 4. Credentials
Create `provider_credentials.yaml` and load secrets from env (recommended) or files:
```yaml
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"
```
Set the environment variable before running: `export ANTHROPIC_API_KEY="sk-..."`.
See `docs/SECURITY.md` for deployment-grade secret handling.

## 5. Minimal Workflow Example
`workflow.yaml`
```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
  - id: "analyze"
    kind: "agent"
    role: "linear"
    context: "global"
    tools: []
  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"
edges:
  - from: "start"
    to: "analyze"
  - from: "analyze"
    to: "exit"
```
`agents.yaml`
```yaml
agents:
  - id: "default_agent"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config: {}
```
`tools.yaml`
```yaml
tools: []
```

## 6. Run the Engine
```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")
result = engine.run({"request": "Hello, who are you?"})
print(result["status"], result["task_id"])
```
Multi-task execution (sequential, isolated):
```python
batch_results = engine.run_multiple([{"request": "A"}, {"request": "B"}])
```
Inspector (read-only):
```python
inspector = engine.create_inspector()
history = inspector.get_task_history(batch_results[0]["task_id"])
```

## 7. CLI REPL
```bash
python -m agent_engine.cli
```
Uses `cli_profiles.yaml` if present. See `docs/CLI_FRAMEWORK.md` for commands and custom command registration.

## 8. Debugging & Troubleshooting
- Schema failures: check `SchemaValidationError` paths and the schemas in `schemas/`.
- DAG validation errors: confirm role constraints and reachability in `workflow.yaml`.
- Credential issues: ensure env vars or files match `provider_credentials.yaml` and revisit `docs/SECURITY.md`.
- Isolation questions: see API methods in `docs/API_REFERENCE.md`.

## 9. Production Readiness
- Deployment patterns: `docs/DEPLOYMENT.md`
- Security hardening: `docs/SECURITY.md`
- Runtime overrides (models/tools/timeouts): `docs/DYNAMIC_PARAMETERS.md`
- Canonical semantics and invariants: `docs/canonical/AGENT_ENGINE_SPEC.md`
