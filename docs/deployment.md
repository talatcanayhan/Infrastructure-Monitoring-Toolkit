# Deployment Guide

## Docker Compose (Quickest)

```bash
# Start the full monitoring stack
make docker-up

# Access:
#   Grafana:    http://localhost:3000 (admin/admin)
#   Prometheus: http://localhost:9090
#   Metrics:    http://localhost:9100/metrics

# Stop
make docker-down
```

## Kubernetes

### Raw Manifests

```bash
kubectl apply -f deploy/kubernetes/namespace.yml
kubectl apply -f deploy/kubernetes/
```

### Helm Chart

```bash
# Install
helm install infraprobe deploy/helm/infraprobe -n infraprobe --create-namespace

# Install with production values
helm install infraprobe deploy/helm/infraprobe -n infraprobe \
  --create-namespace \
  -f deploy/helm/infraprobe/values-production.yaml

# Upgrade
helm upgrade infraprobe deploy/helm/infraprobe -n infraprobe

# Uninstall
helm uninstall infraprobe -n infraprobe
```

## Terraform + Ansible

### 1. Provision Infrastructure

```bash
cd deploy/terraform/environments/dev
terraform init
terraform plan
terraform apply
```

### 2. Configure and Deploy

```bash
cd deploy/ansible
ansible-playbook playbooks/setup_server.yml
ansible-playbook playbooks/deploy_infraprobe.yml
ansible-playbook playbooks/configure_monitoring.yml
```

## Bare Metal (systemd)

### Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/talatcanayhan/infraprobe/main/scripts/install.sh | sudo bash
```

### Manual Install

```bash
# Install
pip install infraprobe

# Create system user
sudo useradd --system --no-create-home infraprobe

# Setup directories
sudo mkdir -p /etc/infraprobe /var/log/infraprobe
sudo cp config.example.yml /etc/infraprobe/config.yml
sudo chown infraprobe:infraprobe /var/log/infraprobe

# Install systemd service
sudo cp systemd/infraprobe.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now infraprobe

# Verify
systemctl status infraprobe
curl http://localhost:9100/metrics
```
