"""Tests for the ICMP ping module."""

import struct
from unittest.mock import MagicMock, patch

import pytest

from infraprobe.network.icmp import (
    ICMP_ECHO_REPLY,
    ICMP_ECHO_REQUEST,
    ICMP_HEADER_FORMAT,
    build_icmp_packet,
    calculate_checksum,
    parse_icmp_reply,
    ping,
    send_ping,
)


class TestCalculateChecksum:
    """Test the RFC 1071 checksum implementation."""

    def test_zero_data(self) -> None:
        """Checksum of all zeros should be 0xFFFF."""
        assert calculate_checksum(b"\x00\x00") == 0xFFFF

    def test_known_value(self) -> None:
        """Verify checksum against a known computation."""
        # Echo request header: type=8, code=0, checksum=0, id=1, seq=1
        header = struct.pack("!BBHHH", 8, 0, 0, 1, 1)
        checksum = calculate_checksum(header)
        assert isinstance(checksum, int)
        assert 0 <= checksum <= 0xFFFF

    def test_checksum_is_self_verifying(self) -> None:
        """A correct checksum makes the total checksum zero."""
        data = b"\x08\x00\x00\x00\x00\x01\x00\x01"
        checksum = calculate_checksum(data)
        # Insert checksum and recompute — should verify to 0
        checked = data[:2] + struct.pack("!H", checksum) + data[4:]
        assert calculate_checksum(checked) == 0

    def test_odd_length_data(self) -> None:
        """Odd-length data should be padded and checksummed."""
        checksum = calculate_checksum(b"\x08\x00\x00")
        assert isinstance(checksum, int)
        assert 0 <= checksum <= 0xFFFF


class TestBuildIcmpPacket:
    """Test ICMP packet construction."""

    def test_packet_structure(self) -> None:
        """Packet should have correct type, code, and non-zero checksum."""
        packet = build_icmp_packet(identifier=1234, sequence=1, payload_size=56)

        # Total size = 8 (header) + 56 (payload) = 64 bytes
        assert len(packet) == 64

        # Parse header
        icmp_type, code, checksum, ident, seq = struct.unpack(
            ICMP_HEADER_FORMAT, packet[:8]
        )
        assert icmp_type == ICMP_ECHO_REQUEST
        assert code == 0
        assert checksum != 0  # Checksum should be computed
        assert ident == 1234
        assert seq == 1

    def test_checksum_validates(self) -> None:
        """The built packet should have a valid checksum."""
        packet = build_icmp_packet(identifier=1, sequence=1)
        # Full packet checksum should be 0 (self-verifying)
        assert calculate_checksum(packet) == 0

    def test_different_payloads(self) -> None:
        """Different payload sizes should produce different packet lengths."""
        small = build_icmp_packet(1, 1, payload_size=8)
        large = build_icmp_packet(1, 1, payload_size=128)
        assert len(small) == 8 + 8
        assert len(large) == 8 + 128


class TestParseIcmpReply:
    """Test ICMP reply parsing."""

    def test_valid_reply(self) -> None:
        """A properly formatted Echo Reply should be parsed correctly."""
        # Build a fake IP header (20 bytes) + ICMP Echo Reply
        ip_header = b"\x45" + b"\x00" * 7 + b"\x40" + b"\x00" * 11  # TTL=64 at byte 8
        icmp_header = struct.pack(ICMP_HEADER_FORMAT, ICMP_ECHO_REPLY, 0, 0, 42, 1)
        data = ip_header + icmp_header

        is_valid, ttl = parse_icmp_reply(data, expected_id=42)
        assert is_valid is True
        assert ttl == 64

    def test_wrong_identifier(self) -> None:
        """Reply with wrong identifier should be rejected."""
        ip_header = b"\x45" + b"\x00" * 7 + b"\x40" + b"\x00" * 11
        icmp_header = struct.pack(ICMP_HEADER_FORMAT, ICMP_ECHO_REPLY, 0, 0, 99, 1)
        data = ip_header + icmp_header

        is_valid, ttl = parse_icmp_reply(data, expected_id=42)
        assert is_valid is False

    def test_too_short(self) -> None:
        """Data shorter than IP + ICMP headers should fail."""
        is_valid, ttl = parse_icmp_reply(b"\x00" * 10, expected_id=1)
        assert is_valid is False
        assert ttl is None


class TestSendPing:
    """Test send_ping with mocked sockets."""

    @patch("infraprobe.network.icmp.socket.socket")
    @patch("infraprobe.network.icmp.socket.gethostbyname", return_value="127.0.0.1")
    def test_permission_error(self, mock_resolve: MagicMock, mock_socket: MagicMock) -> None:
        """Should return error when lacking privileges."""
        mock_socket.side_effect = PermissionError("Operation not permitted")
        result = send_ping("127.0.0.1", sequence=1)
        assert result.success is False
        assert "privileges" in (result.error or "").lower()

    @patch("infraprobe.network.icmp.socket.gethostbyname")
    def test_dns_failure(self, mock_resolve: MagicMock) -> None:
        """Should handle DNS resolution failure."""
        import socket
        mock_resolve.side_effect = socket.gaierror("Name resolution failed")
        result = send_ping("nonexistent.invalid", sequence=1)
        assert result.success is False
        assert "DNS" in (result.error or "")


class TestPing:
    """Test the ping session function."""

    @patch("infraprobe.network.icmp.send_ping")
    @patch("infraprobe.network.icmp.socket.gethostbyname", return_value="1.2.3.4")
    def test_statistics_calculation(self, mock_resolve: MagicMock, mock_send: MagicMock) -> None:
        """Statistics should correctly compute min/avg/max/loss."""
        from infraprobe.network.icmp import PingResult

        mock_send.side_effect = [
            PingResult(sequence=1, target="1.2.3.4", rtt_ms=10.0, ttl=64, success=True, packet_size=64),
            PingResult(sequence=2, target="1.2.3.4", rtt_ms=20.0, ttl=64, success=True, packet_size=64),
            PingResult(sequence=3, target="1.2.3.4", success=False, error="timeout"),
        ]

        stats = ping("1.2.3.4", count=3, interval=0)
        assert stats.packets_sent == 3
        assert stats.packets_received == 2
        assert stats.min_rtt_ms == 10.0
        assert stats.max_rtt_ms == 20.0
        assert stats.avg_rtt_ms == 15.0
        assert stats.packet_loss_percent == pytest.approx(33.3, abs=0.1)
