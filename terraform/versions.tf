# Pins the Terraform CLI and provider versions so plans are reproducible across
# environments and operators.
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.62"
    }
  }
}
