"""Tests for the alerting rule engine."""

from infraprobe.alerting.rules import AlertEngine, _parse_duration


class TestParseDuration:
    """Test duration string parsing."""

    def test_seconds(self) -> None:
        assert _parse_duration("30s") == 30.0

    def test_minutes(self) -> None:
        assert _parse_duration("5m") == 300.0

    def test_hours(self) -> None:
        assert _parse_duration("1h") == 3600.0

    def test_invalid(self) -> None:
        assert _parse_duration("invalid") == 0.0


class TestAlertEngine:
    """Test alert rule evaluation."""

    def _make_engine(self, condition: str = "> 100", duration: str = "0s") -> AlertEngine:
        rules = [
            {
                "name": "test-rule",
                "metric": "latency",
                "condition": condition,
                "duration": duration,
                "severity": "warning",
                "notify": ["webhook"],
            }
        ]
        return AlertEngine(rules)

    def test_fires_on_threshold_breach(self) -> None:
        engine = self._make_engine("> 100", "0s")
        alerts = engine.evaluate("latency", 150.0)
        assert len(alerts) == 1
        assert alerts[0].rule_name == "test-rule"
        assert alerts[0].current_value == 150.0

    def test_no_fire_below_threshold(self) -> None:
        engine = self._make_engine("> 100", "0s")
        alerts = engine.evaluate("latency", 50.0)
        assert len(alerts) == 0

    def test_wrong_metric_ignored(self) -> None:
        engine = self._make_engine("> 100", "0s")
        alerts = engine.evaluate("other_metric", 999.0)
        assert len(alerts) == 0

    def test_less_than_condition(self) -> None:
        engine = self._make_engine("< 50", "0s")
        alerts = engine.evaluate("latency", 30.0)
        assert len(alerts) == 1

    def test_does_not_fire_twice(self) -> None:
        engine = self._make_engine("> 100", "0s")
        alerts1 = engine.evaluate("latency", 150.0)
        alerts2 = engine.evaluate("latency", 160.0)
        assert len(alerts1) == 1
        assert len(alerts2) == 0  # Already firing

    def test_resolves_and_refires(self) -> None:
        engine = self._make_engine("> 100", "0s")
        engine.evaluate("latency", 150.0)  # Fire
        engine.evaluate("latency", 50.0)  # Resolve
        alerts = engine.evaluate("latency", 200.0)  # Re-fire
        assert len(alerts) == 1

    def test_active_alerts(self) -> None:
        engine = self._make_engine("> 100", "0s")
        engine.evaluate("latency", 150.0)
        assert len(engine.active_alerts) == 1
