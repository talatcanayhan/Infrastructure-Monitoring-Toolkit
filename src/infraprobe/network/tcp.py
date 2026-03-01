"""Async TCP port scanner with service banner grabbing.

Uses asyncio for high-concurrency port scanning without threads.
Performs full TCP three-way handshake and attempts to read service
banners from open ports to identify running services.

No external dependencies — pure Python stdlib asyncio + socket.
"""

import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("infraprobe.network.tcp")

# Well-known port to service mapping
WELL_KNOWN_SERVICES: dict[int, str] = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    80: "http",
    110: "pop3",
    111: "rpcbind",
    135: "msrpc",
    139: "netbios-ssn",
    143: "imap",
    443: "https",
    445: "microsoft-ds",
    465: "smtps",
    587: "submission",
    993: "imaps",
    995: "pop3s",
    1433: "mssql",
    1521: "oracle",
    3306: "mysql",
    3389: "rdp",
    5432: "postgresql",
    5672: "amqp",
    6379: "redis",
    8080: "http-proxy",
    8443: "https-alt",
    9090: "prometheus",
    9100: "node-exporter",
    27017: "mongodb",
}


@dataclass
class PortResult:
    """Result of scanning a single port."""

    port: int
    state: str  # "open", "closed", "filtered"
    service: str = ""
    latency_ms: float = 0.0
    banner: str = ""


def parse_port_range(port_spec: str) -> list[int]:
    """Parse a port specification string into a list of port numbers.

    Supports formats:
        - Single port: "80"
        - Range: "1-1024"
        - Comma-separated: "22,80,443"
        - Mixed: "22,80,443,8000-8100"

    Args:
        port_spec: Port specification string.

    Returns:
        Sorted list of unique port numbers.
    """
    ports: set[int] = set()
    for part in port_spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start_port = max(1, int(start))
            end_port = min(65535, int(end))
            ports.update(range(start_port, end_port + 1))
        else:
            port = int(part)
            if 1 <= port <= 65535:
                ports.add(port)
    return sorted(ports)


async def scan_single_port(
    host: str,
    port: int,
    timeout: float = 3.0,
) -> PortResult:
    """Scan a single TCP port using async connect.

    Performs a full TCP three-way handshake (SYN → SYN-ACK → ACK).
    If the port is open, attempts to read a service banner.

    Args:
        host: Target hostname or IP.
        port: Port number to scan.
        timeout: Connection timeout in seconds.

    Returns:
        PortResult with state, latency, and banner information.
    """
    start = time.perf_counter()
    service = WELL_KNOWN_SERVICES.get(port, "")

    try:
        # Attempt TCP connection (three-way handshake)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Port is open — try to grab the service banner
        banner = ""
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            banner = data.decode("utf-8", errors="replace").strip()
        except (asyncio.TimeoutError, Exception):
            pass

        writer.close()
        await writer.wait_closed()

        return PortResult(
            port=port,
            state="open",
            service=service,
            latency_ms=round(elapsed_ms, 2),
            banner=banner,
        )

    except asyncio.TimeoutError:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return PortResult(
            port=port,
            state="filtered",
            service=service,
            latency_ms=round(elapsed_ms, 2),
        )

    except (ConnectionRefusedError, ConnectionResetError):
        elapsed_ms = (time.perf_counter() - start) * 1000
        return PortResult(
            port=port,
            state="closed",
            service=service,
            latency_ms=round(elapsed_ms, 2),
        )

    except OSError:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return PortResult(
            port=port,
            state="filtered",
            service=service,
            latency_ms=round(elapsed_ms, 2),
        )


async def _scan_ports_async(
    host: str,
    ports: list[int],
    timeout: float = 3.0,
    max_concurrent: int = 100,
) -> list[PortResult]:
    """Scan multiple ports concurrently with a semaphore to limit connections.

    Args:
        host: Target hostname or IP.
        ports: List of port numbers to scan.
        timeout: Timeout per connection.
        max_concurrent: Maximum simultaneous connections.

    Returns:
        List of PortResult objects sorted by port number.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _scan_with_limit(port: int) -> PortResult:
        async with semaphore:
            return await scan_single_port(host, port, timeout)

    tasks = [_scan_with_limit(port) for port in ports]
    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda r: r.port)


def scan_ports(
    host: str,
    ports: list[int],
    timeout: float = 3.0,
    max_concurrent: int = 100,
) -> list[PortResult]:
    """Scan TCP ports on a target host.

    This is the synchronous entry point that wraps the async scanner.
    Uses asyncio for high-concurrency scanning without threads.

    Args:
        host: Target hostname or IP address.
        ports: List of port numbers to scan.
        timeout: Connection timeout per port in seconds.
        max_concurrent: Maximum simultaneous connections.

    Returns:
        List of PortResult objects sorted by port number.
    """
    # Resolve hostname once
    try:
        resolved_ip = socket.gethostbyname(host)
    except socket.gaierror:
        resolved_ip = host

    logger.info("Scanning %d ports on %s (%s)", len(ports), host, resolved_ip)
    start = time.perf_counter()

    results = asyncio.run(_scan_ports_async(resolved_ip, ports, timeout, max_concurrent))

    elapsed = time.perf_counter() - start
    open_count = sum(1 for r in results if r.state == "open")
    logger.info(
        "Scan complete: %d open ports found in %.2fs",
        open_count,
        elapsed,
    )

    return results


def tcp_handshake_time(host: str, port: int, timeout: float = 5.0) -> Optional[float]:
    """Measure the time for a TCP three-way handshake.

    Opens a TCP connection and measures the time from SYN sent
    to connection established.

    Args:
        host: Target hostname or IP.
        port: Target port number.
        timeout: Connection timeout in seconds.

    Returns:
        Handshake time in milliseconds, or None if connection failed.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        start = time.perf_counter()
        sock.connect((host, port))
        elapsed_ms = (time.perf_counter() - start) * 1000

        sock.close()
        return round(elapsed_ms, 3)

    except (socket.timeout, ConnectionRefusedError, OSError):
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass
