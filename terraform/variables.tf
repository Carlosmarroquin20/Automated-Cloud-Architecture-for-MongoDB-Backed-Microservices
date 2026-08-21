variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "aws_region must be a valid region identifier, for example us-east-1."
  }
}

variable "project_name" {
  description = "Project identifier used to name and tag resources."
  type        = string
  default     = "mongodb-microservice"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, staging, or prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet."
  type        = string
  default     = "10.0.1.0/24"

  validation {
    condition     = can(cidrhost(var.public_subnet_cidr, 0))
    error_message = "public_subnet_cidr must be a valid IPv4 CIDR block."
  }
}

variable "instance_type" {
  description = "EC2 instance type. Constrained to free-tier eligible types to honor the zero-cost ceiling."
  type        = string
  default     = "t3.micro"

  validation {
    condition     = contains(["t2.micro", "t3.micro"], var.instance_type)
    error_message = "instance_type must be a free-tier eligible type (t2.micro or t3.micro)."
  }
}

variable "app_port" {
  description = "Port on which the application is served."
  type        = number
  default     = 8080

  validation {
    condition     = var.app_port > 0 && var.app_port <= 65535
    error_message = "app_port must be between 1 and 65535."
  }
}

variable "app_ingress_cidr" {
  description = "CIDR permitted to reach the application port."
  type        = string
  default     = "0.0.0.0/0"
}

variable "enable_ssh" {
  description = "Whether to open inbound SSH. Disabled by default; management uses SSM Session Manager."
  type        = bool
  default     = false
}

variable "ssh_ingress_cidr" {
  description = "CIDR permitted to reach SSH when enable_ssh is true. Must be restricted."
  type        = string
  default     = "127.0.0.1/32"

  validation {
    condition     = var.ssh_ingress_cidr != "0.0.0.0/0"
    error_message = "ssh_ingress_cidr must not be open to the entire internet."
  }
}

variable "key_name" {
  description = "Optional EC2 key pair name. Empty relies on SSM Session Manager only."
  type        = string
  default     = ""
}

variable "mongodb_uri" {
  description = "MongoDB connection string. Stored as a SecureString SSM parameter; never committed."
  type        = string
  sensitive   = true
  default     = "mongodb://localhost:27017"
}

variable "mongodb_db_name" {
  description = "Target database name."
  type        = string
  default     = "microservice"
}
