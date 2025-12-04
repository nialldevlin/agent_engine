# Getting Started with Agent Engine

1. **Install dependencies**
   - `python3 -m venv .venv && source .venv/bin/activate`
   - `pip install -e .[dev]` (requires network access)

2. **Run tests**
   - `PYTHONPATH=src pytest`

3. **Explore manifests and patterns**
   - `examples/committee_manifest.yaml`
   - `examples/supervisor_manifest.yaml`
   - `examples/tool_agent/manifest.yaml`

4. **Key docs**
   - Architecture: `docs/canonical/AGENT_ENGINE_OVERVIEW.md`
   - Research: `docs/canonical/RESEARCH.md`, `docs/canonical/RESEARCH_UPDATED.md`
   - Implementation plan: `docs/operational/PLAN_AGENT_ENGINE_CODEX.md`
