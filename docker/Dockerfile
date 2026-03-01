# =============================================================================
# InfraProbe — Multi-Stage Production Dockerfile
# =============================================================================
# Security best practices:
#   - Multi-stage build to minimize final image size
#   - Non-root user for runtime
#   - No pip cache in final image
#   - HEALTHCHECK for container orchestration
#   - Minimal base image (python:3.12-slim)
# =============================================================================

# Stage 1: Build
# Install build dependencies and create wheel
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy only what's needed for the build
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

# Build the wheel
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /build/dist


# Stage 2: Production
# Minimal runtime image
FROM python:3.12-slim AS production

LABEL maintainer="Talat Can Ayhan"
LABEL description="InfraProbe — Infrastructure monitoring toolkit"
LABEL org.opencontainers.image.source="https://github.com/talatcanayhan/infraprobe"

# Security: Create non-root user and group
RUN groupadd --system infraprobe \
    && useradd --system --gid infraprobe --home-dir /app --shell /sbin/nologin infraprobe \
    && mkdir -p /var/log/infraprobe \
    && chown infraprobe:infraprobe /var/log/infraprobe

WORKDIR /app

# Install the pre-built wheel (no build tools in final image)
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm -rf /tmp/*.whl

# Copy default configuration
COPY config.example.yml /app/config.yml

# Switch to non-root user
USER infraprobe

# Expose Prometheus metrics port
EXPOSE 9100

# Health check: verify metrics endpoint responds
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9100/metrics')" || exit 1

ENTRYPOINT ["infraprobe"]
CMD ["serve", "--port", "9100", "--config", "/app/config.yml"]
