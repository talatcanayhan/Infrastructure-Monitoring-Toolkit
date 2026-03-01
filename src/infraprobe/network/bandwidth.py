"""Bandwidth monitoring via /proc/net/dev.

Reads network interface statistics from the Linux /proc filesystem
to calculate real-time throughput (TX/RX bytes per second).

Also provides TCP connection-based bandwidth estimation.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("infraprobe.network.bandwidth")

PROC_NET_DEV = "/proc/net/dev"


@dataclass
class InterfaceStats:
    """Network interface statistics snapshot."""

    name: str
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    rx_dropped: int = 0
    tx_dropped: int = 0


@dataclass
class BandwidthResult:
    """Bandwidth measurement result for an interface."""

    interface: str
    rx_bytes_per_sec: float = 0.0
    tx_bytes_per_sec: float = 0.0
    rx_mbps: float = 0.0
    tx_mbps: float = 0.0
    measurement_duration_sec: float = 0.0


def read_interface_stats() -> list[InterfaceStats]:
    """Read network interface statistics from /proc/net/dev.

    /proc/net/dev format:
        Inter-|   Receive                                  |  Transmit
         face |bytes    packets errs drop fifo frame ...   |bytes    packets errs drop ...
            lo: 12345   100     0    0    0    0   ...      12345   100     0    0   ...
          eth0: 67890   200     0    0    0    0   ...      11111   150     0    0   ...

    Returns:
        List of InterfaceStats for each network interface.
    """
    stats: list[InterfaceStats] = []

    try:
        with open(PROC_NET_DEV, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.warning("%s not found — not running on Linux?", PROC_NET_DEV)
        return stats

    # Skip the first two header lines
    for line in lines[2:]:
        line = line.strip()
        if ":" not in line:
            continue

        iface_name, data = line.split(":", 1)
        iface_name = iface_name.strip()
        fields = data.split()

        if len(fields) < 16:
            continue

        stats.append(
            InterfaceStats(
                name=iface_name,
                rx_bytes=int(fields[0]),
                rx_packets=int(fields[1]),
                rx_errors=int(fields[2]),
                rx_dropped=int(fields[3]),
                tx_bytes=int(fields[8]),
                tx_packets=int(fields[9]),
                tx_errors=int(fields[10]),
                tx_dropped=int(fields[11]),
            )
        )

    return stats


def measure_bandwidth(
    interface: Optional[str] = None,
    duration: float = 2.0,
) -> list[BandwidthResult]:
    """Measure bandwidth by comparing /proc/net/dev snapshots.

    Takes two snapshots separated by `duration` seconds and calculates
    the byte rate for each interface.

    Args:
        interface: Specific interface name to measure (None = all).
        duration: Measurement window in seconds.

    Returns:
        List of BandwidthResult for each measured interface.
    """
    # First snapshot
    stats_before = read_interface_stats()
    time.sleep(duration)
    # Second snapshot
    stats_after = read_interface_stats()

    # Build lookup by interface name
    before_map = {s.name: s for s in stats_before}
    after_map = {s.name: s for s in stats_after}

    results: list[BandwidthResult] = []
    for name in after_map:
        if interface and name != interface:
            continue
        if name == "lo":
            continue  # Skip loopback
        if name not in before_map:
            continue

        before = before_map[name]
        after = after_map[name]

        rx_diff = after.rx_bytes - before.rx_bytes
        tx_diff = after.tx_bytes - before.tx_bytes

        rx_rate = rx_diff / duration
        tx_rate = tx_diff / duration

        results.append(
            BandwidthResult(
                interface=name,
                rx_bytes_per_sec=round(rx_rate, 2),
                tx_bytes_per_sec=round(tx_rate, 2),
                rx_mbps=round(rx_rate * 8 / 1_000_000, 3),
                tx_mbps=round(tx_rate * 8 / 1_000_000, 3),
                measurement_duration_sec=duration,
            )
        )

    return results
