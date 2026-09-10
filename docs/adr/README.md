# Architecture Decision Records

This log captures the significant architecture and security decisions taken while
building the project, with the context that motivated each one. Records are
append-only: a decision is never edited away, only superseded by a later record.

Each entry states the **context** (the forces at play), the **decision** taken,
and its **status**. The intent is that a reviewer can reconstruct *why* the system
looks the way it does, not merely *what* it contains.

| # | Decision | Status |
|---|----------|--------|
| 0001 | Artifact language | Accepted |
| 0002 | Backend framework | Accepted |
| 0003 | Managed database | Accepted |
| 0004 | Image strategy | Accepted |
| 0005 | Terraform backend | Accepted |
| 0006 | Local knowledge base exclusion | Accepted |
| 0007 | Line-ending normalization | Accepted |
| 0008 | MongoDB asynchronous driver | Accepted |
| 0009 | Python language baseline | Accepted |
| 0010 | Frontend stack | Accepted |
| 0011 | Instance access and secret delivery | Accepted |
| 0012 | CI/CD platform and pipeline topology | Accepted |
| 0013 | Container registry and release model | Accepted |
| 0014 | GitHub Actions pinning strategy | Superseded by SHA pinning |
| 0015 | Deploy simulation strategy | Accepted |
| 0016 | Observability stack and topology | Accepted |

---

## ADR-0001 — Artifact language

**Context.** The project targets US corporate standards and international
reviewers.

**Decision.** All repository artifacts — code, configuration, comments, variables,
logs, resource names, and documentation — are authored in technical English.

**Status.** Accepted.

## ADR-0002 — Backend framework

**Context.** The service requires asynchronous I/O, strict input validation, and
first-class typing.

**Decision.** FastAPI with Pydantic v2.

**Status.** Accepted.

## ADR-0003 — Managed database

**Context.** Persistence must be zero-cost, multi-node, and cloud-hosted.

**Decision.** MongoDB Atlas M0 free-tier replica set with TLS-only connections.

**Status.** Accepted.

## ADR-0004 — Image strategy

**Context.** The runtime images should minimize both attack surface and size.

**Decision.** Multi-stage builds targeting distroless (backend) and alpine
(frontend) runtime images, running as a non-root user.

**Consequences.** No shell or package manager ships in the backend runtime,
reducing exploitability; the build tooling never reaches the final image.

**Status.** Accepted.

## ADR-0005 — Terraform backend

**Context.** State integrity matters, and the project should be ready for team
collaboration later.

**Decision.** Use a local backend during development, structured for migration to
a remote S3 backend with state locking.

**Status.** Accepted.

## ADR-0006 — Local knowledge base exclusion

**Context.** Operator working notes may reference environment-specific detail that
should not be published.

**Decision.** The engineering knowledge base and private support notes are
git-ignored and never published; decisions worth sharing are promoted to these
public records instead.

**Status.** Accepted.

## ADR-0007 — Line-ending normalization

**Context.** Cross-platform authoring (Windows host, Linux runtime) risks CRLF/LF
churn and non-executable shell scripts inside containers.

**Decision.** `.gitattributes` enforces LF for text and shell scripts, CRLF for
Windows-native scripts, and binary handling for assets.

**Status.** Accepted.

## ADR-0008 — MongoDB asynchronous driver

**Context.** Motor is deprecated with a scheduled end-of-life; the project needs a
forward-looking asynchronous driver.

**Decision.** Use the native PyMongo asynchronous client (`AsyncMongoClient`).

**Status.** Accepted.

## ADR-0009 — Python language baseline

**Context.** The local interpreter is CPython 3.10 while container runtimes target
a newer minor; the code must run on both.

**Decision.** Target `requires-python >= 3.10` and avoid 3.11-only constructs
(for example `timezone.utc` instead of `datetime.UTC`). Container images may pin a
newer minor. CI runs a 3.10/3.11/3.12 matrix to prove the range.

**Status.** Accepted.

## ADR-0010 — Frontend stack

**Context.** The client should be lightweight and optimized with a minimal
dependency and attack surface.

**Decision.** Vite with strict TypeScript, framework-free and with zero runtime
dependencies. A same-origin reverse-proxy topology embeds no backend host in the
shipped assets.

**Consequences.** The production bundle stays a few kilobytes gzipped and issues
only same-origin requests.

**Status.** Accepted.

## ADR-0011 — Instance access and secret delivery

**Context.** SSH bastions and an inbound port 22 widen the attack surface, and
runtime secrets must not reside in images or in state that reaches version
control.

**Decision.** Manage instances through SSM Session Manager (no inbound SSH by
default) and deliver the MongoDB connection string from an encrypted SSM
SecureString parameter, read via a least-privilege instance role.

**Status.** Accepted.

## ADR-0012 — CI/CD platform and pipeline topology

**Context.** The project requires an automated, auditable quality and delivery
pipeline at zero cost.

**Decision.** GitHub Actions expressed as a directed acyclic graph: parallel
quality gates (backend matrix, frontend, Terraform validate, Kustomize +
kubeconform) fan out, then image build and scan, then a deploy simulation.
Security findings are emitted as SARIF to code scanning. The default token
permission is `contents: read`, elevated per job; concurrency cancels superseded
runs.

**Status.** Accepted.

## ADR-0013 — Container registry and release model

**Context.** Images must be published and versioned without paid infrastructure or
long-lived credentials.

**Decision.** Publish to the GitHub Container Registry on `vX.Y.Z` tags using the
ephemeral `GITHUB_TOKEN`; derive semantic tags with `docker/metadata-action`; and
attach SLSA build provenance and an SBOM. CI builds and scans images but does not
push them; only a tagged release publishes.

**Status.** Accepted.

## ADR-0014 — GitHub Actions pinning strategy

**Context.** Supply-chain integrity must be balanced against the maintainability
of action references.

**Decision.** Initially, pin third-party actions to major-version tags and
delegate currency to Dependabot.

**Status.** Superseded (2026-08-31). All action references are now pinned to
immutable commit SHAs, with the version retained as a trailing comment; Dependabot
continues to track and refresh the pins. The SHA pins the action's code, which a
mutable tag cannot guarantee.

## ADR-0015 — Deploy simulation strategy

**Context.** A deployment gate should exercise real admission and schema
validation while creating no cloud resources.

**Decision.** Stand up an ephemeral in-cluster Kubernetes (kind) on the CI runner
and run a server-side dry run of the dev overlay. Because a server-side dry run
does not persist the overlay's namespace, the namespace is created first; an empty
namespace schedules no workload and creates no provider resource.

**Status.** Accepted.

## ADR-0016 — Observability stack and topology

**Context.** Metrics must be collected and visualized at zero cost without adding
an exporter sidecar or a hosted backend.

**Decision.** Scrape the backend's existing `/metrics` with Prometheus (in-process
rule evaluation, no Alertmanager locally) and visualize with Grafana, both
provisioned as code (a datasource with a fixed uid and file-based dashboards). The
plane runs behind a Compose profile so the default stack stays lean. In-cluster,
Prometheus discovers targets through pod annotations. Grafana uses anonymous
access with the login form disabled in local and in-cluster contexts to avoid
provisioning a credential; this posture is not intended for public exposure.

**Status.** Accepted.
