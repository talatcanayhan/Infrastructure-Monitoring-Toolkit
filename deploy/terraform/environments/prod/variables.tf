# =============================================================================
# InfraProbe - Production Environment Variables
# =============================================================================

variable "region" {
  description = "AWS region for the production environment"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "infraprobe"
}

variable "key_name" {
  description = "Name of the AWS key pair for SSH access to EC2 instances"
  type        = string
}

variable "allowed_cidr" {
  description = "CIDR block allowed to access the production infrastructure"
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_cidr, 0))
    error_message = "The allowed_cidr must be a valid CIDR block (e.g., 10.0.0.0/8)."
  }
}
