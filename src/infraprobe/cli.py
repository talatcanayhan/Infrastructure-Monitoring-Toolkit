"""InfraProbe CLI — the main command-line interface.

Provides subcommands for network probing, system monitoring,
log analysis, and continuous monitoring with Prometheus metrics.
"""

import logging
from typing import Optional

import typer
from rich.console import Console

from infraprobe import __version__
from infraprobe.config import load_config
from infraprobe.logging_config import setup_logging

app = typer.Typer(
    name="infraprobe",
    help="Infrastructure monitoring toolkit — probe your network, systems, and services.",
    no_args_is_help=True,
)
console = Console()
logger = logging.getLogger("infraprobe")


# --- Global options callback ---


def version_callback(value: bool) -> None:
    if value:
        console.print(f"InfraProbe v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress all output except errors"),
    version: bool = typer.Option(
        False, "--version", "-V", callback=version_callback, is_eager=True, help="Show version"
    ),
) -> None:
    """InfraProbe — Infrastructure monitoring toolkit."""
    if verbose:
        setup_logging(level="DEBUG")
    elif quiet:
        setup_logging(level="ERROR")
    else:
        setup_logging(level="INFO")


# --- ping ---


@app.command()
def ping(
    target: str = typer.Argument(help="Hostname or IP address to ping"),
    count: int = typer.Option(4, "--count", "-c", help="Number of pings to send"),
    interval: float = typer.Option(1.0, "--interval", "-i", help="Seconds between pings"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Timeout per ping in seconds"),
    packet_size: int = typer.Option(56, "--size", "-s", help="Payload size in bytes"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Send ICMP echo requests using raw sockets."""
    from infraprobe.network.icmp import ping as icmp_ping
    from infraprobe.output.console import print_ping_results
    from infraprobe.output.json_output import print_json

    results = icmp_ping(
        target=target,
        count=count,
        interval=interval,
        timeout=timeout,
        packet_size=packet_size,
    )

    if output == "json":
        print_json(results)
    else:
        print_ping_results(results)


# --- scan ---


@app.command()
def scan(
    target: str = typer.Argument(help="Hostname or IP address to scan"),
    ports: str = typer.Option(
        "1-1024", "--ports", "-p", help="Port range (e.g., '1-1024' or '22,80,443')"
    ),
    timeout: float = typer.Option(3.0, "--timeout", "-t", help="Timeout per connection in seconds"),
    max_concurrent: int = typer.Option(100, "--concurrency", help="Max concurrent connections"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Scan TCP ports with async concurrency and banner grabbing."""
    from infraprobe.network.tcp import scan_ports, parse_port_range
    from infraprobe.output.console import print_scan_results
    from infraprobe.output.json_output import print_json

    port_list = parse_port_range(ports)
    results = scan_ports(
        host=target,
        ports=port_list,
        timeout=timeout,
        max_concurrent=max_concurrent,
    )

    if output == "json":
        print_json(results)
    else:
        print_scan_results(target, results)


# --- dns ---


@app.command()
def dns(
    domain: str = typer.Argument(help="Domain name to resolve"),
    record_type: str = typer.Option(
        "A", "--type", "-t", help="Record type: A, AAAA, CNAME, MX, NS, TXT, SOA"
    ),
    nameserver: Optional[str] = typer.Option(
        None, "--nameserver", "-n", help="Custom nameserver IP"
    ),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Resolve DNS records using raw UDP queries (RFC 1035)."""
    from infraprobe.network.dns_resolver import resolve
    from infraprobe.output.console import print_dns_results
    from infraprobe.output.json_output import print_json

    results = resolve(domain=domain, record_type=record_type, nameserver=nameserver)

    if output == "json":
        print_json(results)
    else:
        print_dns_results(results)


# --- http ---


@app.command()
def http(
    url: str = typer.Argument(help="URL to check"),
    check_tls: bool = typer.Option(True, "--check-tls/--no-tls", help="Validate TLS certificate"),
    follow_redirects: bool = typer.Option(
        True, "--follow-redirects/--no-follow", help="Follow HTTP redirects"
    ),
    expected_status: int = typer.Option(200, "--expected-status", help="Expected HTTP status code"),
    timeout: float = typer.Option(10.0, "--timeout", "-t", help="Request timeout in seconds"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Check HTTP/HTTPS endpoints with TLS certificate validation."""
    from infraprobe.network.http_checker import check_http
    from infraprobe.output.console import print_http_results
    from infraprobe.output.json_output import print_json

    results = check_http(
        url=url,
        expected_status=expected_status,
        timeout=timeout,
        check_tls=check_tls,
        follow_redirects=follow_redirects,
    )

    if output == "json":
        print_json(results)
    else:
        print_http_results(results)


# --- traceroute ---


@app.command()
def traceroute(
    target: str = typer.Argument(help="Hostname or IP address to trace"),
    max_hops: int = typer.Option(30, "--max-hops", "-m", help="Maximum number of hops"),
    timeout: float = typer.Option(3.0, "--timeout", "-t", help="Timeout per probe in seconds"),
    probes: int = typer.Option(3, "--probes", "-q", help="Number of probes per hop"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Trace the network path to a target using TTL-based ICMP probing."""
    from infraprobe.network.traceroute import traceroute as run_traceroute
    from infraprobe.output.console import print_traceroute_results
    from infraprobe.output.json_output import print_json

    results = run_traceroute(
        target=target,
        max_hops=max_hops,
        timeout=timeout,
        probes_per_hop=probes,
    )

    if output == "json":
        print_json(results)
    else:
        print_traceroute_results(target, results)


# --- system ---


@app.command()
def system(
    cpu: bool = typer.Option(True, "--cpu/--no-cpu", help="Collect CPU metrics"),
    memory: bool = typer.Option(True, "--memory/--no-memory", help="Collect memory metrics"),
    disk: bool = typer.Option(True, "--disk/--no-disk", help="Collect disk metrics"),
    processes: bool = typer.Option(False, "--processes", "-p", help="Show top processes"),
    sockets: bool = typer.Option(False, "--sockets", "-s", help="Show socket states"),
    top_n: int = typer.Option(10, "--top", help="Number of top processes to show"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Collect and display system metrics from /proc."""
    from infraprobe.system.cpu import get_cpu_metrics
    from infraprobe.system.memory import get_memory_metrics
    from infraprobe.system.disk import get_disk_metrics
    from infraprobe.system.process import get_top_processes
    from infraprobe.system.sockets import get_socket_stats
    from infraprobe.output.console import print_system_metrics
    from infraprobe.output.json_output import print_json

    metrics: dict[str, object] = {}
    if cpu:
        metrics["cpu"] = get_cpu_metrics()
    if memory:
        metrics["memory"] = get_memory_metrics()
    if disk:
        metrics["disk"] = get_disk_metrics()
    if processes:
        metrics["processes"] = get_top_processes(top_n=top_n)
    if sockets:
        metrics["sockets"] = get_socket_stats()

    if output == "json":
        print_json(metrics)
    else:
        print_system_metrics(metrics)


# --- logs ---


@app.command()
def logs(
    path: str = typer.Argument(help="Path to log file to analyze"),
    pattern: Optional[str] = typer.Option(None, "--pattern", "-p", help="Regex pattern to filter"),
    log_format: str = typer.Option(
        "auto", "--format", "-f", help="Log format: auto, syslog, nginx, apache"
    ),
    tail: int = typer.Option(0, "--tail", "-n", help="Only analyze last N lines (0 = all)"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json"),
) -> None:
    """Parse and analyze log files for errors and patterns."""
    from infraprobe.logging_analysis.parser import parse_log_file
    from infraprobe.logging_analysis.analyzer import analyze_entries
    from infraprobe.output.console import print_log_analysis
    from infraprobe.output.json_output import print_json

    entries = parse_log_file(path=path, log_format=log_format, tail=tail)
    results = analyze_entries(entries=entries, pattern=pattern)

    if output == "json":
        print_json(results)
    else:
        print_log_analysis(results)


# --- monitor ---


@app.command()
def monitor(
    config_file: str = typer.Argument(help="Path to configuration YAML file"),
    live: bool = typer.Option(False, "--live", "-l", help="Enable live dashboard mode"),
) -> None:
    """Run continuous monitoring based on a YAML configuration file."""
    from infraprobe.metrics.collector import run_collector

    config = load_config(config_file)
    console.print(f"[bold green]Starting InfraProbe monitor[/] with config: {config_file}")
    console.print(f"  Targets: {len(config.targets)}")
    console.print(f"  System metrics: {'enabled' if config.system.enabled else 'disabled'}")
    console.print(f"  Prometheus metrics: {'enabled' if config.metrics.enabled else 'disabled'}")

    run_collector(config=config, live=live)


# --- serve ---


@app.command()
def serve(
    port: int = typer.Option(9100, "--port", "-p", help="Port to listen on"),
    bind: str = typer.Option("0.0.0.0", "--bind", "-b", help="Address to bind to"),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Configuration file for targets"
    ),
) -> None:
    """Start the Prometheus metrics HTTP server."""
    from infraprobe.metrics.prometheus_exporter import start_metrics_server

    config = None
    if config_file:
        config = load_config(config_file)

    console.print(f"[bold green]Starting metrics server[/] on {bind}:{port}")
    console.print(f"  Endpoint: http://{bind}:{port}/metrics")
    start_metrics_server(port=port, bind=bind, config=config)


# --- report ---


@app.command()
def report(
    config_file: str = typer.Argument(help="Path to configuration YAML file"),
    output_format: str = typer.Option(
        "html", "--format", "-f", help="Report format: html, json, md"
    ),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Generate a monitoring report from a one-time scan."""
    from infraprobe.output.report import generate_report

    config = load_config(config_file)
    result_path = generate_report(
        config=config, output_format=output_format, output_file=output_file
    )
    console.print(f"[bold green]Report generated:[/] {result_path}")


if __name__ == "__main__":
    app()
