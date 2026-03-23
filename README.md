# InfraProbe

A tool I made for monitoring your network and system. It can ping things, scan ports, check DNS, monitor CPU/memory, and a bunch of other stuff.

I built most of it from scratch without using wrapper libraries, which was fun but also painful.

## What it does

**Network stuff:**
- Ping hosts (raw ICMP, no cheating)
- Scan TCP ports
- DNS lookups
- Check if websites are up (also checks SSL certs)
- Traceroute
- Bandwidth monitoring

**System stuff:**
- CPU usage
- Memory usage
- Disk usage
- Process monitoring
- Socket monitoring

**Other stuff:**
- Prometheus metrics endpoint
- Grafana dashboards (pre-made)
- Alerts when things go wrong
- JSON output if you need it

## How to run it

**The easy way (Docker):**
```bash
git clone https://github.com/talatcanayhan/infraprobe.git
cd infraprobe
make docker-up
```

Then open:
- Grafana: http://localhost:3000 (login: admin / admin)
- Prometheus: http://localhost:9090
- Metrics: http://localhost:9100/metrics

**Install it locally:**
```bash
pip install .
```

## Commands

```bash
# Ping something
sudo infraprobe ping 8.8.8.8

# Scan ports
infraprobe scan 192.168.1.1 --ports 1-1024

# DNS lookup
infraprobe dns example.com

# Check a website
infraprobe http https://example.com

# Traceroute
sudo infraprobe traceroute 8.8.8.8

# System stats
infraprobe system --cpu --memory --disk

# Start the metrics server
infraprobe serve --port 9100
```

Add `--output json` to any command if you want JSON output.

## Requirements

- Python 3.10 or newer
- Some commands need `sudo` (the ones that use raw sockets)

## Dev setup

```bash
make dev      # install dev dependencies
make test     # run tests
make lint     # check code style
make format   # auto-format
```

## Deployment options

You can run it with Docker Compose, Kubernetes/Helm, Terraform + Ansible, or just plain systemd on a server. Check the `docs/` folder for guides on each.

## Project layout

```
infraprobe/
├── src/infraprobe/      # main code
│   ├── network/         # ping, scan, dns, http, etc.
│   ├── system/          # cpu, memory, disk, etc.
│   ├── metrics/         # prometheus stuff
│   └── alerting/        # alerts
├── tests/               # tests
├── deploy/              # kubernetes, helm, terraform, ansible
├── monitoring/          # prometheus + grafana configs
└── docs/                # documentation
```

## License

MIT — do whatever you want with it.
