"""Phase 13 metrics tests."""

import pytest
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agent_engine.schemas import MetricType, MetricConfig, MetricsProfile, MetricSample
from agent_engine.metrics_loader import load_metrics_manifest, parse_metrics, get_default_profile
from agent_engine.runtime import MetricsCollector
from agent_engine.telemetry import TelemetryBus


# Schema Tests (3 tests)
class TestMetricSchemas:
    """Test metric schema definitions."""

    def test_metric_config_creation(self):
        """Test MetricConfig creation."""
        config = MetricConfig(
            name="test_metric",
            type=MetricType.TIMER,
            enabled=True,
            tags={"key": "value"},
            description="Test metric"
        )
        assert config.name == "test_metric"
        assert config.type == MetricType.TIMER
        assert config.enabled is True
        assert config.tags == {"key": "value"}
        assert config.description == "Test metric"

    def test_metrics_profile_creation(self):
        """Test MetricsProfile creation."""
        metrics = [
            MetricConfig(name="metric1", type=MetricType.TIMER),
            MetricConfig(name="metric2", type=MetricType.COUNTER)
        ]
        profile = MetricsProfile(
            name="test_profile",
            description="Test profile",
            metrics=metrics,
            enabled=True
        )
        assert profile.name == "test_profile"
        assert len(profile.metrics) == 2
        assert profile.enabled is True

    def test_metric_sample_creation(self):
        """Test MetricSample creation."""
        sample = MetricSample(
            metric_name="test_metric",
            metric_type=MetricType.TIMER,
            value=100.5,
            timestamp=datetime.now(ZoneInfo("UTC")).isoformat(),
            tags={"task_id": "t1"},
            metadata={"extra": "info"}
        )
        assert sample.metric_name == "test_metric"
        assert sample.metric_type == MetricType.TIMER
        assert sample.value == 100.5
        assert sample.tags == {"task_id": "t1"}
        assert sample.metadata == {"extra": "info"}


# Loader Tests (5 tests)
class TestMetricsLoader:
    """Test metrics loader functionality."""

    def test_load_metrics_manifest_with_valid_file(self):
        """Test loading metrics manifest from valid YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / "metrics.yaml"
            metrics_path.write_text("""
profiles:
  - name: "test"
    description: "Test profile"
    enabled: true
    metrics:
      - name: "test_metric"
        type: "timer"
        enabled: true
""")
            data = load_metrics_manifest(tmpdir)
            assert data is not None
            assert "profiles" in data
            assert len(data["profiles"]) == 1

    def test_load_metrics_manifest_with_missing_file(self):
        """Test loading metrics manifest when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = load_metrics_manifest(tmpdir)
            assert data is None

    def test_parse_metrics_with_complete_profile(self):
        """Test parsing complete metrics profile."""
        data = {
            "profiles": [
                {
                    "name": "test",
                    "description": "Test profile",
                    "enabled": True,
                    "metrics": [
                        {
                            "name": "test_metric",
                            "type": "timer",
                            "enabled": True,
                            "description": "Test"
                        }
                    ]
                }
            ]
        }
        profiles = parse_metrics(data)
        assert len(profiles) == 1
        assert profiles[0].name == "test"
        assert len(profiles[0].metrics) == 1
        assert profiles[0].metrics[0].name == "test_metric"

    def test_parse_metrics_with_no_data(self):
        """Test parsing metrics with no data returns default."""
        profiles = parse_metrics(None)
        assert len(profiles) == 1
        assert profiles[0].name == "default"

    def test_get_default_profile(self):
        """Test default profile contains expected metrics."""
        profile = get_default_profile()
        assert profile.name == "default"
        assert profile.enabled is True
        metric_names = {m.name for m in profile.metrics}
        assert "node_execution_duration" in metric_names
        assert "tool_invocation_duration" in metric_names
        assert "task_total_duration" in metric_names
        assert "node_execution_count" in metric_names
        assert "tool_invocation_count" in metric_names


# Collector Tests (10 tests)
class TestMetricsCollector:
    """Test metrics collector functionality."""

    def test_record_timer_creates_sample(self):
        """Test recording a timer metric."""
        # Create profile with custom metric
        profile = MetricsProfile(
            name="test",
            metrics=[MetricConfig(name="test_timer", type=MetricType.TIMER, enabled=True)],
            enabled=True
        )
        collector = MetricsCollector(profile)
        collector.record_timer("test_timer", 100.5, tags={"task_id": "t1"})
        samples = collector.get_samples()
        assert len(samples) == 1
        assert samples[0].metric_name == "test_timer"
        assert samples[0].metric_type == MetricType.TIMER
        assert samples[0].value == 100.5
        assert samples[0].tags == {"task_id": "t1"}

    def test_record_counter_creates_sample(self):
        """Test recording a counter metric."""
        # Create profile with custom metric
        profile = MetricsProfile(
            name="test",
            metrics=[MetricConfig(name="test_counter", type=MetricType.COUNTER, enabled=True)],
            enabled=True
        )
        collector = MetricsCollector(profile)
        collector.record_counter("test_counter", count=5, tags={"action": "run"})
        samples = collector.get_samples()
        assert len(samples) == 1
        assert samples[0].metric_name == "test_counter"
        assert samples[0].metric_type == MetricType.COUNTER
        assert samples[0].value == 5.0
        assert samples[0].tags == {"action": "run"}

    def test_record_gauge_creates_sample(self):
        """Test recording a gauge metric."""
        # Create profile with custom metric
        profile = MetricsProfile(
            name="test",
            metrics=[MetricConfig(name="test_gauge", type=MetricType.GAUGE, enabled=True)],
            enabled=True
        )
        collector = MetricsCollector(profile)
        collector.record_gauge("test_gauge", 42.5)
        samples = collector.get_samples()
        assert len(samples) == 1
        assert samples[0].metric_name == "test_gauge"
        assert samples[0].metric_type == MetricType.GAUGE
        assert samples[0].value == 42.5

    def test_is_enabled_checks_metric_configuration(self):
        """Test is_enabled checks metric configuration."""
        profile = MetricsProfile(
            name="test",
            metrics=[
                MetricConfig(name="enabled_metric", type=MetricType.TIMER, enabled=True),
                MetricConfig(name="disabled_metric", type=MetricType.TIMER, enabled=False)
            ],
            enabled=True
        )
        collector = MetricsCollector(profile)
        assert collector.is_enabled("enabled_metric") is True
        assert collector.is_enabled("disabled_metric") is False
        assert collector.is_enabled("unknown_metric") is False

    def test_get_samples_with_no_filters(self):
        """Test get_samples with no filters returns all."""
        # Use default profile which has all three types
        collector = MetricsCollector()
        # Record using default profile metrics
        collector.record_timer("node_execution_duration", 10.0)
        collector.record_counter("node_execution_count", 5)
        collector.record_gauge("node_execution_count", 20.0)  # Gauge with counter metric
        samples = collector.get_samples()
        assert len(samples) == 3

    def test_get_samples_with_metric_name_filter(self):
        """Test get_samples with metric name filter."""
        collector = MetricsCollector()
        collector.record_timer("node_execution_duration", 10.0)
        collector.record_counter("tool_invocation_count", 5)
        samples = collector.get_samples(metric_name="node_execution_duration")
        assert len(samples) == 1
        assert samples[0].metric_name == "node_execution_duration"

    def test_get_samples_with_metric_type_filter(self):
        """Test get_samples with metric type filter."""
        collector = MetricsCollector()
        collector.record_timer("node_execution_duration", 10.0)
        collector.record_timer("tool_invocation_duration", 20.0)
        collector.record_counter("node_execution_count", 5)
        samples = collector.get_samples(metric_type=MetricType.TIMER)
        assert len(samples) == 2
        assert all(s.metric_type == MetricType.TIMER for s in samples)

    def test_disabled_metrics_not_recorded(self):
        """Test disabled metrics are not recorded."""
        profile = MetricsProfile(
            name="test",
            metrics=[
                MetricConfig(name="test_metric", type=MetricType.TIMER, enabled=False)
            ],
            enabled=True
        )
        collector = MetricsCollector(profile)
        collector.record_timer("test_metric", 100.0)
        samples = collector.get_samples()
        assert len(samples) == 0

    def test_clear_empties_samples(self):
        """Test clear() empties all samples."""
        collector = MetricsCollector()
        collector.record_timer("node_execution_duration", 10.0)
        collector.record_counter("node_execution_count", 5)
        assert len(collector.get_samples()) == 2
        collector.clear()
        assert len(collector.get_samples()) == 0

    def test_tags_and_metadata_preserved(self):
        """Test tags and metadata are preserved."""
        collector = MetricsCollector()
        collector.record_timer(
            "node_execution_duration",
            100.0,
            tags={"task_id": "t1", "node_id": "n1"},
            metadata={"extra": "data"}
        )
        samples = collector.get_samples()
        assert samples[0].tags == {"task_id": "t1", "node_id": "n1"}
        assert samples[0].metadata == {"extra": "data"}


# Integration Tests (7+ tests)
class TestMetricsIntegration:
    """Test metrics integration with telemetry and engine."""

    def test_telemetry_bus_with_metrics_collector(self):
        """Test TelemetryBus initialization with metrics collector."""
        profile = get_default_profile()
        collector = MetricsCollector(profile)
        telemetry = TelemetryBus(metrics_collector=collector)
        assert telemetry.metrics_collector is collector

    def test_node_started_records_counter_metric(self):
        """Test node_started records counter metric."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)
        telemetry.node_started("task1", "node1", "actor", "execute", {"input": "data"})

        metrics = collector.get_samples(metric_name="node_execution_count")
        assert len(metrics) == 1
        assert metrics[0].metric_type == MetricType.COUNTER
        assert metrics[0].value == 1.0
        assert metrics[0].tags["task_id"] == "task1"
        assert metrics[0].tags["node_id"] == "node1"

    def test_node_completed_records_timer_metric(self):
        """Test node_completed records timer metric."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)

        # Start and complete node
        telemetry.node_started("task1", "node1", "actor", "execute", {})
        time.sleep(0.01)  # Small sleep to ensure measurable duration
        telemetry.node_completed("task1", "node1", {"output": "data"}, "success")

        metrics = collector.get_samples(metric_name="node_execution_duration")
        assert len(metrics) == 1
        assert metrics[0].metric_type == MetricType.TIMER
        assert metrics[0].value >= 10.0  # At least 10ms
        assert metrics[0].tags["task_id"] == "task1"
        assert metrics[0].tags["status"] == "success"

    def test_tool_invoked_records_counter_metric(self):
        """Test tool_invoked records counter metric."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)
        telemetry.tool_invoked("task1", "node1", "tool_id", {"arg": "value"})

        metrics = collector.get_samples(metric_name="tool_invocation_count")
        assert len(metrics) == 1
        assert metrics[0].metric_type == MetricType.COUNTER
        assert metrics[0].value == 1.0
        assert metrics[0].tags["task_id"] == "task1"
        assert metrics[0].tags["tool_name"] == "tool_id"

    def test_tool_completed_records_timer_metric(self):
        """Test tool_completed records timer metric."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)

        # Invoke and complete tool
        telemetry.tool_invoked("task1", "node1", "tool_id", {})
        time.sleep(0.01)  # Small sleep to ensure measurable duration
        telemetry.tool_completed("task1", "node1", "tool_id", {"result": "data"}, "success")

        metrics = collector.get_samples(metric_name="tool_invocation_duration")
        assert len(metrics) == 1
        assert metrics[0].metric_type == MetricType.TIMER
        assert metrics[0].value >= 10.0  # At least 10ms
        assert metrics[0].tags["tool_name"] == "tool_id"

    def test_telemetry_get_metrics_returns_samples(self):
        """Test TelemetryBus.get_metrics() returns samples."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)
        collector.record_timer("node_execution_duration", 50.0)  # Direct recording for test

        metrics = telemetry.get_metrics()
        assert len(metrics) == 1  # Collector recorded one

    def test_metrics_configuration_from_file(self):
        """Test loading metrics configuration from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / "metrics.yaml"
            metrics_path.write_text("""
profiles:
  - name: "custom"
    description: "Custom metrics"
    enabled: true
    metrics:
      - name: "custom_metric"
        type: "timer"
        enabled: true
""")
            data = load_metrics_manifest(tmpdir)
            profiles = parse_metrics(data)
            assert len(profiles) == 1
            assert profiles[0].name == "custom"
            assert profiles[0].metrics[0].name == "custom_metric"

    def test_node_execution_count_increments(self):
        """Test node execution count increments with multiple executions."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)

        # Record multiple node starts
        for i in range(3):
            telemetry.node_started(f"task1", f"node{i}", "actor", "execute", {})

        metrics = collector.get_samples(metric_name="node_execution_count")
        assert len(metrics) == 3
        assert all(m.value == 1.0 for m in metrics)

    def test_multiple_metrics_types_recorded(self):
        """Test multiple metric types are all recorded."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)

        # Record various metrics
        telemetry.node_started("task1", "node1", "actor", "execute", {})
        time.sleep(0.01)
        telemetry.node_completed("task1", "node1", {}, "success")

        telemetry.tool_invoked("task1", "node1", "tool1", {})
        time.sleep(0.01)
        telemetry.tool_completed("task1", "node1", "tool1", {}, "success")

        metrics = collector.get_samples()
        counter_metrics = [m for m in metrics if m.metric_type == MetricType.COUNTER]
        timer_metrics = [m for m in metrics if m.metric_type == MetricType.TIMER]

        assert len(counter_metrics) == 2  # node count + tool count
        assert len(timer_metrics) == 2    # node duration + tool duration

    def test_metrics_collector_without_profile(self):
        """Test metrics collector uses default profile when none provided."""
        collector = MetricsCollector(None)
        assert collector.profile.name == "default"
        assert len(collector.profile.metrics) > 0

    def test_disabled_profile_no_metrics_recorded(self):
        """Test disabled profile prevents metrics recording."""
        profile = MetricsProfile(name="disabled", enabled=False, metrics=[])
        collector = MetricsCollector(profile)
        collector.record_timer("test", 100.0)
        assert len(collector.get_samples()) == 0

    def test_telemetry_without_collector_safe(self):
        """Test telemetry works safely without metrics collector."""
        telemetry = TelemetryBus(metrics_collector=None)
        telemetry.node_started("task1", "node1", "actor", "execute", {})
        telemetry.node_completed("task1", "node1", {}, "success")

        metrics = telemetry.get_metrics()
        assert len(metrics) == 0  # No metrics without collector

    def test_metric_timestamps_are_iso8601(self):
        """Test metric timestamps are ISO-8601 UTC."""
        collector = MetricsCollector()
        collector.record_timer("node_execution_duration", 100.0)

        sample = collector.get_samples()[0]
        # Should be ISO-8601 format
        assert "T" in sample.timestamp
        assert "Z" in sample.timestamp or "+00:00" in sample.timestamp or "UTC" in sample.timestamp

    def test_start_times_cleaned_up_after_completion(self):
        """Test start times are cleaned up after node/tool completion."""
        collector = MetricsCollector()
        telemetry = TelemetryBus(metrics_collector=collector)

        # Start and complete a node
        telemetry.node_started("task1", "node1", "actor", "execute", {})
        key = "task1:node1"
        assert key in telemetry._node_start_times

        telemetry.node_completed("task1", "node1", {}, "success")
        assert key not in telemetry._node_start_times
