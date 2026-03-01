"""Tests for the HTTP checker module."""

from unittest.mock import MagicMock, patch

import requests

from infraprobe.network.http_checker import check_http


class TestCheckHttp:
    """Test HTTP health checking."""

    @patch("infraprobe.network.http_checker.check_tls_certificate")
    @patch("infraprobe.network.http_checker.requests.get")
    def test_successful_check(self, mock_get: MagicMock, mock_tls: MagicMock) -> None:
        """Should return success for 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.content = b"Hello"
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_get.return_value = mock_response
        mock_tls.return_value = MagicMock(days_until_expiry=90)

        result = check_http("https://example.com", expected_status=200)
        assert result.success is True
        assert result.status_code == 200

    @patch("infraprobe.network.http_checker.requests.get")
    def test_unexpected_status(self, mock_get: MagicMock) -> None:
        """Should return failure for unexpected status code."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.reason = "Service Unavailable"
        mock_response.content = b""
        mock_response.headers = {}
        mock_get.return_value = mock_response

        result = check_http("http://example.com", expected_status=200, check_tls=False)
        assert result.success is False
        assert result.status_code == 503

    @patch("infraprobe.network.http_checker.requests.get")
    def test_connection_error(self, mock_get: MagicMock) -> None:
        """Should handle connection errors gracefully."""
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")

        result = check_http("http://down.example.com", check_tls=False)
        assert result.success is False
        assert result.error is not None
        assert "Connection" in result.error

    @patch("infraprobe.network.http_checker.requests.get")
    def test_timeout(self, mock_get: MagicMock) -> None:
        """Should handle request timeouts."""
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        result = check_http("http://slow.example.com", timeout=1.0, check_tls=False)
        assert result.success is False
        assert "timed out" in (result.error or "").lower()
