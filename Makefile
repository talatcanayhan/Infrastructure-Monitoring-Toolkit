.PHONY: help install dev test test-unit test-integration lint format security docker-build docker-up docker-down helm-lint helm-template clean

help:                     ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:                  ## Install production dependencies
	pip install .

dev:                      ## Install development dependencies
	pip install -e ".[dev]"

test: test-unit           ## Run all tests

test-unit:                ## Run unit tests with coverage
	pytest tests/unit -v --cov=infraprobe --cov-report=term-missing

test-integration:         ## Run integration tests (requires Docker)
	pytest tests/integration -v

lint:                     ## Run all linters
	black --check src/ tests/
	flake8 src/ tests/
	mypy src/

format:                   ## Auto-format code with black
	black src/ tests/

security:                 ## Run security checks
	bandit -r src/ -ll

docker-build:             ## Build Docker image
	docker build -f docker/Dockerfile -t infraprobe:latest .

docker-up:                ## Start full monitoring stack
	docker compose up -d

docker-down:              ## Stop monitoring stack
	docker compose down

helm-lint:                ## Lint Helm chart
	helm lint deploy/helm/infraprobe

helm-template:            ## Render Helm templates locally
	helm template infraprobe deploy/helm/infraprobe

clean:                    ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
