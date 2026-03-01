# =============================================================================
# InfraProbe - Development Environment Variables
# =============================================================================

variable "region" {
  description = "AWS region for the dev environment"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "infraprobe"
}

variable "key_name" {
  description = "Name of the AWS key pair for SSH access to the EC2 instance"
  type        = string
}

variable "allowed_cidr" {
  description = "CIDR block allowed to access the dev infrastructure (your IP)"
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_cidr, 0))
    error_message = "The allowed_cidr must be a valid CIDR block (e.g., 203.0.113.50/32)."
  }
}
