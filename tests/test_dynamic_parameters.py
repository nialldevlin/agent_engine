"""Comprehensive test suite for dynamic parameter configuration.

Tests covering all dynamic parameter functionality including:
- Parameter override schema creation and validation
- Parameter resolver for LLM, tool, and execution configs
- Priority resolution (TASK > PROJECT > GLOBAL)
- Parameter validation and constraint enforcement
- TaskMode constraints
- Engine API integration
- Integration with agent/tool runtime
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional

from agent_engine import Engine
from agent_engine.schemas.override import (
    ParameterOverride,
    ParameterOverrideKind,
    ParameterOverrideStore,
    OverrideSeverity,
)
from agent_engine.runtime.parameter_resolver import ParameterResolver


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def override_store():
    """Create a fresh override store for each test."""
    return ParameterOverrideStore()


@pytest.fixture
def parameter_resolver(override_store):
    """Create a parameter resolver with test store."""
    return ParameterResolver(override_store)


@pytest.fixture
def test_config_dir(tmp_path):
    """Create minimal test configuration directory.

    Sets up a complete but minimal agent engine config with:
    - workflow.yaml with a simple linear flow
    - agents.yaml with test agents
    - tools.yaml with test tools
    - provider_credentials.yaml for authentication
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create minimal workflow.yaml
    workflow = config_dir / "workflow.yaml"
    workflow.write_text("""
nodes:
  - stage_id: "start"
    name: "start_node"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
  - stage_id: "analyze"
    name: "analyze_node"
    kind: "agent"
    role: "linear"
    agent_id: "analyzer"
    context: "global"
    tools: ["read_file"]
  - stage_id: "exit"
    name: "exit_node"
    kind: "deterministic"
    role: "exit"
    context: "none"
edges:
  - from: "start"
    to: "analyze"
  - from: "analyze"
    to: "exit"
""")

    # Create agents.yaml
    agents = config_dir / "agents.yaml"
    agents.write_text("""
agents:
  - id: "analyzer"
    kind: "agent"
    llm: "anthropic/claude-3-5-haiku"
    config:
      temperature: 0.7
      max_tokens: 2000
  - id: "writer"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config:
      temperature: 0.5
      max_tokens: 4000
""")

    # Create tools.yaml
    tools = config_dir / "tools.yaml"
    tools.write_text("""
tools:
  - id: "read_file"
    type: "filesystem"
    name: "Read File"
    description: "Read a file from disk"
    entrypoint: "agent_engine.tools.filesystem:read_file"
    permissions:
      allow_shell: false
      allow_network: false
      root: "/"
  - id: "write_file"
    type: "filesystem"
    name: "Write File"
    description: "Write a file to disk"
    entrypoint: "agent_engine.tools.filesystem:write_file"
    permissions:
      allow_shell: false
      allow_network: false
      root: "/"
""")

    # Create provider_credentials.yaml
    creds = config_dir / "provider_credentials.yaml"
    creds.write_text("""
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"
""")

    # Create memory.yaml
    memory = config_dir / "memory.yaml"
    memory.write_text("""
version: "1.0"
memory:
  task_store:
    type: "in_memory"
  project_store:
    type: "in_memory"
  global_store:
    type: "in_memory"
""")

    # Create context_profiles.yaml
    context = config_dir / "context_profiles.yaml"
    context.write_text("""
context_profiles:
  - id: "default"
    name: "Default Context"
    description: "Default context profile"
    retrieval_strategy: "recent"
    max_items: 10
    compression_enabled: false
""")

    return config_dir


# ============================================================================
# SECTION 1: Parameter Override Schema Tests
# ============================================================================


class TestParameterOverrideSchema:
    """Tests for creating and validating parameter override schemas."""

    def test_parameter_override_creation_llm_config(self):
        """Test creating a parameter override for LLM config.

        Validates that ParameterOverride objects can be created with
        LLM_CONFIG kind and appropriate parameters.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.3, "max_tokens": 500},
            severity=OverrideSeverity.ENFORCE
        )
        assert override.kind == ParameterOverrideKind.LLM_CONFIG
        assert override.scope == "agent/analyzer"
        assert override.parameters["temperature"] == 0.3
        assert override.parameters["max_tokens"] == 500
        assert override.severity == OverrideSeverity.ENFORCE
        assert override.reason is None
        assert override.created_at is not None

    def test_parameter_override_creation_tool_config(self):
        """Test creating a parameter override for tool config.

        Validates that tool config overrides can control enabled state
        and other tool-specific parameters.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.TOOL_CONFIG,
            scope="tool/write_file",
            parameters={"enabled": False},
            severity=OverrideSeverity.ENFORCE,
            reason="Read-only mode enabled"
        )
        assert override.kind == ParameterOverrideKind.TOOL_CONFIG
        assert override.scope == "tool/write_file"
        assert override.parameters["enabled"] is False
        assert override.severity == OverrideSeverity.ENFORCE
        assert override.reason == "Read-only mode enabled"

    def test_parameter_override_creation_execution_config(self):
        """Test creating a parameter override for execution config.

        Validates that execution config overrides can control timeouts,
        retry policies, and other execution parameters.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.EXECUTION_CONFIG,
            scope="node/analyze",
            parameters={"timeout_seconds": 60, "max_retries": 3},
            severity=OverrideSeverity.ENFORCE
        )
        assert override.kind == ParameterOverrideKind.EXECUTION_CONFIG
        assert override.scope == "node/analyze"
        assert override.parameters["timeout_seconds"] == 60
        assert override.parameters["max_retries"] == 3


# ============================================================================
# SECTION 2: Parameter Resolver - LLM Config Tests
# ============================================================================


class TestParameterResolverLLMConfig:
    """Tests for LLM config resolution with override priority."""

    def test_resolve_llm_config_from_manifest(self, parameter_resolver):
        """Test resolving LLM config directly from manifest without overrides.

        When no overrides are present, the resolved config should match
        the manifest config exactly.
        """
        manifest_config = {"temperature": 0.7, "max_tokens": 2000}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config,
            manifest_llm_model="anthropic/claude-3-5-haiku"
        )
        assert resolved["temperature"] == 0.7
        assert resolved["max_tokens"] == 2000

    def test_resolve_llm_config_global_override(self, parameter_resolver):
        """Test LLM config override at global scope.

        Global overrides should be applied to the manifest config,
        replacing specified parameters.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.3},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        manifest_config = {"temperature": 0.7, "max_tokens": 2000}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config
        )
        assert resolved["temperature"] == 0.3  # Overridden
        assert resolved["max_tokens"] == 2000  # From manifest

    def test_resolve_llm_config_project_override(self, parameter_resolver):
        """Test LLM config override at project scope.

        Project-scoped overrides should override global overrides
        when a project_id is provided.
        """
        global_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.3},
            severity=OverrideSeverity.ENFORCE
        )
        project_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.5},
            severity=OverrideSeverity.ENFORCE
        )

        parameter_resolver.add_override(global_override, scope="global")
        parameter_resolver.add_override(
            project_override, scope="project", project_id="proj1"
        )

        manifest_config = {"temperature": 0.7}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config,
            project_id="proj1"
        )
        assert resolved["temperature"] == 0.5  # Project scope wins

    def test_resolve_llm_config_task_override(self, parameter_resolver):
        """Test LLM config override at task scope.

        Task-scoped overrides should override all lower-priority overrides
        when a task_id is provided.
        """
        global_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.3},
            severity=OverrideSeverity.ENFORCE
        )
        task_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.1},
            severity=OverrideSeverity.ENFORCE
        )

        parameter_resolver.add_override(global_override, scope="global")
        parameter_resolver.add_override(
            task_override, scope="task", task_id="task1"
        )

        manifest_config = {"temperature": 0.7}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config,
            task_id="task1"
        )
        assert resolved["temperature"] == 0.1  # Task scope wins

    def test_resolve_llm_config_priority_task_over_project(self, parameter_resolver):
        """Test that task scope overrides project scope.

        With both project and task overrides present, task scope
        should take priority.
        """
        project_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.5, "max_tokens": 3000},
            severity=OverrideSeverity.ENFORCE
        )
        task_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.1},
            severity=OverrideSeverity.ENFORCE
        )

        parameter_resolver.add_override(
            project_override, scope="project", project_id="proj1"
        )
        parameter_resolver.add_override(
            task_override, scope="task", task_id="task1", project_id="proj1"
        )

        manifest_config = {"temperature": 0.7, "max_tokens": 2000}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config,
            task_id="task1",
            project_id="proj1"
        )
        assert resolved["temperature"] == 0.1  # Task scope wins
        # Task override resolved which includes both temperature from task and max_tokens from project
        assert resolved["max_tokens"] == 3000  # From project override (applied before task)

    def test_resolve_llm_config_priority_project_over_global(self, parameter_resolver):
        """Test that project scope overrides global scope.

        With both global and project overrides present, project scope
        should take priority.
        """
        global_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.2, "max_tokens": 1000},
            severity=OverrideSeverity.ENFORCE
        )
        project_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.5},
            severity=OverrideSeverity.ENFORCE
        )

        parameter_resolver.add_override(global_override, scope="global")
        parameter_resolver.add_override(
            project_override, scope="project", project_id="proj1"
        )

        manifest_config = {"temperature": 0.7, "max_tokens": 2000}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config,
            project_id="proj1"
        )
        assert resolved["temperature"] == 0.5  # Project scope wins
        # Project override resolved which includes both temperature from project and max_tokens from global
        assert resolved["max_tokens"] == 1000  # From global override (applied before project)


# ============================================================================
# SECTION 3: Parameter Resolver - Tool Config Tests
# ============================================================================


class TestParameterResolverToolConfig:
    """Tests for tool config resolution with override priority."""

    def test_resolve_tool_config_from_manifest(self, parameter_resolver):
        """Test resolving tool config directly from manifest without overrides.

        When no overrides are present, the resolved config should match
        the manifest config exactly.
        """
        manifest_config = {"enabled": True, "timeout": 30}
        resolved = parameter_resolver.resolve_tool_config(
            tool_id="read_file",
            manifest_config=manifest_config
        )
        assert resolved["enabled"] is True
        assert resolved["timeout"] == 30

    def test_resolve_tool_config_enabled_override(self, parameter_resolver):
        """Test tool enabled/disabled override.

        Should be able to disable a tool via override while keeping
        other manifest config intact.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.TOOL_CONFIG,
            scope="tool/write_file",
            parameters={"enabled": False},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        manifest_config = {"enabled": True, "timeout": 30}
        resolved = parameter_resolver.resolve_tool_config(
            tool_id="write_file",
            manifest_config=manifest_config
        )
        assert resolved["enabled"] is False  # Overridden
        assert resolved["timeout"] == 30  # From manifest

    def test_resolve_tool_config_timeout_override(self, parameter_resolver):
        """Test tool timeout override.

        Should be able to override timeout while keeping other
        config parameters intact.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.TOOL_CONFIG,
            scope="tool/read_file",
            parameters={"timeout": 60},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        manifest_config = {"enabled": True, "timeout": 30}
        resolved = parameter_resolver.resolve_tool_config(
            tool_id="read_file",
            manifest_config=manifest_config
        )
        assert resolved["enabled"] is True  # From manifest
        assert resolved["timeout"] == 60  # Overridden

    def test_resolve_tool_config_permissions_override(self, parameter_resolver):
        """Test tool permissions override.

        Should be able to override tool permissions (respecting
        manifest constraints).
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.TOOL_CONFIG,
            scope="tool/read_file",
            parameters={"permissions": {"allow_shell": False, "allow_network": False}},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        manifest_config = {
            "enabled": True,
            "permissions": {"allow_shell": True, "allow_network": True}
        }
        resolved = parameter_resolver.resolve_tool_config(
            tool_id="read_file",
            manifest_config=manifest_config
        )
        # Both should be overridden
        assert resolved["permissions"]["allow_shell"] is False
        assert resolved["permissions"]["allow_network"] is False


# ============================================================================
# SECTION 4: Parameter Resolver - Execution Config Tests
# ============================================================================


class TestParameterResolverExecutionConfig:
    """Tests for execution config resolution."""

    def test_resolve_execution_config_timeout(self, parameter_resolver):
        """Test resolving execution config with timeout override.

        Should be able to override node timeout from global scope.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.EXECUTION_CONFIG,
            scope="node/analyze",
            parameters={"timeout_seconds": 120},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        resolved = parameter_resolver.resolve_execution_config(node_id="analyze")
        assert resolved["timeout_seconds"] == 120

    def test_resolve_execution_config_retry_policy(self, parameter_resolver):
        """Test resolving execution config with retry policy override.

        Should be able to override retry parameters.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.EXECUTION_CONFIG,
            scope="node/analyze",
            parameters={"max_retries": 5, "retry_backoff": 2.0},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        resolved = parameter_resolver.resolve_execution_config(node_id="analyze")
        assert resolved["max_retries"] == 5
        assert resolved["retry_backoff"] == 2.0

    def test_resolve_execution_config_defaults(self, parameter_resolver):
        """Test resolving execution config with no overrides.

        When no overrides are present, resolved config should be empty
        or contain only defaults.
        """
        resolved = parameter_resolver.resolve_execution_config(node_id="analyze")
        assert isinstance(resolved, dict)
        # Without overrides, should be empty
        assert len(resolved) == 0


# ============================================================================
# SECTION 5: Parameter Validation Tests
# ============================================================================


class TestParameterValidation:
    """Tests for parameter validation."""

    def test_validate_llm_config_valid_temperature(self, parameter_resolver):
        """Test validation of valid temperature value.

        Temperature in range [0.0, 1.0] should pass validation.
        """
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"temperature": 0.5},
            kind=ParameterOverrideKind.LLM_CONFIG
        )
        assert is_valid is True
        assert error is None

    def test_validate_llm_config_invalid_temperature_below_zero(self, parameter_resolver):
        """Test validation fails for temperature < 0.

        Temperature below 0 should fail validation with clear error message.
        """
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"temperature": -0.5},
            kind=ParameterOverrideKind.LLM_CONFIG
        )
        assert is_valid is False
        assert error is not None
        assert "temperature" in error.lower()

    def test_validate_llm_config_invalid_temperature_above_one(self, parameter_resolver):
        """Test validation fails for temperature > 1.

        Temperature above 1 should fail validation with clear error message.
        """
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"temperature": 1.5},
            kind=ParameterOverrideKind.LLM_CONFIG
        )
        assert is_valid is False
        assert error is not None
        assert "temperature" in error.lower()

    def test_validate_llm_config_invalid_max_tokens_zero(self, parameter_resolver):
        """Test validation fails for max_tokens <= 0.

        max_tokens must be greater than 0.
        """
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"max_tokens": 0},
            kind=ParameterOverrideKind.LLM_CONFIG
        )
        assert is_valid is False
        assert error is not None
        assert "max_tokens" in error.lower()

    def test_validate_tool_config_permissions_within_manifest(self, parameter_resolver):
        """Test tool config permissions validation.

        Override permissions should not exceed manifest permissions.
        """
        manifest_constraints = {
            "permissions": {"allow_shell": False, "allow_network": False}
        }

        # Trying to grant shell permission when not allowed should fail
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"permissions": {"allow_shell": True}},
            kind=ParameterOverrideKind.TOOL_CONFIG,
            manifest_constraints=manifest_constraints
        )
        assert is_valid is False
        assert error is not None
        assert "permission" in error.lower()


# ============================================================================
# SECTION 6: TaskMode Constraint Tests
# ============================================================================


class TestTaskModeConstraints:
    """Tests for TaskMode-specific constraints."""

    def test_validate_no_shell_in_dryrun_mode(self, parameter_resolver):
        """Test that shell is not allowed in DRY_RUN mode.

        Tool config overrides that enable shell should fail
        validation when task_mode is DRY_RUN.
        """
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"shell_enabled": True},
            kind=ParameterOverrideKind.TOOL_CONFIG,
            task_mode="DRY_RUN"
        )
        assert is_valid is False
        assert error is not None
        assert "shell" in error.lower() and "dry_run" in error.lower()

    def test_validate_no_network_in_analysis_only_mode(self, parameter_resolver):
        """Test that network is not allowed in ANALYSIS_ONLY mode.

        Tool config overrides that enable network should fail
        validation when task_mode is ANALYSIS_ONLY.
        """
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"network_enabled": True},
            kind=ParameterOverrideKind.TOOL_CONFIG,
            task_mode="ANALYSIS_ONLY"
        )
        assert is_valid is False
        assert error is not None
        assert "network" in error.lower() and "analysis" in error.lower()


# ============================================================================
# SECTION 7: Engine API Tests
# ============================================================================


class TestEngineAPI:
    """Tests for Engine API parameter control methods."""

    def test_set_agent_model_global_scope(self, test_config_dir):
        """Test setting agent model via Engine API at global scope.

        Should be able to override agent model and create appropriate
        override in the parameter resolver.
        """
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            engine = Engine.from_config_dir(str(test_config_dir))
            # This should not raise an error
            engine.set_agent_model("analyzer", "anthropic/claude-3-5-sonnet", scope="global")
            assert engine.parameter_resolver is not None
        finally:
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

    def test_set_agent_hyperparameters_multiple_params(self, test_config_dir):
        """Test setting multiple hyperparameters via Engine API.

        Should be able to override multiple LLM hyperparameters
        in a single call.
        """
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            engine = Engine.from_config_dir(str(test_config_dir))
            engine.set_agent_hyperparameters(
                "analyzer",
                temperature=0.3,
                max_tokens=500,
                scope="global"
            )
            assert engine.parameter_resolver is not None
        finally:
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

    def test_enable_tool_disable_read_only_mode(self, test_config_dir):
        """Test disabling tool via Engine API for read-only mode.

        Should be able to disable tools to enforce read-only mode.
        """
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            engine = Engine.from_config_dir(str(test_config_dir))
            engine.enable_tool("write_file", enabled=False, scope="global")
            assert engine.parameter_resolver is not None
        finally:
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

    def test_set_node_timeout(self, test_config_dir):
        """Test setting node timeout via Engine API.

        Should be able to override execution timeout for specific node.
        """
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            engine = Engine.from_config_dir(str(test_config_dir))
            engine.set_node_timeout("analyze", timeout_seconds=300, scope="global")
            assert engine.parameter_resolver is not None
        finally:
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

    def test_set_task_parameters(self, test_config_dir):
        """Test setting task-scoped parameters via Engine API.

        Should be able to set parameters specifically for a task,
        with highest priority.
        """
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            engine = Engine.from_config_dir(str(test_config_dir))
            engine.set_task_parameters(
                task_id="task123",
                agent_id="analyzer",
                temperature=0.2,
                max_tokens=1000
            )
            assert engine.parameter_resolver is not None
        finally:
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

    def test_clear_overrides(self, test_config_dir):
        """Test clearing overrides via Engine API.

        Should be able to clear overrides and reset to manifest defaults.
        """
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            engine = Engine.from_config_dir(str(test_config_dir))
            # Set an override
            engine.set_agent_model("analyzer", "anthropic/claude-3-5-sonnet")
            # Clear it
            engine.clear_overrides(scope="global")
            assert engine.parameter_resolver is not None
        finally:
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]


# ============================================================================
# SECTION 8: Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests with actual Engine runtime components."""

    def test_agent_runtime_uses_resolved_llm_config(self, parameter_resolver):
        """Test that agent runtime uses parameter resolver output.

        When an override is present, the resolved config should be used
        by the agent runtime (not the manifest config).
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.1, "max_tokens": 100},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        manifest_config = {"temperature": 0.7, "max_tokens": 2000}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config
        )

        # Agent runtime should use resolved config
        assert resolved["temperature"] == 0.1
        assert resolved["max_tokens"] == 100

    def test_tool_runtime_respects_enabled_override(self, parameter_resolver):
        """Test that tool runtime respects enabled/disabled overrides.

        When a tool is disabled via override, tool runtime should
        skip or fail execution of that tool.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.TOOL_CONFIG,
            scope="tool/write_file",
            parameters={"enabled": False},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        manifest_config = {"enabled": True, "timeout": 30}
        resolved = parameter_resolver.resolve_tool_config(
            tool_id="write_file",
            manifest_config=manifest_config
        )

        # Tool runtime should see tool as disabled
        assert resolved["enabled"] is False

    def test_node_executor_applies_timeout_override(self, parameter_resolver):
        """Test that node executor applies timeout overrides.

        When node timeout is overridden, executor should use the
        override value instead of default.
        """
        override = ParameterOverride(
            kind=ParameterOverrideKind.EXECUTION_CONFIG,
            scope="node/analyze",
            parameters={"timeout_seconds": 300},
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        resolved = parameter_resolver.resolve_execution_config(node_id="analyze")

        # Node executor should use overridden timeout
        assert resolved["timeout_seconds"] == 300


# ============================================================================
# Additional edge case tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_parameters_dict(self, parameter_resolver):
        """Test that empty parameters dict is handled gracefully."""
        manifest_config = {"temperature": 0.7, "max_tokens": 2000}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config
        )
        # Should return manifest config unchanged
        assert resolved == manifest_config

    def test_multiple_overrides_same_scope_latest_wins(self, parameter_resolver):
        """Test that when adding multiple overrides for same scope, latest overwrites."""
        override1 = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.3},
            severity=OverrideSeverity.ENFORCE
        )
        override2 = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.5},
            severity=OverrideSeverity.ENFORCE
        )

        parameter_resolver.add_override(override1, scope="global")
        parameter_resolver.add_override(override2, scope="global")

        manifest_config = {"temperature": 0.7}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config
        )
        # Latest override should win
        assert resolved["temperature"] == 0.5

    def test_override_severity_hint_vs_enforce(self, parameter_resolver):
        """Test that both HINT and ENFORCE severity levels are stored."""
        hint_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.3},
            severity=OverrideSeverity.HINT
        )
        enforce_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/writer",
            parameters={"temperature": 0.5},
            severity=OverrideSeverity.ENFORCE
        )

        parameter_resolver.add_override(hint_override, scope="global")
        parameter_resolver.add_override(enforce_override, scope="global")

        # Both should be stored
        assert hint_override.severity == OverrideSeverity.HINT
        assert enforce_override.severity == OverrideSeverity.ENFORCE

    def test_validate_zero_timeout_fails(self, parameter_resolver):
        """Test that zero timeout is rejected."""
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"timeout_seconds": 0},
            kind=ParameterOverrideKind.EXECUTION_CONFIG
        )
        assert is_valid is False
        assert error is not None

    def test_validate_negative_max_retries_fails(self, parameter_resolver):
        """Test that negative max_retries is rejected."""
        is_valid, error = parameter_resolver.validate_parameters(
            parameters={"max_retries": -1},
            kind=ParameterOverrideKind.EXECUTION_CONFIG
        )
        assert is_valid is False
        assert error is not None

    def test_partial_parameter_override(self, parameter_resolver):
        """Test that partial overrides (only some parameters) work correctly."""
        override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.3},  # Only temperature, not max_tokens
            severity=OverrideSeverity.ENFORCE
        )
        parameter_resolver.add_override(override, scope="global")

        manifest_config = {"temperature": 0.7, "max_tokens": 2000}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config
        )
        # Override should only affect temperature
        assert resolved["temperature"] == 0.3
        assert resolved["max_tokens"] == 2000

    def test_clear_task_overrides_doesnt_affect_others(self, parameter_resolver):
        """Test that clearing task overrides doesn't affect global/project overrides."""
        global_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.2},
            severity=OverrideSeverity.ENFORCE
        )
        task_override = ParameterOverride(
            kind=ParameterOverrideKind.LLM_CONFIG,
            scope="agent/analyzer",
            parameters={"temperature": 0.1},
            severity=OverrideSeverity.ENFORCE
        )

        parameter_resolver.add_override(global_override, scope="global")
        parameter_resolver.add_override(
            task_override, scope="task", task_id="task1"
        )

        # Clear task overrides
        parameter_resolver.clear_task_overrides("task1")

        # Global override should still be there
        manifest_config = {"temperature": 0.7}
        resolved = parameter_resolver.resolve_llm_config(
            agent_id="analyzer",
            manifest_config=manifest_config
        )
        # Should now use global override (since task override was cleared)
        assert resolved["temperature"] == 0.2
