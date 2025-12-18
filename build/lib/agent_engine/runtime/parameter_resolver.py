"""ParameterResolver service - core logic for runtime parameter resolution.

This service merges manifest-defined parameters with runtime overrides,
respecting priority (TASK > PROJECT > GLOBAL) and validating constraints.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from agent_engine.schemas.override import (
    ParameterOverride,
    ParameterOverrideKind,
    ParameterOverrideStore,
    OverrideSeverity,
)

logger = logging.getLogger(__name__)


# Valid LLM models for validation
SUPPORTED_MODELS = {
    "anthropic": ["claude-3-5-haiku", "claude-3-5-sonnet", "claude-opus-4-5"],
    "openai": ["gpt-4", "gpt-3.5-turbo"],
    "ollama": ["llama2", "llama3", "mistral", "neural-chat"],
}

# Parameter ranges
TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 1.0
MAX_TOKENS_MIN = 1
MAX_TOKENS_MAX = 200000
TIMEOUT_MIN = 1
MAX_RETRIES_MAX = 10


class ParameterResolver:
    """Resolve runtime parameters from manifests + overrides.

    Manages parameter override store, resolves final parameters by merging
    defaults + overrides, and validates parameters against constraints.
    Handles per-run override scope (reset after each task).
    """

    def __init__(self, override_store: ParameterOverrideStore) -> None:
        """Initialize with override store.

        Args:
            override_store: Storage for parameter overrides across scopes.
        """
        self.override_store = override_store

    def add_override(
        self,
        override: ParameterOverride,
        scope: str = "global",
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Add parameter override.

        Args:
            override: The parameter override to add.
            scope: Storage scope ("global", "project", or "task").
            project_id: Project ID if scope is "project" or "task".
            task_id: Task ID if scope is "task".
        """
        self.override_store.add_override(
            override=override,
            scope=scope,
            project_id=project_id,
            task_id=task_id,
        )

    def resolve_llm_config(
        self,
        agent_id: str,
        manifest_config: Dict[str, Any],
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        manifest_llm_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve final LLM config for agent.

        Merges:
        1. Manifest config (base)
        2. Global overrides
        3. Project overrides
        4. Task overrides (highest priority)

        Args:
            agent_id: ID of the agent.
            manifest_config: Base config from manifest.
            task_id: Task ID for task-scoped overrides.
            project_id: Project ID for project-scoped overrides.
            manifest_llm_model: The LLM model defined in manifest.

        Returns:
            Resolved LLM config dict with keys like:
            {temperature, max_tokens, model, timeout, etc.}
        """
        resolved = {}

        # Step 1: Start with manifest config
        resolved.update(manifest_config)

        # Step 2: Apply global overrides
        target_scope = f"agent/{agent_id}"
        global_overrides = self.override_store.get_overrides(
            override_kind=ParameterOverrideKind.LLM_CONFIG,
            target_scope=target_scope,
        )
        for override in global_overrides:
            resolved.update(override.parameters)

        # Step 3: Apply project overrides (if project_id provided)
        if project_id:
            project_overrides = self.override_store.get_overrides(
                override_kind=ParameterOverrideKind.LLM_CONFIG,
                target_scope=target_scope,
                project_id=project_id,
            )
            for override in project_overrides:
                resolved.update(override.parameters)

        # Step 4: Apply task overrides (if task_id provided, highest priority)
        if task_id:
            task_overrides = self.override_store.get_overrides(
                override_kind=ParameterOverrideKind.LLM_CONFIG,
                target_scope=target_scope,
                task_id=task_id,
                project_id=project_id,
            )
            for override in task_overrides:
                resolved.update(override.parameters)

        return resolved

    def resolve_tool_config(
        self,
        tool_id: str,
        manifest_config: Dict[str, Any],
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve final tool config.

        Args:
            tool_id: ID of the tool.
            manifest_config: Base config from manifest.
            task_id: Task ID for task-scoped overrides.
            project_id: Project ID for project-scoped overrides.

        Returns:
            Resolved tool config dict with keys like:
            {enabled, timeout, permissions, etc.}
        """
        resolved = {}

        # Step 1: Start with manifest config
        resolved.update(manifest_config)

        # Step 2: Apply global overrides
        target_scope = f"tool/{tool_id}"
        global_overrides = self.override_store.get_overrides(
            override_kind=ParameterOverrideKind.TOOL_CONFIG,
            target_scope=target_scope,
        )
        for override in global_overrides:
            resolved.update(override.parameters)

        # Step 3: Apply project overrides (if project_id provided)
        if project_id:
            project_overrides = self.override_store.get_overrides(
                override_kind=ParameterOverrideKind.TOOL_CONFIG,
                target_scope=target_scope,
                project_id=project_id,
            )
            for override in project_overrides:
                resolved.update(override.parameters)

        # Step 4: Apply task overrides (if task_id provided, highest priority)
        if task_id:
            task_overrides = self.override_store.get_overrides(
                override_kind=ParameterOverrideKind.TOOL_CONFIG,
                target_scope=target_scope,
                task_id=task_id,
                project_id=project_id,
            )
            for override in task_overrides:
                resolved.update(override.parameters)

        return resolved

    def resolve_execution_config(
        self,
        node_id: Optional[str] = None,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve execution config (timeouts, retry policy).

        Args:
            node_id: Node ID for node-scoped overrides. If None, applies globally.
            task_id: Task ID for task-scoped overrides.
            project_id: Project ID for project-scoped overrides.

        Returns:
            Resolved execution config dict with keys like:
            {timeout_seconds, max_retries, retry_backoff, etc.}
        """
        resolved = {}

        # Determine target scope
        target_scope = f"node/{node_id}" if node_id else "global"

        # Step 1: Apply global overrides
        global_overrides = self.override_store.get_overrides(
            override_kind=ParameterOverrideKind.EXECUTION_CONFIG,
            target_scope=target_scope,
        )
        for override in global_overrides:
            resolved.update(override.parameters)

        # Step 2: Apply project overrides (if project_id provided)
        if project_id:
            project_overrides = self.override_store.get_overrides(
                override_kind=ParameterOverrideKind.EXECUTION_CONFIG,
                target_scope=target_scope,
                project_id=project_id,
            )
            for override in project_overrides:
                resolved.update(override.parameters)

        # Step 3: Apply task overrides (if task_id provided, highest priority)
        if task_id:
            task_overrides = self.override_store.get_overrides(
                override_kind=ParameterOverrideKind.EXECUTION_CONFIG,
                target_scope=target_scope,
                task_id=task_id,
                project_id=project_id,
            )
            for override in task_overrides:
                resolved.update(override.parameters)

        return resolved

    def validate_parameters(
        self,
        parameters: Dict[str, Any],
        kind: ParameterOverrideKind,
        manifest_constraints: Optional[Dict[str, Any]] = None,
        task_mode: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate parameter overrides.

        Checks:
        - LLM: temperature in [0, 1], max_tokens > 0
        - Tools: can't exceed manifest permissions
        - Execution: timeout > 0, retries >= 0
        - TaskMode: no shell in DRY_RUN, no network in ANALYSIS_ONLY

        Args:
            parameters: The parameters to validate.
            kind: The kind of parameter override.
            manifest_constraints: Optional constraints from manifest.
            task_mode: Optional task mode for TaskMode restrictions.

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if kind == ParameterOverrideKind.LLM_CONFIG:
            return self._validate_llm_config(parameters, manifest_constraints)
        elif kind == ParameterOverrideKind.TOOL_CONFIG:
            return self._validate_tool_config(parameters, manifest_constraints, task_mode)
        elif kind == ParameterOverrideKind.EXECUTION_CONFIG:
            return self._validate_execution_config(parameters)
        else:
            return False, f"Unknown parameter kind: {kind}"

    def _validate_llm_config(
        self,
        parameters: Dict[str, Any],
        manifest_constraints: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate LLM configuration parameters.

        Args:
            parameters: The LLM parameters to validate.
            manifest_constraints: Optional constraints from manifest.

        Returns:
            Tuple of (is_valid, error_message).
        """
        manifest_constraints = manifest_constraints or {}

        # Validate temperature
        if "temperature" in parameters:
            temp = parameters["temperature"]
            if not isinstance(temp, (int, float)):
                return False, f"temperature must be numeric, got {type(temp)}"
            if temp < TEMPERATURE_MIN or temp > TEMPERATURE_MAX:
                return (
                    False,
                    f"temperature must be in range [{TEMPERATURE_MIN}, {TEMPERATURE_MAX}], got {temp}",
                )

        # Validate max_tokens
        if "max_tokens" in parameters:
            max_tokens = parameters["max_tokens"]
            if not isinstance(max_tokens, int):
                return False, f"max_tokens must be an integer, got {type(max_tokens)}"
            if max_tokens < MAX_TOKENS_MIN:
                return False, f"max_tokens must be >= {MAX_TOKENS_MIN}, got {max_tokens}"

            # Check against manifest constraint if provided
            manifest_max = manifest_constraints.get("max_tokens", MAX_TOKENS_MAX)
            if max_tokens > manifest_max:
                return (
                    False,
                    f"max_tokens {max_tokens} exceeds manifest limit {manifest_max}",
                )

        # Validate model
        if "model" in parameters:
            model = parameters["model"]
            if not isinstance(model, str):
                return False, f"model must be a string, got {type(model)}"

            # Check if model is supported
            is_supported = False
            for provider_models in SUPPORTED_MODELS.values():
                if model in provider_models:
                    is_supported = True
                    break

            if not is_supported:
                supported_list = [
                    m for models in SUPPORTED_MODELS.values() for m in models
                ]
                return (
                    False,
                    f"model {model} not in supported list: {supported_list}",
                )

        # Validate timeout
        if "timeout" in parameters:
            timeout = parameters["timeout"]
            if not isinstance(timeout, (int, float)):
                return False, f"timeout must be numeric, got {type(timeout)}"
            if timeout <= 0:
                return False, f"timeout must be > 0, got {timeout}"

        return True, None

    def _validate_tool_config(
        self,
        parameters: Dict[str, Any],
        manifest_constraints: Optional[Dict[str, Any]] = None,
        task_mode: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate tool configuration parameters.

        Args:
            parameters: The tool parameters to validate.
            manifest_constraints: Optional constraints from manifest.
            task_mode: Optional task mode for restrictions.

        Returns:
            Tuple of (is_valid, error_message).
        """
        manifest_constraints = manifest_constraints or {}

        # Validate enabled flag
        if "enabled" in parameters:
            enabled = parameters["enabled"]
            if not isinstance(enabled, bool):
                return False, f"enabled must be boolean, got {type(enabled)}"

        # Validate timeout
        if "timeout" in parameters:
            timeout = parameters["timeout"]
            if not isinstance(timeout, (int, float)):
                return False, f"timeout must be numeric, got {type(timeout)}"
            if timeout <= 0:
                return False, f"timeout must be > 0, got {timeout}"

        # Validate permissions (can't exceed manifest permissions)
        if "permissions" in parameters:
            override_perms = parameters["permissions"]
            manifest_perms = manifest_constraints.get("permissions", {})

            if isinstance(override_perms, dict):
                for perm_key, perm_value in override_perms.items():
                    manifest_perm = manifest_perms.get(perm_key, False)
                    # Can't grant more permissions than manifest allows
                    if perm_value and not manifest_perm:
                        return (
                            False,
                            f"override grants permission '{perm_key}' not in manifest",
                        )

        # TaskMode restrictions
        if task_mode == "DRY_RUN":
            if parameters.get("shell_enabled", False):
                return False, "shell is not allowed in DRY_RUN mode"

        if task_mode == "ANALYSIS_ONLY":
            if parameters.get("network_enabled", False):
                return False, "network is not allowed in ANALYSIS_ONLY mode"

        return True, None

    def _validate_execution_config(
        self,
        parameters: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """Validate execution configuration parameters.

        Args:
            parameters: The execution parameters to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        # Validate timeout
        if "timeout_seconds" in parameters:
            timeout = parameters["timeout_seconds"]
            if not isinstance(timeout, (int, float)):
                return False, f"timeout_seconds must be numeric, got {type(timeout)}"
            if timeout <= 0:
                return False, f"timeout_seconds must be > 0, got {timeout}"

        # Validate max_retries
        if "max_retries" in parameters:
            retries = parameters["max_retries"]
            if not isinstance(retries, int):
                return False, f"max_retries must be an integer, got {type(retries)}"
            if retries < 0:
                return False, f"max_retries must be >= 0, got {retries}"
            if retries > MAX_RETRIES_MAX:
                return (
                    False,
                    f"max_retries must be <= {MAX_RETRIES_MAX}, got {retries}",
                )

        # Validate retry_backoff
        if "retry_backoff" in parameters:
            backoff = parameters["retry_backoff"]
            if not isinstance(backoff, (int, float)):
                return False, f"retry_backoff must be numeric, got {type(backoff)}"
            if backoff <= 0:
                return False, f"retry_backoff must be > 0, got {backoff}"

        return True, None

    def clear_task_overrides(self, task_id: str) -> None:
        """Clear overrides for a task (call when task completes).

        Per-run scope means we reset after each task.

        Args:
            task_id: Task ID whose overrides should be cleared.
        """
        self.override_store.clear_task_overrides(task_id)
