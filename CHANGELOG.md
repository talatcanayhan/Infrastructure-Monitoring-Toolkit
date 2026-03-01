# Changelog

All notable changes to InfraProbe will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-22

### Added
- Raw ICMP ping implementation with RTT statistics
- Async TCP port scanner with banner grabbing
- DNS resolver with raw query construction (RFC 1035)
- HTTP/HTTPS health checker with TLS certificate validation
- TTL-based traceroute implementation
- System monitoring (CPU, memory, disk, processes, sockets) via /proc
- Log file parsing and analysis (syslog, nginx, apache formats)
- Prometheus metrics exporter on /metrics endpoint
- Threshold-based alerting with webhook notifications
- Rich terminal output with color-coded status tables
- JSON output mode for all commands
- HTML/Markdown report generation
- Multi-stage Docker build with security hardening
- Docker Compose stack (InfraProbe + Prometheus + Grafana)
- GitHub Actions CI/CD pipeline (lint, test, security scan, build)
- Kubernetes manifests and Helm chart
- Terraform modules for infrastructure provisioning
- Ansible roles for automated deployment
- Grafana dashboards (overview, network, system)
- Prometheus alerting rules
- systemd service and timer units
- Load testing with Locust
