"""Metrics collector for recording performance metrics."""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

from agent_engine.schemas import MetricSample, MetricType, MetricsProfile


class MetricsCollector:
    """Collects and stores metric samples."""

    def __init__(self, profile: Optional[MetricsProfile] = None):
        """Initialize metrics collector.

        Args:
            profile: Optional metrics profile (uses default if None)
        """
        from agent_engine.metrics_loader import get_default_profile

        self.profile = profile or get_default_profile()
        self.samples: List[MetricSample] = []

        # Build lookup for enabled metrics
        self.enabled_metrics = {
            m.name: m for m in self.profile.metrics if m.enabled
        } if self.profile.enabled else {}

    def is_enabled(self, metric_name: str) -> bool:
        """Check if a metric is enabled for collection."""
        return metric_name in self.enabled_metrics

    def record_timer(
        self,
        metric_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a timer metric (duration in milliseconds).

        Args:
            metric_name: Name of the metric
            duration_ms: Duration in milliseconds
            tags: Optional tags for filtering
            metadata: Optional additional metadata
        """
        if not self.is_enabled(metric_name):
            return

        sample = MetricSample(
            metric_name=metric_name,
            metric_type=MetricType.TIMER,
            value=duration_ms,
            timestamp=datetime.now(ZoneInfo("UTC")).isoformat(),
            tags=tags or {},
            metadata=metadata or {}
        )
        self.samples.append(sample)

    def record_counter(
        self,
        metric_name: str,
        count: int = 1,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a counter metric.

        Args:
            metric_name: Name of the metric
            count: Count value (default 1)
            tags: Optional tags for filtering
            metadata: Optional additional metadata
        """
        if not self.is_enabled(metric_name):
            return

        sample = MetricSample(
            metric_name=metric_name,
            metric_type=MetricType.COUNTER,
            value=float(count),
            timestamp=datetime.now(ZoneInfo("UTC")).isoformat(),
            tags=tags or {},
            metadata=metadata or {}
        )
        self.samples.append(sample)

    def record_gauge(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a gauge metric (point-in-time value).

        Args:
            metric_name: Name of the metric
            value: Gauge value
            tags: Optional tags for filtering
            metadata: Optional additional metadata
        """
        if not self.is_enabled(metric_name):
            return

        sample = MetricSample(
            metric_name=metric_name,
            metric_type=MetricType.GAUGE,
            value=value,
            timestamp=datetime.now(ZoneInfo("UTC")).isoformat(),
            tags=tags or {},
            metadata=metadata or {}
        )
        self.samples.append(sample)

    def get_samples(
        self,
        metric_name: Optional[str] = None,
        metric_type: Optional[MetricType] = None
    ) -> List[MetricSample]:
        """Get metric samples with optional filtering.

        Args:
            metric_name: Optional metric name filter
            metric_type: Optional metric type filter

        Returns:
            List of matching metric samples
        """
        samples = self.samples

        if metric_name:
            samples = [s for s in samples if s.metric_name == metric_name]

        if metric_type:
            samples = [s for s in samples if s.metric_type == metric_type]

        return samples

    def clear(self) -> None:
        """Clear all collected samples."""
        self.samples.clear()
