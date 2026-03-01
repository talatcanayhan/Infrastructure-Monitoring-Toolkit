"""Configuration management for InfraProbe.

Loads configuration from YAML files with environment variable overrides.
Uses Pydantic for validation and type safety.
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

# --- Check models ---


class PingCheck(BaseModel):
    """Configuration for an ICMP ping check."""

    type: str = "ping"
    interval: int = Field(default=30, ge=1, description="Check interval in seconds")
    timeout: float = Field(default=5.0, gt=0, description="Timeout in seconds")
    count: int = Field(default=3, ge=1, description="Number of pings per check")


class HTTPCheck(BaseModel):
    """Configuration for an HTTP/HTTPS health check."""

    type: str = "http"
    url: str
    expected_status: int = Field(default=200, ge=100, le=599)
    check_tls: bool = Field(default=True, description="Validate TLS certificate")
    follow_redirects: bool = True
    interval: int = Field(default=60, ge=1)
    timeout: float = Field(default=10.0, gt=0)


class TCPCheck(BaseModel):
    """Configuration for a TCP port scan check."""

    type: str = "tcp"
    ports: list[int] = Field(default_factory=lambda: [22, 80, 443])
    interval: int = Field(default=120, ge=1)
    timeout: float = Field(default=5.0, gt=0)


class DNSCheck(BaseModel):
    """Configuration for a DNS resolution check."""

    type: str = "dns"
    domain: str = "example.com"
    record_type: str = Field(default="A", pattern=r"^(A|AAAA|CNAME|MX|NS|TXT|SOA)$")
    nameserver: Optional[str] = None
    interval: int = Field(default=60, ge=1)


# --- Target model ---


class TargetConfig(BaseModel):
    """Configuration for a monitoring target."""

    name: str
    host: str
    checks: list[dict[str, Any]] = Field(default_factory=list)

    def get_typed_checks(self) -> list[PingCheck | HTTPCheck | TCPCheck | DNSCheck]:
        """Parse raw check dicts into typed check models."""
        typed: list[PingCheck | HTTPCheck | TCPCheck | DNSCheck] = []
        type_map = {
            "ping": PingCheck,
            "http": HTTPCheck,
            "tcp": TCPCheck,
            "dns": DNSCheck,
        }
        for check in self.checks:
            check_type = check.get("type", "")
            model = type_map.get(check_type)
            if model:
                typed.append(model(**check))
        return typed


# --- System config ---


class SystemConfig(BaseModel):
    """Configuration for system metric collection."""

    enabled: bool = True
    collect_cpu: bool = True
    collect_memory: bool = True
    collect_disk: bool = True
    collect_processes: bool = True
    collect_sockets: bool = True
    disk_paths: list[str] = Field(default_factory=lambda: ["/"])
    interval: int = Field(default=15, ge=1)


# --- Logging config ---


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = Field(default="text", pattern=r"^(json|text)$")
    file: Optional[str] = None


# --- Alerting config ---


class AlertRule(BaseModel):
    """A single alerting rule definition."""

    name: str
    metric: str
    condition: str = Field(description="Comparison expression like '> 100' or '< 50'")
    duration: str = Field(default="5m", pattern=r"^\d+[smh]$")
    severity: str = Field(default="warning", pattern=r"^(info|warning|critical)$")
    notify: list[str] = Field(default_factory=lambda: ["webhook"])


class WebhookNotifier(BaseModel):
    """Webhook notifier configuration."""

    url: str
    timeout: int = Field(default=10, ge=1)


class AlertingConfig(BaseModel):
    """Configuration for the alerting system."""

    rules: list[AlertRule] = Field(default_factory=list)
    notifiers: dict[str, Any] = Field(default_factory=dict)


# --- Metrics config ---


class MetricsConfig(BaseModel):
    """Configuration for the Prometheus metrics server."""

    enabled: bool = True
    port: int = Field(default=9100, ge=1, le=65535)
    bind: str = "0.0.0.0"


# --- Root config ---


class InfraProbeConfig(BaseModel):
    """Root configuration model for InfraProbe."""

    targets: list[TargetConfig] = Field(default_factory=list)
    system: SystemConfig = Field(default_factory=SystemConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    @field_validator("targets")
    @classmethod
    def validate_unique_target_names(cls, v: list[TargetConfig]) -> list[TargetConfig]:
        names = [t.name for t in v]
        if len(names) != len(set(names)):
            raise ValueError("Target names must be unique")
        return v


def load_config(config_path: str | Path) -> InfraProbeConfig:
    """Load and validate configuration from a YAML file.

    Environment variables can override config values using the prefix INFRAPROBE_.
    For example: INFRAPROBE_METRICS_PORT=9200 overrides metrics.port.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated InfraProbeConfig instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
        pydantic.ValidationError: If the config fails validation.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r") as f:
        raw_config = yaml.safe_load(f) or {}

    raw_config = _apply_env_overrides(raw_config)
    return InfraProbeConfig(**raw_config)


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides to config.

    Supports flat env vars like INFRAPROBE_METRICS_PORT=9200
    which maps to config["metrics"]["port"] = 9200.
    """
    prefix = "INFRAPROBE_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].lower().split("_")
        target = config
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]

        final_key = parts[-1]
        # Attempt type coercion
        if value.lower() in ("true", "false"):
            target[final_key] = value.lower() == "true"
        elif value.isdigit():
            target[final_key] = int(value)
        else:
            target[final_key] = value

    return config
