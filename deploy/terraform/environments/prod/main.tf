# =============================================================================
# InfraProbe - Production Environment
# =============================================================================
# Deploys a production-grade InfraProbe stack with:
#   - 2 EC2 instances across different AZs for high availability
#   - t3.small instance type for adequate monitoring capacity
#   - Instances in public subnets for external target monitoring
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
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# Network Module
# -----------------------------------------------------------------------------

module "network" {
  source = "../../modules/network"

  vpc_cidr             = "10.1.0.0/16"
  public_subnet_cidrs  = ["10.1.1.0/24", "10.1.2.0/24"]
  private_subnet_cidrs = ["10.1.10.0/24", "10.1.20.0/24"]
  allowed_cidr         = var.allowed_cidr
  project_name         = var.project_name
}

# -----------------------------------------------------------------------------
# Compute Module - Primary instance (AZ-1)
# -----------------------------------------------------------------------------

module "compute_primary" {
  source = "../../modules/compute"

  instance_type     = "t3.small"
  subnet_id         = module.network.public_subnet_ids[0]
  security_group_id = module.network.security_group_id
  key_name          = var.key_name
  project_name      = "${var.project_name}-primary"
}

# -----------------------------------------------------------------------------
# Compute Module - Secondary instance (AZ-2)
# -----------------------------------------------------------------------------

module "compute_secondary" {
  source = "../../modules/compute"

  instance_type     = "t3.small"
  subnet_id         = module.network.public_subnet_ids[1]
  security_group_id = module.network.security_group_id
  key_name          = var.key_name
  project_name      = "${var.project_name}-secondary"
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "VPC ID"
  value       = module.network.vpc_id
}

output "primary_public_ip" {
  description = "Public IP of the primary InfraProbe server"
  value       = module.compute_primary.public_ip
}

output "primary_private_ip" {
  description = "Private IP of the primary InfraProbe server"
  value       = module.compute_primary.private_ip
}

output "secondary_public_ip" {
  description = "Public IP of the secondary InfraProbe server"
  value       = module.compute_secondary.public_ip
}

output "secondary_private_ip" {
  description = "Private IP of the secondary InfraProbe server"
  value       = module.compute_secondary.private_ip
}

output "grafana_url_primary" {
  description = "URL to access Grafana on the primary server"
  value       = "http://${module.compute_primary.public_ip}:3000"
}

output "prometheus_url_primary" {
  description = "URL to access Prometheus on the primary server"
  value       = "http://${module.compute_primary.public_ip}:9090"
}

output "ssh_command_primary" {
  description = "SSH command to connect to the primary instance"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${module.compute_primary.public_ip}"
}

output "ssh_command_secondary" {
  description = "SSH command to connect to the secondary instance"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${module.compute_secondary.public_ip}"
}
