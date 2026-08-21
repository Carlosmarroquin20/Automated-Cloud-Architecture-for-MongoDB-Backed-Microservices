# Infrastructure as Code (Terraform)

Modular Terraform that provisions a free-tier AWS footprint for the containerized
microservice: an isolated network, a least-privilege security posture, and a
single application host.

## Design

- **Cost ceiling zero.** Only free-tier eligible resources are used — a VPC and
  its networking primitives (no charge), a `t3.micro` instance, and a 20 GiB gp3
  root volume. No NAT gateway, load balancer, or managed database is created.
- **Least privilege.** The instance role grants only SSM Session Manager access
  and read access to the service's own parameters. Inbound SSH is closed by
  default; management uses Session Manager.
- **Secret handling.** The MongoDB connection string is stored as an encrypted
  SSM SecureString parameter and injected at boot, never committed.
- **Reproducibility.** Provider and CLI versions are pinned and the dependency
  lock file is tracked.

## Modules

| Module | Responsibility |
|--------|----------------|
| `network` | VPC, public subnet, internet gateway, route table |
| `security` | Application security group and least-privilege IAM role |
| `compute` | EC2 instance, IMDSv2 enforcement, and boot provisioning |

## Usage

```bash
cd terraform
terraform init
terraform fmt -check -recursive
terraform validate

# Provide the connection string out-of-band, then review and apply.
export TF_VAR_mongodb_uri="mongodb+srv://<user>:<password>@<cluster-host>/..."
terraform plan
terraform apply
```

Applying requires AWS credentials with permission to manage the listed
resources. Remove the footprint with `terraform destroy`.

## State backend

A local backend is used during development. `backend.tf` documents the migration
to a remote S3 backend with DynamoDB-based locking (ADR-0005).
