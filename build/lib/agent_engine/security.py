"""Security and permission scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agent_engine.schemas import ToolCapability, ToolDefinition, ToolRiskLevel


@dataclass
class SecurityDecision:
    allowed: bool
    reason: str
    require_review: bool = False


def check_tool_call(
    tool: ToolDefinition,
    allow_network: bool = False,
    allow_workspace_mutation: bool = False,
    max_risk: ToolRiskLevel = ToolRiskLevel.HIGH,
) -> SecurityDecision:
    """Basic capability/risk gate for tool calls."""
    if tool.risk_level.value not in [level.value for level in ToolRiskLevel]:
        return SecurityDecision(False, "Unknown risk level")

    if tool.risk_level.value not in _risk_order(max_risk):
        return SecurityDecision(False, f"Risk level {tool.risk_level} exceeds allowed {max_risk}")

    if ToolCapability.EXTERNAL_NETWORK in tool.capabilities and not allow_network:
        return SecurityDecision(False, "External network not permitted")

    if ToolCapability.WORKSPACE_MUTATION in tool.capabilities and not allow_workspace_mutation:
        return SecurityDecision(False, "Workspace mutation not permitted")

    require_review = tool.risk_level == ToolRiskLevel.HIGH
    return SecurityDecision(True, "Allowed", require_review=require_review)


def _risk_order(max_risk: ToolRiskLevel) -> set[str]:
    order = [ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH]
    idx = order.index(max_risk)
    return {level.value for level in order[: idx + 1]}
