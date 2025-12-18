"""Policy schema definitions for Phase 14 Security & Policy Layer."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class PolicyAction(str, Enum):
    """Policy action types."""

    ALLOW = "allow"
    DENY = "deny"


class PolicyTarget(str, Enum):
    """Policy target types."""

    TOOL = "tool"
    CONTEXT = "context"  # Future
    NODE = "node"  # Future


@dataclass
class PolicyRule:
    """A single policy rule."""

    target: PolicyTarget
    target_id: str  # tool name, node id, etc.
    action: PolicyAction
    reason: str = ""

    def dict(self):
        """Convert to dictionary."""
        return {
            "target": self.target.value,
            "target_id": self.target_id,
            "action": self.action.value,
            "reason": self.reason,
        }


@dataclass
class PolicySet:
    """A collection of related policy rules."""

    name: str
    rules: List[PolicyRule] = field(default_factory=list)
    enabled: bool = True

    def dict(self):
        """Convert to dictionary."""
        return {
            "name": self.name,
            "rules": [r.dict() for r in self.rules],
            "enabled": self.enabled,
        }
