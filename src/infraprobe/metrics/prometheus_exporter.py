"""Prometheus metrics exporter for InfraProbe.

Exposes all collected metrics on an HTTP /metrics endpoint using
the official prometheus_client library. Supports Gauge, Counter,
and Histogram metric types following Prometheus naming conventions.

Metrics are prefixed with 'infraprobe_' and use labels for targets.

References:
    - https://prometheus.io/docs/practices/naming/
    - https://prometheus.io/docs/concepts/metric_types/
"""

import logging
import signal
import threading
from typing import Any, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

logger = logging.getLogger("infraprobe.metrics.prometheus")

# --- Network metrics ---

ping_rtt = Histogram(
    "infraprobe_ping_rtt_seconds",
    "ICMP ping round-trip time in seconds",
    ["target"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

ping_packet_loss = Gauge(
    "infraprobe_ping_packet_loss_ratio",
    "ICMP ping packet loss ratio (0.0 to 1.0)",
    ["target"],
)

ping_success = Gauge(
    "infraprobe_ping_success",
    "Whether the last ping was successful (1=yes, 0=no)",
    ["target"],
)

dns_resolution_time = Histogram(
    "infraprobe_dns_resolution_seconds",
    "DNS resolution time in seconds",
    ["domain", "record_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

http_response_time = Histogram(
    "infraprobe_http_response_seconds",
    "HTTP response time in seconds",
    ["url", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_status_code = Gauge(
    "infraprobe_http_status_code",
    "HTTP response status code",
    ["url"],
)

http_success = Gauge(
    "infraprobe_http_success",
    "Whether the HTTP check was successful (1=yes, 0=no)",
    ["url"],
)

tls_days_until_expiry = Gauge(
    "infraprobe_tls_days_until_expiry",
    "Days until TLS certificate expires",
    ["hostname"],
)

port_open = Gauge(
    "infraprobe_port_open",
    "Whether a TCP port is open (1=open, 0=closed)",
    ["target", "port"],
)

# --- System metrics ---

cpu_usage = Gauge(
    "infraprobe_cpu_usage_percent",
    "CPU usage percentage",
    ["mode"],
)

memory_usage_bytes = Gauge(
    "infraprobe_memory_usage_bytes",
    "Memory usage in bytes",
    ["type"],
)

memory_usage_percent = Gauge(
    "infraprobe_memory_usage_percent",
    "Memory usage percentage",
)

disk_usage_percent = Gauge(
    "infraprobe_disk_usage_percent",
    "Disk usage percentage",
    ["mountpoint"],
)

disk_usage_bytes = Gauge(
    "infraprobe_disk_usage_bytes",
    "Disk usage in bytes",
    ["mountpoint", "type"],
)

# --- Operational metrics ---

checks_total = Counter(
    "infraprobe_checks_total",
    "Total number of checks performed",
    ["check_type", "target"],
)

checks_failed_total = Counter(
    "infraprobe_checks_failed_total",
    "Total number of failed checks",
    ["check_type", "target"],
)

collection_duration = Histogram(
    "infraprobe_collection_duration_seconds",
    "Time spent collecting metrics",
    ["collector"],
)


def update_ping_metrics(target: str, stats: Any) -> None:
    """Update Prometheus metrics from ping results."""
    if stats.packets_received > 0:
        for result in stats.results:
            if result.success and result.rtt_ms is not None:
                ping_rtt.labels(target=target).observe(result.rtt_ms / 1000)
        ping_success.labels(target=target).set(1)
    else:
        ping_success.labels(target=target).set(0)

    ping_packet_loss.labels(target=target).set(
        stats.packet_loss_percent / 100 if stats.packets_sent > 0 else 1.0
    )
    checks_total.labels(check_type="ping", target=target).inc()
    if stats.packet_loss_percent >= 100:
        checks_failed_total.labels(check_type="ping", target=target).inc()


def update_http_metrics(url: str, result: Any) -> None:
    """Update Prometheus metrics from HTTP check results."""
    if result.response_time_ms > 0:
        http_response_time.labels(url=url, method="GET").observe(result.response_time_ms / 1000)
    http_status_code.labels(url=url).set(result.status_code)
    http_success.labels(url=url).set(1 if result.success else 0)

    if result.tls_info and result.tls_info.days_until_expiry:
        from urllib.parse import urlparse

        hostname = urlparse(url).hostname or url
        tls_days_until_expiry.labels(hostname=hostname).set(result.tls_info.days_until_expiry)

    checks_total.labels(check_type="http", target=url).inc()
    if not result.success:
        checks_failed_total.labels(check_type="http", target=url).inc()


def update_dns_metrics(domain: str, record_type: str, result: Any) -> None:
    """Update Prometheus metrics from DNS resolution results."""
    if result.query_time_ms > 0:
        dns_resolution_time.labels(domain=domain, record_type=record_type).observe(
            result.query_time_ms / 1000
        )
    checks_total.labels(check_type="dns", target=domain).inc()
    if result.error:
        checks_failed_total.labels(check_type="dns", target=domain).inc()


def update_system_metrics(metrics: dict[str, Any]) -> None:
    """Update Prometheus metrics from system metric collection."""
    if "cpu" in metrics:
        cpu = metrics["cpu"]
        cpu_usage.labels(mode="user").set(cpu.user_percent)
        cpu_usage.labels(mode="system").set(cpu.system_percent)
        cpu_usage.labels(mode="idle").set(cpu.idle_percent)
        cpu_usage.labels(mode="iowait").set(cpu.iowait_percent)
        cpu_usage.labels(mode="total").set(cpu.total_percent)

    if "memory" in metrics:
        mem = metrics["memory"]
        memory_usage_bytes.labels(type="total").set(mem.total_mb * 1024 * 1024)
        memory_usage_bytes.labels(type="used").set(mem.used_mb * 1024 * 1024)
        memory_usage_bytes.labels(type="available").set(mem.available_mb * 1024 * 1024)
        memory_usage_bytes.labels(type="cached").set(mem.cached_mb * 1024 * 1024)
        memory_usage_percent.set(mem.used_percent)

    if "disk" in metrics:
        for disk in metrics["disk"]:
            disk_usage_percent.labels(mountpoint=disk.mountpoint).set(disk.used_percent)
            disk_usage_bytes.labels(mountpoint=disk.mountpoint, type="total").set(
                disk.total_gb * 1024 * 1024 * 1024
            )
            disk_usage_bytes.labels(mountpoint=disk.mountpoint, type="used").set(
                disk.used_gb * 1024 * 1024 * 1024
            )


def start_metrics_server(
    port: int = 9100,
    bind: str = "0.0.0.0",
    config: Optional[Any] = None,
) -> None:
    """Start the Prometheus metrics HTTP server.

    Runs an HTTP server that serves metrics in Prometheus text format
    on the /metrics endpoint. Blocks forever (intended to be the main loop).

    Args:
        port: Port to listen on.
        bind: Address to bind to.
        config: Optional InfraProbeConfig for continuous collection.
    """
    start_http_server(port, addr=bind)
    logger.info("Prometheus metrics server started on %s:%d", bind, port)

    # If config provided, start the collector loop
    if config:
        from infraprobe.metrics.collector import run_collector

        run_collector(config=config, live=False)
    else:
        # Just serve metrics, block forever
        shutdown_event = threading.Event()

        def _signal_handler(signum: int, frame: Any) -> None:
            logger.info("Received signal %d, shutting down", signum)
            shutdown_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        shutdown_event.wait()
