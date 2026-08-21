output "vpc_id" {
  description = "Identifier of the VPC."
  value       = aws_vpc.this.id
}

output "public_subnet_id" {
  description = "Identifier of the public subnet."
  value       = aws_subnet.public.id
}
