"""Tests for the DNS resolver module."""

import struct
from unittest.mock import MagicMock, patch

import pytest

from infraprobe.network.dns_resolver import (
    DNS_CLASS_IN,
    DNS_FLAG_RD,
    RECORD_TYPES,
    _decode_name,
    _encode_domain_name,
    build_dns_query,
    parse_dns_response,
    resolve,
)


class TestEncodeDomainName:
    """Test DNS wire format encoding."""

    def test_simple_domain(self) -> None:
        """example.com should encode with length-prefixed labels."""
        encoded = _encode_domain_name("example.com")
        assert encoded == b"\x07example\x03com\x00"

    def test_subdomain(self) -> None:
        """sub.example.com should encode three labels."""
        encoded = _encode_domain_name("sub.example.com")
        assert encoded == b"\x03sub\x07example\x03com\x00"

    def test_trailing_dot(self) -> None:
        """Trailing dot (FQDN) should be handled."""
        encoded = _encode_domain_name("example.com.")
        assert encoded == b"\x07example\x03com\x00"

    def test_label_too_long(self) -> None:
        """Labels > 63 characters should raise ValueError."""
        long_label = "a" * 64 + ".com"
        with pytest.raises(ValueError, match="too long"):
            _encode_domain_name(long_label)


class TestBuildDnsQuery:
    """Test DNS query packet construction."""

    def test_query_structure(self) -> None:
        """Query should have correct header fields."""
        packet, txn_id = build_dns_query("example.com", "A")

        # Parse header (12 bytes)
        header = struct.unpack("!HHHHHH", packet[:12])
        assert header[0] == txn_id  # Transaction ID
        assert header[1] == DNS_FLAG_RD  # Flags (RD=1)
        assert header[2] == 1  # QDCOUNT = 1
        assert header[3] == 0  # ANCOUNT = 0
        assert header[4] == 0  # NSCOUNT = 0
        assert header[5] == 0  # ARCOUNT = 0

    def test_question_section(self) -> None:
        """Question section should contain encoded name + QTYPE + QCLASS."""
        packet, _ = build_dns_query("example.com", "A")
        # After 12-byte header, expect the question section
        question = packet[12:]
        # Should end with QTYPE (A=1) and QCLASS (IN=1)
        qtype, qclass = struct.unpack("!HH", question[-4:])
        assert qtype == RECORD_TYPES["A"]
        assert qclass == DNS_CLASS_IN

    def test_aaaa_query(self) -> None:
        """AAAA query should use type code 28."""
        packet, _ = build_dns_query("example.com", "AAAA")
        question = packet[12:]
        qtype, _ = struct.unpack("!HH", question[-4:])
        assert qtype == RECORD_TYPES["AAAA"]

    def test_unsupported_type(self) -> None:
        """Unsupported record types should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            build_dns_query("example.com", "INVALID")


class TestDecodeName:
    """Test DNS name decompression."""

    def test_simple_name(self) -> None:
        """Decode a simple uncompressed name."""
        data = b"\x07example\x03com\x00extra"
        name, offset = _decode_name(data, 0)
        assert name == "example.com"
        assert offset == 13  # 1+7+1+3+1

    def test_compression_pointer(self) -> None:
        """Decode a name with a compression pointer."""
        # Name at offset 0: example.com\x00
        # Pointer at offset 13: \xc0\x00 (points to offset 0)
        data = b"\x07example\x03com\x00\xc0\x00"
        name, offset = _decode_name(data, 13)
        assert name == "example.com"
        assert offset == 15  # pointer is 2 bytes


class TestParseDnsResponse:
    """Test DNS response packet parsing."""

    def test_a_record_response(self) -> None:
        """Parse a response with an A record."""
        # Build a minimal DNS response
        # Header: ID=1, flags=0x8180 (response, no error), QD=1, AN=1, NS=0, AR=0
        header = struct.pack("!HHHHHH", 1, 0x8180, 1, 1, 0, 0)

        # Question section: example.com A IN
        question = b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)

        # Answer: pointer to name(0x0C), type A(1), class IN(1), TTL 300, rdlength 4, IP 1.2.3.4
        answer = struct.pack("!H", 0xC00C)  # Pointer to offset 12 (name in question)
        answer += struct.pack("!HHIH", 1, 1, 300, 4)  # Type, Class, TTL, RDLength
        answer += bytes([1, 2, 3, 4])  # RDATA: 1.2.3.4

        response = header + question + answer
        records = parse_dns_response(response, "A")

        assert len(records) == 1
        assert records[0].record_type == "A"
        assert records[0].value == "1.2.3.4"
        assert records[0].ttl == 300


class TestResolve:
    """Test the high-level resolve function."""

    @patch("infraprobe.network.dns_resolver.socket.socket")
    def test_timeout(self, mock_socket_cls: MagicMock) -> None:
        """Should handle socket timeout gracefully."""
        import socket

        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout("timed out")
        mock_socket_cls.return_value = mock_sock

        result = resolve("example.com", nameserver="8.8.8.8")
        assert result.error is not None
        assert "timed out" in result.error.lower()
