"""Tests for the memory metrics module."""

import tempfile
from pathlib import Path

from infraprobe.system.memory import get_memory_metrics


class TestGetMemoryMetrics:
    """Test memory metric collection from mocked /proc/meminfo."""

    def test_parses_meminfo(self, tmp_path: Path) -> None:
        """Should correctly parse /proc/meminfo content."""
        meminfo = tmp_path / "meminfo"
        meminfo.write_text(
            "MemTotal:       16384000 kB\n"
            "MemFree:         2048000 kB\n"
            "MemAvailable:    8192000 kB\n"
            "Buffers:          512000 kB\n"
            "Cached:          4096000 kB\n"
            "SwapTotal:       2048000 kB\n"
            "SwapFree:        2048000 kB\n"
            "Slab:             256000 kB\n"
        )

        metrics = get_memory_metrics(str(meminfo))

        assert metrics.total_mb == 16000.0
        assert metrics.available_mb == 8000.0
        # used = total - available
        assert metrics.used_mb == 8000.0
        assert metrics.used_percent == 50.0
        assert metrics.buffers_mb == 500.0
        assert metrics.cached_mb == 4000.0
        assert metrics.swap_total_mb == 2000.0
        assert metrics.swap_free_mb == 2000.0
        assert metrics.swap_used_mb == 0.0
        assert metrics.swap_used_percent == 0.0

    def test_missing_file(self) -> None:
        """Should return zeros when /proc/meminfo doesn't exist."""
        metrics = get_memory_metrics("/nonexistent/meminfo")
        assert metrics.total_mb == 0.0
        assert metrics.used_percent == 0.0
