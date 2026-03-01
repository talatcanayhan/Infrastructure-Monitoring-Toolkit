"""Tests for the TCP port scanner module."""

import pytest

from infraprobe.network.tcp import (
    WELL_KNOWN_SERVICES,
    parse_port_range,
)


class TestParsePortRange:
    """Test port specification parsing."""

    def test_single_port(self) -> None:
        assert parse_port_range("80") == [80]

    def test_range(self) -> None:
        result = parse_port_range("20-25")
        assert result == [20, 21, 22, 23, 24, 25]

    def test_comma_separated(self) -> None:
        result = parse_port_range("22,80,443")
        assert result == [22, 80, 443]

    def test_mixed(self) -> None:
        result = parse_port_range("22,80,8000-8003")
        assert result == [22, 80, 8000, 8001, 8002, 8003]

    def test_deduplication(self) -> None:
        result = parse_port_range("80,80,80")
        assert result == [80]

    def test_sorted_output(self) -> None:
        result = parse_port_range("443,22,80")
        assert result == [22, 80, 443]

    def test_clamps_to_valid_range(self) -> None:
        result = parse_port_range("0-3")
        assert result == [1, 2, 3]  # Port 0 excluded


class TestWellKnownServices:
    """Verify service name mapping."""

    def test_common_ports(self) -> None:
        assert WELL_KNOWN_SERVICES[22] == "ssh"
        assert WELL_KNOWN_SERVICES[80] == "http"
        assert WELL_KNOWN_SERVICES[443] == "https"
        assert WELL_KNOWN_SERVICES[3306] == "mysql"
        assert WELL_KNOWN_SERVICES[5432] == "postgresql"
        assert WELL_KNOWN_SERVICES[6379] == "redis"
