variable "name" {
  description = "Resource name prefix."
  type        = string
}

variable "ami_id" {
  description = "AMI identifier for the instance."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
}

variable "subnet_id" {
  description = "Subnet in which to launch the instance."
  type        = string
}

variable "security_group_id" {
  description = "Security group attached to the instance."
  type        = string
}

variable "instance_profile_name" {
  description = "IAM instance profile granting SSM and parameter access."
  type        = string
}

variable "mongodb_uri_parameter" {
  description = "Name of the SSM parameter holding the MongoDB connection string."
  type        = string
}

variable "mongodb_db_name" {
  description = "Target database name."
  type        = string
}

variable "key_name" {
  description = "Optional EC2 key pair name."
  type        = string
}
