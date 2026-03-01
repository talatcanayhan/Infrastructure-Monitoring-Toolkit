"""Tests for the log analyzer module."""

from infraprobe.logging_analysis.analyzer import analyze_entries
from infraprobe.logging_analysis.parser import LogEntry


def _make_entry(level: str = "INFO", message: str = "test") -> LogEntry:
    return LogEntry(raw=message, level=level, message=message, timestamp="2026-02-22 14:00:00")


class TestAnalyzeEntries:
    """Test log entry analysis."""

    def test_empty_entries(self) -> None:
        result = analyze_entries([])
        assert result.total_entries == 0

    def test_level_distribution(self) -> None:
        entries = [
            _make_entry("INFO", "ok"),
            _make_entry("INFO", "ok"),
            _make_entry("ERROR", "fail"),
            _make_entry("WARNING", "warn"),
        ]
        result = analyze_entries(entries)
        assert result.level_distribution["INFO"] == 2
        assert result.level_distribution["ERROR"] == 1
        assert result.level_distribution["WARNING"] == 1

    def test_error_rate(self) -> None:
        entries = [_make_entry("INFO")] * 8 + [_make_entry("ERROR")] * 2
        result = analyze_entries(entries)
        assert result.error_count == 2
        assert result.error_rate_percent == 20.0

    def test_pattern_matching(self) -> None:
        entries = [
            _make_entry("ERROR", "disk I/O error on sda"),
            _make_entry("INFO", "system running normally"),
            _make_entry("ERROR", "disk I/O error on sdb"),
        ]
        result = analyze_entries(entries, pattern="disk.*error")
        assert len(result.pattern_matches) == 2

    def test_invalid_pattern(self) -> None:
        entries = [_make_entry("INFO", "test")]
        result = analyze_entries(entries, pattern="[invalid")
        assert len(result.pattern_matches) == 0

    def test_time_range(self) -> None:
        entries = [
            LogEntry(raw="a", timestamp="2026-02-22 14:00:00", level="INFO", message="a"),
            LogEntry(raw="b", timestamp="2026-02-22 15:00:00", level="INFO", message="b"),
        ]
        result = analyze_entries(entries)
        assert "14:00:00" in result.time_range
        assert "15:00:00" in result.time_range
