"""Raw socket ICMP ping implementation.

Constructs ICMP Echo Request packets from scratch using the struct module,
calculates checksums per RFC 1071, and measures round-trip time.
No external libraries — pure Python stdlib with raw sockets.

Requires root/admin privileges for raw socket access.

References:
    - RFC 792: Internet Control Message Protocol
    - RFC 1071: Computing the Internet Checksum
"""

import logging
import os
import socket
import struct
import time
from dataclasses import dataclass, field
from statistics import mean, stdev
from typing import Optional

logger = logging.getLogger("infraprobe.network.icmp")

# ICMP message types
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0

# ICMP header format: Type (8), Code (8), Checksum (16), Identifier (16), Sequence (16)
ICMP_HEADER_FORMAT = "!BBHHH"
ICMP_HEADER_SIZE = struct.calcsize(ICMP_HEADER_FORMAT)

# IP header is 20 bytes minimum (no options)
IP_HEADER_SIZE = 20


@dataclass
class PingResult:
    """Result of a single ICMP echo request/reply."""

    sequence: int
    target: str
    rtt_ms: Optional[float] = None
    ttl: Optional[int] = None
    packet_size: int = 0
    success: bool = False
    error: Optional[str] = None


@dataclass
class PingStatistics:
    """Aggregate statistics for a ping session."""

    target: str
    resolved_ip: str
    packets_sent: int = 0
    packets_received: int = 0
    packet_loss_percent: float = 0.0
    min_rtt_ms: float = 0.0
    avg_rtt_ms: float = 0.0
    max_rtt_ms: float = 0.0
    stddev_rtt_ms: float = 0.0
    results: list[PingResult] = field(default_factory=list)


def calculate_checksum(data: bytes) -> int:
    """Calculate the ICMP checksum per RFC 1071.

    The checksum is the 16-bit one's complement of the one's complement
    sum of all 16-bit words in the data. If the data has an odd number
    of bytes, it is padded with a zero byte for computation.

    Args:
        data: The bytes to checksum (ICMP header + payload).

    Returns:
        The computed 16-bit checksum value.
    """
    # Pad to even length
    if len(data) % 2:
        data += b"\x00"

    # Sum all 16-bit words (network byte order)
    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word

    # Fold 32-bit sum into 16 bits: add carry bits back
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16

    # One's complement
    return ~total & 0xFFFF


def build_icmp_packet(identifier: int, sequence: int, payload_size: int = 56) -> bytes:
    """Build a raw ICMP Echo Request packet.

    Packet structure (RFC 792):
        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |     Type      |     Code      |          Checksum             |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |           Identifier          |        Sequence Number        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                          Payload                              |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    Args:
        identifier: 16-bit identifier (usually PID & 0xFFFF).
        sequence: 16-bit sequence number.
        payload_size: Size of the random payload in bytes.

    Returns:
        The complete ICMP packet as bytes.
    """
    # Build header with zero checksum first
    header = struct.pack(
        ICMP_HEADER_FORMAT,
        ICMP_ECHO_REQUEST,  # Type 8 = Echo Request
        0,  # Code 0
        0,  # Checksum placeholder
        identifier,
        sequence,
    )

    # Generate random payload (avoids compression on some networks)
    payload = os.urandom(payload_size)

    # Calculate checksum over header + payload
    checksum = calculate_checksum(header + payload)

    # Rebuild header with computed checksum
    header = struct.pack(
        ICMP_HEADER_FORMAT,
        ICMP_ECHO_REQUEST,
        0,
        checksum,
        identifier,
        sequence,
    )

    return header + payload


def parse_icmp_reply(data: bytes, expected_id: int) -> tuple[bool, Optional[int]]:
    """Parse an ICMP Echo Reply from raw received data.

    Args:
        data: Raw bytes received from the socket (includes IP header).
        expected_id: The identifier we expect in the reply.

    Returns:
        Tuple of (is_valid_reply, ttl).
    """
    if len(data) < IP_HEADER_SIZE + ICMP_HEADER_SIZE:
        return False, None

    # Extract TTL from IP header (byte offset 8)
    ip_ttl = data[8]

    # Parse ICMP header (after IP header)
    icmp_header = data[IP_HEADER_SIZE : IP_HEADER_SIZE + ICMP_HEADER_SIZE]
    icmp_type, icmp_code, _, reply_id, _ = struct.unpack(ICMP_HEADER_FORMAT, icmp_header)

    # Validate: must be Echo Reply (type 0) with matching identifier
    if icmp_type == ICMP_ECHO_REPLY and reply_id == expected_id:
        return True, ip_ttl

    return False, None


def send_ping(
    target: str,
    sequence: int,
    timeout: float = 5.0,
    packet_size: int = 56,
    identifier: Optional[int] = None,
) -> PingResult:
    """Send a single ICMP Echo Request and wait for the reply.

    Opens a raw socket, sends the crafted ICMP packet, and measures
    the round-trip time to the target.

    Args:
        target: Hostname or IP address.
        sequence: ICMP sequence number for this ping.
        timeout: Maximum time to wait for reply in seconds.
        packet_size: Payload size in bytes.
        identifier: ICMP identifier (defaults to PID & 0xFFFF).

    Returns:
        PingResult with RTT, TTL, and success status.
    """
    if identifier is None:
        identifier = os.getpid() & 0xFFFF

    # Resolve hostname to IP
    try:
        dest_ip = socket.gethostbyname(target)
    except socket.gaierror as e:
        return PingResult(
            sequence=sequence,
            target=target,
            success=False,
            error=f"DNS resolution failed: {e}",
        )

    # Build the ICMP packet
    packet = build_icmp_packet(identifier, sequence, packet_size)

    try:
        # Create raw socket for ICMP
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.settimeout(timeout)
    except PermissionError:
        return PingResult(
            sequence=sequence,
            target=target,
            success=False,
            error="Raw socket requires root/admin privileges",
        )

    try:
        # Record send time and transmit
        send_time = time.perf_counter()
        sock.sendto(packet, (dest_ip, 0))

        # Wait for reply
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                recv_time = time.perf_counter()
            except socket.timeout:
                return PingResult(
                    sequence=sequence,
                    target=target,
                    success=False,
                    error="Request timed out",
                )

            # Parse and validate the reply
            is_valid, ttl = parse_icmp_reply(data, identifier)
            if is_valid:
                rtt_ms = (recv_time - send_time) * 1000
                return PingResult(
                    sequence=sequence,
                    target=target,
                    rtt_ms=round(rtt_ms, 3),
                    ttl=ttl,
                    packet_size=len(packet),
                    success=True,
                )

    except OSError as e:
        return PingResult(
            sequence=sequence,
            target=target,
            success=False,
            error=str(e),
        )
    finally:
        sock.close()

    return PingResult(sequence=sequence, target=target, success=False, error="Unknown error")


def ping(
    target: str,
    count: int = 4,
    interval: float = 1.0,
    timeout: float = 5.0,
    packet_size: int = 56,
) -> PingStatistics:
    """Run a ping session against a target.

    Sends multiple ICMP Echo Requests and collects statistics
    including min/avg/max/stddev RTT and packet loss.

    Args:
        target: Hostname or IP address to ping.
        count: Number of echo requests to send.
        interval: Seconds to wait between pings.
        timeout: Timeout per individual ping in seconds.
        packet_size: ICMP payload size in bytes.

    Returns:
        PingStatistics with per-packet results and aggregate stats.
    """
    # Resolve target once
    try:
        resolved_ip = socket.gethostbyname(target)
    except socket.gaierror:
        resolved_ip = target

    identifier = os.getpid() & 0xFFFF
    stats = PingStatistics(target=target, resolved_ip=resolved_ip)

    logger.info("PING %s (%s): %d data bytes", target, resolved_ip, packet_size)

    for seq in range(1, count + 1):
        result = send_ping(
            target=target,
            sequence=seq,
            timeout=timeout,
            packet_size=packet_size,
            identifier=identifier,
        )
        stats.results.append(result)
        stats.packets_sent += 1

        if result.success:
            stats.packets_received += 1
            logger.debug(
                "Reply from %s: bytes=%d seq=%d ttl=%s time=%.3fms",
                resolved_ip,
                result.packet_size,
                seq,
                result.ttl,
                result.rtt_ms or 0,
            )
        else:
            logger.debug("Seq %d: %s", seq, result.error)

        # Wait between pings (except after the last one)
        if seq < count:
            time.sleep(interval)

    # Calculate statistics
    rtts = [r.rtt_ms for r in stats.results if r.success and r.rtt_ms is not None]

    if stats.packets_sent > 0:
        stats.packet_loss_percent = round(
            ((stats.packets_sent - stats.packets_received) / stats.packets_sent) * 100, 1
        )

    if rtts:
        stats.min_rtt_ms = round(min(rtts), 3)
        stats.avg_rtt_ms = round(mean(rtts), 3)
        stats.max_rtt_ms = round(max(rtts), 3)
        stats.stddev_rtt_ms = round(stdev(rtts), 3) if len(rtts) > 1 else 0.0

    return stats
