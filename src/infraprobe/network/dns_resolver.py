"""DNS resolver with raw UDP query construction.

Builds DNS query packets from scratch per RFC 1035 and sends them
over UDP to port 53. Also provides a system resolver fallback.

Supports A, AAAA, CNAME, MX, NS, TXT, and SOA record types.

References:
    - RFC 1035: Domain Names - Implementation and Specification
    - RFC 3596: DNS Extensions to Support IPv6 (AAAA records)
"""

import logging
import os
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("infraprobe.network.dns")

# DNS record type codes
RECORD_TYPES: dict[str, int] = {
    "A": 1,
    "NS": 2,
    "CNAME": 5,
    "SOA": 6,
    "MX": 15,
    "TXT": 16,
    "AAAA": 28,
}

# DNS class (IN = Internet)
DNS_CLASS_IN = 1

# DNS header flags
DNS_FLAG_RD = 0x0100  # Recursion Desired


@dataclass
class DNSRecord:
    """A single DNS resource record."""

    record_type: str
    value: str
    ttl: Optional[int] = None


@dataclass
class DNSResult:
    """Result of a DNS resolution query."""

    domain: str
    record_type: str
    nameserver: str
    query_time_ms: float = 0.0
    records: list[DNSRecord] = field(default_factory=list)
    error: Optional[str] = None


def _encode_domain_name(domain: str) -> bytes:
    """Encode a domain name into DNS wire format.

    Each label is prefixed with its length byte, terminated with 0x00.
    Example: "example.com" -> b'\\x07example\\x03com\\x00'

    Args:
        domain: The domain name string.

    Returns:
        DNS wire format encoded domain name.
    """
    encoded = b""
    for label in domain.rstrip(".").split("."):
        length = len(label)
        if length > 63:
            raise ValueError(f"DNS label too long ({length} > 63): {label}")
        encoded += struct.pack("B", length) + label.encode("ascii")
    encoded += b"\x00"  # Root label terminator
    return encoded


def build_dns_query(domain: str, record_type: str = "A") -> tuple[bytes, int]:
    """Build a raw DNS query packet per RFC 1035.

    DNS Message Format:
        +---------------------+
        |        Header       |  12 bytes
        +---------------------+
        |       Question      |  Variable
        +---------------------+

    Header format (12 bytes):
        ID (16)  | Flags (16) | QDCOUNT (16) | ANCOUNT (16) | NSCOUNT (16) | ARCOUNT (16)

    Args:
        domain: Domain name to query.
        record_type: Record type string (A, AAAA, MX, etc.).

    Returns:
        Tuple of (query_packet, transaction_id).
    """
    # Generate random transaction ID
    transaction_id = os.getpid() & 0xFFFF

    # Get numeric record type
    qtype = RECORD_TYPES.get(record_type.upper())
    if qtype is None:
        raise ValueError(f"Unsupported record type: {record_type}")

    # Build header: ID, Flags (RD=1), QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
    header = struct.pack(
        "!HHHHHH",
        transaction_id,
        DNS_FLAG_RD,  # Standard query with recursion desired
        1,            # One question
        0, 0, 0,      # No answer, authority, or additional records
    )

    # Build question section: QNAME + QTYPE + QCLASS
    qname = _encode_domain_name(domain)
    question = qname + struct.pack("!HH", qtype, DNS_CLASS_IN)

    return header + question, transaction_id


def _decode_name(data: bytes, offset: int) -> tuple[str, int]:
    """Decode a DNS name from response data, handling compression pointers.

    DNS names can contain compression pointers (0xC0 prefix) that point
    to a previously seen name in the packet. This function recursively
    follows pointers.

    Args:
        data: The full DNS response packet.
        offset: Starting byte offset for this name.

    Returns:
        Tuple of (decoded_name, new_offset_after_name).
    """
    labels = []
    jumped = False
    original_offset = offset
    max_jumps = 20  # Prevent infinite loops from malformed packets

    for _ in range(max_jumps):
        if offset >= len(data):
            break

        length = data[offset]

        if length == 0:
            # Root label — end of name
            if not jumped:
                original_offset = offset + 1
            break

        if (length & 0xC0) == 0xC0:
            # Compression pointer: next two bytes form a 14-bit offset
            if offset + 1 >= len(data):
                break
            pointer = struct.unpack("!H", data[offset : offset + 2])[0] & 0x3FFF
            if not jumped:
                original_offset = offset + 2
            offset = pointer
            jumped = True
            continue

        # Regular label
        offset += 1
        if offset + length > len(data):
            break
        labels.append(data[offset : offset + length].decode("ascii", errors="replace"))
        offset += length

    return ".".join(labels), original_offset


def _parse_rdata(data: bytes, offset: int, rdlength: int, rtype: int) -> str:
    """Parse the RDATA field of a DNS resource record.

    Args:
        data: Full DNS response packet.
        offset: Start of RDATA.
        rdlength: Length of RDATA in bytes.
        rtype: Numeric record type.

    Returns:
        Human-readable string representation of the RDATA.
    """
    if rtype == 1 and rdlength == 4:
        # A record: 4 bytes IPv4
        return socket.inet_ntoa(data[offset : offset + 4])

    elif rtype == 28 and rdlength == 16:
        # AAAA record: 16 bytes IPv6
        return socket.inet_ntop(socket.AF_INET6, data[offset : offset + 16])

    elif rtype in (2, 5):
        # NS or CNAME: compressed domain name
        name, _ = _decode_name(data, offset)
        return name

    elif rtype == 15:
        # MX: 2 bytes preference + domain name
        preference = struct.unpack("!H", data[offset : offset + 2])[0]
        name, _ = _decode_name(data, offset + 2)
        return f"{preference} {name}"

    elif rtype == 16:
        # TXT: one or more <length><text> pairs
        texts = []
        pos = offset
        end = offset + rdlength
        while pos < end:
            txt_len = data[pos]
            pos += 1
            texts.append(data[pos : pos + txt_len].decode("utf-8", errors="replace"))
            pos += txt_len
        return " ".join(texts)

    elif rtype == 6:
        # SOA: mname, rname, serial, refresh, retry, expire, minimum
        mname, pos = _decode_name(data, offset)
        rname, pos = _decode_name(data, pos)
        if pos + 20 <= len(data):
            serial, refresh, retry, expire, minimum = struct.unpack(
                "!IIIII", data[pos : pos + 20]
            )
            return f"{mname} {rname} {serial} {refresh} {retry} {expire} {minimum}"
        return f"{mname} {rname}"

    # Fallback: hex representation
    return data[offset : offset + rdlength].hex()


def parse_dns_response(data: bytes, query_type: str) -> list[DNSRecord]:
    """Parse a DNS response packet and extract answer records.

    Args:
        data: Raw DNS response bytes.
        query_type: The record type we queried for.

    Returns:
        List of DNSRecord objects from the answer section.
    """
    if len(data) < 12:
        return []

    # Parse header
    _, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", data[:12])

    # Check for errors in response code (lower 4 bits of flags)
    rcode = flags & 0x000F
    if rcode != 0:
        logger.warning("DNS response error: rcode=%d", rcode)
        return []

    offset = 12

    # Skip question section
    for _ in range(qdcount):
        _, offset = _decode_name(data, offset)
        offset += 4  # QTYPE (2) + QCLASS (2)

    # Parse answer section
    records: list[DNSRecord] = []
    for _ in range(ancount):
        if offset >= len(data):
            break

        name, offset = _decode_name(data, offset)

        if offset + 10 > len(data):
            break

        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset : offset + 10])
        offset += 10

        if offset + rdlength > len(data):
            break

        # Reverse lookup: numeric type -> string
        type_name = next((k for k, v in RECORD_TYPES.items() if v == rtype), f"TYPE{rtype}")
        value = _parse_rdata(data, offset, rdlength, rtype)

        records.append(DNSRecord(record_type=type_name, value=value, ttl=ttl))
        offset += rdlength

    return records


def resolve(
    domain: str,
    record_type: str = "A",
    nameserver: Optional[str] = None,
) -> DNSResult:
    """Resolve a DNS record using a raw UDP query.

    Constructs a DNS query packet from scratch and sends it to the
    specified nameserver (or system default) on UDP port 53.

    Args:
        domain: Domain name to resolve.
        record_type: Record type (A, AAAA, CNAME, MX, NS, TXT, SOA).
        nameserver: Custom nameserver IP. Defaults to 8.8.8.8.

    Returns:
        DNSResult with records and query timing.
    """
    ns = nameserver or "8.8.8.8"
    result = DNSResult(domain=domain, record_type=record_type, nameserver=ns)

    try:
        # Build the raw DNS query
        query_packet, txn_id = build_dns_query(domain, record_type)

        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)

        try:
            # Send query to nameserver on port 53
            start = time.perf_counter()
            sock.sendto(query_packet, (ns, 53))

            # Wait for response
            response_data, _ = sock.recvfrom(4096)
            elapsed_ms = (time.perf_counter() - start) * 1000

            result.query_time_ms = round(elapsed_ms, 2)

            # Verify transaction ID matches
            if len(response_data) >= 2:
                resp_id = struct.unpack("!H", response_data[:2])[0]
                if resp_id != txn_id:
                    result.error = "Transaction ID mismatch in response"
                    return result

            # Parse the response
            result.records = parse_dns_response(response_data, record_type)

            if not result.records:
                # Fallback to system resolver for A/AAAA records
                result.records = _system_resolve_fallback(domain, record_type)

        finally:
            sock.close()

    except socket.timeout:
        result.error = f"DNS query timed out (nameserver: {ns})"
    except socket.gaierror as e:
        result.error = f"DNS resolution failed: {e}"
    except Exception as e:
        result.error = f"DNS query error: {e}"

    logger.info(
        "DNS %s %s via %s: %d records in %.2fms",
        record_type,
        domain,
        ns,
        len(result.records),
        result.query_time_ms,
    )

    return result


def _system_resolve_fallback(domain: str, record_type: str) -> list[DNSRecord]:
    """Fallback to system resolver using socket.getaddrinfo().

    Args:
        domain: Domain name to resolve.
        record_type: Record type (only A and AAAA supported).

    Returns:
        List of DNSRecord objects.
    """
    records: list[DNSRecord] = []
    family = socket.AF_INET if record_type == "A" else socket.AF_INET6 if record_type == "AAAA" else None

    if family is None:
        return records

    try:
        results = socket.getaddrinfo(domain, None, family)
        seen: set[str] = set()
        for _, _, _, _, sockaddr in results:
            ip = sockaddr[0]
            if ip not in seen:
                seen.add(ip)
                records.append(DNSRecord(record_type=record_type, value=ip))
    except socket.gaierror:
        pass

    return records
