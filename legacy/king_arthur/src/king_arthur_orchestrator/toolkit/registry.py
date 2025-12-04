"""
Toolkit registry for tool registration, discovery, and consent-aware invocation.

The ToolRegistry is the single source of truth for all tools available to agents.
It enforces consent policies before deterministic tool execution and routes peasant
invocations to the appropriate agent-backed task_runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from king_arthur_orchestrator.toolkit.base import Tool, ToolResult, ConsentPolicy, ConsentCategory
from king_arthur_orchestrator.toolkit.consent import ConsentManager, ConsentChoice
from king_arthur_orchestrator.toolkit.prompt_utils import render_option_list, validate_option_choice


@dataclass
class ToolEntry:
    kind: str
    tool: Optional[Tool] = None
    task_runner: Optional[Callable[..., ToolResult]] = None
    metadata: Dict[str, str] = field(default_factory=dict)


class ToolRegistry:
    """Single tool registry that tracks deterministic tools and peasant agents."""

    def __init__(
        self,
        consent_manager: Optional[ConsentManager] = None,
        chooser: Optional[Callable[[str, Optional[Sequence[str]], int], Optional[str]]] = None
    ):
        self._entries: Dict[str, ToolEntry] = {}
        self._consent = consent_manager
        self._chooser = chooser

    def register(self, tool: Tool, kind: str = "deterministic") -> None:
        """Register a deterministic tool."""
        if kind not in {"deterministic", "peasant"}:
            raise ValueError(f"Invalid tool kind '{kind}'")
        if tool.name in self._entries:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._entries[tool.name] = ToolEntry(kind=kind, tool=tool)

    def register_peasant(self, name: str, agent_id: str, task_runner: Callable[..., ToolResult]) -> None:
        """Register a peasant agent as a tool-style entry."""
        if name in self._entries:
            raise ValueError(f"Tool '{name}' is already registered.")
        self._entries[name] = ToolEntry(kind="peasant", task_runner=task_runner, metadata={"agent_id": agent_id})

    def get(self, name: str) -> Tool:
        """Retrieve a deterministic tool by name."""
        entry = self._entries.get(name)
        if not entry or entry.kind != "deterministic" or not entry.tool:
            raise KeyError(f"Tool '{name}' is not registered or not deterministic.")
        return entry.tool

    def list(self) -> Iterable[Tool]:
        """Return all deterministic tools."""
        return [entry.tool for entry in self._entries.values() if entry.tool]

    def filter_by_names(self, names: List[str]) -> List[Tool]:
        """Return deterministic tools whose names appear in the provided list."""
        return [self._entries[name].tool for name in names if name in self._entries and self._entries[name].tool]

    def run(self, name: str, **kwargs) -> ToolResult:
        """Invoke a registered tool or peasant agent."""
        entry = self._entries.get(name)
        if not entry:
            raise KeyError(f"Tool '{name}' is not registered.")

        if entry.kind == "deterministic":
            tool = entry.tool
            assert tool, "Deterministic entry missing Tool"
            if not self._check_consent(tool):
                return ToolResult(False, error="Consent denied for tool")
            return tool.run(**kwargs)

        if entry.kind == "peasant":
            task_runner = entry.task_runner
            if not task_runner:
                raise RuntimeError(f"Peasant entry '{name}' has no task_runner.")
            return task_runner(**kwargs)

        raise RuntimeError(f"Unsupported tool kind: {entry.kind}")

    # Consent helpers copied from previous implementation
    def _check_consent(self, tool: Tool) -> bool:
        """Check and enforce consent for a deterministic tool."""
        if tool.consent == ConsentPolicy.NONE or not self._consent or not self._chooser:
            return True

        stored = self._consent.get(tool.name)
        if stored == "no":
            return False

        if stored in {"session", "persist"}:
            return True

        if stored == "once":
            self._consent.set_session(tool.name, "no")
            return True

        return self._prompt_for_consent(tool)

    def _prompt_for_consent(self, tool: Tool) -> bool:
        if not self._chooser or not self._consent:
            return False

        options = ["no", "yes once", "yes session", "yes persist"]
        category = tool.consent_category.value if tool.consent_category else ConsentCategory.GENERAL.value
        context_hint = tool.consent_context or category
        prompt_text = (
            f"Consent required for tool '{tool.name}' ({context_hint}):\n"
            + render_option_list(options, default=1)
            + "\nSelect an option (default 1=no): "
        )
        choice_raw = self._chooser(prompt_text, options, 1)
        if choice_raw is None:
            return False
        valid, chosen = validate_option_choice(str(choice_raw), options)
        if not valid or not chosen:
            return False

        chosen_lower = chosen.lower()
        if chosen_lower.startswith("no"):
            self._consent.set_session(tool.name, "no")
            return False

        if "once" in chosen_lower:
            self._consent.set_session(tool.name, "no")
            return True

        if "session" in chosen_lower:
            self._consent.set_session(tool.name, "session")
            return True

        if "persist" in chosen_lower:
            return self._prompt_for_persist_scope(tool)

        return False

    def _prompt_for_persist_scope(self, tool: Tool) -> bool:
        if not self._chooser or not self._consent:
            return False

        options = ["project", "global"]
        prompt_text = (
            f"Persist consent for '{tool.name}' at project or global scope?\n"
            + render_option_list(options, default=1)
            + "\nSelect an option (default 1=project): "
        )
        choice_raw = self._chooser(prompt_text, options, 1)
        if choice_raw is None:
            return False
        valid, chosen = validate_option_choice(str(choice_raw), options)
        if not valid or not chosen:
            return False

        if chosen.lower().startswith("project"):
            self._consent.set_project(tool.name, "persist")
            return True

        self._consent.set_global(tool.name, "persist")
        return True
