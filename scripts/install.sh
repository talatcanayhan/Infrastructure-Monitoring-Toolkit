#!/usr/bin/env bash
# =============================================================================
# InfraProbe Quick Install Script
# =============================================================================
# Downloads and installs InfraProbe with system configuration.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/talatcanayhan/infraprobe/main/scripts/install.sh | bash
#
# Or manually:
#   chmod +x scripts/install.sh && sudo ./scripts/install.sh
# =============================================================================

set -euo pipefail

INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/infraprobe"
LOG_DIR="/var/log/infraprobe"
SERVICE_USER="infraprobe"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_info "Found Python ${PYTHON_VERSION}"

    if ! python3 -c "import sys; assert sys.version_info >= (3, 10)" 2>/dev/null; then
        log_error "Python 3.10+ is required (found ${PYTHON_VERSION})"
        exit 1
    fi
}

# Create system user
create_user() {
    if id "$SERVICE_USER" &>/dev/null; then
        log_info "User ${SERVICE_USER} already exists"
    else
        useradd --system --no-create-home --shell /sbin/nologin "$SERVICE_USER"
        log_info "Created system user: ${SERVICE_USER}"
    fi
}

# Create directories
create_directories() {
    mkdir -p "$CONFIG_DIR" "$LOG_DIR"
    chown "$SERVICE_USER":"$SERVICE_USER" "$LOG_DIR"
    log_info "Created directories: ${CONFIG_DIR}, ${LOG_DIR}"
}

# Install InfraProbe
install_infraprobe() {
    log_info "Installing InfraProbe via pip..."
    pip3 install --quiet infraprobe

    if command -v infraprobe &> /dev/null; then
        VERSION=$(infraprobe --version 2>/dev/null || echo "unknown")
        log_info "InfraProbe installed: ${VERSION}"
    else
        log_error "Installation failed — infraprobe not found in PATH"
        exit 1
    fi
}

# Install default configuration
install_config() {
    if [[ ! -f "${CONFIG_DIR}/config.yml" ]]; then
        cat > "${CONFIG_DIR}/config.yml" << 'YAML'
# InfraProbe Configuration
# See config.example.yml for all options

targets:
  - name: "localhost"
    host: "127.0.0.1"
    checks:
      - type: ping
        interval: 30
        timeout: 5

system:
  enabled: true
  collect_cpu: true
  collect_memory: true
  collect_disk: true
  interval: 15

metrics:
  enabled: true
  port: 9100
  bind: "0.0.0.0"

logging:
  level: INFO
  format: json
  file: /var/log/infraprobe/infraprobe.log
YAML
        log_info "Default configuration written to ${CONFIG_DIR}/config.yml"
    else
        log_warn "Configuration already exists at ${CONFIG_DIR}/config.yml — skipping"
    fi
}

# Install systemd service
install_systemd() {
    cat > /etc/systemd/system/infraprobe.service << EOF
[Unit]
Description=InfraProbe Infrastructure Monitoring
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
ExecStart=${INSTALL_DIR}/infraprobe serve --config ${CONFIG_DIR}/config.yml --port 9100
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=infraprobe
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${LOG_DIR}
PrivateTmp=yes
AmbientCapabilities=CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable infraprobe
    systemctl start infraprobe

    log_info "systemd service installed and started"
}

# Verify installation
verify() {
    sleep 2
    if systemctl is-active --quiet infraprobe; then
        log_info "InfraProbe is running"
    else
        log_error "InfraProbe failed to start. Check: journalctl -u infraprobe"
        exit 1
    fi

    if curl -sf http://localhost:9100/metrics > /dev/null 2>&1; then
        log_info "Metrics endpoint responding at http://localhost:9100/metrics"
    else
        log_warn "Metrics endpoint not yet available (may need a moment to start)"
    fi
}

# Main
main() {
    echo ""
    echo "=============================="
    echo "  InfraProbe Installer"
    echo "=============================="
    echo ""

    check_prerequisites
    create_user
    create_directories
    install_infraprobe
    install_config
    install_systemd
    verify

    echo ""
    log_info "Installation complete!"
    echo ""
    echo "  Metrics:  http://localhost:9100/metrics"
    echo "  Config:   ${CONFIG_DIR}/config.yml"
    echo "  Logs:     journalctl -u infraprobe -f"
    echo "  Status:   systemctl status infraprobe"
    echo ""
}

main "$@"
