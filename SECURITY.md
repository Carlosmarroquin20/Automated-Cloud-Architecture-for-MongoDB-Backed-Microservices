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

Report privately through GitHub's private vulnerability reporting for this
repository:

- **[Open a private security advisory](https://github.com/Carlosmarroquin20/Automated-Cloud-Architecture-for-MongoDB-Backed-Microservices/security/advisories/new)**

This opens a private report visible only to the maintainers. Background on the
mechanism is documented at
<https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability>.

When reporting, include where possible:

- A description of the issue and its impact.
- The affected component (backend, frontend, container images, Terraform, or
  Kubernetes manifests) and the version or commit.
- Steps to reproduce, and any proof-of-concept.
- Any suggested remediation.

## Disclosure process and timelines

The following target timelines apply from the moment a report is received:

- **Acknowledgement:** within 3 business days.
- **Triage and severity assessment:** within 10 business days, using CVSS v3.1
  to rate impact.
- **Fix and coordinated disclosure:** a remediation is targeted within 90 days of
  acknowledgement. The fix and a public advisory are published together, and the
  reporter is credited unless they request otherwise.

If a report is declined as out of scope, the reason is communicated within the
10 business day triage window.

## Scope and hardening posture

The project holds no secrets in version control: credentials are injected at
runtime through environment variables and Kubernetes Secrets, state files and
environment files are excluded from Git, and the CI pipeline runs secret
scanning, dependency review, container and IaC vulnerability scanning, and CodeQL
analysis on every change. Published release images carry SLSA build provenance
and an SBOM. Reports that strengthen this posture are welcome.
