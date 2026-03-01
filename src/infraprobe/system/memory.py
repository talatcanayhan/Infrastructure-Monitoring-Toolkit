"""Memory metrics collection from /proc/meminfo.

Reads raw memory statistics from the Linux kernel and calculates
actual memory usage (total - available), distinguishing between
truly free memory and memory used for buffers/cache.

Key insight: Linux uses free memory for disk cache, so "free"
memory as shown by `free` command is misleadingly low. The
"available" metric (MemAvailable) is the correct measure of
memory that can be allocated without swapping.

References:
    - proc(5) man page
    - https://www.kernel.org/doc/Documentation/filesystems/proc.rst
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("infraprobe.system.memory")

PROC_MEMINFO = "/proc/meminfo"


@dataclass
class MemoryMetrics:
    """Computed memory utilization metrics."""

    total_mb: float = 0.0
    used_mb: float = 0.0
    available_mb: float = 0.0
    free_mb: float = 0.0
    buffers_mb: float = 0.0
    cached_mb: float = 0.0
    used_percent: float = 0.0
    swap_total_mb: float = 0.0
    swap_used_mb: float = 0.0
    swap_free_mb: float = 0.0
    swap_used_percent: float = 0.0
    slab_mb: float = 0.0


def _parse_meminfo(proc_meminfo: str = PROC_MEMINFO) -> dict[str, int]:
    """Parse /proc/meminfo into a dict of field -> value in kB.

    /proc/meminfo format:
        MemTotal:       16384000 kB
        MemFree:         2048000 kB
        MemAvailable:    8192000 kB
        Buffers:          512000 kB
        Cached:          4096000 kB
        ...

    Each line has: FieldName: value kB

    Returns:
        Dict mapping field names (e.g., "MemTotal") to values in kB.
    """
    meminfo: dict[str, int] = {}

    try:
        with open(proc_meminfo, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    try:
                        meminfo[key] = int(parts[1])
                    except ValueError:
                        continue
    except FileNotFoundError:
        logger.warning("%s not found — not running on Linux?", proc_meminfo)

    return meminfo


def get_memory_metrics(proc_meminfo: str = PROC_MEMINFO) -> MemoryMetrics:
    """Collect memory utilization metrics from /proc/meminfo.

    Calculates actual used memory as:
        used = total - available  (NOT total - free)

    This correctly accounts for memory used by buffers and cache,
    which is reclaimable and should not be counted as "used".

    Args:
        proc_meminfo: Path to the meminfo file (for testing).

    Returns:
        MemoryMetrics with usage values in MB and percentages.
    """
    raw = _parse_meminfo(proc_meminfo)
    metrics = MemoryMetrics()

    if not raw:
        return metrics

    # Helper: kB to MB
    def to_mb(key: str) -> float:
        return round(raw.get(key, 0) / 1024, 1)

    metrics.total_mb = to_mb("MemTotal")
    metrics.free_mb = to_mb("MemFree")
    metrics.available_mb = to_mb("MemAvailable")
    metrics.buffers_mb = to_mb("Buffers")
    metrics.cached_mb = to_mb("Cached")
    metrics.slab_mb = to_mb("Slab")

    # Used = Total - Available (correct calculation)
    metrics.used_mb = round(metrics.total_mb - metrics.available_mb, 1)

    if metrics.total_mb > 0:
        metrics.used_percent = round((metrics.used_mb / metrics.total_mb) * 100, 1)

    # Swap metrics
    metrics.swap_total_mb = to_mb("SwapTotal")
    metrics.swap_free_mb = to_mb("SwapFree")
    metrics.swap_used_mb = round(metrics.swap_total_mb - metrics.swap_free_mb, 1)

    if metrics.swap_total_mb > 0:
        metrics.swap_used_percent = round(
            (metrics.swap_used_mb / metrics.swap_total_mb) * 100, 1
        )

    return metrics
