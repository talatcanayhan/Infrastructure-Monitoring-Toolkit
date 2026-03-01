"""Socket state monitoring via /proc/net/tcp and /proc/net/udp.

Reads kernel socket tables to track TCP connection states
(ESTABLISHED, TIME_WAIT, CLOSE_WAIT, LISTEN, etc.) and
monitor file descriptor usage.

TCP state tracking is essential for diagnosing:
- Connection leaks (growing CLOSE_WAIT count)
- Port exhaustion (too many TIME_WAIT)
- Service availability (LISTEN state verification)

References:
    - proc(5) man page — /proc/net/tcp section
    - Linux kernel net/ipv4/tcp_ipv4.c (state constants)
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("infraprobe.system.sockets")

PROC_NET_TCP = "/proc/net/tcp"
PROC_NET_TCP6 = "/proc/net/tcp6"
PROC_NET_UDP = "/proc/net/udp"

# TCP connection states (from include/net/tcp_states.h)
TCP_STATES: dict[str, str] = {
    "01": "ESTABLISHED",
    "02": "SYN_SENT",
    "03": "SYN_RECV",
    "04": "FIN_WAIT1",
    "05": "FIN_WAIT2",
    "06": "TIME_WAIT",
    "07": "CLOSE",
    "08": "CLOSE_WAIT",
    "09": "LAST_ACK",
    "0A": "LISTEN",
    "0B": "CLOSING",
}


@dataclass
class SocketEntry:
    """A single socket entry from /proc/net/tcp."""

    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    state: str
    protocol: str = "tcp"


@dataclass
class SocketStats:
    """Aggregated socket statistics."""

    total: int = 0
    state_counts: dict[str, int] = field(default_factory=dict)
    listening_ports: list[int] = field(default_factory=list)
    entries: list[SocketEntry] = field(default_factory=list)


def _hex_to_ip(hex_addr: str) -> str:
    """Convert a hex-encoded IP address from /proc/net/tcp to dotted notation.

    /proc/net/tcp stores IPv4 addresses as 8-character hex strings
    in little-endian byte order.

    Example: "0100007F" -> "127.0.0.1"

    Args:
        hex_addr: 8-character hex string.

    Returns:
        Dotted-decimal IPv4 string.
    """
    # Convert hex to integer (stored in little-endian)
    addr_int = int(hex_addr, 16)

    # Extract bytes (little-endian → reverse for display)
    b1 = addr_int & 0xFF
    b2 = (addr_int >> 8) & 0xFF
    b3 = (addr_int >> 16) & 0xFF
    b4 = (addr_int >> 24) & 0xFF

    return f"{b1}.{b2}.{b3}.{b4}"


def _parse_proc_net_tcp(path: str = PROC_NET_TCP, protocol: str = "tcp") -> list[SocketEntry]:
    """Parse /proc/net/tcp or /proc/net/udp.

    /proc/net/tcp format:
        sl  local_address rem_address   st tx_queue rx_queue tr tm->when ...
         0: 0100007F:0035 00000000:0000 0A 00000000:00000000 00:00000000 ...

    Fields:
        local_address: hex_ip:hex_port
        rem_address:   hex_ip:hex_port
        st:            TCP state as 2-digit hex

    Args:
        path: Path to the proc net file.
        protocol: Protocol name ("tcp" or "udp").

    Returns:
        List of SocketEntry objects.
    """
    entries: list[SocketEntry] = []

    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.warning("%s not found", path)
        return entries

    # Skip header line
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue

        try:
            # Parse local address
            local_hex_ip, local_hex_port = parts[1].split(":")
            local_ip = _hex_to_ip(local_hex_ip)
            local_port = int(local_hex_port, 16)

            # Parse remote address
            remote_hex_ip, remote_hex_port = parts[2].split(":")
            remote_ip = _hex_to_ip(remote_hex_ip)
            remote_port = int(remote_hex_port, 16)

            # Parse state
            state_hex = parts[3]
            state = TCP_STATES.get(state_hex, f"UNKNOWN({state_hex})")

            entries.append(
                SocketEntry(
                    local_address=local_ip,
                    local_port=local_port,
                    remote_address=remote_ip,
                    remote_port=remote_port,
                    state=state,
                    protocol=protocol,
                )
            )
        except (ValueError, IndexError) as e:
            logger.debug("Failed to parse line: %s (%s)", line.strip(), e)
            continue

    return entries


def get_socket_stats() -> SocketStats:
    """Collect socket statistics from /proc/net/tcp and /proc/net/udp.

    Reads all TCP and UDP socket entries, counts states,
    and identifies listening ports.

    Returns:
        SocketStats with counts per state and listening port list.
    """
    stats = SocketStats()

    # Read TCP sockets (IPv4 and IPv6)
    tcp4_entries = _parse_proc_net_tcp(PROC_NET_TCP, "tcp")
    tcp6_entries = _parse_proc_net_tcp(PROC_NET_TCP6, "tcp6")
    udp_entries = _parse_proc_net_tcp(PROC_NET_UDP, "udp")

    all_entries = tcp4_entries + tcp6_entries + udp_entries
    stats.entries = all_entries
    stats.total = len(all_entries)

    # Count states
    for entry in all_entries:
        state = entry.state
        stats.state_counts[state] = stats.state_counts.get(state, 0) + 1

        if state == "LISTEN":
            if entry.local_port not in stats.listening_ports:
                stats.listening_ports.append(entry.local_port)

    stats.listening_ports.sort()

    return stats
