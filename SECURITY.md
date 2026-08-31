# Security Policy

## Supported versions

This is a reference architecture delivered as a single evolving line of work. The
`main` branch is the only supported version; fixes are applied there and are not
backported.

| Version | Supported |
|---------|-----------|
| `main`  | Yes       |
| Older commits / tags | No |

## Reporting a vulnerability

Please do not report security issues through public GitHub issues, pull
requests, or discussions.

Instead, use **GitHub's private vulnerability reporting** for this repository:
open the **Security** tab and choose **Report a vulnerability**. This opens a
private advisory visible only to the maintainers.

When reporting, include where possible:

- A description of the issue and its impact.
- The affected component (backend, frontend, container images, Terraform, or
  Kubernetes manifests) and version or commit.
- Steps to reproduce, and any proof-of-concept.
- Any suggested remediation.

## What to expect

- Acknowledgement of a report within a few days.
- An assessment of severity and affected components.
- A private fix and coordinated disclosure once a remediation is available.

## Scope and hardening posture

The project is designed to hold no secrets in version control: credentials are
injected at runtime through environment variables and Kubernetes Secrets, state
files and environment files are excluded from Git, and the CI pipeline runs
secret scanning, dependency review, container and IaC vulnerability scanning, and
CodeQL analysis on every change. Reports that strengthen this posture are
welcome.
