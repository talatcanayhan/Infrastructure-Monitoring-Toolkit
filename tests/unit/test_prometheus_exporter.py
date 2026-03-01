"""Tests for the Prometheus metrics exporter."""

from unittest.mock import MagicMock

from infraprobe.metrics.prometheus_exporter import (
    update_ping_metrics,
    update_system_metrics,
)


class TestUpdatePingMetrics:
    """Test Prometheus metric updates from ping results."""

    def test_successful_ping(self) -> None:
        """Should update metrics for successful pings."""
        stats = MagicMock()
        stats.packets_sent = 3
        stats.packets_received = 3
        stats.packet_loss_percent = 0.0
        result1 = MagicMock(success=True, rtt_ms=10.0)
        result2 = MagicMock(success=True, rtt_ms=15.0)
        stats.results = [result1, result2]

        # Should not raise
        update_ping_metrics("8.8.8.8", stats)

    def test_failed_ping(self) -> None:
        """Should handle 100% packet loss."""
        stats = MagicMock()
        stats.packets_sent = 3
        stats.packets_received = 0
        stats.packet_loss_percent = 100.0
        stats.results = []

        update_ping_metrics("unreachable.host", stats)


class TestUpdateSystemMetrics:
    """Test system metric updates."""

    def test_cpu_metrics(self) -> None:
        cpu = MagicMock()
        cpu.total_percent = 45.0
        cpu.user_percent = 30.0
        cpu.system_percent = 10.0
        cpu.idle_percent = 55.0
        cpu.iowait_percent = 5.0

        update_system_metrics({"cpu": cpu})

    def test_memory_metrics(self) -> None:
        mem = MagicMock()
        mem.total_mb = 16000.0
        mem.used_mb = 8000.0
        mem.available_mb = 8000.0
        mem.cached_mb = 4000.0
        mem.used_percent = 50.0

        update_system_metrics({"memory": mem})

    def test_empty_metrics(self) -> None:
        """Should handle empty metrics dict."""
        update_system_metrics({})
