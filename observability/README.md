# Observability

Metrics, alerting, and tracing for the services. The items API, the outbox
relay, and the audit service expose Prometheus metrics; Prometheus scrapes them
and evaluates alert rules, Grafana renders provisioned dashboards, and Jaeger
stores traces. All tools are open-source and run locally at no cost.

## Layout

```
observability/
├── blackbox/
│   └── blackbox.yml       # Synthetic prober configuration
├── prometheus/
│   ├── prometheus.yml     # Scrape config (three services + self) and rule wiring
│   ├── alerts.yml         # SLO recordings, burn-rate, availability, and event-pipeline rules
│   └── alerts.test.yml    # promtool unit tests for the rules
└── grafana/
    ├── provisioning/
    │   ├── datasources/    # Prometheus datasource (fixed uid)
    │   └── dashboards/     # File-based dashboard provider
    └── dashboards/
        ├── microservice-overview.json
        ├── event-pipeline.json
        └── service-level-objectives.json
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

Grafana provisions the **Microservice Overview**, **Event Pipeline**, and
**Service Level Objectives** dashboards. Generate traffic against the API (for example through the UI) to
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
| `audit_dead_letters` | Gauge | — | Abandoned events awaiting replay |

Process and interpreter metrics (`process_*`, `python_*`) are exported by the
Prometheus client library and drive the resource panels.

## Service Level Objectives

The items API has two objectives over a rolling 30-day period, measured on its
versioned `/api/` routes only (probes and scrapes are not client traffic):

| Objective | Indicator | Error budget |
|-----------|-----------|--------------|
| Availability 99.5% | Requests answered without a 5xx status | 0.5% of requests |
| Latency 99% | Requests completed within 500ms | 1% of requests |

Recording rules (`slo:api_errors:ratio_rate*`, `slo:api_slow_requests:ratio_rate*`)
compute each ratio once per window, from five minutes to 30 days, and the
remaining budget (`slo:api_*:error_budget_remaining`). The alerts follow the
multiwindow, multi-burn-rate method of the Google SRE Workbook. The burn rate is
the error ratio divided by the budget: at 1 the budget lasts exactly 30 days.

| Severity | Burn rate | Long window | Short window | Budget spent before alerting |
|----------|-----------|-------------|--------------|------------------------------|
| critical (page) | 14.4 | 1h | 5m | 2% |
| critical (page) | 6 | 6h | 30m | 5% |
| warning (ticket) | 3 | 1d | 2h | 10% |
| warning (ticket) | 1 | 3d | 6h | 10% |

The long window shows the burn is significant; the short window ends the alert
soon after the burn stops. Prometheus keeps 31 days locally so the 30-day
windows are complete.

### Measured from outside

The indicators above come from the backend's own counters, so they cannot see a
request that never reaches it: while readiness withdraws every pod, the reverse
proxy answers alone and the backend records nothing. A blackbox exporter therefore
sends a request through the proxy every 15 seconds to the items API, the audit API,
and the web client. `probe_success` for the items API feeds a third objective,
99.5% of probes succeeding, with the same budget and burn-rate thresholds
(`slo:api_edge_errors:ratio_rate*`, `ApiEdgeAvailabilityBudgetBurn*`).

| Service-side alert | Edge alert | Meaning |
|--------------------|------------|---------|
| Firing | Firing | The backend answers with errors |
| Silent | Firing | Requests are not reaching the backend |
| Firing | Silent | Failures on routes or methods the read-only probe does not exercise |

The probes count as traffic in the service-side indicators, about four requests a
minute. That keeps those ratios defined while the service is idle. Because they
are reads, they do not exercise the write path, which only the service-side
indicators cover.

## Alerts

Rules target client-visible symptoms and are visible in the Prometheus UI under
**Alerts**. An Alertmanager is intentionally omitted locally to keep the
footprint minimal; routing to a receiver is a deployment-time concern.

The rules are unit-tested in [`prometheus/alerts.test.yml`](prometheus/alerts.test.yml):
synthetic series are fed through them and the expected alerts asserted:
an outage at low traffic, where an earlier error-ratio rule understated the
ratio and stayed silent, with probe traffic that must not dilute it; a page
that clears once the burn stops; and a modest error rate sustained for a day
that opens a ticket without paging. CI runs the tests with
the same pinned Prometheus image Compose uses:

```bash
docker run --rm --entrypoint promtool -v "$PWD/observability/prometheus:/etc/prometheus:ro" \
  prom/prometheus:v2.53.1 test rules /etc/prometheus/alerts.test.yml
```

| Alert | Condition |
|-------|-----------|
| `BackendDown` | Target unscrapeable for 1m |
| `ApiAvailabilityBudgetBurnFast` | Availability budget burning at 14.4x (1h and 5m) or 6x (6h and 30m) |
| `ApiAvailabilityBudgetBurnSlow` | Availability budget burning at 3x (1d and 2h) or 1x (3d and 6h) |
| `ApiLatencyBudgetBurnFast` | Latency budget burning at 14.4x (1h and 5m) or 6x (6h and 30m) |
| `ApiLatencyBudgetBurnSlow` | Latency budget burning at 3x (1d and 2h) or 1x (3d and 6h) |
| `EventServiceDown` | Relay or audit target unscrapeable for 1m |
| `OutboxBacklogStale` | Oldest unpublished event older than 60s for 2m |
| `OutboxPublishFailing` | Publish failures in each 1m window for 2m |
| `AuditConsumerDisconnected` | Any audit replica unbound from the stream for 2m |
| `AuditEventsRetrying` | Events redelivered after storage failures for 5m |
| `AuditEventsRejected` | Any malformed event terminated in the last 15m |
| `AuditDeadLetters` | Any dead letter not yet replayed or discarded |
| `ApiEdgeAvailabilityBudgetBurnFast` | Probes failing at 14.4x (1h and 5m) or 6x (6h and 30m) of the budget |
| `ApiEdgeAvailabilityBudgetBurnSlow` | Probes failing at 3x (1d and 2h) or 1x (3d and 6h) of the budget |
| `EdgeProbeFailing` | The audit API or web client probe failing for 2m |
| `EdgeProberDown` | Prober unreachable for 2m, so the edge objective is not measured |

The event-pipeline rules watch progress rather than request symptoms: when the
pipeline stalls, writes keep succeeding and only the history falls behind.
