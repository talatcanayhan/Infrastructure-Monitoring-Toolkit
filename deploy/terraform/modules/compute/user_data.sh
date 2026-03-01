#!/bin/bash
# =============================================================================
# InfraProbe EC2 Instance Bootstrap Script
# =============================================================================
# Installs Docker, docker-compose, and prepares the host for InfraProbe.
# This script runs once on first boot via cloud-init.
# =============================================================================

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

echo ">>> Starting InfraProbe instance bootstrap..."

# -----------------------------------------------------------------------------
# System updates and base packages
# -----------------------------------------------------------------------------

apt-get update -y
apt-get upgrade -y
apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  jq \
  htop \
  net-tools \
  unzip \
  fail2ban

# -----------------------------------------------------------------------------
# Install Docker Engine (official repository)
# -----------------------------------------------------------------------------

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
systemctl enable docker
systemctl start docker

# -----------------------------------------------------------------------------
# Install standalone docker-compose (v2 as a fallback alias)
# -----------------------------------------------------------------------------

COMPOSE_VERSION="v2.24.5"
curl -fsSL "https://github.com/docker/compose/releases/download/$${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# -----------------------------------------------------------------------------
# Create infraprobe system user
# -----------------------------------------------------------------------------

if ! id -u infraprobe &>/dev/null; then
  useradd --system --shell /usr/sbin/nologin --create-home --home-dir /opt/infraprobe infraprobe
fi

usermod -aG docker infraprobe

# -----------------------------------------------------------------------------
# Prepare application directories
# -----------------------------------------------------------------------------

mkdir -p /opt/infraprobe/{config,data,logs}
mkdir -p /var/log/infraprobe

chown -R infraprobe:infraprobe /opt/infraprobe
chown -R infraprobe:infraprobe /var/log/infraprobe

# -----------------------------------------------------------------------------
# Configure Docker daemon
# -----------------------------------------------------------------------------

cat > /etc/docker/daemon.json <<'DOCKER_CONF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-address-pools": [
    {
      "base": "172.17.0.0/16",
      "size": 24
    }
  ]
}
DOCKER_CONF

systemctl restart docker

# -----------------------------------------------------------------------------
# Configure fail2ban for SSH protection
# -----------------------------------------------------------------------------

cat > /etc/fail2ban/jail.local <<'FAIL2BAN'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
findtime = 600
FAIL2BAN

systemctl enable fail2ban
systemctl restart fail2ban

# -----------------------------------------------------------------------------
# Kernel tuning for monitoring workloads
# -----------------------------------------------------------------------------

cat >> /etc/sysctl.d/99-infraprobe.conf <<'SYSCTL'
# Increase max open files
fs.file-max = 65535
# Increase network buffer sizes
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
# Enable TCP BBR congestion control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
# Allow ICMP for ping probes
net.ipv4.ping_group_range = 0 2147483647
SYSCTL

sysctl --system

# -----------------------------------------------------------------------------
# Tag completion
# -----------------------------------------------------------------------------

echo ">>> InfraProbe instance bootstrap complete at $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee /opt/infraprobe/bootstrap.log
