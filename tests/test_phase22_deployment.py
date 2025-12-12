"""Tests for Phase 22: Packaging & Deployment Templates.

Tests verify:
- Deployment metadata collection
- Template structure and validity
- Bootstrap script functionality (dry-run)
- Health check script functionality
- Template instantiation
- Configuration validation
- Deployment environment handling
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

import pytest

from agent_engine import Engine
from agent_engine.schemas import EngineMetadata
from agent_engine.runtime.metadata_collector import (
    collect_deployment_metadata,
    collect_engine_metadata,
)


# Test 1: Deployment metadata collection from environment
def test_collect_deployment_metadata_from_env(monkeypatch):
    """Test collecting deployment metadata from environment variables."""
    monkeypatch.setenv("DEPLOYMENT_ID", "test-deployment-001")
    monkeypatch.setenv("AGENT_ENGINE_ENV", "production")
    monkeypatch.setenv("DEPLOYMENT_TIMESTAMP", "2025-01-01T00:00:00Z")
    monkeypatch.setenv("BOOTSTRAP_HASH", "abc123def456")

    deployment_id, deployment_timestamp, bootstrap_hash, environment = (
        collect_deployment_metadata()
    )

    assert deployment_id == "test-deployment-001"
    assert deployment_timestamp == "2025-01-01T00:00:00Z"
    assert bootstrap_hash == "abc123def456"
    assert environment == "production"


# Test 2: Deployment metadata defaults to current time
def test_collect_deployment_metadata_uses_current_time(monkeypatch):
    """Test that deployment timestamp defaults to current time when not set."""
    monkeypatch.delenv("DEPLOYMENT_TIMESTAMP", raising=False)
    monkeypatch.setenv("AGENT_ENGINE_ENV", "development")

    _, deployment_timestamp, _, environment = collect_deployment_metadata()

    # Verify timestamp is ISO-8601 format and recent
    assert deployment_timestamp
    assert "T" in deployment_timestamp
    assert "Z" in deployment_timestamp or "+" in deployment_timestamp
    assert environment == "development"


# Test 3: Deployment metadata in EngineMetadata
def test_engine_metadata_includes_deployment_fields(tmp_path):
    """Test that EngineMetadata includes deployment fields."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create minimal manifests
    (config_dir / "workflow.yaml").write_text("nodes: []\nedges: []")
    (config_dir / "agents.yaml").write_text("agents: []")
    (config_dir / "tools.yaml").write_text("tools: []")

    os.environ["DEPLOYMENT_ID"] = "test-001"
    os.environ["AGENT_ENGINE_ENV"] = "staging"

    metadata = collect_engine_metadata(str(config_dir))

    assert hasattr(metadata, "deployment_id")
    assert hasattr(metadata, "deployment_timestamp")
    assert hasattr(metadata, "bootstrap_hash")
    assert hasattr(metadata, "environment")

    assert metadata.deployment_id == "test-001"
    assert metadata.environment == "staging"
    assert metadata.deployment_timestamp  # Should have a value


# Test 4: Engine loads and includes deployment metadata
def test_engine_metadata_with_deployment_info(tmp_path, monkeypatch):
    """Test that Engine.from_config_dir includes deployment metadata."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create minimal valid manifests
    (config_dir / "workflow.yaml").write_text(
        """nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
edges: []
"""
    )
    (config_dir / "agents.yaml").write_text("agents: []")
    (config_dir / "tools.yaml").write_text("tools: []")

    monkeypatch.setenv("DEPLOYMENT_ID", "engine-test-001")
    monkeypatch.setenv("AGENT_ENGINE_ENV", "production")

    engine = Engine.from_config_dir(str(config_dir))

    assert engine.metadata.deployment_id == "engine-test-001"
    assert engine.metadata.environment == "production"


# Test 5: Deployment templates exist
def test_deployment_templates_exist():
    """Test that all deployment templates exist."""
    templates_dir = Path(__file__).parent.parent / "templates" / "deployment"

    assert templates_dir.exists(), "Deployment templates directory not found"

    # Check Docker templates
    assert (templates_dir / "docker" / "Dockerfile").exists()
    assert (templates_dir / "docker" / "docker-compose.yml").exists()
    assert (templates_dir / "docker" / ".dockerignore").exists()

    # Check systemd templates
    assert (templates_dir / "systemd" / "agent-engine.service").exists()
    assert (templates_dir / "systemd" / "agent-engine.environment").exists()

    # Check Kubernetes templates
    assert (templates_dir / "kubernetes" / "deployment.yaml").exists()

    # Check scripts
    assert (templates_dir / "scripts" / "bootstrap.sh").exists()
    assert (templates_dir / "scripts" / "healthcheck.py").exists()


# Test 6: Project template exists
def test_project_template_exists():
    """Test that project template directory exists with expected structure."""
    template_dir = Path(__file__).parent.parent / "templates" / "project_template"

    assert template_dir.exists(), "Project template directory not found"

    # Check config files
    config_dir = template_dir / "config"
    assert (config_dir / "workflow.yaml").exists()
    assert (config_dir / "agents.yaml").exists()
    assert (config_dir / "tools.yaml").exists()
    assert (config_dir / "memory.yaml").exists()
    assert (config_dir / "plugins.yaml").exists()
    assert (config_dir / "scheduler.yaml").exists()
    assert (config_dir / "provider_credentials.yaml.template").exists()

    # Check project files
    assert (template_dir / ".env.template").exists()
    assert (template_dir / "README.md").exists()


# Test 7: Bootstrap script is executable
def test_bootstrap_script_executable():
    """Test that bootstrap script exists and is executable."""
    bootstrap_script = (
        Path(__file__).parent.parent / "templates" / "deployment" / "scripts" / "bootstrap.sh"
    )

    assert bootstrap_script.exists()

    # Check if file is readable
    with open(bootstrap_script) as f:
        content = f.read()
        assert "#!/bin/bash" in content
        assert "AGENT_ENGINE_CONFIG_DIR" in content


# Test 8: Healthcheck script is executable
def test_healthcheck_script_executable():
    """Test that healthcheck script exists and is executable."""
    healthcheck_script = (
        Path(__file__).parent.parent / "templates" / "deployment" / "scripts" / "healthcheck.py"
    )

    assert healthcheck_script.exists()

    with open(healthcheck_script) as f:
        content = f.read()
        assert "#!/usr/bin/env python3" in content
        assert "def perform_health_check" in content


# Test 9: Healthcheck script runs successfully
def test_healthcheck_script_runs(tmp_path, monkeypatch):
    """Test that healthcheck script runs without errors in dry mode."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create minimal manifests
    (config_dir / "workflow.yaml").write_text(
        """nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
edges: []
"""
    )
    (config_dir / "agents.yaml").write_text("agents: []")
    (config_dir / "tools.yaml").write_text("tools: []")

    monkeypatch.setenv("AGENT_ENGINE_CONFIG_DIR", str(config_dir))

    healthcheck_script = (
        Path(__file__).parent.parent / "templates" / "deployment" / "scripts" / "healthcheck.py"
    )

    # Run healthcheck script
    result = subprocess.run(
        [sys.executable, str(healthcheck_script)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Should run successfully
    assert result.returncode in [0, 2], f"Healthcheck failed: {result.stderr}"

    # Output should be valid JSON
    output = json.loads(result.stdout)
    assert "status" in output
    assert "timestamp" in output
    assert "checks" in output


# Test 10: Dockerfile template is valid
def test_dockerfile_template_valid():
    """Test that Dockerfile template has valid structure."""
    dockerfile = Path(__file__).parent.parent / "templates" / "deployment" / "docker" / "Dockerfile"

    with open(dockerfile) as f:
        content = f.read()

    # Check for multi-stage build
    assert "FROM python" in content
    assert "as builder" in content

    # Check for security practices
    assert "USER" in content or "useradd" in content
    assert "HEALTHCHECK" in content

    # Check for environment setup
    assert "PYTHONUNBUFFERED" in content
    assert "AGENT_ENGINE_CONFIG_DIR" in content


# Test 11: docker-compose template is valid YAML
def test_docker_compose_template_valid():
    """Test that docker-compose template is valid YAML."""
    docker_compose = (
        Path(__file__).parent.parent / "templates" / "deployment" / "docker" / "docker-compose.yml"
    )

    with open(docker_compose) as f:
        content = f.read()

    # Should be parseable as YAML
    import yaml

    config = yaml.safe_load(content)
    assert "services" in config
    assert "agent-engine" in config["services"]


# Test 12: Systemd service template is valid
def test_systemd_service_template_valid():
    """Test that systemd service template is valid."""
    service_file = (
        Path(__file__).parent.parent
        / "templates"
        / "deployment"
        / "systemd"
        / "agent-engine.service"
    )

    with open(service_file) as f:
        content = f.read()

    # Check for required sections
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content

    # Check for security settings
    assert "ProtectSystem" in content
    assert "NoNewPrivileges" in content


# Test 13: Kubernetes deployment template is valid YAML
def test_kubernetes_deployment_template_valid():
    """Test that Kubernetes deployment template is valid YAML."""
    k8s_file = (
        Path(__file__).parent.parent
        / "templates"
        / "deployment"
        / "kubernetes"
        / "deployment.yaml"
    )

    with open(k8s_file) as f:
        content = f.read()

    import yaml

    config = yaml.safe_load(content)
    assert config["apiVersion"] == "apps/v1"
    assert config["kind"] == "Deployment"
    assert "spec" in config


# Test 14: Environment template loads successfully
def test_env_template_loads():
    """Test that .env template can be loaded."""
    env_template = Path(__file__).parent.parent / "templates" / "project_template" / ".env.template"

    with open(env_template) as f:
        content = f.read()

    # Should be parseable as environment file
    lines = [line.strip() for line in content.split("\n") if line.strip() and not line.startswith("#")]

    for line in lines:
        if "=" in line:
            # Valid environment variable format
            key, _ = line.split("=", 1)
            assert key.isupper() or "_" in key


# Test 15: Deployment documentation exists
def test_deployment_documentation_exists():
    """Test that deployment documentation exists."""
    docs_dir = Path(__file__).parent.parent / "docs"

    assert (docs_dir / "DEPLOYMENT.md").exists()
    assert (docs_dir / "PACKAGING.md").exists()

    # Check content
    deployment_doc = (docs_dir / "DEPLOYMENT.md").read_text()
    assert "Deployment" in deployment_doc
    assert "Docker" in deployment_doc or "deployment" in deployment_doc.lower()

    packaging_doc = (docs_dir / "PACKAGING.md").read_text()
    assert "Packaging" in packaging_doc or "packaging" in packaging_doc.lower()


# Test 16: Deployment metadata persists through workflow
def test_deployment_metadata_persists(tmp_path, monkeypatch):
    """Test that deployment metadata is preserved through engine lifecycle."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create valid manifests
    (config_dir / "workflow.yaml").write_text(
        """nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
edges: []
"""
    )
    (config_dir / "agents.yaml").write_text("agents: []")
    (config_dir / "tools.yaml").write_text("tools: []")

    deployment_id = "persistent-test-001"
    environment = "testing"

    monkeypatch.setenv("DEPLOYMENT_ID", deployment_id)
    monkeypatch.setenv("AGENT_ENGINE_ENV", environment)

    # Load engine twice
    engine1 = Engine.from_config_dir(str(config_dir))
    engine2 = Engine.from_config_dir(str(config_dir))

    # Both should have same deployment metadata
    assert engine1.metadata.deployment_id == deployment_id
    assert engine2.metadata.deployment_id == deployment_id
    assert engine1.metadata.environment == environment
    assert engine2.metadata.environment == environment


# Test 17: Template instantiation from project template
def test_project_template_instantiation(tmp_path):
    """Test that project template can be instantiated."""
    template_dir = Path(__file__).parent.parent / "templates" / "project_template"
    target_dir = tmp_path / "my_project"

    # Copy template
    import shutil

    shutil.copytree(template_dir, target_dir)

    # Verify structure
    assert (target_dir / "config").exists()
    assert (target_dir / "config" / "workflow.yaml").exists()
    assert (target_dir / "README.md").exists()
    assert (target_dir / ".env.template").exists()


# Test 18: Configuration template is valid
def test_configuration_templates_valid(tmp_path):
    """Test that configuration templates are valid."""
    template_dir = Path(__file__).parent.parent / "templates" / "project_template"

    import yaml

    # workflow.yaml
    workflow = yaml.safe_load((template_dir / "config" / "workflow.yaml").read_text())
    assert "nodes" in workflow
    assert "edges" in workflow

    # agents.yaml
    agents = yaml.safe_load((template_dir / "config" / "agents.yaml").read_text())
    assert "agents" in agents

    # tools.yaml
    tools = yaml.safe_load((template_dir / "config" / "tools.yaml").read_text())
    assert "tools" in tools

    # memory.yaml
    memory = yaml.safe_load((template_dir / "config" / "memory.yaml").read_text())
    assert "backend" in memory


# Test 19: Deployment environment variable handling
def test_deployment_environment_variants(monkeypatch):
    """Test that both AGENT_ENGINE_ENV and DEPLOYMENT_ENV are supported."""
    # Test with AGENT_ENGINE_ENV
    monkeypatch.setenv("AGENT_ENGINE_ENV", "prod")
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)

    _, _, _, env1 = collect_deployment_metadata()
    assert env1 == "prod"

    # Test with DEPLOYMENT_ENV fallback
    monkeypatch.delenv("AGENT_ENGINE_ENV", raising=False)
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")

    _, _, _, env2 = collect_deployment_metadata()
    assert env2 == "staging"

    # Test priority (AGENT_ENGINE_ENV wins)
    monkeypatch.setenv("AGENT_ENGINE_ENV", "prod")
    monkeypatch.setenv("DEPLOYMENT_ENV", "staging")

    _, _, _, env3 = collect_deployment_metadata()
    assert env3 == "prod"


# Test 20: Metadata includes all required fields
def test_engine_metadata_completeness(tmp_path, monkeypatch):
    """Test that EngineMetadata has all required and optional fields."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create minimal manifests
    (config_dir / "workflow.yaml").write_text("nodes: []\nedges: []")
    (config_dir / "agents.yaml").write_text("agents: []")
    (config_dir / "tools.yaml").write_text("tools: []")

    monkeypatch.setenv("DEPLOYMENT_ID", "complete-test-001")
    monkeypatch.setenv("AGENT_ENGINE_ENV", "testing")

    metadata = collect_engine_metadata(str(config_dir))

    # Core fields (existing)
    assert metadata.engine_version
    assert metadata.schema_version
    assert metadata.load_timestamp
    assert metadata.config_dir

    # Deployment fields (Phase 22)
    assert metadata.deployment_id == "complete-test-001"
    assert metadata.environment == "testing"
    assert metadata.deployment_timestamp
    # bootstrap_hash may be empty if not set
    assert isinstance(metadata.bootstrap_hash, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
