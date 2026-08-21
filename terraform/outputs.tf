output "vpc_id" {
  description = "Identifier of the created VPC."
  value       = module.network.vpc_id
}

output "instance_id" {
  description = "Identifier of the application EC2 instance."
  value       = module.compute.instance_id
}

output "public_ip" {
  description = "Public IPv4 address of the application instance."
  value       = module.compute.public_ip
}

output "application_url" {
  description = "URL where the application is reachable once provisioned."
  value       = "http://${module.compute.public_ip}:${var.app_port}"
}
