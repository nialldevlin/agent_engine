#!/usr/bin/env python3
"""Health check script for Agent Engine deployment.

This script performs comprehensive health checks and is suitable for:
- Kubernetes liveness/readiness probes
- Docker HEALTHCHECK directive
- Systemd ExecHealthCheck
- Manual monitoring

Exit codes:
  0 = Healthy
  1 = Unhealthy
  2 = Degraded
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path


def get_config_dir() -> str:
    """Get configuration directory from environment or default."""
    return os.getenv("AGENT_ENGINE_CONFIG_DIR", "config")


def check_engine_load() -> dict:
    """Check if engine loads successfully."""
    try:
        from agent_engine import Engine

        config_dir = get_config_dir()
        engine = Engine.from_config_dir(config_dir)
        return {
            "status": "healthy",
            "message": "Engine loaded successfully",
            "version": engine.metadata.engine_version,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Engine load failed: {str(e)}",
        }


def check_manifests() -> dict:
    """Check manifest files exist and are valid."""
    config_dir = get_config_dir()
    required = ["workflow.yaml", "agents.yaml", "tools.yaml"]
    missing = []

    for fname in required:
        if not Path(config_dir) / fname:
            missing.append(fname)

    if missing:
        return {
            "status": "unhealthy",
            "message": f"Missing manifests: {', '.join(missing)}",
        }

    return {
        "status": "healthy",
        "message": f"All {len(required)} required manifests found",
    }


def check_dag_validation() -> dict:
    """Check DAG is valid."""
    try:
        from agent_engine import Engine

        config_dir = get_config_dir()
        engine = Engine.from_config_dir(config_dir)

        if engine.dag.validate():
            return {
                "status": "healthy",
                "message": "DAG validation passed",
                "nodes": len(engine.dag.nodes),
                "edges": len(engine.dag.edges),
            }
        else:
            return {
                "status": "unhealthy",
                "message": "DAG validation failed",
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"DAG validation error: {str(e)}",
        }


def check_manifest_timestamps() -> dict:
    """Check manifest file ages."""
    config_dir = get_config_dir()
    manifest_ages = {}
    max_age_seconds = 86400 * 30  # 30 days

    for fname in ["workflow.yaml", "agents.yaml", "tools.yaml"]:
        fpath = Path(config_dir) / fname
        if fpath.exists():
            age_seconds = (datetime.now() - datetime.fromtimestamp(fpath.stat().st_mtime)).total_seconds()
            manifest_ages[fname] = int(age_seconds)

            if age_seconds > max_age_seconds:
                return {
                    "status": "degraded",
                    "message": f"Manifest {fname} is {int(age_seconds / 86400)} days old",
                    "manifest_ages": manifest_ages,
                }

    return {
        "status": "healthy",
        "message": "All manifests within acceptable age",
        "manifest_ages": manifest_ages,
    }


def check_directories() -> dict:
    """Check required directories exist and are writable."""
    dirs_to_check = {
        "data": "data",
        "logs": "logs",
        "artifacts": "artifacts",
    }

    missing = []
    unwritable = []

    for label, dirname in dirs_to_check.items():
        path = Path(dirname)
        if not path.exists():
            missing.append(label)
        elif not os.access(path, os.W_OK):
            unwritable.append(label)

    if missing or unwritable:
        msg = ""
        if missing:
            msg += f"Missing: {', '.join(missing)}. "
        if unwritable:
            msg += f"Unwritable: {', '.join(unwritable)}"

        return {
            "status": "degraded",
            "message": msg.strip(),
        }

    return {
        "status": "healthy",
        "message": "All required directories exist and are writable",
    }


def check_environment() -> dict:
    """Check environment variables are set."""
    required_vars = ["AGENT_ENGINE_CONFIG_DIR"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        return {
            "status": "degraded",
            "message": f"Missing environment variables: {', '.join(missing)}",
        }

    return {
        "status": "healthy",
        "message": "Required environment variables set",
    }


def perform_health_check() -> dict:
    """Perform comprehensive health check."""
    checks = {
        "engine_load": check_engine_load(),
        "manifests": check_manifests(),
        "dag_validation": check_dag_validation(),
        "manifest_age": check_manifest_timestamps(),
        "directories": check_directories(),
        "environment": check_environment(),
    }

    # Determine overall status
    statuses = [check["status"] for check in checks.values()]
    if "unhealthy" in statuses:
        overall_status = "unhealthy"
    elif "degraded" in statuses:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    result = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks,
    }

    return result


def main() -> int:
    """Main entry point."""
    try:
        health = perform_health_check()

        # Output health check result
        print(json.dumps(health, indent=2))

        # Return appropriate exit code
        if health["status"] == "healthy":
            return 0
        elif health["status"] == "degraded":
            return 2
        else:
            return 1

    except Exception as e:
        error_result = {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": str(e),
        }
        print(json.dumps(error_result, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
