resource "aws_instance" "app" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = var.instance_profile_name
  key_name               = var.key_name != "" ? var.key_name : null

  # Enforces IMDSv2, mitigating credential exfiltration via SSRF against the
  # instance metadata service.
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  # Encrypted, right-sized root volume within the free-tier storage allowance.
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    mongodb_uri_parameter = var.mongodb_uri_parameter
    mongodb_db_name       = var.mongodb_db_name
  })

  tags = {
    Name = "${var.name}-app"
  }
}
