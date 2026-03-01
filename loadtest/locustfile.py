"""Load testing for InfraProbe metrics endpoint.

Uses Locust to simulate Prometheus scraping the /metrics endpoint
at high frequency to identify performance bottlenecks.

Usage:
    pip install locust
    locust -f loadtest/locustfile.py --host http://localhost:9100
"""

from locust import HttpUser, between, task


class PrometheusScraperUser(HttpUser):
    """Simulates Prometheus scraping the InfraProbe /metrics endpoint."""

    wait_time = between(1, 3)

    @task(10)
    def scrape_metrics(self) -> None:
        """Scrape the Prometheus metrics endpoint.

        This is the primary load pattern — Prometheus scrapes /metrics
        every 10-15 seconds per target. We weight this heavily.
        """
        self.client.get(
            "/metrics",
            headers={"Accept": "text/plain"},
            name="/metrics",
        )

    @task(1)
    def health_check(self) -> None:
        """Hit the health endpoint (lightweight check)."""
        self.client.get(
            "/metrics",
            headers={"Accept": "text/plain"},
            name="/health",
        )
