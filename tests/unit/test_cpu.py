"""Tests for the CPU metrics module."""

from pathlib import Path
from unittest.mock import patch

from infraprobe.system.cpu import CPUTimes, _calculate_percentages, _read_cpu_times


class TestCPUTimes:
    """Test CPUTimes dataclass calculations."""

    def test_total(self) -> None:
        times = CPUTimes(user=100, nice=10, system=50, idle=800, iowait=20, irq=5, softirq=5, steal=10)
        assert times.total == 1000

    def test_busy(self) -> None:
        times = CPUTimes(user=100, nice=10, system=50, idle=800, iowait=20, irq=5, softirq=5, steal=10)
        assert times.busy == 1000 - 800 - 20  # total - idle - iowait


class TestCalculatePercentages:
    """Test CPU percentage calculations."""

    def test_50_percent_usage(self) -> None:
        before = CPUTimes(user=0, system=0, idle=100, iowait=0)
        after = CPUTimes(user=50, system=0, idle=150, iowait=0)
        pcts = _calculate_percentages(before, after)
        assert pcts["total"] == 50.0
        assert pcts["user"] == 50.0
        assert pcts["idle"] == 50.0

    def test_zero_delta(self) -> None:
        times = CPUTimes(user=100, system=50, idle=800)
        pcts = _calculate_percentages(times, times)
        assert pcts["idle"] == 100.0
        assert pcts["total"] == 0.0


class TestReadCPUTimes:
    """Test /proc/stat parsing."""

    def test_parses_proc_stat(self, tmp_path: Path) -> None:
        stat_file = tmp_path / "stat"
        stat_file.write_text(
            "cpu  10132153 290696 3084719 46828483 16683 0 25195 0 0 0\n"
            "cpu0 1393280 32966 572056 13343292 6130 0 17875 0 0 0\n"
            "intr 12345\n"
        )
        cpus = _read_cpu_times(str(stat_file))
        assert "cpu" in cpus
        assert "cpu0" in cpus
        assert cpus["cpu"].user == 10132153
        assert cpus["cpu0"].user == 1393280

    def test_missing_file(self) -> None:
        cpus = _read_cpu_times("/nonexistent/stat")
        assert cpus == {}
