# State backend.
#
# A local backend is used during development. State is migrated to a remote S3
# backend with DynamoDB-based locking for state integrity and team collaboration
# (ADR-0005). Enable the remote backend by uncommenting the block, supplying the
# bucket and lock table, and running `terraform init -migrate-state`.
#
# terraform {
#   backend "s3" {
#     bucket         = "REPLACE_WITH_STATE_BUCKET"
#     key            = "mongodb-microservice/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "REPLACE_WITH_LOCK_TABLE"
#     encrypt        = true
#   }
# }
