"""Tests for the traceroute module."""

from unittest.mock import MagicMock, patch

from infraprobe.network.traceroute import _resolve_hostname, traceroute


class TestResolveHostname:
    """Test reverse DNS lookup."""

    @patch("infraprobe.network.traceroute.socket.gethostbyaddr")
    def test_successful_resolve(self, mock_resolve: MagicMock) -> None:
        mock_resolve.return_value = ("router.example.com", [], ["1.2.3.4"])
        assert _resolve_hostname("1.2.3.4") == "router.example.com"

    @patch("infraprobe.network.traceroute.socket.gethostbyaddr")
    def test_failed_resolve(self, mock_resolve: MagicMock) -> None:
        import socket

        mock_resolve.side_effect = socket.herror("not found")
        assert _resolve_hostname("1.2.3.4") == "1.2.3.4"


class TestTraceroute:
    """Test traceroute function."""

    @patch("infraprobe.network.traceroute.socket.gethostbyname")
    def test_dns_failure(self, mock_resolve: MagicMock) -> None:
        import socket

        mock_resolve.side_effect = socket.gaierror("not found")
        hops = traceroute("nonexistent.invalid")
        assert hops == []
