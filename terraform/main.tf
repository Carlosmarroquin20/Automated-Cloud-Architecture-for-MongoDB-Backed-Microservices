locals {
  name = "${var.project_name}-${var.environment}"
}

# Latest Amazon Linux 2023 image; resolving it dynamically avoids region-specific
# hardcoded AMI identifiers. The image ships the SSM agent used for management.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# The credential-bearing connection string is held as an encrypted SecureString
# parameter. It is injected at instance boot and never written into the image or
# committed to version control.
resource "aws_ssm_parameter" "mongodb_uri" {
  name        = "/${var.project_name}/${var.environment}/mongodb-uri"
  description = "MongoDB connection string consumed by the service at runtime."
  type        = "SecureString"
  value       = var.mongodb_uri
}

module "network" {
  source      = "./modules/network"
  name        = local.name
  vpc_cidr    = var.vpc_cidr
  subnet_cidr = var.public_subnet_cidr
}

module "security" {
  source             = "./modules/security"
  name               = local.name
  vpc_id             = module.network.vpc_id
  app_port           = var.app_port
  app_ingress_cidr   = var.app_ingress_cidr
  enable_ssh         = var.enable_ssh
  ssh_ingress_cidr   = var.ssh_ingress_cidr
  ssm_parameter_arns = [aws_ssm_parameter.mongodb_uri.arn]
}

module "compute" {
  source                = "./modules/compute"
  name                  = local.name
  ami_id                = data.aws_ami.al2023.id
  instance_type         = var.instance_type
  subnet_id             = module.network.public_subnet_id
  security_group_id     = module.security.app_security_group_id
  instance_profile_name = module.security.instance_profile_name
  mongodb_uri_parameter = aws_ssm_parameter.mongodb_uri.name
  mongodb_db_name       = var.mongodb_db_name
  key_name              = var.key_name
}
