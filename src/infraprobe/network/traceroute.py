"""Traceroute implementation using ICMP with incrementing TTL.

Discovers the network path to a target by sending ICMP Echo Requests
with increasing Time-To-Live (TTL) values. Each router along the path
decrements TTL by 1; when it reaches 0, the router sends back an
ICMP Time Exceeded message, revealing its IP address.

Requires root/admin privileges for raw socket access.

References:
    - RFC 792: ICMP - Type 11 (Time Exceeded)
    - RFC 1393: Traceroute Using an IP Option
"""

import logging
import os
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Optional

from infraprobe.network.icmp import (
    ICMP_HEADER_FORMAT,
    ICMP_HEADER_SIZE,
    IP_HEADER_SIZE,
    build_icmp_packet,
)

logger = logging.getLogger("infraprobe.network.traceroute")

# ICMP type codes
ICMP_TIME_EXCEEDED = 11
ICMP_ECHO_REPLY = 0


@dataclass
class TracerouteHop:
    """A single hop in the traceroute path."""

    hop_number: int
    ip: Optional[str] = None
    hostname: Optional[str] = None
    rtts: list[Optional[float]] = field(default_factory=list)


def _resolve_hostname(ip: str) -> str:
    """Attempt reverse DNS lookup for an IP address.

    Args:
        ip: IP address string.

    Returns:
        Hostname if resolvable, otherwise the original IP.
    """
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror):
        return ip


def _send_probe(
    target_ip: str,
    ttl: int,
    sequence: int,
    timeout: float,
    identifier: int,
) -> tuple[Optional[str], Optional[float], bool]:
    """Send a single traceroute probe with a specific TTL.

    Args:
        target_ip: Destination IP address.
        ttl: Time-To-Live value for this probe.
        sequence: ICMP sequence number.
        timeout: Timeout in seconds for this probe.
        identifier: ICMP identifier.

    Returns:
        Tuple of (responder_ip, rtt_ms, reached_destination).
    """
    packet = build_icmp_packet(identifier, sequence, payload_size=32)

    try:
        # Create raw ICMP socket and set TTL
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        sock.settimeout(timeout)
    except PermissionError:
        logger.error("Raw socket requires root/admin privileges")
        return None, None, False

    try:
        send_time = time.perf_counter()
        sock.sendto(packet, (target_ip, 0))

        try:
            data, addr = sock.recvfrom(1024)
            recv_time = time.perf_counter()
        except socket.timeout:
            return None, None, False

        rtt_ms = round((recv_time - send_time) * 1000, 2)
        responder_ip = addr[0]

        # Parse ICMP type from response
        if len(data) >= IP_HEADER_SIZE + 1:
            icmp_type = data[IP_HEADER_SIZE]

            if icmp_type == ICMP_TIME_EXCEEDED:
                # Intermediate router — TTL expired
                return responder_ip, rtt_ms, False

            elif icmp_type == ICMP_ECHO_REPLY:
                # Final destination reached
                return responder_ip, rtt_ms, True

        return responder_ip, rtt_ms, False

    except OSError as e:
        logger.debug("Probe TTL=%d failed: %s", ttl, e)
        return None, None, False
    finally:
        sock.close()


def traceroute(
    target: str,
    max_hops: int = 30,
    timeout: float = 3.0,
    probes_per_hop: int = 3,
) -> list[TracerouteHop]:
    """Trace the network path to a target.

    Sends ICMP Echo Requests with incrementing TTL from 1 to max_hops.
    For each TTL value, sends multiple probes to measure RTT variance.
    Stops when the target responds with an Echo Reply.

    Args:
        target: Hostname or IP address to trace to.
        max_hops: Maximum number of hops (TTL values) to try.
        timeout: Timeout per probe in seconds.
        probes_per_hop: Number of probes to send per hop.

    Returns:
        List of TracerouteHop objects representing the path.
    """
    # Resolve target
    try:
        target_ip = socket.gethostbyname(target)
    except socket.gaierror as e:
        logger.error("Cannot resolve %s: %s", target, e)
        return []

    identifier = os.getpid() & 0xFFFF
    hops: list[TracerouteHop] = []
    sequence = 1

    logger.info(
        "Traceroute to %s (%s), %d hops max, %d probes per hop",
        target, target_ip, max_hops, probes_per_hop,
    )

    for ttl in range(1, max_hops + 1):
        hop = TracerouteHop(hop_number=ttl)
        reached = False

        for probe in range(probes_per_hop):
            responder_ip, rtt_ms, is_destination = _send_probe(
                target_ip=target_ip,
                ttl=ttl,
                sequence=sequence,
                timeout=timeout,
                identifier=identifier,
            )
            sequence += 1

            if responder_ip and not hop.ip:
                hop.ip = responder_ip
                hop.hostname = _resolve_hostname(responder_ip)

            hop.rtts.append(rtt_ms)

            if is_destination:
                reached = True

        hops.append(hop)

        if hop.ip:
            avg_rtt = sum(r for r in hop.rtts if r is not None) / max(
                sum(1 for r in hop.rtts if r is not None), 1
            )
            logger.debug(
                "Hop %2d: %s (%s) avg=%.2fms",
                ttl, hop.hostname, hop.ip, avg_rtt,
            )
        else:
            logger.debug("Hop %2d: * * *", ttl)

        if reached:
            break

    return hops
