# Ingress is limited to the application port. SSH is closed by default because
# management is performed through SSM Session Manager, which removes the need for
# an inbound SSH port and a bastion.

resource "aws_security_group" "app" {
  name        = "${var.name}-app"
  description = "Application instance ingress and egress."
  vpc_id      = var.vpc_id

  ingress {
    description = "Application traffic"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = [var.app_ingress_cidr]
  }

  dynamic "ingress" {
    for_each = var.enable_ssh ? [1] : []

    content {
      description = "SSH (restricted source)"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.ssh_ingress_cidr]
    }
  }

  egress {
    description = "Outbound for TLS to MongoDB Atlas and image and package pulls"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name}-app-sg"
  }
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.name}-instance"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# Managed policy that enables SSM Session Manager and agent connectivity.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Scoped read access to only the service's own parameters, following least
# privilege rather than granting broad SSM access.
data "aws_iam_policy_document" "parameters" {
  statement {
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = var.ssm_parameter_arns
  }
}

resource "aws_iam_role_policy" "parameters" {
  name   = "${var.name}-read-parameters"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.parameters.json
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.name}-instance"
  role = aws_iam_role.instance.name
}
