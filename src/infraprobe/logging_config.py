"""Structured logging configuration for InfraProbe."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for log aggregation pipelines."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """Human-readable log format for terminal output."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[1;31m",  # Bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelname, "")
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        msg = record.getMessage()
        formatted = f"{timestamp} {color}{record.levelname:<8}{self.RESET} {record.name} - {msg}"
        if record.exc_info and record.exc_info[1]:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted


def setup_logging(
    level: str = "INFO",
    log_format: str = "text",
    log_file: Optional[str] = None,
) -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format - "json" for structured or "text" for human-readable.
        log_file: Optional file path to write logs to.
    """
    root_logger = logging.getLogger("infraprobe")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()

    if log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
