"""CPU metrics collection from /proc/stat and /proc/loadavg.

Reads raw kernel CPU accounting data and calculates utilization
percentages without using psutil or any external library.

The CPU time values in /proc/stat are cumulative since boot,
measured in USER_HZ (typically 100 Hz = 10ms ticks). To get
current utilization, we take two snapshots and compute the delta.

References:
    - proc(5) man page
    - Linux kernel Documentation/filesystems/proc.rst
"""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger("infraprobe.system.cpu")

PROC_STAT = "/proc/stat"
PROC_LOADAVG = "/proc/loadavg"
PROC_CPUINFO = "/proc/cpuinfo"


@dataclass
class CPUTimes:
    """Raw CPU time values from /proc/stat (in jiffies/ticks)."""

    user: int = 0
    nice: int = 0
    system: int = 0
    idle: int = 0
    iowait: int = 0
    irq: int = 0
    softirq: int = 0
    steal: int = 0
    guest: int = 0
    guest_nice: int = 0

    @property
    def total(self) -> int:
        """Total CPU time across all states."""
        return (
            self.user
            + self.nice
            + self.system
            + self.idle
            + self.iowait
            + self.irq
            + self.softirq
            + self.steal
        )

    @property
    def busy(self) -> int:
        """Total non-idle CPU time."""
        return self.total - self.idle - self.iowait


@dataclass
class CPUMetrics:
    """Computed CPU utilization metrics."""

    total_percent: float = 0.0
    user_percent: float = 0.0
    system_percent: float = 0.0
    idle_percent: float = 0.0
    iowait_percent: float = 0.0
    steal_percent: float = 0.0
    irq_percent: float = 0.0
    softirq_percent: float = 0.0
    core_count: int = 0
    load_avg_1: float = 0.0
    load_avg_5: float = 0.0
    load_avg_15: float = 0.0
    per_core: list[float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.per_core is None:
            self.per_core = []


def _read_cpu_times(proc_stat: str = PROC_STAT) -> dict[str, CPUTimes]:
    """Read CPU time counters from /proc/stat.

    /proc/stat format:
        cpu  user nice system idle iowait irq softirq steal guest guest_nice
        cpu0 user nice system idle iowait irq softirq steal guest guest_nice
        ...

    Args:
        proc_stat: Path to proc/stat file.

    Returns:
        Dict mapping CPU name ("cpu", "cpu0", "cpu1", ...) to CPUTimes.
    """
    cpus: dict[str, CPUTimes] = {}

    try:
        with open(proc_stat, "r") as f:
            for line in f:
                if not line.startswith("cpu"):
                    continue
                parts = line.split()
                name = parts[0]
                values = [int(x) for x in parts[1:]]

                cpus[name] = CPUTimes(
                    user=values[0] if len(values) > 0 else 0,
                    nice=values[1] if len(values) > 1 else 0,
                    system=values[2] if len(values) > 2 else 0,
                    idle=values[3] if len(values) > 3 else 0,
                    iowait=values[4] if len(values) > 4 else 0,
                    irq=values[5] if len(values) > 5 else 0,
                    softirq=values[6] if len(values) > 6 else 0,
                    steal=values[7] if len(values) > 7 else 0,
                    guest=values[8] if len(values) > 8 else 0,
                    guest_nice=values[9] if len(values) > 9 else 0,
                )
    except FileNotFoundError:
        logger.warning("%s not found — not running on Linux?", proc_stat)

    return cpus


def _read_load_average(proc_loadavg: str = PROC_LOADAVG) -> tuple[float, float, float]:
    """Read system load averages from /proc/loadavg.

    /proc/loadavg format:
        1.23 0.98 0.76 1/305 12345
        ^    ^    ^    ^     ^
        1m   5m   15m  running/total  last_pid

    Returns:
        Tuple of (1min, 5min, 15min) load averages.
    """
    try:
        with open(proc_loadavg, "r") as f:
            parts = f.read().split()
            return float(parts[0]), float(parts[1]), float(parts[2])
    except (FileNotFoundError, IndexError, ValueError):
        return 0.0, 0.0, 0.0


def _calculate_percentages(before: CPUTimes, after: CPUTimes) -> dict[str, float]:
    """Calculate CPU utilization percentages from two time snapshots.

    Args:
        before: CPU times at the start of the measurement window.
        after: CPU times at the end of the measurement window.

    Returns:
        Dict with percentage values for each CPU state.
    """
    total_delta = after.total - before.total
    if total_delta == 0:
        return {
            "total": 0.0,
            "user": 0.0,
            "system": 0.0,
            "idle": 100.0,
            "iowait": 0.0,
            "steal": 0.0,
            "irq": 0.0,
            "softirq": 0.0,
        }

    def pct(before_val: int, after_val: int) -> float:
        return round(((after_val - before_val) / total_delta) * 100, 2)

    idle_pct = pct(before.idle, after.idle)
    iowait_pct = pct(before.iowait, after.iowait)

    return {
        "total": round(100.0 - idle_pct - iowait_pct, 2),
        "user": pct(before.user, after.user),
        "system": pct(before.system, after.system),
        "idle": idle_pct,
        "iowait": iowait_pct,
        "steal": pct(before.steal, after.steal),
        "irq": pct(before.irq, after.irq),
        "softirq": pct(before.softirq, after.softirq),
    }


def get_cpu_metrics(sample_interval: float = 0.5) -> CPUMetrics:
    """Collect CPU utilization metrics.

    Takes two /proc/stat snapshots separated by sample_interval to
    calculate current CPU utilization rather than cumulative averages.

    Args:
        sample_interval: Seconds between the two snapshots.

    Returns:
        CPUMetrics with utilization percentages and load averages.
    """
    # First snapshot
    before = _read_cpu_times()
    time.sleep(sample_interval)
    # Second snapshot
    after = _read_cpu_times()

    metrics = CPUMetrics()

    # Overall CPU (aggregate "cpu" line)
    if "cpu" in before and "cpu" in after:
        pcts = _calculate_percentages(before["cpu"], after["cpu"])
        metrics.total_percent = pcts["total"]
        metrics.user_percent = pcts["user"]
        metrics.system_percent = pcts["system"]
        metrics.idle_percent = pcts["idle"]
        metrics.iowait_percent = pcts["iowait"]
        metrics.steal_percent = pcts["steal"]
        metrics.irq_percent = pcts["irq"]
        metrics.softirq_percent = pcts["softirq"]

    # Per-core utilization
    core_pcts: list[float] = []
    core_id = 0
    while True:
        core_name = f"cpu{core_id}"
        if core_name not in before or core_name not in after:
            break
        pcts = _calculate_percentages(before[core_name], after[core_name])
        core_pcts.append(pcts["total"])
        core_id += 1

    metrics.per_core = core_pcts
    metrics.core_count = len(core_pcts)

    # Load averages
    metrics.load_avg_1, metrics.load_avg_5, metrics.load_avg_15 = _read_load_average()

    return metrics
