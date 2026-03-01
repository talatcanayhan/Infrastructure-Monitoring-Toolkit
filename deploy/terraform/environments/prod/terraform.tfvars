# =============================================================================
# InfraProbe - Production Environment Values
# =============================================================================
# Production configuration. Ensure these values are reviewed before applying.
# Run: terraform plan -var-file="terraform.tfvars"
# =============================================================================

# AWS region for production deployment
region = "eu-west-1"

# Project identifier (used in resource names and tags)
project_name = "infraprobe"

# Name of your EC2 key pair (must already exist in the target region)
key_name = "infraprobe-prod"

# Restrict access to your office/VPN CIDR range
# IMPORTANT: Never use 0.0.0.0/0 in production
allowed_cidr = "10.0.0.0/8"
