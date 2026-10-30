# Architecture (C4 model)

The system is described at the first three levels of the
[C4 model](https://c4model.com/): system context, containers, and the components
of the two services, followed by a dynamic view of one change travelling from
the API to the audit history. The diagrams are Mermaid source, versioned with
the code they describe and rendered natively by GitHub.

Delivery (the CI/CD pipeline, image publication, and the Kubernetes runtime
topology) is covered by the diagram in the [README](../README.md#architecture),
the reasoning behind each choice by the
[architecture decision records](adr/README.md), and the interfaces by the
[REST contract](api/openapi.json) and the [event contract](api/asyncapi.yaml).

## Level 1 — System context

Who uses the platform and which external systems it depends on.

```mermaid
C4Context
  title System context: MongoDB-backed microservice platform

  Person(user, "End user", "Manages items through the web client")
  Person(operator, "Operator", "Deploys, monitors, and troubleshoots the platform")

  System(platform, "Microservice platform", "Serves the web client, the versioned items REST API, and each item's change history")

  System_Ext(atlas, "MongoDB Atlas", "Managed M0 replica set, TLS only")
  System_Ext(github, "GitHub", "CI/CD pipeline and container registry (GHCR)")

  Rel(user, platform, "Uses", "HTTPS")
  Rel(operator, platform, "Observes", "Dashboards, alerts, traces")
  Rel(platform, atlas, "Reads and writes items, events, and history", "MongoDB protocol over TLS")
  Rel(github, platform, "Delivers signed images to", "OCI")

  UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Level 2 — Containers

The deployable units inside the platform boundary. Item changes reach the audit
service only as events: the items API commits each change together with an
outbox event, the relay publishes it to JetStream, and the audit service
consumes it into its own database. The observability plane runs behind a
Compose profile locally and as a separate Kustomize overlay on Kubernetes; in
the `dev` overlay an in-cluster MongoDB replaces Atlas and Jaeger is enabled.

```mermaid
C4Container
  title Containers: MongoDB-backed microservice platform

  Person(user, "End user", "Browser")

  System_Boundary(platform, "Microservice platform") {
    Container(web, "Web frontend", "nginx (unprivileged), Vite + TypeScript bundle", "Serves static assets; same-origin reverse proxy for both APIs; per-client rate limit")
    Container(api, "Items API", "Python, FastAPI, PyMongo async", "Versioned REST API; writes each change and its event in one transaction")
    Container(relay, "Outbox relay", "Python worker, same image as the API", "Publishes committed outbox events, oldest first")
    ContainerQueue(nats, "NATS JetStream", "NATS 2.15", "Stream ITEMS: items.>, file storage, 7-day retention, deduplication")
    Container(audit, "Audit service", "Python, FastAPI, nats-py", "Consumes item events idempotently; serves item history")
    Container(obs, "Observability", "Prometheus, Grafana, Jaeger", "Metrics, alerts, dashboards, traces")
  }

  System_Boundary(atlas, "MongoDB Atlas (M0 replica set, TLS)") {
    ContainerDb(itemsdb, "Items database", "MongoDB", "items and outbox collections")
    ContainerDb(auditdb, "Audit database", "MongoDB", "history collection, own credential")
  }

  Rel(user, web, "Uses", "HTTPS")
  Rel(web, api, "Proxies /api and /health", "HTTP")
  Rel(web, audit, "Proxies /api/v1/audit", "HTTP")
  Rel(api, itemsdb, "Item and outbox writes in one transaction", "TLS")
  Rel(relay, itemsdb, "Reads pending events, marks them published", "TLS")
  Rel(relay, nats, "Publishes CloudEvents", "NATS")
  Rel(audit, nats, "Pulls from durable consumer", "NATS")
  Rel(audit, auditdb, "Records history", "TLS")
  Rel(obs, api, "Scrapes metrics, receives spans")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Level 3 — Components of the items API

How a request flows through the service. Middleware wraps every route; the
repositories are the only components that issue database operations, and every
write goes through a transaction that also records its event.

```mermaid
C4Component
  title Components: Items API

  Container(web, "Web frontend", "nginx", "Reverse proxy")
  ContainerDb(mongo, "MongoDB", "Atlas or in-cluster", "items and outbox collections")
  Container(prom, "Prometheus", "Prometheus", "Metrics scraper")

  Container_Boundary(api, "Items API") {
    Component(mw, "Request middleware", "Starlette middleware", "Assigns the correlation id; records request count, latency, and in-flight gauges")
    Component(items, "Items router", "FastAPI router, /api/v1", "CRUD with tag and name filtering and pagination")
    Component(health, "Health router", "FastAPI router", "Liveness and readiness (database ping)")
    Component(metrics, "Metrics endpoint", "prometheus-client", "Exposes /metrics")
    Component(errors, "Error handlers", "FastAPI exception handlers", "Uniform error envelope without internal detail")
    Component(repo, "Item repository", "PyMongo async", "Queries, indexes, document mapping; one transaction per write")
    Component(outbox, "Outbox", "PyMongo async", "Builds CloudEvents with the trace context; pending and TTL indexes")
    Component(conn, "Connection manager", "AsyncMongoClient", "Timeouts, pooling, and startup retries with jittered backoff")
  }

  Rel(web, mw, "Forwards requests", "HTTP")
  Rel(mw, items, "Dispatches")
  Rel(mw, health, "Dispatches")
  Rel(items, repo, "Uses")
  Rel(items, errors, "Raises domain errors to")
  Rel(health, conn, "Pings through")
  Rel(repo, outbox, "Records the event in the same transaction")
  Rel(repo, conn, "Obtains the database from")
  Rel(conn, mongo, "Connects to", "MongoDB protocol")
  Rel(prom, metrics, "Scrapes", "HTTP")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Level 3 — Components of the audit service

The consumer and the HTTP API share one process and one repository. The
consumer runs as a background task whose failures never affect the API's
readiness.

```mermaid
C4Component
  title Components: Audit service

  Container(web, "Web frontend", "nginx", "Reverse proxy")
  ContainerQueue(nats, "NATS JetStream", "NATS", "Streams ITEMS and AUDIT_DEAD_LETTERS")
  ContainerDb(auditdb, "Audit database", "MongoDB", "history collection")

  Container_Boundary(audit, "Audit service") {
    Component(consumer, "Audit consumer", "nats-py pull subscription", "Binds the durable consumer; reconnects with jittered backoff")
    Component(handler, "Event handler", "Pydantic", "Validates the envelope; settles each message: ack, term, or delayed nak")
    Component(repo, "Audit repository", "PyMongo async", "Inserts keyed by event id; history ordered by event time")
    Component(api, "History API", "FastAPI router", "GET /api/v1/audit/items/{id}/events; health; metrics")
    Component(replay, "Dead-letter replay", "Operator command", "python3 -m app.replay: records abandoned events, removes their dead letters")
  }

  Rel(consumer, nats, "Fetches batches", "NATS")
  Rel(consumer, handler, "Dispatches each message")
  Rel(handler, repo, "Records")
  Rel(web, api, "Forwards requests", "HTTP")
  Rel(api, repo, "Reads history")
  Rel(repo, auditdb, "Reads and writes", "MongoDB protocol")
  Rel(replay, nats, "Reads dead letters and their events", "NATS")
  Rel(replay, repo, "Records")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Dynamic view — one change, end to end

A create request as it travels to the history. Steps 1 to 4 are synchronous and
answer the client; the rest happens afterwards, within about a second when the
pipeline is healthy. The trace context written in step 3 is what lets one trace
cover every step.

```mermaid
sequenceDiagram
  autonumber
  actor U as Client
  participant W as Web frontend
  participant A as Items API
  participant D as Items database
  participant R as Outbox relay
  participant N as NATS JetStream
  participant C as Audit service
  participant H as Audit database

  U->>W: POST /api/v1/items
  W->>A: proxy
  A->>D: transaction: insert item + insert outbox event (with traceparent)
  A-->>U: 201 Created
  loop every poll interval
    R->>D: find pending events, oldest first
  end
  R->>N: publish items.created (Nats-Msg-Id = event id, traceparent)
  N-->>R: ack (duplicate flag)
  R->>D: set published_at
  C->>N: fetch batch (durable consumer)
  N-->>C: items.created
  C->>H: insert history entry keyed by event id
  C->>N: ack
```
