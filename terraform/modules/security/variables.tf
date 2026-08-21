variable "name" {
  description = "Resource name prefix."
  type        = string
}

variable "vpc_id" {
  description = "VPC in which to create the security group."
  type        = string
}

variable "app_port" {
  description = "Application ingress port."
  type        = number
}

variable "app_ingress_cidr" {
  description = "CIDR permitted to reach the application port."
  type        = string
}

variable "enable_ssh" {
  description = "Whether to open inbound SSH."
  type        = bool
}

variable "ssh_ingress_cidr" {
  description = "CIDR permitted to reach SSH when enabled."
  type        = string
}

variable "ssm_parameter_arns" {
  description = "SSM parameter ARNs the instance is allowed to read."
  type        = list(string)
}
