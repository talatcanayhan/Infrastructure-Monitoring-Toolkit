# =============================================================================
# InfraProbe - Provider Configuration
# =============================================================================
# Shared provider configuration for all environments.
# Each environment passes region via its own variables.
# =============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "infraprobe"
      ManagedBy   = "terraform"
      Repository  = "infraprobe"
    }
  }
}

variable "aws_region" {
  description = "AWS region to deploy infrastructure into"
  type        = string
  default     = "eu-west-1"
}
