"""Metric collection scheduler for continuous monitoring.

Runs periodic checks against configured targets and updates
Prometheus metrics. Each check type runs on its own interval.
"""

import logging
import signal
import threading
import time
from typing import Any

logger = logging.getLogger("infraprobe.metrics.collector")


class MetricCollector:
    """Schedules and runs periodic metric collection."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        """Start all collection loops in background threads."""
        # Collect target checks
        for target in self.config.targets:
            for check in target.get_typed_checks():
                thread = threading.Thread(
                    target=self._check_loop,
                    args=(target, check),
                    daemon=True,
                    name=f"check-{target.name}-{check.type}",
                )
                self._threads.append(thread)
                thread.start()

        # Collect system metrics
        if self.config.system.enabled:
            thread = threading.Thread(
                target=self._system_loop,
                daemon=True,
                name="system-collector",
            )
            self._threads.append(thread)
            thread.start()

        logger.info(
            "Started %d collection threads (%d targets, system=%s)",
            len(self._threads),
            len(self.config.targets),
            self.config.system.enabled,
        )

    def stop(self) -> None:
        """Signal all collection threads to stop."""
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=5)
        logger.info("All collectors stopped")

    def _check_loop(self, target: Any, check: Any) -> None:
        """Run a single check on an interval."""
        from infraprobe.metrics.prometheus_exporter import (
            update_ping_metrics,
            update_http_metrics,
            update_dns_metrics,
            collection_duration,
            port_open as port_open_gauge,
            checks_total,
        )

        interval = getattr(check, "interval", 60)
        check_type = check.type
        logger.info("Starting %s check for %s (interval=%ds)", check_type, target.name, interval)

        while not self._stop_event.is_set():
            try:
                start = time.perf_counter()

                if check_type == "ping":
                    from infraprobe.network.icmp import ping

                    stats = ping(target=target.host, count=check.count, timeout=check.timeout)
                    update_ping_metrics(target.host, stats)

                elif check_type == "http":
                    from infraprobe.network.http_checker import check_http

                    result = check_http(
                        url=check.url,
                        expected_status=check.expected_status,
                        timeout=check.timeout,
                        check_tls=check.check_tls,
                    )
                    update_http_metrics(check.url, result)

                elif check_type == "tcp":
                    from infraprobe.network.tcp import scan_ports

                    results = scan_ports(
                        host=target.host,
                        ports=check.ports,
                        timeout=check.timeout,
                    )
                    for r in results:
                        port_open_gauge.labels(target=target.host, port=str(r.port)).set(
                            1 if r.state == "open" else 0
                        )
                    checks_total.labels(check_type="tcp", target=target.host).inc()

                elif check_type == "dns":
                    from infraprobe.network.dns_resolver import resolve

                    dns_result = resolve(
                        domain=check.domain,
                        record_type=check.record_type,
                        nameserver=getattr(check, "nameserver", None),
                    )
                    update_dns_metrics(check.domain, check.record_type, dns_result)

                elapsed = time.perf_counter() - start
                collection_duration.labels(collector=f"{check_type}-{target.name}").observe(elapsed)

            except Exception as e:
                logger.error("Check %s for %s failed: %s", check_type, target.name, e)

            self._stop_event.wait(timeout=interval)

    def _system_loop(self) -> None:
        """Collect system metrics on an interval."""
        from infraprobe.metrics.prometheus_exporter import (
            update_system_metrics,
            collection_duration,
        )

        interval = self.config.system.interval

        while not self._stop_event.is_set():
            try:
                start = time.perf_counter()
                metrics: dict[str, Any] = {}

                if self.config.system.collect_cpu:
                    from infraprobe.system.cpu import get_cpu_metrics

                    metrics["cpu"] = get_cpu_metrics(sample_interval=0.5)

                if self.config.system.collect_memory:
                    from infraprobe.system.memory import get_memory_metrics

                    metrics["memory"] = get_memory_metrics()

                if self.config.system.collect_disk:
                    from infraprobe.system.disk import get_disk_metrics

                    metrics["disk"] = get_disk_metrics(paths=self.config.system.disk_paths)

                update_system_metrics(metrics)
                elapsed = time.perf_counter() - start
                collection_duration.labels(collector="system").observe(elapsed)

            except Exception as e:
                logger.error("System metric collection failed: %s", e)

            self._stop_event.wait(timeout=interval)


def run_collector(config: Any, live: bool = False) -> None:
    """Run the metric collector until interrupted.

    Args:
        config: InfraProbeConfig instance.
        live: Whether to show a live dashboard (future feature).
    """
    collector = MetricCollector(config)
    collector.start()

    # Block until SIGINT or SIGTERM
    shutdown_event = threading.Event()

    def _handle_signal(signum: int, frame: Any) -> None:
        logger.info("Received signal %d, stopping collector", signum)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        shutdown_event.wait()
    finally:
        collector.stop()
