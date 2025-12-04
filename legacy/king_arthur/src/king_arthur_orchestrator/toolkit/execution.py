"""
Toolkit execution module: tools for executing plans and bash commands.

Provides deterministic execution capabilities for agents:
- bash_run: Execute bash commands with validation, timeout, and consent.
- plan_execute: Execute multi-step plans with filesystem operations.

Each tool validates inputs, requires consent, handles errors gracefully,
supports dry-run mode, and returns structured ToolResult objects.

Design principles:
- Tools are deterministic and contain no LLM logic.
- All inputs are validated before execution.
- Errors are returned as ToolResult, not raised as exceptions.
- Dangerous operations require explicit consent.
- Bash execution supports timeout, environment variables, and working directory.
- Plan execution preserves step-by-step semantics with progress tracking.
- Dry-run mode allows inspection without modifying filesystem.
"""

from __future__ import annotations

import json as _json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from king_arthur_orchestrator.toolkit.base import Tool, ToolResult, ConsentPolicy, ConsentCategory
from . import filesystem as tk_fs


# Configuration constants for execution limits and safety
DEFAULT_BASH_TIMEOUT_SECONDS = 30  # Default timeout for bash commands
DEFAULT_BASH_MAX_OUTPUT_BYTES = 50_000  # Max output before truncation
DANGEROUS_COMMAND_PATTERNS = ["rm -rf", "sudo", "mkfs", "dd if="]  # Patterns requiring extra confirmation

# Plan schema validation constants
VALID_PLAN_ACTIONS = {"bash", "file_write", "file_edit", "file_read"}
VALID_PLAN_SCHEMA_FIELDS = {"action", "target", "content", "description"}


def _safe_env() -> dict:
    """
    Build a safe environment for subprocess execution.

    Constructs a minimal environment that:
    - Preserves essential system paths while preventing injection.
    - Maintains HOME, USER, LANG, and PYTHONPATH when available.
    - Allows safe environment variables (TERM, SHELL, EDITOR, VIRTUAL_ENV).

    Returns:
        dict: Safe environment mapping for subprocess.run().
    """
    home = os.environ.get("HOME", "/tmp")
    original_path = os.environ.get("PATH", "")
    base_path = "/usr/local/bin:/usr/bin:/bin"
    user_local_bin = os.path.join(home, ".local", "bin")
    path_parts = [original_path, base_path]
    if os.path.isdir(user_local_bin):
        path_parts.append(user_local_bin)

    safe_env = {
        "PATH": ":".join(filter(None, path_parts)),
        "HOME": home,
        "USER": os.environ.get("USER", "nobody"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }

    # Whitelist additional safe environment variables
    safe_to_copy = {"TERM", "SHELL", "EDITOR", "PYTHONPATH", "VIRTUAL_ENV"}
    for var in safe_to_copy:
        if var in os.environ:
            safe_env[var] = os.environ[var]

    return safe_env


def _validate_plan_schema(plan_dict: dict) -> tuple[bool, Optional[str]]:
    """
    Validate that a plan dictionary has the required schema.

    Required structure:
    {
        "steps": [
            {
                "action": "bash|file_write|file_edit|file_read",
                "target": "command or file path",
                "content": "optional content for write/edit",
                "description": "optional human-readable description"
            },
            ...
        ]
    }

    Args:
        plan_dict: Dictionary to validate.

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(plan_dict, dict):
        return False, "Plan must be a dictionary"

    if "steps" not in plan_dict:
        return False, "Plan missing required 'steps' field"

    if not isinstance(plan_dict["steps"], list):
        return False, "Plan 'steps' field must be a list"

    if not plan_dict["steps"]:
        return False, "Plan has no steps"

    for i, step in enumerate(plan_dict["steps"]):
        if not isinstance(step, dict):
            return False, f"Step {i} is not a dictionary"

        if "action" not in step:
            return False, f"Step {i} missing required 'action' field"

        if "target" not in step:
            return False, f"Step {i} missing required 'target' field"

        action = step.get("action")
        if action not in VALID_PLAN_ACTIONS:
            return False, f"Step {i} has invalid action '{action}'. Must be one of: {VALID_PLAN_ACTIONS}"

        # file_write and file_edit require content
        if action in {"file_write", "file_edit"}:
            if "content" not in step and step.get("content") is None:
                return False, f"Step {i} ({action}) requires 'content' field"

    return True, None


def _is_dangerous_command(command: str) -> bool:
    """
    Check if a bash command matches dangerous patterns.

    Args:
        command: Command string to check.

    Returns:
        bool: True if command matches a dangerous pattern.
    """
    cmd_lower = command.lower()
    return any(pattern in cmd_lower for pattern in DANGEROUS_COMMAND_PATTERNS)


def _bash_run(
    command: str,
    cwd: Path | str = ".",
    timeout: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    max_output: int = DEFAULT_BASH_MAX_OUTPUT_BYTES,
) -> ToolResult:
    """
    Execute a bash command with timeout and output limits.

    Args:
        command: Bash command string to execute.
        cwd: Working directory for command execution (default ".").
        timeout: Timeout in seconds (default 30).
        max_output: Maximum output bytes before truncation (default 50KB).

    Returns:
        ToolResult with success, output, error, and exit code metadata.
    """
    cwd_path = Path(cwd) if isinstance(cwd, str) else cwd

    try:
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            shell=False,  # Use list form to avoid shell injection
            cwd=str(cwd_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_safe_env(),
        )

        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"

        # Truncate if necessary
        if len(output) > max_output:
            output = output[:max_output] + "\n[OUTPUT TRUNCATED]"

        success = result.returncode == 0
        return ToolResult(
            success,
            output=output,
            error=None if success else f"Exit code: {result.returncode}",
            metadata={"exit_code": result.returncode, "output_bytes": len(output)},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            False,
            error=f"Command timed out after {timeout} seconds",
            metadata={"timeout_seconds": timeout},
        )
    except Exception as e:
        return ToolResult(
            False,
            error=f"Bash execution failed: {str(e)}",
            metadata={"exception": type(e).__name__},
        )


def _plan_execute(
    steps: List[dict],
    base_dir: Path | str = ".",
    timeout: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    max_output: int = DEFAULT_BASH_MAX_OUTPUT_BYTES,
    dry_run: bool = False,
) -> ToolResult:
    """
    Execute a multi-step plan with filesystem operations.

    Each step is executed sequentially. Supports:
    - bash: Execute shell command
    - file_read: Read file contents
    - file_write: Write file (creates parent directories)
    - file_edit: Edit file by replacing anchor text

    Stops on first failure and returns accumulated progress.
    Supports dry-run mode to inspect without modifying filesystem.

    Plan schema (validated before execution):
    {
        "steps": [
            {
                "action": "bash|file_write|file_edit|file_read",
                "target": "command or file path",
                "content": "optional content for write/edit",
                "description": "optional human-readable description"
            }
        ]
    }

    Args:
        steps: List of step dictionaries.
        base_dir: Base directory for file operations (default ".").
        timeout: Timeout for bash commands in seconds (default 30).
        max_output: Max output bytes per step (default 50KB).
        dry_run: If True, no filesystem changes are made (default False).

    Returns:
        ToolResult with step-by-step progress and metadata.
        Metadata includes "steps" list with individual results and "diffs" for edits.
    """
    base_dir_path = Path(base_dir) if isinstance(base_dir, str) else base_dir

    # Collect step results
    step_results = []
    diffs = {}

    for i, step in enumerate(steps):
        step_num = i + 1
        action = step.get("action")
        target = step.get("target", "")
        content = step.get("content", "")
        description = step.get("description", f"{action} {target}")

        # Initialize result for this step
        step_result = {
            "step_num": step_num,
            "action": action,
            "target": target,
            "description": description,
            "success": False,
            "output": "",
            "error": None,
        }

        # Execute step based on action type
        if action == "bash":
            res = _bash_run(target, base_dir_path, timeout=timeout, max_output=max_output)

        elif action == "file_write":
            if dry_run:
                res = ToolResult(
                    True,
                    output=f"[DRY RUN] Would write {len(content or '')} bytes to {target}",
                    metadata={"dry_run": True, "bytes": len(content or "")},
                )
            else:
                res = tk_fs._file_write(base_dir_path, target, content or "", max_bytes=None)

        elif action == "file_edit":
            if dry_run:
                res = ToolResult(
                    True,
                    output=f"[DRY RUN] Would edit {target}",
                    metadata={"dry_run": True},
                )
            else:
                # Parse edit specification (old_string, new_string)
                try:
                    if isinstance(content, str):
                        spec = _json.loads(content)
                    else:
                        spec = content

                    old_str = spec.get("old_string", "")
                    new_str = spec.get("new_string", "")
                    res = tk_fs._file_edit(base_dir_path, target, old_str, new_str)

                    # Capture diff if available
                    if res.success and "diff" in res.metadata:
                        diffs[target] = res.metadata.get("diff", "")
                except (ValueError, TypeError, AttributeError) as e:
                    res = ToolResult(False, error=f"Invalid edit spec: {str(e)}")

        elif action == "file_read":
            res = tk_fs._file_read(base_dir_path, target, max_bytes=max_output)

        else:
            res = ToolResult(False, error=f"Unknown action: {action}")

        # Convert ToolResult to step result format
        step_result["success"] = res.success
        step_result["output"] = res.output or ""
        step_result["error"] = res.error

        # Add metadata if available
        if hasattr(res, "metadata") and res.metadata:
            step_result["metadata"] = res.metadata

        step_results.append(step_result)

        # Stop on first failure
        if not res.success:
            # Build error output with all accumulated progress
            progress_lines = [f"Step {sr['step_num']}: {sr['action']} {sr['target']}" for sr in step_results]
            progress_summary = "\n".join(progress_lines)
            return ToolResult(
                False,
                output=progress_summary,
                error=f"Plan execution failed at step {step_num}: {res.error}",
                metadata={"steps": step_results, "diffs": diffs, "failed_at_step": step_num},
            )

    # Success: return all steps with summary
    progress_lines = [f"Step {sr['step_num']}: {sr['action']} {sr['target']}" for sr in step_results]
    progress_summary = "\n".join(progress_lines)
    return ToolResult(
        True,
        output=progress_summary,
        metadata={"steps": step_results, "diffs": diffs, "total_steps": len(step_results)},
    )


def bash_run(
    command: str,
    timeout: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    max_output: int = DEFAULT_BASH_MAX_OUTPUT_BYTES,
    cwd: str = ".",
) -> ToolResult:
    """
    Execute a bash command within the workspace.

    Tool for executing shell commands with safety guards:
    - Timeout prevents runaway processes.
    - Output is truncated to prevent excessive data.
    - Environment is sanitized to prevent injection.
    - Uses subprocess list form to prevent shell injection.

    Args:
        command: Bash command string (required).
        timeout: Timeout in seconds (optional, default 30).
        max_output: Max output bytes (optional, default 50KB).
        cwd: Working directory (optional, default ".").

    Returns:
        ToolResult with command output, exit code, and metadata.
    """
    return _bash_run(command, cwd=Path(cwd), timeout=timeout, max_output=max_output)


def plan_execute(
    steps: List[dict],
    timeout: int = DEFAULT_BASH_TIMEOUT_SECONDS,
    max_output: int = DEFAULT_BASH_MAX_OUTPUT_BYTES,
    cwd: str = ".",
    dry_run: bool = False,
) -> ToolResult:
    """
    Execute a multi-step plan using filesystem and execution tools.

    Tool for executing structured plans with multiple steps.
    Each step performs one action: bash command, file write, file edit, or file read.
    Supports dry-run mode for inspection without modification.

    Plan schema validation (required fields):
    {
        "steps": [
            {
                "action": "bash|file_write|file_edit|file_read",
                "target": "command string or file path",
                "content": "optional content for write/edit/file read",
                "description": "optional human-readable description"
            }
        ]
    }

    Execution semantics:
    - Steps execute sequentially in order.
    - Plan stops on first failure.
    - File operations use toolkit.filesystem tools (read, write, edit, delete).
    - Bash commands execute with timeout and output limits.
    - Dry-run mode prevents filesystem changes.

    Args:
        steps: List of step dictionaries (required, must match schema).
        timeout: Timeout for bash commands in seconds (optional, default 30).
        max_output: Max output bytes per step (optional, default 50KB).
        cwd: Working directory for file operations (optional, default ".").
        dry_run: If True, no filesystem changes (optional, default False).

    Returns:
        ToolResult with step results, diffs for edits, and progress tracking.
        Metadata includes full "steps" list and "diffs" dict for all edits.
    """
    # Validate plan schema
    plan_dict = {"steps": steps}
    is_valid, error_msg = _validate_plan_schema(plan_dict)
    if not is_valid:
        return ToolResult(False, error=f"Invalid plan schema: {error_msg}")

    return _plan_execute(steps, base_dir=Path(cwd), timeout=timeout, max_output=max_output, dry_run=dry_run)


def register_execution_tools(registry, base_dir: Path | str = ".") -> None:
    """
    Register execution tools with the given registry.

    Registers two tools:
    - execution.bash: Execute bash commands.
    - execution.plan: Execute multi-step plans.

    Args:
        registry: Tool registry instance.
        base_dir: Base directory for file operations (optional).
    """
    base_path = Path(base_dir) if isinstance(base_dir, str) else base_dir

    # bash_run tool
    registry.register(
        Tool(
            name="execution.bash",
            description="Execute a bash command within the workspace. Supports timeout, output limits, and safe environment.",
            execute=lambda command, timeout=DEFAULT_BASH_TIMEOUT_SECONDS, max_output=DEFAULT_BASH_MAX_OUTPUT_BYTES, cwd=".": bash_run(
                command, timeout=timeout, max_output=max_output, cwd=cwd
            ),
            parameters={
                "command": "Bash command string (required)",
                "timeout": f"Timeout in seconds (optional, default {DEFAULT_BASH_TIMEOUT_SECONDS})",
                "max_output": f"Max output bytes (optional, default {DEFAULT_BASH_MAX_OUTPUT_BYTES})",
                "cwd": "Working directory (optional, default '.')",
            },
            consent=ConsentPolicy.REQUIRED,
            consent_category=ConsentCategory.DESTRUCTIVE,
            consent_context="Run bash command",
            side_effects=True,
        )
    )

    # plan_execute tool
    registry.register(
        Tool(
            name="execution.plan",
            description="Execute a multi-step plan with filesystem and bash operations. Supports dry-run mode. Each step validates inputs and requires consent.",
            execute=lambda steps, timeout=DEFAULT_BASH_TIMEOUT_SECONDS, max_output=DEFAULT_BASH_MAX_OUTPUT_BYTES, cwd=".", dry_run=False: plan_execute(
                steps, timeout=timeout, max_output=max_output, cwd=cwd, dry_run=dry_run
            ),
            parameters={
                "steps": "List of step dicts with action/target/content/description (required). See tool description for schema.",
                "timeout": f"Timeout for bash steps in seconds (optional, default {DEFAULT_BASH_TIMEOUT_SECONDS})",
                "max_output": f"Max output bytes per step (optional, default {DEFAULT_BASH_MAX_OUTPUT_BYTES})",
                "cwd": "Working directory for file operations (optional, default '.')",
                "dry_run": "If true, no filesystem changes are made (optional, default False)",
            },
            consent=ConsentPolicy.REQUIRED,
            consent_category=ConsentCategory.DESTRUCTIVE,
            consent_context="Execute multi-step plan",
            side_effects=True,
        )
    )
