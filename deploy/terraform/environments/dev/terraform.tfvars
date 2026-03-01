# =============================================================================
# InfraProbe - Development Environment Values
# =============================================================================
# Customize these values for your dev environment.
# Run: terraform plan -var-file="terraform.tfvars"
# =============================================================================

# AWS region to deploy into
region = "eu-west-1"

# Project identifier (used in resource names and tags)
project_name = "infraprobe"

# Name of your EC2 key pair (must already exist in the target region)
# Create one via: aws ec2 create-key-pair --key-name infraprobe-dev --query 'KeyMaterial' --output text > infraprobe-dev.pem
key_name = "infraprobe-dev"

# Your public IP in CIDR notation for SSH and dashboard access
# Find your IP: curl -s https://checkip.amazonaws.com
# Replace with your actual IP, e.g., "203.0.113.50/32"
allowed_cidr = "0.0.0.0/0" # WARNING: Restrict this to your IP in practice
