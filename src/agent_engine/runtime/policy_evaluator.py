"""Policy evaluator for checking tool usage against policies."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from agent_engine.schemas.policy import PolicyAction, PolicySet, PolicyTarget

if TYPE_CHECKING:
    from agent_engine.telemetry import TelemetryBus


class PolicyEvaluator:
    """Evaluates policies to determine if tool usage is allowed."""

    def __init__(self, policy_sets: List[PolicySet], telemetry: Optional[TelemetryBus] = None):
        """Initialize policy evaluator.

        Args:
            policy_sets: List of PolicySet objects
            telemetry: Optional TelemetryBus for emitting denial events
        """
        self.policy_sets = [ps for ps in policy_sets if ps.enabled]
        self.telemetry = telemetry

    def check_tool_allowed(self, tool_name: str, task_id: str = "") -> Tuple[bool, str]:
        """Check if tool is allowed by policies.

        Checks all enabled policy sets in order. If any DENY rule matches,
        returns False with reason. Otherwise returns True.

        Args:
            tool_name: Name of the tool to check
            task_id: Optional task ID for telemetry

        Returns:
            (allowed: bool, reason: str) - True if allowed, False if denied
        """
        # Check all enabled policy sets
        for policy_set in self.policy_sets:
            for rule in policy_set.rules:
                # Check if rule applies to this tool
                if rule.target == PolicyTarget.TOOL and rule.target_id == tool_name:
                    if rule.action == PolicyAction.DENY:
                        reason = rule.reason or f"Tool '{tool_name}' is denied by policy '{policy_set.name}'"
                        self._emit_denial(tool_name, reason, task_id)
                        return False, reason

        # No deny rules matched, allow
        return True, ""

    def _emit_denial(self, target: str, reason: str, task_id: str = "") -> None:
        """Emit telemetry event for policy denial.

        Args:
            target: Target that was denied (tool name, etc.)
            reason: Reason for denial
            task_id: Optional task ID
        """
        if self.telemetry:
            self.telemetry.emit_policy_denied(
                target=target,
                reason=reason,
                task_id=task_id,
            )
