# Development Guide

## Prerequisites

- Python 3.10+
- Docker and Docker Compose (for integration tests)
- make

## Setup

```bash
# Clone the repo
git clone https://github.com/talatcanayhan/infraprobe.git
cd infraprobe

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dev dependencies
make dev

# Install pre-commit hooks
pre-commit install
```

## Common Tasks

```bash
make help          # Show all available targets
make test          # Run unit tests with coverage
make lint          # Run black, flake8, mypy
make format        # Auto-format code with black
make security      # Run bandit security check
make docker-build  # Build Docker image
make docker-up     # Start full monitoring stack
make clean         # Remove build artifacts
```

## Project Structure

- `src/infraprobe/` — Application source code
- `tests/unit/` — Unit tests (mock /proc and sockets)
- `tests/integration/` — Integration tests (require Docker)
- `tests/fixtures/` — Test data files

## Running Individual Commands

```bash
# During development, run commands directly
python -m infraprobe --help
python -m infraprobe ping 8.8.8.8 --count 3
python -m infraprobe system --cpu --memory
```

## Adding a New Check Type

1. Create the module in `src/infraprobe/network/` or `system/`
2. Add a CLI subcommand in `cli.py`
3. Add Prometheus metrics in `metrics/prometheus_exporter.py`
4. Add output formatting in `output/console.py`
5. Write unit tests in `tests/unit/`
6. Add the check type to `config.py` models
