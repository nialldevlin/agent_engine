"""Task memory store for ephemeral task-specific context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List
from uuid import uuid4

from agent_engine.schemas.memory import ContextItem

from .backend import InMemoryBackend, MemoryBackend


@dataclass
class TaskMemoryStore:
    """Ephemeral memory for a single task.

    Automatically cleared when task completes.
    Optimized for fast access during task execution.
    """

    task_id: str
    backend: MemoryBackend = field(default_factory=InMemoryBackend)

    def add_reasoning(self, text: str, stage_id: str) -> ContextItem:
        """Add reasoning from a stage.

        Args:
            text: The reasoning text
            stage_id: ID of the stage producing this reasoning

        Returns:
            ContextItem for the added reasoning
        """
        item = ContextItem(
            context_item_id=f"reasoning-{stage_id}-{uuid4()}",
            kind="reasoning",
            source=f"task/{self.task_id}/{stage_id}",
            timestamp=datetime.now().isoformat(),
            tags=["task", stage_id],
            importance=0.5,
            token_cost=len(text.split()),
            payload={"text": text}
        )
        self.backend.add(item)
        return item

    def add_tool_output(self, tool_id: str, output: Any) -> ContextItem:
        """Add tool execution output.

        Args:
            tool_id: ID of the tool
            output: The output from the tool

        Returns:
            ContextItem for the added tool output
        """
        item = ContextItem(
            context_item_id=f"tool-{tool_id}-{uuid4()}",
            kind="tool_output",
            source=f"task/{self.task_id}",
            timestamp=datetime.now().isoformat(),
            tags=["task", "tool", tool_id],
            importance=0.7,
            token_cost=len(str(output).split()),
            payload={"tool_id": tool_id, "output": output}
        )
        self.backend.add(item)
        return item

    def get_stage_outputs(self, stage_id: str) -> List[ContextItem]:
        """Get all outputs from a specific stage.

        Args:
            stage_id: ID of the stage to query

        Returns:
            List of ContextItems from that stage
        """
        return self.backend.query(
            filters={"source": f"task/{self.task_id}/{stage_id}"},
            limit=1000
        )

    def clear(self) -> None:
        """Clear all task memory (called on task completion)."""
        self.backend.clear()
