# =============================================================================
# InfraProbe - Compute Module Outputs
# =============================================================================

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.infraprobe.id
}

output "public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.infraprobe.public_ip
}

output "private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.infraprobe.private_ip
}

output "instance_profile_arn" {
  description = "ARN of the IAM instance profile"
  value       = aws_iam_instance_profile.infraprobe.arn
}
