"""Tests for the configuration module."""

import os
from pathlib import Path

import pytest
import yaml

from infraprobe.config import (
    InfraProbeConfig,
    TargetConfig,
    load_config,
    _apply_env_overrides,
)


class TestInfraProbeConfig:
    """Test configuration model validation."""

    def test_default_config(self) -> None:
        """Default config should be valid with no targets."""
        config = InfraProbeConfig()
        assert config.targets == []
        assert config.system.enabled is True
        assert config.metrics.port == 9100

    def test_unique_target_names(self) -> None:
        """Duplicate target names should fail validation."""
        with pytest.raises(ValueError, match="unique"):
            InfraProbeConfig(
                targets=[
                    TargetConfig(name="server", host="1.2.3.4"),
                    TargetConfig(name="server", host="5.6.7.8"),
                ]
            )


class TestLoadConfig:
    """Test loading configuration from YAML files."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Should load and parse a valid YAML config."""
        config_data = {
            "targets": [
                {
                    "name": "test",
                    "host": "127.0.0.1",
                    "checks": [{"type": "ping", "interval": 30, "timeout": 5, "count": 3}],
                }
            ],
            "metrics": {"enabled": True, "port": 9200, "bind": "0.0.0.0"},
        }
        config_file = tmp_path / "config.yml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(str(config_file))
        assert len(config.targets) == 1
        assert config.targets[0].name == "test"
        assert config.metrics.port == 9200

    def test_missing_file(self) -> None:
        """Should raise FileNotFoundError for missing config."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yml")

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty YAML file should produce default config."""
        config_file = tmp_path / "empty.yml"
        config_file.write_text("")
        config = load_config(str(config_file))
        assert config.targets == []


class TestEnvOverrides:
    """Test environment variable overrides."""

    def test_override_metrics_port(self) -> None:
        """INFRAPROBE_METRICS_PORT should override metrics.port."""
        os.environ["INFRAPROBE_METRICS_PORT"] = "9200"
        try:
            config = _apply_env_overrides({"metrics": {"port": 9100}})
            assert config["metrics"]["port"] == 9200
        finally:
            del os.environ["INFRAPROBE_METRICS_PORT"]

    def test_override_boolean(self) -> None:
        """Boolean env vars should be coerced correctly."""
        os.environ["INFRAPROBE_SYSTEM_ENABLED"] = "false"
        try:
            config = _apply_env_overrides({"system": {"enabled": True}})
            assert config["system"]["enabled"] is False
        finally:
            del os.environ["INFRAPROBE_SYSTEM_ENABLED"]

    def test_non_infraprobe_vars_ignored(self) -> None:
        """Env vars without INFRAPROBE_ prefix should be ignored."""
        config = {"metrics": {"port": 9100}}
        result = _apply_env_overrides(config)
        assert result["metrics"]["port"] == 9100
