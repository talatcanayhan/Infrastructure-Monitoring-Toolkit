# Contributing to InfraProbe

Thank you for your interest in contributing to InfraProbe!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/talatcanayhan/infraprobe.git
   cd infraprobe
   ```

2. Create a virtual environment and install dev dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   make dev
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Development Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run the test suite: `make test`
4. Run linters: `make lint`
5. Run security checks: `make security`
6. Submit a pull request

## Code Style

- Code is formatted with **Black** (line length 100)
- Type hints are required for all public functions
- Linting with **flake8** and type checking with **mypy** must pass
- All networking modules use **stdlib only** (no wrapper libraries)
- All system modules read **/proc directly** (no psutil)

## Testing

- Unit tests go in `tests/unit/`
- Integration tests go in `tests/integration/`
- Use `pytest` fixtures for shared setup
- Mock `/proc` reads and raw sockets in unit tests
- Aim for 85%+ code coverage

## Commit Messages

Use conventional commit format:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation changes
- `test:` adding or updating tests
- `refactor:` code refactoring
- `ci:` CI/CD changes
- `chore:` maintenance tasks
