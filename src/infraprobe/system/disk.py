"""Disk usage and I/O metrics from os.statvfs and /proc/diskstats.

Collects disk space usage per mount point using the statvfs system call,
and I/O performance metrics (IOPS, throughput) from /proc/diskstats.

References:
    - statvfs(2) man page
    - proc(5) man page — /proc/diskstats section
    - Linux kernel Documentation/admin-guide/iostats.rst
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("infraprobe.system.disk")

PROC_DISKSTATS = "/proc/diskstats"
PROC_MOUNTS = "/proc/mounts"


@dataclass
class DiskUsage:
    """Disk space usage for a single mount point."""

    mountpoint: str
    device: str = ""
    filesystem: str = ""
    total_gb: float = 0.0
    used_gb: float = 0.0
    free_gb: float = 0.0
    used_percent: float = 0.0
    inodes_total: int = 0
    inodes_used: int = 0
    inodes_free: int = 0


@dataclass
class DiskIOStats:
    """I/O statistics for a block device."""

    device: str
    reads_completed: int = 0
    writes_completed: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    read_time_ms: int = 0
    write_time_ms: int = 0
    io_in_progress: int = 0


def _get_mount_points() -> list[tuple[str, str, str]]:
    """Read mount points from /proc/mounts.

    Returns:
        List of (device, mountpoint, filesystem_type) tuples.
        Filters to real filesystems only (ext4, xfs, btrfs, etc.).
    """
    real_fs_types = {"ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "ntfs", "vfat", "fat32"}
    mounts: list[tuple[str, str, str]] = []

    try:
        with open(PROC_MOUNTS, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    device, mountpoint, fs_type = parts[0], parts[1], parts[2]
                    if fs_type in real_fs_types:
                        mounts.append((device, mountpoint, fs_type))
    except FileNotFoundError:
        # Fallback: just check root
        mounts.append(("", "/", "unknown"))

    return mounts


def get_disk_usage(paths: Optional[list[str]] = None) -> list[DiskUsage]:
    """Get disk space usage for mount points.

    Uses os.statvfs() which calls the statvfs(2) system call to get
    filesystem statistics without needing external tools.

    statvfs fields:
        f_frsize  — fragment size (fundamental block size)
        f_blocks  — total blocks
        f_bfree   — free blocks
        f_bavail  — free blocks for unprivileged users
        f_files   — total inodes
        f_ffree   — free inodes

    Args:
        paths: Specific mount points to check. If None, auto-detects
               from /proc/mounts.

    Returns:
        List of DiskUsage for each mount point.
    """
    results: list[DiskUsage] = []

    if paths:
        mount_info = [(path, "", "unknown") for path in paths]
    else:
        mount_info = [(m[1], m[0], m[2]) for m in _get_mount_points()]

    for mountpoint, device, fs_type in mount_info:
        try:
            stat = os.statvfs(mountpoint)
        except (OSError, FileNotFoundError) as e:
            logger.warning("Cannot stat %s: %s", mountpoint, e)
            continue

        block_size = stat.f_frsize
        total_bytes = stat.f_blocks * block_size
        free_bytes = stat.f_bavail * block_size  # Available to non-root
        used_bytes = total_bytes - (stat.f_bfree * block_size)

        if total_bytes == 0:
            continue

        usage = DiskUsage(
            mountpoint=mountpoint,
            device=device,
            filesystem=fs_type,
            total_gb=round(total_bytes / (1024**3), 2),
            used_gb=round(used_bytes / (1024**3), 2),
            free_gb=round(free_bytes / (1024**3), 2),
            used_percent=round((used_bytes / total_bytes) * 100, 1),
            inodes_total=stat.f_files,
            inodes_used=stat.f_files - stat.f_ffree,
            inodes_free=stat.f_ffree,
        )
        results.append(usage)

    return results


def _read_diskstats() -> dict[str, DiskIOStats]:
    """Read I/O statistics from /proc/diskstats.

    /proc/diskstats format (per line):
        major minor name reads_completed reads_merged sectors_read read_time
        writes_completed writes_merged sectors_written write_time
        ios_in_progress io_time weighted_io_time ...

    Returns:
        Dict mapping device name to DiskIOStats.
    """
    stats: dict[str, DiskIOStats] = {}

    try:
        with open(PROC_DISKSTATS, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 14:
                    continue

                name = parts[2]
                # Skip partitions (only keep whole devices like sda, nvme0n1)
                # Heuristic: skip if name ends with a digit after letters
                if (
                    any(c.isdigit() for c in name)
                    and name[-1].isdigit()
                    and not name.startswith("nvme")
                ):
                    continue

                stats[name] = DiskIOStats(
                    device=name,
                    reads_completed=int(parts[3]),
                    writes_completed=int(parts[7]),
                    # sectors are 512 bytes each
                    read_bytes=int(parts[5]) * 512,
                    write_bytes=int(parts[9]) * 512,
                    read_time_ms=int(parts[6]),
                    write_time_ms=int(parts[10]),
                    io_in_progress=int(parts[11]),
                )
    except FileNotFoundError:
        logger.warning("%s not found", PROC_DISKSTATS)

    return stats


def get_disk_metrics(paths: Optional[list[str]] = None) -> list[DiskUsage]:
    """Collect disk usage metrics.

    Convenience function that wraps get_disk_usage for the CLI.

    Args:
        paths: Optional list of paths to check.

    Returns:
        List of DiskUsage objects.
    """
    if paths:
        return get_disk_usage(paths=paths)
    return get_disk_usage()
