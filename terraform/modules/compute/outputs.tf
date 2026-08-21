output "instance_id" {
  description = "Identifier of the application instance."
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Public IPv4 address of the instance."
  value       = aws_instance.app.public_ip
}

output "public_dns" {
  description = "Public DNS name of the instance."
  value       = aws_instance.app.public_dns
}
