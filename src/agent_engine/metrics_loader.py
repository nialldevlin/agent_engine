"""Metrics loader and configuration."""

import os
import yaml
from typing import Dict, List, Optional
from agent_engine.schemas import MetricsProfile, MetricConfig, MetricType
from agent_engine.exceptions import ManifestLoadError


def load_metrics_manifest(config_dir: str) -> Optional[Dict]:
    """Load metrics.yaml (optional).

    Returns:
        Dict with loaded metrics configuration, or None if file doesn't exist
    """
    path = os.path.join(config_dir, "metrics.yaml")
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return data if data else None
    except yaml.YAMLError as e:
        raise ManifestLoadError("metrics.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("metrics.yaml", str(e))


def parse_metrics(data: Optional[Dict]) -> List[MetricsProfile]:
    """Parse loaded metrics YAML into MetricsProfile objects.

    Expected format:
    profiles:
      - name: "default"
        description: "Default metrics collection"
        enabled: true
        metrics:
          - name: "node_execution_duration"
            type: "timer"
            enabled: true
            description: "Duration of node execution in ms"
          - name: "tool_invocation_count"
            type: "counter"
            enabled: true
    """
    if not data or "profiles" not in data:
        # Return default profile if no config
        return [get_default_profile()]

    profiles = []
    for profile_data in data["profiles"]:
        metrics = []
        for metric_data in profile_data.get("metrics", []):
            metric = MetricConfig(
                name=metric_data["name"],
                type=MetricType(metric_data["type"]),
                enabled=metric_data.get("enabled", True),
                tags=metric_data.get("tags", {}),
                description=metric_data.get("description", "")
            )
            metrics.append(metric)

        profile = MetricsProfile(
            name=profile_data["name"],
            description=profile_data.get("description", ""),
            metrics=metrics,
            enabled=profile_data.get("enabled", True)
        )
        profiles.append(profile)

    return profiles


def get_default_profile() -> MetricsProfile:
    """Get default metrics profile with standard metrics."""
    return MetricsProfile(
        name="default",
        description="Default metrics collection",
        enabled=True,
        metrics=[
            MetricConfig(
                name="node_execution_duration",
                type=MetricType.TIMER,
                enabled=True,
                description="Duration of node execution in milliseconds"
            ),
            MetricConfig(
                name="tool_invocation_duration",
                type=MetricType.TIMER,
                enabled=True,
                description="Duration of tool invocation in milliseconds"
            ),
            MetricConfig(
                name="task_total_duration",
                type=MetricType.TIMER,
                enabled=True,
                description="Total task execution duration in milliseconds"
            ),
            MetricConfig(
                name="node_execution_count",
                type=MetricType.COUNTER,
                enabled=True,
                description="Number of node executions"
            ),
            MetricConfig(
                name="tool_invocation_count",
                type=MetricType.COUNTER,
                enabled=True,
                description="Number of tool invocations"
            )
        ]
    )
