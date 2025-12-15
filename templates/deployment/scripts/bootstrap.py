#!/usr/bin/env python3
"""
Bootstrap script for Agent Engine deployment
Cross-platform initialization and setup tasks before main process starts
"""
import sys
import os
import json
import hashlib
import logging
import signal
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Optional colorama for cross-platform colors
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Fallback stubs
    class Fore:
        GREEN = RED = YELLOW = ""
    class Style:
        RESET_ALL = ""


class BootstrapLogger:
    """Custom logger with colored output and file logging"""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _log(self, level: str, message: str, color: str = ""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        colored_level = f"{color}[{level}]{Style.RESET_ALL}" if HAS_COLOR else f"[{level}]"
        log_line = f"{colored_level} {timestamp} - {message}"

        # Print to console
        print(log_line)

        # Write to file (without colors)
        plain_line = f"[{level}] {timestamp} - {message}\n"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(plain_line)

    def info(self, message: str):
        self._log("INFO", message, Fore.GREEN)

    def warn(self, message: str):
        self._log("WARN", message, Fore.YELLOW)

    def error(self, message: str):
        self._log("ERROR", message, Fore.RED)


def get_script_paths():
    """Get project paths based on script location"""
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent  # templates/deployment/scripts -> root
    config_dir = Path(os.getenv("AGENT_ENGINE_CONFIG_DIR", project_root / "config")).resolve()

    return {
        "project_root": project_root,
        "config_dir": config_dir,
        "data_dir": project_root / "data",
        "logs_dir": project_root / "logs",
        "artifacts_dir": project_root / "artifacts",
    }


def setup_directories(paths: dict, logger: BootstrapLogger):
    """Create required directories"""
    logger.info("Creating required directories...")

    for name in ["data_dir", "logs_dir", "artifacts_dir"]:
        path = paths[name]
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✓ {name.replace('_dir', '')}: {path}")


def validate_config_directory(paths: dict, logger: BootstrapLogger):
    """Validate configuration directory exists"""
    config_dir = paths["config_dir"]

    if not config_dir.exists():
        logger.error(f"Configuration directory not found: {config_dir}")
        sys.exit(1)

    logger.info(f"Configuration directory verified: {config_dir}")


def validate_manifests(paths: dict, logger: BootstrapLogger):
    """Check for required manifest files"""
    logger.info("Validating manifest files...")
    config_dir = paths["config_dir"]
    required_files = ["workflow.yaml", "agents.yaml", "tools.yaml"]

    for filename in required_files:
        manifest_path = config_dir / filename
        if not manifest_path.exists():
            logger.error(f"Required manifest file not found: {manifest_path}")
            sys.exit(1)
        logger.info(f"  ✓ {filename}")


def load_env_file(paths: dict, logger: BootstrapLogger):
    """Load environment variables from .env file if present"""
    env_file = paths["project_root"] / ".env"

    if not env_file.exists():
        return

    logger.info("Loading environment variables from .env")

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


def validate_python_version(logger: BootstrapLogger):
    """Validate Python version >= 3.10"""
    logger.info("Checking Python version...")

    version_info = sys.version_info
    current_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

    if version_info < (3, 10):
        logger.error(f"Python 3.10+ required, found: {current_version}")
        sys.exit(1)

    logger.info(f"Python version valid: {current_version}")


def validate_agent_engine(logger: BootstrapLogger) -> str:
    """Validate agent-engine is installed and return version"""
    logger.info("Checking agent-engine installation...")

    try:
        import agent_engine
        version = agent_engine.__version__
        logger.info(f"agent-engine version: {version}")
        return version
    except ImportError:
        logger.error("agent-engine package not installed")
        sys.exit(1)


def validate_configuration(paths: dict, logger: BootstrapLogger):
    """Validate configuration with agent-engine"""
    logger.info("Validating configuration with agent-engine...")

    try:
        from agent_engine import Engine

        config_dir = str(paths["config_dir"])
        engine = Engine.from_config_dir(config_dir)

        logger.info("  ✓ Configuration valid")
        logger.info(f"  ✓ Engine version: {engine.metadata.engine_version}")
        logger.info(f"  ✓ Manifests loaded: {len(engine.metadata.manifest_hashes)} files")

        # Validate DAG
        is_valid = engine.dag.validate()
        logger.info(f"  ✓ DAG validation: {'passed' if is_valid else 'failed'}")

        if not is_valid:
            logger.error("DAG validation failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)


def create_bootstrap_metadata(paths: dict, agent_version: str, logger: BootstrapLogger):
    """Create bootstrap metadata record"""
    logger.info("Recording bootstrap metadata...")

    # Calculate config hash
    workflow_file = paths["config_dir"] / "workflow.yaml"
    config_hash = ""
    if workflow_file.exists():
        with open(workflow_file, "rb") as f:
            config_hash = hashlib.sha256(f.read()).hexdigest()

    # Create metadata
    bootstrap_time = datetime.now(timezone.utc).isoformat()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    metadata = {
        "bootstrap_timestamp": bootstrap_time,
        "config_hash": config_hash,
        "deployment_env": os.getenv("AGENT_ENGINE_ENV", "development"),
        "agent_version": agent_version,
        "python_version": python_version,
    }

    # Write to file
    bootstrap_file = paths["data_dir"] / "bootstrap.json"
    with open(bootstrap_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Bootstrap metadata recorded")


def setup_signal_handlers(logger: BootstrapLogger):
    """Set up signal handlers for graceful shutdown"""
    logger.info("Setting up signal handlers...")

    def signal_handler(signum, frame):
        logger.info("Shutdown signal received")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def wait_for_postgres(logger: BootstrapLogger):
    """Wait for PostgreSQL to be ready (optional)"""
    import time

    if os.getenv("WAIT_FOR_POSTGRES", "false").lower() != "true":
        return

    logger.info("Waiting for PostgreSQL...")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        logger.warn("DATABASE_URL not set, skipping PostgreSQL wait")
        return

    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        try:
            import psycopg2
            psycopg2.connect(database_url)
            logger.info("PostgreSQL is ready")
            return
        except Exception:
            logger.warn(f"Attempt {attempt}/{max_attempts}: PostgreSQL not ready yet...")
            time.sleep(2)

    logger.error("PostgreSQL failed to start within timeout")
    sys.exit(1)


def run_pre_start_script(paths: dict, logger: BootstrapLogger):
    """Run optional pre-start script"""
    import subprocess

    pre_start = paths["project_root"] / "scripts" / "pre-start.sh"

    if not pre_start.exists():
        return

    logger.info("Running pre-start script...")

    try:
        subprocess.run(["bash", str(pre_start)], check=True)
    except subprocess.CalledProcessError:
        logger.error("Pre-start script failed")
        sys.exit(1)
    except FileNotFoundError:
        # bash not available (Windows), try python version
        pre_start_py = paths["project_root"] / "scripts" / "pre-start.py"
        if pre_start_py.exists():
            subprocess.run([sys.executable, str(pre_start_py)], check=True)


def main():
    """Main bootstrap sequence"""
    # Get paths
    paths = get_script_paths()

    # Set up logger
    logger = BootstrapLogger(paths["logs_dir"] / "bootstrap.log")

    # Set environment variables
    os.environ["AGENT_ENGINE_CONFIG_DIR"] = str(paths["config_dir"])
    os.environ["PYTHONUNBUFFERED"] = "1"

    # Bootstrap sequence
    setup_directories(paths, logger)
    validate_config_directory(paths, logger)
    validate_manifests(paths, logger)
    load_env_file(paths, logger)
    validate_python_version(logger)
    agent_version = validate_agent_engine(logger)
    validate_configuration(paths, logger)
    create_bootstrap_metadata(paths, agent_version, logger)
    setup_signal_handlers(logger)
    wait_for_postgres(logger)
    run_pre_start_script(paths, logger)

    logger.info("Bootstrap completed successfully")
    logger.info("Ready to start Agent Engine")

    return 0


if __name__ == "__main__":
    sys.exit(main())
