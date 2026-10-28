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
| 0015 | Deploy verification strategy | Accepted (amended) |
| 0016 | Observability stack and topology | Accepted |
| 0017 | Distributed tracing | Accepted |
| 0018 | Retry jitter and graceful termination | Accepted |
| 0019 | Request rate limiting at the reverse proxy | Accepted |
| 0020 | API contract as a versioned artifact | Accepted |
| 0021 | Document data model | Accepted |

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
reducing exploitability; the build tooling never reaches the final image. The
frontend uses the unprivileged nginx variant listening on port 8080, so neither
runtime needs a Linux capability and both run with a read-only root filesystem
on Kubernetes.

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
kubeconform) fan out, then image build and scan, then an ephemeral deployment
verified by an end-to-end smoke test.
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

## ADR-0015 — Deploy verification strategy

**Context.** A deployment gate should prove that the manifests and images actually
run together, not only that they pass admission, while creating no cloud
resources.

**Decision.** Stand up an ephemeral Kubernetes cluster (kind) on the CI runner and
load the images built in the same job. The dev overlay is first validated with a
server-side dry run, then applied for real; every rollout must complete, and an
end-to-end smoke test drives readiness and an item create/read/delete cycle
through the frontend origin, exercising the reverse proxy, the backend, and the
database together. On failure, pod state, events, and logs are captured as job
annotations. The cluster exists only for the job, so no provider resource is
created.

**Status.** Accepted (amended 2026-10-28). The original decision stopped at the
server-side dry run, with the namespace created first because a dry run does not
persist it. The first real deployment surfaced two defects that admission alone
could not detect: nginx exiting under its dropped capability set, and a database
readiness probe exceeding its timeout.

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

## ADR-0017 — Distributed tracing

**Context.** Metrics and structured logs are in place, but request-level causality
across the service and its database is not observable. Adding tracing must not
bloat the minimal default image or its attack surface (ADR-0004, ADR-0010).

**Decision.** Instrument FastAPI and PyMongo with OpenTelemetry and export spans
over OTLP (HTTP). Tracing is opt-in through `OTEL_ENABLED` (off by default), so
the default build produces no spans and the dependency is inert unless enabled.

**Consequences.** A modest dependency addition is accepted to complete the three
observability signals; a bundled Jaeger instance in the Compose observability
profile makes the traces inspectable locally.

**Status.** Accepted.

## ADR-0018 — Retry jitter and graceful termination

**Context.** Replicas restarted together, as in a rollout or after a node failure,
retried the database on an identical exponential schedule and reached it as
synchronized bursts. Separately, Kubernetes removes a terminating pod from its
endpoints at the same moment it sends SIGTERM, while kube-proxy and ingress
controllers observe the removal with a delay, so a pod that stops immediately
can drop requests still being routed to it.

**Decision.** Startup retries keep the capped exponential ceiling but sleep for a
uniformly random duration up to it (full jitter). Each workload pauses in a
`preStop` hook before shutdown so routing converges first; the backend uses the
native `sleep` action because its distroless image has no shell. uvicorn drains
in-flight requests for at most 20 seconds, inside a 30-second termination grace
period, so the lifespan teardown that closes the MongoDB client always runs.
nginx stops on SIGQUIT, its graceful mode, as declared by the image.

**Consequences.** A forced kill is no longer the normal termination path. The
retry schedule becomes non-deterministic, so tests pin the random draw.

**Status.** Accepted (2026-10-28).

## ADR-0019 — Request rate limiting at the reverse proxy

**Context.** The API had no protection against a single client exhausting the
backend. The usual place for that control is the ingress layer, but expressing it
as controller-specific annotations ties it to one controller, and the widely used
ingress-nginx controller has been retired upstream.

**Decision.** Enforce a per-client limit (20 requests per second, burst of 40,
rejected immediately) in the frontend nginx, the reverse proxy that already
fronts every API call. The same control then applies under Compose, on the VM
host, and on Kubernetes. Rejections return HTTP 429 with `Retry-After` and the
backend's error envelope; health probes are exempt. The CI smoke test asserts
that a concurrent burst is throttled.

**Consequences.** Clients are keyed by connection address, so behind another
proxy the key is that proxy hop and the limit caps aggregate load per hop rather
than per end user. Per-user limits belong at the external edge (a gateway or
WAF), which can see the original client address.

**Status.** Accepted (2026-10-28).

## ADR-0020 — API contract as a versioned artifact

**Context.** FastAPI generates the OpenAPI document at runtime, and production
disables its endpoint to reduce the exposed surface. Reviewers and client
authors therefore had no stable, reviewable contract, and API changes were
invisible in diffs.

**Decision.** Commit the generated document as `docs/api/openapi.json`, produced
from the application itself by `scripts/export_openapi.py`. CI regenerates it and
fails when it differs from the committed copy, so every change to the API surface
arrives with a visible contract diff.

**Consequences.** Because CI installs the newest dependency versions within the
declared ranges, a framework release that changes schema generation can fail the
check without a code change; the remedy is to regenerate and commit, which keeps
the published contract accurate.

**Status.** Accepted (2026-10-28).

## ADR-0021 — Document data model

**Context.** The domain is a catalogue of items, each a self-contained record
with a variable-length list of tags, read and written as a whole. Persistence must
be managed, replicated, and free (ADR-0003).

**Decision.** Store each item as a single MongoDB document, with tags embedded as
an array, rather than normalizing them into relational tables. Every read
resolves without a join, writes are single-document and therefore atomic without
multi-document transactions, and the schema can evolve without migrations, with
validation enforced at the API boundary by Pydantic.

**Consequences.** Atlas M0 provides a managed, replicated deployment at no cost,
satisfying ADR-0003. The domain is simple enough that a relational design would
also serve, and free managed relational tiers exist; the choice rests on
aggregate-shaped access, schema flexibility, and native asynchronous driver
support (ADR-0008), not on a claim that relational storage could not. Queries
that span items, such as reporting, would be served by the aggregation pipeline.

**Status.** Accepted (2026-10-28).
