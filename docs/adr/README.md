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
| 0013 | Container registry and release model | Accepted (amended) |
| 0014 | GitHub Actions pinning strategy | Superseded by SHA pinning |
| 0015 | Deploy verification strategy | Accepted (amended twice) |
| 0016 | Observability stack and topology | Accepted |
| 0017 | Distributed tracing | Accepted (amended) |
| 0018 | Retry jitter and graceful termination | Accepted |
| 0019 | Request rate limiting at the reverse proxy | Accepted |
| 0020 | API contract as a versioned artifact | Accepted |
| 0021 | Document data model | Accepted (amended) |
| 0022 | Event-driven integration through a transactional outbox | Accepted |
| 0023 | Message broker | Accepted |
| 0024 | Idempotent consumer and settlement policy | Accepted |
| 0025 | Database per service | Accepted |
| 0026 | Event contract as a checked artifact | Accepted |
| 0027 | Trace context across the asynchronous boundary | Accepted |
| 0028 | Broker outage as a verified failure mode | Accepted |

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

**Status.** Accepted (amended 2026-10-28). The services expose their version at
runtime, and before `v1.0.2` they reported `0.1.0` in every release. The
release workflow now refuses to publish a component whose declared version
differs from the tag, and the release notes reference the bare semantic image
tags (`1.0.2`), which is what the registry holds; earlier notes pointed to
`v`-prefixed tags that were never published.

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

Amended again with the event pipeline (ADR-0022): the deployment also runs the
broker, the outbox relay, the audit service, and a trace collector. After the
smoke test, which reads the item's history back through the audit service, the
job asserts that the outbox holds exactly the two expected events, all
published; that the stream holds exactly those two messages; that the audit
consumer has acknowledged both; and that each event produced one trace linking
the originating request, the publish, and the consumption (ADR-0027).

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

**Status.** Accepted (amended 2026-10-28). The bundled collector moved from the
retired Jaeger v1 all-in-one image to Jaeger v2, pinned by digest, which also
serves the Kubernetes dev overlay. Tracing now spans process boundaries
(ADR-0027).

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

**Status.** Accepted (amended 2026-10-28). The original text held that writes
need no multi-document transactions. That remains true of the item itself, but
each write now also records an event in the outbox collection, and the two
writes commit in one transaction (ADR-0022). Transactions require a replica set:
Atlas clusters, including M0, are replica sets, and the local and in-cluster
development servers run as single-member replica sets for the same reason.

## ADR-0022 — Event-driven integration through a transactional outbox

**Context.** A second service needs to react to every item change. A
synchronous call from the items API would couple its availability and latency
to that service. Publishing to a broker directly from the request handler is a
dual write: a crash, or a broker outage, between the database commit and the
publish loses the event, and publishing first can announce a change that is
then rolled back. Deriving events from MongoDB change streams avoids the dual
write but makes the published contract follow the storage schema rather than a
deliberate domain decision.

**Decision.** Each create, update, and delete writes the state change and a
CloudEvents 1.0 event to an `outbox` collection in one MongoDB transaction. A
separate relay process, built from the same image, publishes pending events to
the broker oldest first, stops a batch at the first failure so events for an
item never overtake each other, and marks each event published only after the
broker acknowledges it. Events carry the full item state, so consumers need no
callback. Published events expire after seven days through a TTL index;
unpublished events never expire.

**Consequences.** A change is never persisted without its event, and no event
describes a change that did not commit. Delivery is at-least-once, because a
crash after publishing and before marking republishes the event; the broker's
duplicate window and idempotent consumers (ADR-0024) absorb this. Consumers see
changes after a short delay, so the history is eventually consistent. The relay
runs as a single replica with a heartbeat-file liveness probe; a second replica
would stay correct but only publish duplicates. Its backlog age is exported as
a metric and alerted on.

**Status.** Accepted (2026-10-28).

## ADR-0023 — Message broker

**Context.** The outbox needs a broker that persists messages, deduplicates
republished events, supports durable consumers with explicit acknowledgement,
and allows replay. It must run at no cost on free-tier compute (a 1 GiB
instance under ADR-0011) next to the rest of the stack, and in an ephemeral CI
cluster.

**Decision.** Use NATS with JetStream: one stream (`ITEMS`) over the subjects
`items.>`, file storage, limits-based retention with a seven-day maximum age,
and a 120-second duplicate window keyed by the `Nats-Msg-Id` header, which
carries the event id. The server is a single static binary started with explicit
flags, pinned by digest, and runs non-root with a read-only root filesystem.

**Consequences.** The broker fits the memory budget with room to spare; Apache
Kafka was not chosen because its broker processes need far more memory than the
budget allows, and its strengths (partitioned throughput, a large connector
ecosystem) are not needs of this system. RabbitMQ would also fit, but
JetStream provides publish deduplication, durable pull consumers, and replay
from one component. The stream runs one replica; a production deployment would
run a three-node cluster with stream replication, a configuration change rather
than a design change. The event contract (ADR-0026) does not depend on the
broker, so it could be replaced without changing producers' or consumers'
payloads.

**Status.** Accepted (2026-10-28).

## ADR-0024 — Idempotent consumer and settlement policy

**Context.** At-least-once delivery (ADR-0022) means a consumer can receive an
event more than once: after a relay crash, after a redelivery, or when two
replicas race. A consumer that cannot tell success from a duplicate, or a
transient failure from a permanent one, either corrupts its data or retries a
poison message forever.

**Decision.** The audit service writes each event under its event id as the
document key, so a repeated event fails the uniqueness check and is
acknowledged as a duplicate. Every message is settled explicitly: acknowledged
when recorded or already recorded; terminated when malformed, because it would
fail identically on every delivery; and negatively acknowledged with a delay of
1, 2, 4, 8 … seconds (capped at 30) when the database rejects the write, for at
most five deliveries. Replicas share one durable pull consumer, so each message
is processed by one replica at a time, and the history is ordered by event time
rather than arrival order.

**Consequences.** Processing is effectively once while delivery stays
at-least-once. A storage outage longer than the retry budget drops events from
the history; this is reported by a metric and an alert rather than blocking the
stream, and the stream's seven-day retention allows those events to be replayed
by resetting the consumer. Rejected events signal a contract mismatch and also
alert.

**Status.** Accepted (2026-10-28).

## ADR-0025 — Database per service

**Context.** The audit service could read the items collection directly, or
share the items database. Either would couple the two services' schemas,
releases, and failure modes, and let one service's credential reach the other's
data.

**Decision.** The audit service owns an `audit` database, reached through its
own connection string in its own Secret (`audit-mongodb-credentials`), so it
can be granted access to that database only. It never reads the items data and
never calls the items API; its state is built entirely from events. Its
readiness depends on its database alone, so the history API stays available
while the broker is unreachable.

**Consequences.** Each service can change its storage independently, and a
compromised credential exposes one database. The audit service holds a copy of
item state as of each event, which is the intended content of a history. On the
free tier both databases share one M0 cluster; isolation is by database and
credential, not by hardware. Locally and in the dev overlay both connection
strings point at the same credential-free server.

**Status.** Accepted (2026-10-28).

## ADR-0026 — Event contract as a checked artifact

**Context.** The REST contract is generated from code and checked for drift
(ADR-0020). The events have no equivalent generator, so a hand-written contract
would drift silently as the producer evolves, and consumers would discover
changes only when their validation failed in production.

**Decision.** Describe the events in AsyncAPI 3.0 as
`docs/api/asyncapi.yaml`: the server, one channel per event type, the
publishing and consuming operations, the CloudEvents envelope, the headers
including the trace context, and the item state. Backend tests hold the
document to the producer: every event type must have a channel on the subject
the relay uses, and the envelope, headers, and item state the relay actually
publishes must match the declared schemas field for field. Consumers validate
only what they rely on and ignore the rest, so adding an attribute is a
compatible change.

**Consequences.** A change to the published events fails CI until the contract
changes with it, so every event change arrives with a reviewable contract diff.
The tests check structure and constants, not full JSON Schema validation, which
keeps the test dependencies to a YAML parser.

**Status.** Accepted (2026-10-28).

## ADR-0027 — Trace context across the asynchronous boundary

**Context.** With an outbox between them, the request that changes an item and
the processing of the resulting event happen in different processes and at
different times. Without propagation, each appears as an unrelated trace, and
the delay between a change and its consumption cannot be attributed.

**Decision.** The W3C `traceparent` of the active request is stored in the
outbox document with the event. The relay starts a producer span as a child of
that stored context and sends its own context in the message headers; the
consumer starts its processing span as a child of the header context. One trace
therefore links the request, the publish, and the consumption. The relay's
polling reads are excluded from tracing, because they repeat every interval and
have no causal link to any request. Tracing stays off in the base manifests; the
dev overlay runs a collector and enables it, and the CI deployment asserts that
each event's trace contains the request, publish, and consumer spans in
parent-child order.

**Consequences.** The trace context leaves the CloudEvents payload, which
carries domain data only, and travels as a header. With tracing disabled the
stored context is forwarded unchanged, so enabling tracing on one service later
still joins existing chains.

**Status.** Accepted (2026-10-28).

## ADR-0028 — Broker outage as a verified failure mode

**Context.** The outbox (ADR-0022) and the idempotent consumer (ADR-0024)
promise that a broker outage delays events but never loses or duplicates them,
and the event-pipeline alerts promise to report such an outage. Every check so
far exercised the healthy path only, so those promises were stated, not shown.

**Decision.** Treat a broker outage as a failure mode that is injected and
verified. The CI deployment removes the NATS StatefulSet while the API takes
writes and asserts that every write still succeeds, that the events wait in the
outbox, and that the audit consumer reports itself unbound; after the broker
returns, the outbox must drain and the outbox, the stream, and the audit history
must hold the same number of events with nothing pending or awaiting
acknowledgement. The alert rules carry `promtool` unit tests that replay an
outage and its recovery.

**Consequences.** A live four-minute outage under traffic, run before this
decision, confirmed the guarantees: 327 events waited in the outbox, the backlog
drained 20 seconds after the broker returned, and 440 new events ended in the
outbox, the stream, and the audit history alike; the broker also discarded one
republished event by its message id. The same run exposed two defects that
healthy-path checks could not: the consumer reported itself bound throughout
the outage, because a reconnecting client raises nothing and its fetches only
time out, so its binding state now follows the client's connection events; and
`OutboxPublishFailing`, with a five-minute window and hold, fired only after
recovery and lingered five minutes, so it now uses a one-minute window and a
two-minute hold.

**Status.** Accepted (2026-10-29).
