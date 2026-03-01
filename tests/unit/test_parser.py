"""Tests for the log parser module."""

from pathlib import Path

import pytest

from infraprobe.logging_analysis.parser import (
    _detect_level,
    _parse_nginx_access,
    _parse_syslog,
    parse_log_file,
)


class TestDetectLevel:
    """Test keyword-based log level detection."""

    def test_error_keywords(self) -> None:
        assert _detect_level("Connection error occurred") == "ERROR"
        assert _detect_level("Task failed") == "ERROR"

    def test_warning_keywords(self) -> None:
        assert _detect_level("High latency warning") == "WARNING"

    def test_critical_keywords(self) -> None:
        assert _detect_level("FATAL: disk full") == "CRITICAL"

    def test_default_info(self) -> None:
        assert _detect_level("Everything is fine") == "INFO"


class TestParseSyslog:
    """Test syslog format parsing."""

    def test_standard_syslog(self) -> None:
        line = "Feb 22 14:30:01 myhost sshd[1234]: Accepted publickey for user"
        entry = _parse_syslog(line)
        assert entry is not None
        assert entry.timestamp == "Feb 22 14:30:01"
        assert entry.source == "sshd"
        assert "Accepted publickey" in entry.message

    def test_syslog_with_error(self) -> None:
        line = "Feb 22 14:30:01 myhost kernel: Out of memory: Kill process 1234"
        entry = _parse_syslog(line)
        assert entry is not None
        assert entry.level == "ERROR"


class TestParseNginxAccess:
    """Test nginx access log parsing."""

    def test_200_response(self) -> None:
        line = '10.0.0.1 - - [22/Feb/2026:14:30:01 +0000] "GET /api/health HTTP/1.1" 200 612'
        entry = _parse_nginx_access(line)
        assert entry is not None
        assert entry.level == "INFO"
        assert "200" in entry.message

    def test_500_response(self) -> None:
        line = '10.0.0.1 - - [22/Feb/2026:14:30:01 +0000] "POST /api/data HTTP/1.1" 500 128'
        entry = _parse_nginx_access(line)
        assert entry is not None
        assert entry.level == "ERROR"

    def test_404_response(self) -> None:
        line = '10.0.0.1 - - [22/Feb/2026:14:30:01 +0000] "GET /missing HTTP/1.1" 404 0'
        entry = _parse_nginx_access(line)
        assert entry is not None
        assert entry.level == "WARNING"


class TestParseLogFile:
    """Test file-level log parsing."""

    def test_parse_syslog_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "syslog"
        log_file.write_text(
            "Feb 22 14:30:01 host sshd[1]: Connection from 10.0.0.1\n"
            "Feb 22 14:30:02 host kernel: error: disk I/O failure\n"
            "Feb 22 14:30:03 host cron[2]: Running job\n"
        )
        entries = parse_log_file(str(log_file), log_format="syslog")
        assert len(entries) == 3
        assert entries[1].level == "ERROR"

    def test_tail_parameter(self, tmp_path: Path) -> None:
        log_file = tmp_path / "big.log"
        lines = [f"Feb 22 14:30:{i:02d} host test[1]: Line {i}\n" for i in range(100)]
        log_file.write_text("".join(lines))
        entries = parse_log_file(str(log_file), log_format="syslog", tail=10)
        assert len(entries) == 10

    def test_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_log_file("/nonexistent/log")
