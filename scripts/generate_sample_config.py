#!/usr/bin/env python3
"""Generate a sample InfraProbe configuration file."""

import yaml


def generate() -> dict:
    return {
        "targets": [
            {
                "name": "google-dns",
                "host": "8.8.8.8",
                "checks": [
                    {"type": "ping", "interval": 30, "timeout": 5, "count": 3},
                    {"type": "dns", "domain": "example.com", "record_type": "A", "interval": 60},
                ],
            },
            {
                "name": "example-website",
                "host": "93.184.216.34",
                "checks": [
                    {
                        "type": "http",
                        "url": "https://example.com",
                        "expected_status": 200,
                        "check_tls": True,
                        "interval": 60,
                        "timeout": 10,
                    },
                    {"type": "tcp", "ports": [80, 443], "interval": 120, "timeout": 5},
                ],
            },
        ],
        "system": {
            "enabled": True,
            "collect_cpu": True,
            "collect_memory": True,
            "collect_disk": True,
            "collect_processes": False,
            "collect_sockets": False,
            "disk_paths": ["/"],
            "interval": 15,
        },
        "metrics": {"enabled": True, "port": 9100, "bind": "0.0.0.0"},
        "logging": {"level": "INFO", "format": "json", "file": None},
        "alerting": {
            "rules": [
                {
                    "name": "high-latency",
                    "metric": "ping_rtt_ms",
                    "condition": "> 100",
                    "duration": "5m",
                    "severity": "warning",
                    "notify": ["webhook"],
                }
            ],
            "notifiers": {
                "webhook": {
                    "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
                    "timeout": 10,
                }
            },
        },
    }


if __name__ == "__main__":
    config = generate()
    print(yaml.dump(config, default_flow_style=False, sort_keys=False))
