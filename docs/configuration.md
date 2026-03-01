# Configuration Reference

InfraProbe is configured via a YAML file. Configuration values can be overridden by environment variables with the prefix `INFRAPROBE_`.

## Configuration File

Copy `config.example.yml` and customize:

```bash
cp config.example.yml config.yml
```

## Sections

### targets

Define monitoring targets with their checks.

```yaml
targets:
  - name: "web-server"       # Unique target name
    host: "192.168.1.10"      # Hostname or IP
    checks:
      - type: ping            # Check type
        interval: 30          # Seconds between checks
        timeout: 5            # Per-check timeout
        count: 3              # Pings per check cycle
```

#### Check types

| Type | Description | Fields |
|------|------------|--------|
| `ping` | ICMP echo request | `interval`, `timeout`, `count` |
| `http` | HTTP/HTTPS health check | `url`, `expected_status`, `check_tls`, `follow_redirects`, `interval`, `timeout` |
| `tcp` | TCP port scan | `ports` (list), `interval`, `timeout` |
| `dns` | DNS resolution | `domain`, `record_type`, `nameserver`, `interval` |

### system

```yaml
system:
  enabled: true
  collect_cpu: true
  collect_memory: true
  collect_disk: true
  collect_processes: true
  collect_sockets: true
  disk_paths: ["/", "/var"]
  interval: 15
```

### metrics

```yaml
metrics:
  enabled: true
  port: 9100
  bind: "0.0.0.0"
```

### alerting

```yaml
alerting:
  rules:
    - name: "high-latency"
      metric: "ping_rtt_ms"
      condition: "> 100"
      duration: "5m"
      severity: warning
      notify: ["webhook"]
  notifiers:
    webhook:
      url: "https://hooks.slack.com/services/..."
      timeout: 10
```

### logging

```yaml
logging:
  level: INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: json         # json or text
  file: /var/log/infraprobe/infraprobe.log
```

## Environment Variable Overrides

Any config value can be overridden via environment variables:

```bash
INFRAPROBE_METRICS_PORT=9200 infraprobe serve
INFRAPROBE_LOGGING_LEVEL=DEBUG infraprobe monitor config.yml
```

Pattern: `INFRAPROBE_<SECTION>_<KEY>=value`
