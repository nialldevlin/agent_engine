"""Metrics schema definitions."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class MetricType(str, Enum):
    """Types of metrics that can be collected."""
    TIMER = "timer"  # Duration/latency metrics
    COUNTER = "counter"  # Count metrics
    GAUGE = "gauge"  # Point-in-time value metrics


@dataclass
class MetricConfig:
    """Configuration for a single metric."""
    name: str  # Metric name (e.g., "node_execution_duration")
    type: MetricType
    enabled: bool = True
    tags: Dict[str, str] = field(default_factory=dict)  # Additional tags for filtering
    description: str = ""


@dataclass
class MetricsProfile:
    """Collection of metric configurations."""
    name: str
    description: str = ""
    metrics: List[MetricConfig] = field(default_factory=list)
    enabled: bool = True


@dataclass
class MetricSample:
    """Single metric sample/measurement."""
    metric_name: str
    metric_type: MetricType
    value: float  # Duration in ms for timers, count for counters, value for gauges
    timestamp: str  # ISO-8601
    tags: Dict[str, str] = field(default_factory=dict)  # task_id, node_id, tool_name, etc.
    metadata: Dict[str, str] = field(default_factory=dict)  # Additional context
