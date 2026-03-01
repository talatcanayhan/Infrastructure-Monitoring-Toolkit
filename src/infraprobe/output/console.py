"""Rich terminal output for InfraProbe.

Provides formatted, color-coded terminal output using the Rich library.
Each function handles a specific output type (ping, scan, dns, etc.).
"""

from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def _status_color(success: bool) -> str:
    return "green" if success else "red"


# --- Ping output ---


def print_ping_results(stats: Any) -> None:
    """Print ping session results with color-coded RTT values."""
    console.print(
        f"\n[bold]PING[/bold] {stats.target} ({stats.resolved_ip})"
    )

    for r in stats.results:
        if r.success:
            color = "green" if (r.rtt_ms or 0) < 50 else "yellow" if (r.rtt_ms or 0) < 100 else "red"
            console.print(
                f"  Reply from {stats.resolved_ip}: "
                f"bytes={r.packet_size} seq={r.sequence} ttl={r.ttl} "
                f"time=[{color}]{r.rtt_ms:.3f}ms[/{color}]"
            )
        else:
            console.print(f"  [red]Seq {r.sequence}: {r.error}[/red]")

    console.print(f"\n--- {stats.target} ping statistics ---")
    loss_color = "green" if stats.packet_loss_percent == 0 else "yellow" if stats.packet_loss_percent < 50 else "red"
    console.print(
        f"{stats.packets_sent} packets transmitted, {stats.packets_received} received, "
        f"[{loss_color}]{stats.packet_loss_percent}% packet loss[/{loss_color}]"
    )

    if stats.packets_received > 0:
        console.print(
            f"rtt min/avg/max/stddev = "
            f"{stats.min_rtt_ms:.3f}/{stats.avg_rtt_ms:.3f}/"
            f"{stats.max_rtt_ms:.3f}/{stats.stddev_rtt_ms:.3f} ms"
        )
    console.print()


# --- Scan output ---


def print_scan_results(target: str, results: Any) -> None:
    """Print port scan results as a Rich table."""
    table = Table(title=f"Port Scan: {target}")
    table.add_column("Port", style="cyan", justify="right")
    table.add_column("State", justify="center")
    table.add_column("Service", style="dim")
    table.add_column("Latency", justify="right")
    table.add_column("Banner", style="dim", max_width=50)

    open_count = 0
    for r in results:
        if r.state == "open":
            open_count += 1
            state_text = Text("OPEN", style="bold green")
        elif r.state == "closed":
            state_text = Text("CLOSED", style="dim red")
        else:
            state_text = Text(r.state.upper(), style="yellow")

        # Only show open ports by default
        if r.state == "open":
            table.add_row(
                str(r.port),
                state_text,
                r.service or "",
                f"{r.latency_ms:.1f}ms" if r.latency_ms else "-",
                r.banner[:50] if r.banner else "",
            )

    console.print()
    console.print(table)
    closed_count = len(results) - open_count
    console.print(f"\n{open_count} open, {closed_count} closed/filtered out of {len(results)} scanned")
    console.print()


# --- DNS output ---


def print_dns_results(results: Any) -> None:
    """Print DNS resolution results."""
    console.print(f"\n[bold]DNS Resolution:[/bold] {results.domain}")
    console.print(f"  Nameserver: {results.nameserver}")
    console.print(f"  Query time: {results.query_time_ms:.1f}ms")

    if results.records:
        table = Table()
        table.add_column("Type", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("TTL", style="dim", justify="right")

        for record in results.records:
            table.add_row(record.record_type, record.value, str(record.ttl) if record.ttl else "-")

        console.print(table)
    else:
        console.print("  [yellow]No records found[/yellow]")

    if results.error:
        console.print(f"  [red]Error: {results.error}[/red]")
    console.print()


# --- HTTP output ---


def print_http_results(results: Any) -> None:
    """Print HTTP health check results."""
    status_color = "green" if results.success else "red"
    console.print(f"\n[bold]HTTP Check:[/bold] {results.url}")
    console.print(
        f"  Status: [{status_color}]{results.status_code}[/{status_color}] "
        f"({results.reason})"
    )
    console.print(f"  Response time: {results.response_time_ms:.1f}ms")
    console.print(f"  Content length: {results.content_length} bytes")

    if results.tls_info:
        tls = results.tls_info
        expiry_color = "green" if tls.days_until_expiry > 30 else "yellow" if tls.days_until_expiry > 7 else "red"
        console.print(f"\n  [bold]TLS Certificate:[/bold]")
        console.print(f"    Subject: {tls.subject}")
        console.print(f"    Issuer: {tls.issuer}")
        console.print(f"    Valid: {tls.not_before} to {tls.not_after}")
        console.print(f"    Expires in: [{expiry_color}]{tls.days_until_expiry} days[/{expiry_color}]")
        console.print(f"    Protocol: {tls.protocol_version}")
        console.print(f"    SANs: {', '.join(tls.san[:5])}")

    if results.error:
        console.print(f"  [red]Error: {results.error}[/red]")
    console.print()


# --- Traceroute output ---


def print_traceroute_results(target: str, results: list[Any]) -> None:
    """Print traceroute results with hop-by-hop RTT."""
    console.print(f"\n[bold]Traceroute to {target}[/bold]")

    table = Table()
    table.add_column("Hop", style="cyan", justify="right")
    table.add_column("Host", style="green")
    table.add_column("IP", style="dim")
    table.add_column("RTT 1", justify="right")
    table.add_column("RTT 2", justify="right")
    table.add_column("RTT 3", justify="right")

    for hop in results:
        rtts = []
        for rtt in hop.rtts:
            if rtt is not None:
                color = "green" if rtt < 50 else "yellow" if rtt < 100 else "red"
                rtts.append(f"[{color}]{rtt:.1f}ms[/{color}]")
            else:
                rtts.append("[dim]*[/dim]")

        # Pad to 3 RTT columns
        while len(rtts) < 3:
            rtts.append("[dim]*[/dim]")

        table.add_row(
            str(hop.hop_number),
            hop.hostname or "*",
            hop.ip or "*",
            rtts[0],
            rtts[1],
            rtts[2],
        )

    console.print(table)
    console.print()


# --- System metrics output ---


def print_system_metrics(metrics: dict[str, Any]) -> None:
    """Print system metrics with formatted panels."""
    if "cpu" in metrics:
        cpu = metrics["cpu"]
        table = Table(title="CPU Usage")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        usage_color = "green" if cpu.total_percent < 60 else "yellow" if cpu.total_percent < 85 else "red"
        table.add_row("Total Usage", f"[{usage_color}]{cpu.total_percent:.1f}%[/{usage_color}]")
        table.add_row("User", f"{cpu.user_percent:.1f}%")
        table.add_row("System", f"{cpu.system_percent:.1f}%")
        table.add_row("Idle", f"{cpu.idle_percent:.1f}%")
        table.add_row("I/O Wait", f"{cpu.iowait_percent:.1f}%")
        table.add_row("Load Average (1/5/15)", f"{cpu.load_avg_1:.2f} / {cpu.load_avg_5:.2f} / {cpu.load_avg_15:.2f}")
        console.print(table)
        console.print()

    if "memory" in metrics:
        mem = metrics["memory"]
        table = Table(title="Memory Usage")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        usage_color = "green" if mem.used_percent < 60 else "yellow" if mem.used_percent < 85 else "red"
        table.add_row("Total", f"{mem.total_mb:.0f} MB")
        table.add_row("Used", f"[{usage_color}]{mem.used_mb:.0f} MB ({mem.used_percent:.1f}%)[/{usage_color}]")
        table.add_row("Available", f"{mem.available_mb:.0f} MB")
        table.add_row("Buffers/Cached", f"{mem.buffers_mb:.0f} / {mem.cached_mb:.0f} MB")
        table.add_row("Swap Used", f"{mem.swap_used_mb:.0f} / {mem.swap_total_mb:.0f} MB")
        console.print(table)
        console.print()

    if "disk" in metrics:
        table = Table(title="Disk Usage")
        table.add_column("Mount", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("Used", justify="right")
        table.add_column("Free", justify="right")
        table.add_column("Use%", justify="right")

        for d in metrics["disk"]:
            usage_color = "green" if d.used_percent < 60 else "yellow" if d.used_percent < 85 else "red"
            table.add_row(
                d.mountpoint,
                f"{d.total_gb:.1f}G",
                f"{d.used_gb:.1f}G",
                f"{d.free_gb:.1f}G",
                f"[{usage_color}]{d.used_percent:.1f}%[/{usage_color}]",
            )
        console.print(table)
        console.print()

    if "processes" in metrics:
        table = Table(title="Top Processes")
        table.add_column("PID", style="cyan", justify="right")
        table.add_column("Name")
        table.add_column("CPU%", justify="right")
        table.add_column("MEM%", justify="right")
        table.add_column("State")

        for p in metrics["processes"]:
            table.add_row(
                str(p.pid),
                p.name[:30],
                f"{p.cpu_percent:.1f}%",
                f"{p.memory_percent:.1f}%",
                p.state,
            )
        console.print(table)
        console.print()

    if "sockets" in metrics:
        sock = metrics["sockets"]
        table = Table(title="Socket States")
        table.add_column("State", style="cyan")
        table.add_column("Count", justify="right")

        for state, count in sorted(sock.state_counts.items(), key=lambda x: x[1], reverse=True):
            table.add_row(state, str(count))
        table.add_row("[bold]Total[/bold]", f"[bold]{sock.total}[/bold]")
        console.print(table)
        console.print()


# --- Log analysis output ---


def print_log_analysis(results: Any) -> None:
    """Print log analysis results."""
    console.print(f"\n[bold]Log Analysis[/bold]")
    console.print(f"  Total entries: {results.total_entries}")
    console.print(f"  Time range: {results.time_range}")

    if results.level_distribution:
        table = Table(title="Log Level Distribution")
        table.add_column("Level", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Percentage", justify="right")

        for level, count in sorted(
            results.level_distribution.items(), key=lambda x: x[1], reverse=True
        ):
            color = {"ERROR": "red", "WARN": "yellow", "WARNING": "yellow", "INFO": "green"}.get(
                level.upper(), "dim"
            )
            pct = (count / results.total_entries * 100) if results.total_entries > 0 else 0
            table.add_row(f"[{color}]{level}[/{color}]", str(count), f"{pct:.1f}%")

        console.print(table)

    if results.pattern_matches:
        table = Table(title="Pattern Matches")
        table.add_column("#", style="dim", justify="right")
        table.add_column("Timestamp", style="dim")
        table.add_column("Level")
        table.add_column("Message", max_width=80)

        for i, entry in enumerate(results.pattern_matches[:20], 1):
            color = "red" if "error" in entry.level.lower() else "yellow"
            table.add_row(
                str(i),
                entry.timestamp or "-",
                f"[{color}]{entry.level}[/{color}]",
                entry.message[:80],
            )

        console.print(table)
        if len(results.pattern_matches) > 20:
            console.print(f"  [dim]... and {len(results.pattern_matches) - 20} more matches[/dim]")

    console.print()
