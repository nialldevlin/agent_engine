from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from king_arthur_orchestrator.toolkit.base import Tool, ToolResult, ConsentPolicy
from king_arthur_orchestrator.toolkit.workspace import workspace_signature


def normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.strip().lower().split())


def cache_key(prompt: str, workspace_root: Path) -> str:
    norm = normalize_prompt(prompt)
    sig = workspace_signature(workspace_root)
    return hashlib.md5((norm + sig).encode()).hexdigest()


def register_context_tools(registry, base_dir: Path) -> None:
    registry.register(Tool(
        name="context.normalize_prompt",
        description="Normalize prompt for cache keys (lowercase, squash whitespace)",
        execute=lambda prompt: ToolResult(True, output=normalize_prompt(prompt)),
        parameters={"prompt": "raw prompt"},
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))
    registry.register(Tool(
        name="context.cache_key",
        description="Compute cache key from prompt + workspace signature",
        execute=lambda prompt: ToolResult(True, output=cache_key(prompt, base_dir)),
        parameters={"prompt": "raw prompt"},
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))


def register_memory_context_tools(registry, context_manager) -> None:
    """Register deterministic context services backed by the ContextManager."""

    def get_preferences() -> ToolResult:
        prefs = context_manager.memory.project_memory.preferences or {}
        return ToolResult(True, output=json.dumps(prefs))

    def set_preference(key: str, value: str) -> ToolResult:
        context_manager.memory.remember_preference(key, value)
        return ToolResult(True, output=json.dumps({key: value}))

    def get_project_context() -> ToolResult:
        context = context_manager.memory.project_memory.project_context or ""
        return ToolResult(True, output=context)

    def record_event(event: str | dict) -> ToolResult:
        if isinstance(event, dict):
            note = json.dumps(event)
        else:
            note = str(event)
        context_manager.memory.remember_fact(note)
        return ToolResult(True, output="event recorded")

    registry.register(Tool(
        name="context.get_global_preferences",
        description="Return the persisted project-level preferences as JSON.",
        execute=lambda: get_preferences(),
        parameters={},
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))

    registry.register(Tool(
        name="context.set_global_preference",
        description="Set a single project preference (key=value).",
        execute=lambda key, value: set_preference(key, value),
        parameters={"key": "Preference name", "value": "Preference value"},
        consent=ConsentPolicy.NONE,
        side_effects=True,
    ))

    registry.register(Tool(
        name="context.get_project_context",
        description="Return the current project context description.",
        execute=lambda: get_project_context(),
        parameters={},
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))

    registry.register(Tool(
        name="context.record_event",
        description="Record an event/fact in project memory.",
        execute=lambda event: record_event(event),
        parameters={"event": "Event string or dict"},
        consent=ConsentPolicy.NONE,
        side_effects=True,
    ))
