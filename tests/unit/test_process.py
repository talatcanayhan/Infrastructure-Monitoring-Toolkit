"""Tests for the process monitoring module."""

from infraprobe.system.process import PROCESS_STATES, _extract_kb


class TestProcessStates:
    """Test process state code mapping."""

    def test_known_states(self) -> None:
        assert PROCESS_STATES["R"] == "Running"
        assert PROCESS_STATES["S"] == "Sleeping"
        assert PROCESS_STATES["Z"] == "Zombie"
        assert PROCESS_STATES["D"] == "Disk Sleep"
        assert PROCESS_STATES["T"] == "Stopped"


class TestExtractKb:
    """Test kB value extraction from /proc/[pid]/status fields."""

    def test_normal_value(self) -> None:
        assert _extract_kb("12345 kB") == 12345

    def test_zero(self) -> None:
        assert _extract_kb("0 kB") == 0

    def test_no_unit(self) -> None:
        assert _extract_kb("12345") == 12345

    def test_empty(self) -> None:
        assert _extract_kb("") == 0

    def test_invalid(self) -> None:
        assert _extract_kb("abc kB") == 0
