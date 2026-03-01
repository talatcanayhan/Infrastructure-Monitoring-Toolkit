"""Shared test fixtures for InfraProbe."""

import pytest


@pytest.fixture
def sample_config() -> dict:
    """Return a minimal valid configuration dict for testing."""
    return {
        "targets": [
            {
                "name": "test-server",
                "host": "127.0.0.1",
                "checks": [
                    {
                        "type": "ping",
                        "interval": 30,
                        "timeout": 5,
                        "count": 3,
                    }
                ],
            }
        ],
        "system": {
            "enabled": False,
            "collect_cpu": True,
            "collect_memory": True,
            "collect_disk": False,
            "collect_processes": False,
            "collect_sockets": False,
            "disk_paths": ["/"],
            "interval": 15,
        },
        "metrics": {
            "enabled": False,
            "port": 9100,
            "bind": "127.0.0.1",
        },
        "logging": {
            "level": "DEBUG",
            "format": "text",
            "file": None,
        },
        "alerting": {
            "rules": [],
            "notifiers": {},
        },
    }


@pytest.fixture
def mock_proc_stat() -> str:
    """Return sample /proc/stat content."""
    return (
        "cpu  10132153 290696 3084719 46828483 16683 0 25195 0 0 0\n"
        "cpu0 1393280 32966 572056 13343292 6130 0 17875 0 0 0\n"
    )


@pytest.fixture
def mock_proc_meminfo() -> str:
    """Return sample /proc/meminfo content."""
    return (
        "MemTotal:       16384000 kB\n"
        "MemFree:         2048000 kB\n"
        "MemAvailable:    8192000 kB\n"
        "Buffers:          512000 kB\n"
        "Cached:          4096000 kB\n"
        "SwapTotal:       2048000 kB\n"
        "SwapFree:        2048000 kB\n"
    )
