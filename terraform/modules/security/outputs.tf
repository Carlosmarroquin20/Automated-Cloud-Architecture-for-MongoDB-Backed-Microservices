output "app_security_group_id" {
  description = "Identifier of the application security group."
  value       = aws_security_group.app.id
}

output "instance_profile_name" {
  description = "Name of the instance profile attached to the application host."
  value       = aws_iam_instance_profile.instance.name
}
