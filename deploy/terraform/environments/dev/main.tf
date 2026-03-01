# =============================================================================
# InfraProbe - Development Environment
# =============================================================================
# Deploys a minimal InfraProbe stack suitable for development and testing.
# Single EC2 instance (t3.micro) in a public subnet.
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# Network Module
# -----------------------------------------------------------------------------

module "network" {
  source = "../../modules/network"

  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24"]
  allowed_cidr         = var.allowed_cidr
  project_name         = var.project_name
}

# -----------------------------------------------------------------------------
# Compute Module - Single instance for dev
# -----------------------------------------------------------------------------

module "compute" {
  source = "../../modules/compute"

  instance_type     = "t3.micro"
  subnet_id         = module.network.public_subnet_ids[0]
  security_group_id = module.network.security_group_id
  key_name          = var.key_name
  project_name      = var.project_name
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "VPC ID"
  value       = module.network.vpc_id
}

output "instance_public_ip" {
  description = "Public IP of the InfraProbe dev server"
  value       = module.compute.public_ip
}

output "instance_private_ip" {
  description = "Private IP of the InfraProbe dev server"
  value       = module.compute.private_ip
}

output "grafana_url" {
  description = "URL to access Grafana dashboard"
  value       = "http://${module.compute.public_ip}:3000"
}

output "prometheus_url" {
  description = "URL to access Prometheus"
  value       = "http://${module.compute.public_ip}:9090"
}

output "metrics_url" {
  description = "URL to access InfraProbe metrics"
  value       = "http://${module.compute.public_ip}:9100/metrics"
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${module.compute.public_ip}"
}
