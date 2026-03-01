"""Process monitoring via /proc/[pid] directory traversal.

Reads per-process statistics directly from the /proc filesystem
to identify resource-heavy processes, detect zombie processes,
and monitor open file descriptors.

/proc/[pid]/stat  — CPU time, state, priority
/proc/[pid]/status — Memory usage (VmRSS, VmSize)
/proc/[pid]/fd/   — Open file descriptors
/proc/[pid]/comm  — Process name

References:
    - proc(5) man page
    - Linux kernel Documentation/filesystems/proc.rst
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("infraprobe.system.process")

PROC_DIR = "/proc"


@dataclass
class ProcessInfo:
    """Information about a single process."""

    pid: int
    name: str = ""
    state: str = ""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_rss_kb: int = 0
    memory_vms_kb: int = 0
    threads: int = 0
    open_fds: int = 0
    ppid: int = 0
    user: str = ""


# Process state codes from /proc/[pid]/stat
PROCESS_STATES = {
    "R": "Running",
    "S": "Sleeping",
    "D": "Disk Sleep",
    "Z": "Zombie",
    "T": "Stopped",
    "t": "Tracing Stop",
    "X": "Dead",
    "I": "Idle",
}


def _get_total_memory_kb() -> int:
    """Read total system memory from /proc/meminfo.

    Returns:
        Total memory in kB, or 0 if unavailable.
    """
    try:
        with open("/proc/meminfo", "r") as f:
            line = f.readline()
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1])
    except (FileNotFoundError, ValueError):
        pass
    return 0


def _read_process_stat(pid: int) -> Optional[dict[str, Any]]:
    """Read /proc/[pid]/stat for CPU time and state.

    The stat file format is tricky because the process name (comm)
    can contain spaces and parentheses. The name is enclosed in
    parentheses, so we find the last ')' to split correctly.

    Format after the name: state ppid pgrp session tty_nr tpgid flags
        minflt cminflt majflt cmajflt utime stime cutime cstime ...

    Returns:
        Dict with 'state', 'utime', 'stime', 'ppid', 'threads', or None.
    """
    try:
        with open(f"{PROC_DIR}/{pid}/stat", "r") as f:
            content = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    # Find the end of the comm field (last closing paren)
    paren_end = content.rfind(")")
    if paren_end == -1:
        return None

    fields = content[paren_end + 2 :].split()
    if len(fields) < 20:
        return None

    return {
        "state": fields[0],
        "ppid": int(fields[1]),
        "utime": int(fields[11]),  # User CPU time in clock ticks
        "stime": int(fields[12]),  # System CPU time in clock ticks
        "threads": int(fields[17]),
    }


def _read_process_status(pid: int) -> dict[str, str]:
    """Read /proc/[pid]/status for memory and metadata.

    Format: key-value pairs, one per line.
        Name:    process_name
        VmSize:  12345 kB
        VmRSS:   6789 kB
        Uid:     1000   1000   1000   1000
        ...

    Returns:
        Dict of key -> value strings.
    """
    status: dict[str, str] = {}
    try:
        with open(f"{PROC_DIR}/{pid}/status", "r") as f:
            for line in f:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    status[parts[0].strip()] = parts[1].strip()
    except (FileNotFoundError, PermissionError):
        pass
    return status


def _count_fds(pid: int) -> int:
    """Count open file descriptors for a process via /proc/[pid]/fd/.

    Each entry in the fd directory is a symlink to the open file.

    Returns:
        Number of open file descriptors, or 0 if inaccessible.
    """
    try:
        fd_path = f"{PROC_DIR}/{pid}/fd"
        return len(os.listdir(fd_path))
    except (FileNotFoundError, PermissionError):
        return 0


def _extract_kb(value: str) -> int:
    """Extract kB value from a /proc/[pid]/status field.

    Example: "12345 kB" -> 12345
    """
    parts = value.split()
    if parts:
        try:
            return int(parts[0])
        except ValueError:
            pass
    return 0


def list_processes() -> list[ProcessInfo]:
    """List all processes with their resource usage.

    Scans /proc for numeric directories (PIDs) and reads
    stat, status, and fd information for each.

    Returns:
        List of ProcessInfo objects for all readable processes.
    """
    total_memory_kb = _get_total_memory_kb()
    processes: list[ProcessInfo] = []

    try:
        entries = os.listdir(PROC_DIR)
    except FileNotFoundError:
        logger.warning("/proc not found — not running on Linux?")
        return processes

    for entry in entries:
        if not entry.isdigit():
            continue

        pid = int(entry)
        stat = _read_process_stat(pid)
        if stat is None:
            continue

        status = _read_process_status(pid)
        if not status:
            continue

        name = status.get("Name", "")
        state_code = stat["state"]
        state = PROCESS_STATES.get(state_code, state_code)

        rss_kb = _extract_kb(status.get("VmRSS", "0"))
        vms_kb = _extract_kb(status.get("VmSize", "0"))

        mem_pct = 0.0
        if total_memory_kb > 0:
            mem_pct = round((rss_kb / total_memory_kb) * 100, 2)

        processes.append(
            ProcessInfo(
                pid=pid,
                name=name,
                state=state,
                memory_rss_kb=rss_kb,
                memory_vms_kb=vms_kb,
                memory_percent=mem_pct,
                threads=stat["threads"],
                ppid=stat["ppid"],
                open_fds=_count_fds(pid),
                # CPU percent requires two snapshots — simplified here
                cpu_percent=0.0,
            )
        )

    return processes


def get_top_processes(
    top_n: int = 10,
    sort_by: str = "memory",
) -> list[ProcessInfo]:
    """Get the top N processes by resource consumption.

    Args:
        top_n: Number of processes to return.
        sort_by: Sort key — "memory" or "cpu".

    Returns:
        Top N ProcessInfo objects sorted by the specified metric.
    """
    processes = list_processes()

    if sort_by == "memory":
        processes.sort(key=lambda p: p.memory_rss_kb, reverse=True)
    elif sort_by == "cpu":
        processes.sort(key=lambda p: p.cpu_percent, reverse=True)

    return processes[:top_n]


def get_zombie_processes() -> list[ProcessInfo]:
    """Find all zombie processes.

    A zombie (state 'Z') is a process that has terminated but
    whose parent hasn't yet called wait() to collect its exit status.
    Too many zombies indicate a parent process bug.

    Returns:
        List of ProcessInfo for zombie processes.
    """
    return [p for p in list_processes() if p.state == "Zombie"]
