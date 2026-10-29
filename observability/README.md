# Observability

Metrics, alerting, and tracing for the services. The items API, the outbox
relay, and the audit service expose Prometheus metrics; Prometheus scrapes them
and evaluates alert rules, Grafana renders provisioned dashboards, and Jaeger
stores traces. All tools are open-source and run locally at no cost.

## Layout

```
observability/
├── prometheus/
│   ├── prometheus.yml     # Scrape config (three services + self) and rule wiring
│   └── alerts.yml         # Availability, SLO, and event-pipeline rules
└── grafana/
    ├── provisioning/
    │   ├── datasources/    # Prometheus datasource (fixed uid)
    │   └── dashboards/     # File-based dashboard provider
    └── dashboards/
        ├── microservice-overview.json
        └── event-pipeline.json
```

## Run

The observability plane is gated behind a Compose profile so the default stack
remains minimal.

```bash
docker compose --profile observability up --build
```

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:8080 | Application UI |
| Backend metrics | http://localhost:8000/metrics | Prometheus exposition |
| Prometheus | http://localhost:9090 | Targets, graph, alerts |
| Grafana | http://localhost:3000 | Anonymous access (local only) |
| Jaeger | http://localhost:16686 | Trace UI (when tracing is enabled) |

Grafana provisions the **Microservice Overview** and **Event Pipeline**
dashboards. Generate traffic against the API (for example through the UI) to
populate the panels; every create, update, and delete also moves an event
through the pipeline.

## Tracing

Every service is instrumented with OpenTelemetry (FastAPI and PyMongo, plus
messaging spans in the relay and the consumer) but produces spans only when
tracing is enabled, so the default footprint stays minimal. Enable it alongside
the observability profile to export spans to the bundled Jaeger collector:

```bash
OTEL_ENABLED=true docker compose --profile observability up --build
```

Generate traffic, then open Jaeger at http://localhost:16686 and pick the
`audit-service` service. A write's trace starts at the items API request
(`mongodb-microservice`), continues in the relay's `publish items.*` span
(`outbox-relay`), and ends in the consumer's `process items.*` span and its
database write (`audit-service`): the trace context travels inside the outbox
document and then in the message headers. The exporter targets
`http://jaeger:4318/v1/traces` by default; the Jaeger v2 store is in-memory,
suited to local inspection.

## Metrics

The dashboards and alerts are built on the metrics the services already export.
Items API:

| Metric | Type | Labels | Use |
|--------|------|--------|-----|
| `http_requests_total` | Counter | method, path, status | Throughput, error rate |
| `http_request_duration_seconds` | Histogram | method, path | Latency percentiles |
| `http_requests_in_progress` | Gauge | method | Saturation |
| `app_info` | Info | name, version, environment | Build metadata |

Event pipeline:

| Metric | Type | Labels | Use |
|--------|------|--------|-----|
| `outbox_events_published_total` | Counter | type | Publication rate by event type |
| `outbox_publish_failures_total` | Counter | — | Publishes retried on the next pass |
| `outbox_publish_duplicates_total` | Counter | — | Republished events JetStream discarded |
| `outbox_oldest_pending_age_seconds` | Gauge | — | Backlog age; zero when drained |
| `audit_events_consumed_total` | Counter | outcome | `recorded`, `duplicate`, `retried`, `rejected` |
| `audit_consumer_connected` | Gauge | — | 1 while bound to the stream |

Process and interpreter metrics (`process_*`, `python_*`) are exported by the
Prometheus client library and drive the resource panels.

## Alerts

Rules target client-visible symptoms and are visible in the Prometheus UI under
**Alerts**. An Alertmanager is intentionally omitted locally to keep the
footprint minimal; routing to a receiver is a deployment-time concern.

| Alert | Condition |
|-------|-----------|
| `BackendDown` | Target unscrapeable for 1m |
| `HighErrorRate` | 5xx ratio above 5% over 5m |
| `HighRequestLatencyP95` | p95 latency above 500ms over 5m |
| `EventServiceDown` | Relay or audit target unscrapeable for 1m |
| `OutboxBacklogStale` | Oldest unpublished event older than 60s for 2m |
| `OutboxPublishFailing` | Publish failures sustained for 5m |
| `AuditConsumerDisconnected` | Any audit replica unbound from the stream for 2m |
| `AuditEventsRetrying` | Events redelivered after storage failures for 5m |
| `AuditEventsRejected` | Any malformed event terminated in the last 15m |

The event-pipeline rules watch progress rather than request symptoms: when the
pipeline stalls, writes keep succeeding and only the history falls behind.
