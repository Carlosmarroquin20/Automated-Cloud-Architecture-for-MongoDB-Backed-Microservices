variable "name" {
  description = "Resource name prefix."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "subnet_cidr" {
  description = "CIDR block for the public subnet."
  type        = string
}
