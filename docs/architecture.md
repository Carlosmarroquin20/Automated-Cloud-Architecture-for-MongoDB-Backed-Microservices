# Architecture (C4 model)

The system is described at the first three levels of the
[C4 model](https://c4model.com/): system context, containers, and the components
of the items API. The diagrams are Mermaid source, versioned with the code they
describe and rendered natively by GitHub.

Delivery (the CI/CD pipeline, image publication, and the Kubernetes runtime
topology) is covered by the diagram in the [README](../README.md#architecture),
and the reasoning behind each choice by the
[architecture decision records](adr/README.md).

## Level 1 — System context

Who uses the platform and which external systems it depends on.

```mermaid
C4Context
  title System context: MongoDB-backed microservice platform

  Person(user, "End user", "Manages items through the web client")
  Person(operator, "Operator", "Deploys, monitors, and troubleshoots the platform")

  System(platform, "Microservice platform", "Serves the web client and the versioned items REST API")

  System_Ext(atlas, "MongoDB Atlas", "Managed M0 replica set, TLS only")
  System_Ext(github, "GitHub", "CI/CD pipeline and container registry (GHCR)")

  Rel(user, platform, "Uses", "HTTPS")
  Rel(operator, platform, "Observes", "Dashboards, alerts, traces")
  Rel(platform, atlas, "Reads and writes items", "MongoDB protocol over TLS")
  Rel(github, platform, "Delivers signed images to", "OCI")

  UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Level 2 — Containers

The deployable units inside the platform boundary. The observability plane runs
behind a Compose profile locally and as a separate Kustomize overlay on
Kubernetes; in the `dev` overlay an in-cluster MongoDB replaces Atlas.

```mermaid
C4Container
  title Containers: MongoDB-backed microservice platform

  Person(user, "End user", "Browser")

  System_Boundary(platform, "Microservice platform") {
    Container(web, "Web frontend", "nginx (unprivileged), Vite + TypeScript bundle", "Serves static assets; same-origin reverse proxy for /api and /health; per-client rate limit")
    Container(api, "Items API", "Python, FastAPI, PyMongo async", "Versioned REST API, health probes, Prometheus metrics, OpenTelemetry spans")
    Container(prom, "Prometheus", "Prometheus", "Scrapes metrics and evaluates alert rules")
    Container(graf, "Grafana", "Grafana", "Provisioned service dashboard")
    Container(jaeger, "Jaeger", "Jaeger all-in-one", "Stores and visualizes traces (opt-in)")
  }

  System_Ext(atlas, "MongoDB Atlas", "M0 replica set, TLS only")

  Rel(user, web, "Uses", "HTTPS")
  Rel(web, api, "Proxies API and health calls", "HTTP")
  Rel(api, atlas, "Reads and writes items", "MongoDB protocol over TLS")
  Rel(prom, api, "Scrapes /metrics", "HTTP")
  Rel(graf, prom, "Queries", "PromQL")
  Rel(api, jaeger, "Exports spans", "OTLP over HTTP")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Level 3 — Components of the items API

How a request flows through the service. Middleware wraps every route; the
repository is the only component that issues database operations.

```mermaid
C4Component
  title Components: Items API

  Container(web, "Web frontend", "nginx", "Reverse proxy")
  ContainerDb(mongo, "MongoDB", "Atlas or in-cluster", "items collection")
  Container(prom, "Prometheus", "Prometheus", "Metrics scraper")

  Container_Boundary(api, "Items API") {
    Component(mw, "Request middleware", "Starlette middleware", "Assigns the correlation id; records request count, latency, and in-flight gauges")
    Component(items, "Items router", "FastAPI router, /api/v1", "CRUD with tag and name filtering and pagination")
    Component(health, "Health router", "FastAPI router", "Liveness and readiness (database ping)")
    Component(metrics, "Metrics endpoint", "prometheus-client", "Exposes /metrics")
    Component(errors, "Error handlers", "FastAPI exception handlers", "Uniform error envelope without internal detail")
    Component(repo, "Item repository", "PyMongo async", "Queries, indexes, and document mapping")
    Component(conn, "Connection manager", "AsyncMongoClient", "Timeouts, pooling, and startup retries with jittered backoff")
  }

  Rel(web, mw, "Forwards requests", "HTTP")
  Rel(mw, items, "Dispatches")
  Rel(mw, health, "Dispatches")
  Rel(items, repo, "Uses")
  Rel(items, errors, "Raises domain errors to")
  Rel(health, conn, "Pings through")
  Rel(repo, conn, "Obtains the database from")
  Rel(conn, mongo, "Connects to", "MongoDB protocol")
  Rel(prom, metrics, "Scrapes", "HTTP")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```
