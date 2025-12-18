"""Centralized path utilities for Agent Engine runtime state."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

STATE_ENV_VAR = "AGENT_ENGINE_STATE_DIR"


def resolve_state_root(config_dir: Optional[str] = None) -> Path:
    """Return the directory used for runtime state.

    Priority:
        1. AGENT_ENGINE_STATE_DIR environment variable (absolute or relative).
        2. `<config_dir>/.agent_engine` if config_dir provided.
        3. Current working directory `.agent_engine`.
    """
    env_path = os.getenv(STATE_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser().resolve()

    base = Path(config_dir).resolve() if config_dir else Path.cwd().resolve()
    return base / ".agent_engine"


def ensure_directory(path: Path) -> Path:
    """Create the directory if it does not exist and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_subdir(*parts: str, config_dir: Optional[str] = None, create: bool = True) -> Path:
    """Return a path under the state root, optionally creating directories."""
    root = resolve_state_root(config_dir)
    target = root.joinpath(*parts)
    if create:
        if target.suffix:  # treat as file -> ensure parent
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)
    return target
