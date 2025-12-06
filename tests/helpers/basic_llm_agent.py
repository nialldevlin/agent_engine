from __future__ import annotations

from pathlib import Path

from agent_engine import Engine
from agent_engine.schemas import TaskMode

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs" / "basic_llm_agent"


class ExampleLLMClient:
    """Minimal deterministic stand-in LLM used by tests."""

    def generate(self, prompt: dict):
        stage_id = prompt.get("agent_stage")
        request = prompt.get("task_request")
        if stage_id == "user_input":
            return {"notes": request}
        if stage_id == "interpretation":
            return {"summary": f"Understand request: {request}", "intent": "execute simple actions"}
        if stage_id == "decomposition":
            return {"steps": ["clarify goals", "list files", "prepare edits"], "request": request}
        if stage_id == "planning":
            return {"plan": f"Plan steps for: {request}", "tools": prompt.get("tools")}
        if stage_id == "review":
            return {"status": "approved", "notes": "Plan reviewed", "request": request}
        if stage_id == "results":
            return {"status": "done", "request": request}
        return {"echo": request, "stage": stage_id}


def gather_context_handler(call_input):
    cwd = Path(".")
    files = sorted([p.name for p in cwd.iterdir() if p.is_file()])[:10]
    return {"workspace_files": files, "request": call_input.get("request")}


def execution_handler(call_input):
    request = (call_input.get("request") or "").strip()
    cwd = Path(".")
    if request.lower().startswith(("ls", "list")):
        entries = sorted(p.name for p in cwd.iterdir())[:50]
        return {"executed": True, "kind": "list", "entries": entries}
    if request.lower().startswith("read "):
        target = request.split(" ", 1)[1].strip()
        path = cwd / target
        if path.exists() and path.is_file():
            return {"executed": True, "kind": "read", "path": target, "content": path.read_text()[:4000]}
        return {"executed": False, "error": f"File not found: {target}"}
    if request.lower().startswith("search "):
        needle = request.split(" ", 1)[1].strip()
        matches = []
        for p in cwd.rglob("*"):
            if p.is_file():
                try:
                    text = p.read_text()
                except Exception:
                    continue
                if needle in text:
                    matches.append(str(p))
            if len(matches) >= 20:
                break
        return {"executed": True, "kind": "search", "query": needle, "matches": matches}
    return {
        "executed": False,
        "kind": "noop",
        "message": f"Execution stub: request '{request}' not actioned (writes are disabled in tests).",
    }


def build_engine():
    engine = Engine.from_config_dir(str(CONFIG_DIR), llm_client=ExampleLLMClient())
    engine.register_tool_handler("gather_context", gather_context_handler)
    engine.register_tool_handler("execution", execution_handler)
    return engine
