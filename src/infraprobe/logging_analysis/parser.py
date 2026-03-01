"""Log file parsing engine for multiple log formats.

Parses syslog, nginx access/error, and Apache combined log formats
using regex patterns. Auto-detects format when possible.

Supported formats:
    - syslog: "Feb 22 14:30:01 hostname service[pid]: message"
    - nginx:  '10.0.0.1 - - [22/Feb/2026:14:30:01 +0000] "GET / HTTP/1.1" 200 612 ...'
    - apache: Combined Log Format (same as nginx with referrer and user-agent)
    - generic: Timestamp-prefixed lines with level keywords
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("infraprobe.logging_analysis.parser")


@dataclass
class LogEntry:
    """A single parsed log entry."""

    raw: str
    timestamp: Optional[str] = None
    level: str = "INFO"
    source: str = ""
    message: str = ""
    line_number: int = 0


# Regex patterns for log formats

# Syslog: "Feb 22 14:30:01 hostname service[pid]: message"
SYSLOG_PATTERN = re.compile(
    r"^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<service>\S+?)(?:\[\d+\])?:\s+"
    r"(?P<message>.+)$"
)

# Nginx/Apache combined: '10.0.0.1 - - [22/Feb/2026:14:30:01 +0000] "GET / HTTP/1.1" 200 612'
NGINX_PATTERN = re.compile(
    r'^(?P<remote_addr>\S+)\s+\S+\s+\S+\s+'
    r'\[(?P<timestamp>[^\]]+)\]\s+'
    r'"(?P<request>[^"]+)"\s+'
    r'(?P<status>\d{3})\s+'
    r'(?P<body_bytes>\d+)'
)

# Nginx error log: "2026/02/22 14:30:01 [error] 1234#0: *5678 message"
NGINX_ERROR_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"\[(?P<level>\w+)\]\s+"
    r"(?P<pid>\d+)#\d+:\s+"
    r"(?P<message>.+)$"
)

# Generic timestamp pattern with level
GENERIC_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[\sT]\d{2}:\d{2}:\d{2}[^\s]*)\s+"
    r"(?P<level>DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\s+"
    r"(?P<message>.+)$",
    re.IGNORECASE,
)

# Level detection keywords for unstructured logs
LEVEL_KEYWORDS = {
    "error": "ERROR",
    "err": "ERROR",
    "fail": "ERROR",
    "fatal": "CRITICAL",
    "critical": "CRITICAL",
    "crit": "CRITICAL",
    "warn": "WARNING",
    "warning": "WARNING",
    "notice": "INFO",
    "info": "INFO",
    "debug": "DEBUG",
}


def _detect_level(message: str) -> str:
    """Detect log level from message content using keywords.

    Args:
        message: The log message text.

    Returns:
        Detected log level string.
    """
    lower = message.lower()
    for keyword, level in LEVEL_KEYWORDS.items():
        if keyword in lower:
            return level
    return "INFO"


def _parse_syslog(line: str) -> Optional[LogEntry]:
    """Parse a syslog-format line."""
    match = SYSLOG_PATTERN.match(line)
    if not match:
        return None
    return LogEntry(
        raw=line,
        timestamp=match.group("timestamp"),
        level=_detect_level(match.group("message")),
        source=match.group("service"),
        message=match.group("message"),
    )


def _parse_nginx_access(line: str) -> Optional[LogEntry]:
    """Parse an nginx/apache access log line."""
    match = NGINX_PATTERN.match(line)
    if not match:
        return None

    status = int(match.group("status"))
    if status >= 500:
        level = "ERROR"
    elif status >= 400:
        level = "WARNING"
    else:
        level = "INFO"

    return LogEntry(
        raw=line,
        timestamp=match.group("timestamp"),
        level=level,
        source=match.group("remote_addr"),
        message=f'{match.group("request")} -> {status} ({match.group("body_bytes")} bytes)',
    )


def _parse_nginx_error(line: str) -> Optional[LogEntry]:
    """Parse an nginx error log line."""
    match = NGINX_ERROR_PATTERN.match(line)
    if not match:
        return None
    return LogEntry(
        raw=line,
        timestamp=match.group("timestamp"),
        level=match.group("level").upper(),
        source="nginx",
        message=match.group("message"),
    )


def _parse_generic(line: str) -> Optional[LogEntry]:
    """Parse a generic timestamped log line."""
    match = GENERIC_PATTERN.match(line)
    if not match:
        return None
    return LogEntry(
        raw=line,
        timestamp=match.group("timestamp"),
        level=match.group("level").upper(),
        message=match.group("message"),
    )


def _auto_detect_format(lines: list[str]) -> str:
    """Auto-detect log format by testing first few lines.

    Args:
        lines: First few lines of the log file.

    Returns:
        Detected format name.
    """
    for line in lines[:10]:
        line = line.strip()
        if not line:
            continue
        if NGINX_PATTERN.match(line):
            return "nginx"
        if NGINX_ERROR_PATTERN.match(line):
            return "nginx_error"
        if SYSLOG_PATTERN.match(line):
            return "syslog"
        if GENERIC_PATTERN.match(line):
            return "generic"
    return "generic"


def parse_log_file(
    path: str,
    log_format: str = "auto",
    tail: int = 0,
) -> list[LogEntry]:
    """Parse a log file into structured entries.

    Args:
        path: Path to the log file.
        log_format: Format hint ("auto", "syslog", "nginx", "apache", "generic").
        tail: Only parse last N lines (0 = all).

    Returns:
        List of parsed LogEntry objects.

    Raises:
        FileNotFoundError: If the log file doesn't exist.
    """
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()

    if tail > 0:
        lines = lines[-tail:]

    # Detect format
    if log_format == "auto":
        log_format = _auto_detect_format(lines)
        logger.info("Auto-detected log format: %s", log_format)

    # Select parser
    parsers = {
        "syslog": _parse_syslog,
        "nginx": _parse_nginx_access,
        "apache": _parse_nginx_access,  # Same format
        "nginx_error": _parse_nginx_error,
        "generic": _parse_generic,
    }
    parser_fn = parsers.get(log_format, _parse_generic)

    entries: list[LogEntry] = []
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        entry = parser_fn(line)
        if entry is None:
            # Fallback: create basic entry with level detection
            entry = LogEntry(
                raw=line,
                level=_detect_level(line),
                message=line,
            )

        entry.line_number = i
        entries.append(entry)

    logger.info("Parsed %d log entries from %s (format: %s)", len(entries), path, log_format)
    return entries
