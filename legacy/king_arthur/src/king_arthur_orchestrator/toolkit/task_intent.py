"""
Toolkit helpers for analyzing task intent and side effects.

Provides deterministic functions used across the CLI, pipeline, and tests to
decide whether a plan should perform workspace mutations or stay read-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from king_arthur_orchestrator.infra.models import ExecutionPlan


@dataclass
class SideEffectRequirement:
    requires_changes: bool
    change_type: str
    confidence: float
    indicators: List[str]
    explanation: str


def analyze_task_intent(user_prompt: str, interpretation: dict, todo: dict) -> SideEffectRequirement:
    """Infer whether a task should mutate the workspace."""
    indicators: List[str] = []
    confidence_score = 0.0
    prompt_lower = user_prompt.lower()

    creation_keywords = {
        "create", "build", "make", "generate", "implement", "write",
        "develop", "scaffold", "init", "initialize", "setup", "add",
        "new project", "new file", "start a", "build a", "develop a",
    }
    modification_keywords = {
        "update", "modify", "change", "fix", "refactor", "edit",
        "improve", "enhance", "extend", "add to", "insert",
    }
    readonly_keywords = {
        "what", "how", "why", "explain", "show", "list", "find",
        "search", "analyze", "review", "check", "inspect", "examine",
        "tell me", "show me", "what does", "what is", "what are",
    }
    artifact_nouns = {
        "project", "app", "application", "program", "script", "module",
        "package", "library", "tool", "game", "website", "api", "service",
    }

    creation_matches = [kw for kw in creation_keywords if kw in prompt_lower]
    if creation_matches:
        indicators.extend(creation_matches)
        confidence_score += 0.4

    artifact_matches = [noun for noun in artifact_nouns if noun in prompt_lower]
    if artifact_matches and creation_matches:
        indicators.extend([f"artifact:{a}" for a in artifact_matches])
        confidence_score += 0.3

    modification_matches = [kw for kw in modification_keywords if kw in prompt_lower]
    if modification_matches:
        indicators.extend(modification_matches)
        confidence_score += 0.3

    readonly_matches = [kw for kw in readonly_keywords if kw in prompt_lower]
    if readonly_matches:
        indicators.extend([f"readonly:{r}" for r in readonly_matches])
        confidence_score -= 0.2

    file_pattern = r'@(\S+\.(?:py|js|ts|jsx|tsx|json|yaml|yml|md|txt|sh|rs|go|java|cpp|c|h))'
    file_refs = re.findall(file_pattern, user_prompt)
    if file_refs:
        indicators.extend([f"file_ref:{f}" for f in file_refs[:3]])
        if not readonly_matches:
            confidence_score += 0.2

    if interpretation:
        for req in interpretation.get("interpreted_requirements", []):
            req_lower = req.lower() if isinstance(req, str) else ""
            if any(kw in req_lower for kw in creation_keywords | modification_keywords):
                indicators.append(f"interp_req:{req[:30]}")
                confidence_score += 0.15

    if todo:
        subtasks = todo.get("subtasks", [])
        actionable_tasks = sum(
            1 for task in subtasks
            if any(kw in (task.get("task", "") if isinstance(task, dict) else str(task)).lower()
                   for kw in creation_keywords | modification_keywords)
        )
        if actionable_tasks > 0:
            indicators.append(f"todo_actionable:{actionable_tasks}")
            confidence_score += min(0.2, actionable_tasks * 0.05)

    confidence_score = max(0.0, min(1.0, confidence_score))

    if confidence_score >= 0.4:
        if creation_matches or artifact_matches:
            change_type = "create"
            explanation = (
                "Task appears to require creating new files/projects. "
                f"Keywords: {', '.join(creation_matches + artifact_matches[:2])}"
            )
        else:
            change_type = "modify"
            explanation = (
                "Task appears to require modifying existing files. "
                f"Keywords: {', '.join(modification_matches[:3])}"
            )
        requires_changes = True
    elif confidence_score <= -0.1 or readonly_matches:
        change_type = "read_only"
        explanation = (
            "Task appears to be informational/read-only. "
            f"Keywords: {', '.join(readonly_matches[:3])}"
        )
        requires_changes = False
        confidence_score = abs(confidence_score)
    else:
        change_type = "unknown"
        explanation = (
            "Task intent unclear - defaulting to requiring changes. "
            "Use explicit keywords ('create', 'what is', etc.) for better detection."
        )
        requires_changes = True
        confidence_score = 0.3

    return SideEffectRequirement(
        requires_changes=requires_changes,
        change_type=change_type,
        confidence=confidence_score,
        indicators=indicators,
        explanation=explanation,
    )


def has_write_operations(plan: ExecutionPlan) -> bool:
    """Return True if plan contains any file_write/file_edit actions."""
    if not plan or not plan.steps:
        return False
    return any(step.action in {"file_write", "file_edit"} for step in plan.steps)


def is_plan_readonly(plan: ExecutionPlan) -> bool:
    """Return True if all plan steps are read-only."""
    if not plan or not plan.steps:
        return True
    safe_bash_prefixes = {
        "ls", "list", "cat", "grep", "head", "tail", "find", "stat", "wc", "df",
        "du", "echo", "printf", "whoami", "id", "pwd", "test", "sort", "uniq",
    }

    def _is_safe_bash(target: str) -> bool:
        if not target:
            return True
        first = target.strip().split()[0]
        return first in safe_bash_prefixes

    for step in plan.steps:
        if step.action == "file_read":
            continue
        if step.action == "bash":
            if _is_safe_bash(step.target):
                continue
            return False
        return False
    return True


__all__ = [
    "SideEffectRequirement",
    "analyze_task_intent",
    "has_write_operations",
    "is_plan_readonly",
]
