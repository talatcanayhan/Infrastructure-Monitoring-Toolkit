"""Threshold-based alerting rule engine.

Evaluates metrics against configurable alert rules with support for:
- Comparison operators (>, <, >=, <=, ==, !=)
- Duration requirements (alert must be true for N minutes)
- Severity levels (info, warning, critical)
"""

import logging
import operator
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("infraprobe.alerting.rules")

# Supported comparison operators
OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

# Parse condition string like "> 100" or "< 50"
CONDITION_PATTERN = re.compile(r"^\s*(>=|<=|!=|>|<|==)\s*(-?\d+(?:\.\d+)?)\s*$")

# Parse duration string like "5m", "1h", "30s"
DURATION_PATTERN = re.compile(r"^(\d+)([smh])$")
DURATION_MULTIPLIERS = {"s": 1, "m": 60, "h": 3600}


@dataclass
class Alert:
    """A triggered alert."""

    rule_name: str
    metric: str
    current_value: float
    threshold: float
    condition: str
    severity: str
    message: str
    fired_at: float = field(default_factory=time.time)
    resolved: bool = False


@dataclass
class RuleState:
    """Internal state tracking for a rule."""

    first_triggered: Optional[float] = None
    is_firing: bool = False
    last_value: float = 0.0


class AlertEngine:
    """Evaluates alert rules against metric values."""

    def __init__(self, rules: list[dict[str, Any]]) -> None:
        self.rules = rules
        self._state: dict[str, RuleState] = {}
        self._alerts: list[Alert] = []

        # Initialize state for each rule
        for rule in rules:
            self._state[rule["name"]] = RuleState()

    def evaluate(self, metric_name: str, value: float) -> list[Alert]:
        """Evaluate all rules against a metric value.

        Args:
            metric_name: Name of the metric being checked.
            value: Current metric value.

        Returns:
            List of newly fired Alert objects.
        """
        new_alerts: list[Alert] = []

        for rule in self.rules:
            if rule["metric"] != metric_name:
                continue

            rule_name = rule["name"]
            state = self._state[rule_name]
            state.last_value = value

            # Parse condition
            condition_str = rule.get("condition", "> 0")
            match = CONDITION_PATTERN.match(condition_str)
            if not match:
                logger.warning("Invalid condition '%s' in rule '%s'", condition_str, rule_name)
                continue

            op_str = match.group(1)
            threshold = float(match.group(2))
            compare_fn = OPERATORS.get(op_str)
            if not compare_fn:
                continue

            # Check if condition is met
            condition_met = compare_fn(value, threshold)

            if condition_met:
                now = time.time()
                if state.first_triggered is None:
                    state.first_triggered = now

                # Check duration requirement
                duration_str = rule.get("duration", "0s")
                required_duration = _parse_duration(duration_str)
                elapsed = now - state.first_triggered

                if elapsed >= required_duration and not state.is_firing:
                    # Alert fires!
                    state.is_firing = True
                    alert = Alert(
                        rule_name=rule_name,
                        metric=metric_name,
                        current_value=value,
                        threshold=threshold,
                        condition=condition_str,
                        severity=rule.get("severity", "warning"),
                        message=(
                            f"[{rule.get('severity', 'warning').upper()}] "
                            f"{rule_name}: {metric_name} is {value} "
                            f"(threshold: {condition_str})"
                        ),
                    )
                    new_alerts.append(alert)
                    self._alerts.append(alert)
                    logger.warning("Alert fired: %s", alert.message)
            else:
                # Condition no longer met — resolve
                if state.is_firing:
                    state.is_firing = False
                    logger.info("Alert resolved: %s", rule_name)
                state.first_triggered = None

        return new_alerts

    @property
    def active_alerts(self) -> list[Alert]:
        """Return currently firing (unresolved) alerts."""
        return [a for a in self._alerts if not a.resolved]


def _parse_duration(duration_str: str) -> float:
    """Parse a duration string into seconds.

    Args:
        duration_str: Duration like "5m", "1h", "30s".

    Returns:
        Duration in seconds.
    """
    match = DURATION_PATTERN.match(duration_str)
    if not match:
        return 0.0

    value = int(match.group(1))
    unit = match.group(2)
    return float(value * DURATION_MULTIPLIERS.get(unit, 1))
