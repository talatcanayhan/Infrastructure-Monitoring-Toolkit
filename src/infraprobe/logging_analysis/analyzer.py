"""Log analysis engine for pattern detection and statistics.

Analyzes parsed log entries to produce:
- Log level distribution
- Error rate over time
- Pattern matching (regex filtering)
- Frequency analysis of recurring messages
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from infraprobe.logging_analysis.parser import LogEntry

logger = logging.getLogger("infraprobe.logging_analysis.analyzer")


@dataclass
class AnalysisResult:
    """Results of log file analysis."""

    total_entries: int = 0
    time_range: str = ""
    level_distribution: dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    warning_count: int = 0
    error_rate_percent: float = 0.0
    pattern_matches: list[LogEntry] = field(default_factory=list)
    top_messages: list[tuple[str, int]] = field(default_factory=list)


def analyze_entries(
    entries: list[LogEntry],
    pattern: Optional[str] = None,
    top_n: int = 10,
) -> AnalysisResult:
    """Analyze a list of log entries.

    Produces statistics about log levels, error rates,
    and optionally filters by regex pattern.

    Args:
        entries: Parsed log entries to analyze.
        pattern: Optional regex pattern to filter/highlight matching entries.
        top_n: Number of most frequent messages to report.

    Returns:
        AnalysisResult with statistics and matched entries.
    """
    result = AnalysisResult(total_entries=len(entries))

    if not entries:
        return result

    # Time range
    timestamps = [e.timestamp for e in entries if e.timestamp]
    if timestamps:
        result.time_range = f"{timestamps[0]} to {timestamps[-1]}"

    # Level distribution
    level_counts: Counter[str] = Counter()
    for entry in entries:
        level_counts[entry.level] += 1

    result.level_distribution = dict(level_counts)
    result.error_count = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
    result.warning_count = level_counts.get("WARNING", 0) + level_counts.get("WARN", 0)

    if result.total_entries > 0:
        result.error_rate_percent = round((result.error_count / result.total_entries) * 100, 2)

    # Pattern matching
    if pattern:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            result.pattern_matches = [
                e for e in entries if compiled.search(e.message) or compiled.search(e.raw)
            ]
        except re.error as e:
            logger.warning("Invalid regex pattern '%s': %s", pattern, e)

    # Top recurring messages (normalized — strip numbers and IPs for grouping)
    def normalize_message(msg: str) -> str:
        msg = re.sub(r"\d+\.\d+\.\d+\.\d+", "<IP>", msg)
        msg = re.sub(r"\d{2,}", "<N>", msg)
        return msg[:100]

    message_counts: Counter[str] = Counter()
    for entry in entries:
        normalized = normalize_message(entry.message)
        message_counts[normalized] += 1

    result.top_messages = message_counts.most_common(top_n)

    return result
