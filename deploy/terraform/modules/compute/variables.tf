# =============================================================================
# InfraProbe - Compute Module Variables
# =============================================================================

variable "instance_type" {
  description = "EC2 instance type for the InfraProbe server"
  type        = string
  default     = "t3.micro"

  validation {
    condition     = can(regex("^t[23]\\.", var.instance_type))
    error_message = "Instance type must be a t2 or t3 family instance for cost efficiency."
  }
}

variable "subnet_id" {
  description = "ID of the subnet to launch the instance in"
  type        = string

  validation {
    condition     = can(regex("^subnet-", var.subnet_id))
    error_message = "The subnet_id must be a valid AWS subnet ID."
  }
}

variable "security_group_id" {
  description = "ID of the security group to attach to the instance"
  type        = string

  validation {
    condition     = can(regex("^sg-", var.security_group_id))
    error_message = "The security_group_id must be a valid AWS security group ID."
  }
}

variable "key_name" {
  description = "Name of the SSH key pair for instance access"
  type        = string
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "infraprobe"
}
