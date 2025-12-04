"""
Deterministic plan validation helpers shared across the pipeline.
"""

from __future__ import annotations

from typing import List, Tuple

from king_arthur_orchestrator.infra.models import ExecutionPlan
from king_arthur_orchestrator.toolkit.task_intent import SideEffectRequirement, has_write_operations, is_plan_readonly

VALID_ACTIONS = {"bash", "file_write", "file_edit", "file_read"}


def validate_plan(plan: ExecutionPlan) -> tuple[bool, List[str]]:
    """Perform basic structural validation of an execution plan."""
    issues: List[str] = []
    if not plan or not plan.steps:
        issues.append("Plan has no steps")
        return False, issues

    seen_ids = set()
    for step in plan.steps:
        if step.step_id in seen_ids:
            issues.append(f"Duplicate step ID: {step.step_id}")
        seen_ids.add(step.step_id)

        if step.action not in VALID_ACTIONS:
            issues.append(f"Invalid action '{step.action}' in step {step.step_id}")

        for dep in step.depends_on:
            if dep not in seen_ids or dep >= step.step_id:
                issues.append(f"Step {step.step_id} depends on non-existent step {dep}")

        if step.action in {"file_write", "file_edit"} and not step.content:
            issues.append(f"Step {step.step_id} ({step.action}) missing content")

    return len(issues) == 0, issues


def validate_plan_strict(plan: ExecutionPlan, side_effect_req: SideEffectRequirement) -> Tuple[bool, List[str]]:
    """
    Validate plan while honoring side-effect requirements (read-only vs. create/modify intent).
    """
    is_valid, issues = validate_plan(plan)
    if not is_valid:
        return False, issues

    if side_effect_req.requires_changes:
        if not has_write_operations(plan):
            issues.append(
                f"Plan contains no file_write or file_edit operations but task intent requires changes "
                f"({side_effect_req.explanation})"
            )
            return False, issues
        if is_plan_readonly(plan):
            issues.append(
                f"Task requires {side_effect_req.change_type} operations but plan is read-only "
                f"({side_effect_req.explanation})"
            )
            return False, issues

    return True, []


__all__ = ["validate_plan", "validate_plan_strict", "VALID_ACTIONS"]
