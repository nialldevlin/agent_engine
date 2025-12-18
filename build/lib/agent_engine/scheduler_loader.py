"""Scheduler manifest loader for Phase 21.

Loads optional scheduler.yaml configuration.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from .schemas.scheduler import SchedulerConfig, QueuePolicy


def load_scheduler_manifest(config_dir: str) -> Optional[Dict[str, Any]]:
    """Load optional scheduler.yaml manifest.

    Per canonical design:
    - File is optional
    - If missing, default config is used
    - Returns None if file doesn't exist

    Args:
        config_dir: Path to config directory

    Returns:
        Parsed YAML as dict, or None if file not found

    Raises:
        ValueError: If YAML is invalid
    """
    scheduler_path = Path(config_dir) / "scheduler.yaml"

    if not scheduler_path.exists():
        return None

    try:
        import yaml
        with open(scheduler_path, 'r') as f:
            data = yaml.safe_load(f)
            return data if data else {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid scheduler.yaml: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load scheduler.yaml: {e}")


def parse_scheduler(data: Optional[Dict[str, Any]]) -> SchedulerConfig:
    """Parse scheduler configuration from manifest data.

    Per canonical design:
    - Uses data from scheduler.yaml if present
    - Applies sensible defaults
    - Validates configuration

    Args:
        data: Parsed scheduler.yaml data (or None for defaults)

    Returns:
        SchedulerConfig instance

    Raises:
        ValueError: If configuration is invalid
    """
    if not data or 'scheduler' not in data:
        return get_default_config()

    scheduler_cfg = data['scheduler']

    # Extract fields with defaults
    enabled = scheduler_cfg.get('enabled', True)
    max_concurrency = scheduler_cfg.get('max_concurrency', 1)
    queue_policy_str = scheduler_cfg.get('queue_policy', 'fifo')
    max_queue_size = scheduler_cfg.get('max_queue_size', None)

    # Parse queue policy enum
    try:
        queue_policy = QueuePolicy(queue_policy_str)
    except ValueError:
        raise ValueError(f"Unknown queue_policy: {queue_policy_str}")

    # Create config
    config = SchedulerConfig(
        enabled=enabled,
        max_concurrency=max_concurrency,
        queue_policy=queue_policy,
        max_queue_size=max_queue_size,
    )

    # Validate
    config.validate()

    return config


def get_default_config() -> SchedulerConfig:
    """Get default scheduler configuration.

    Per canonical design (Phase 21):
    - Sequential execution (max_concurrency = 1)
    - FIFO queue policy
    - Unbounded queue size
    - Scheduler enabled by default

    Returns:
        Default SchedulerConfig
    """
    return SchedulerConfig(
        enabled=True,
        max_concurrency=1,
        queue_policy=QueuePolicy.FIFO,
        max_queue_size=None,
    )
