# Observability

Metrics collection and visualization for the microservice. The backend exposes
application metrics on `/metrics`; Prometheus scrapes them and Grafana renders a
provisioned dashboard. Both tools are open-source and run locally at no cost.

## Layout

```
observability/
├── prometheus/
│   ├── prometheus.yml     # Scrape config (backend + self) and rule file wiring
│   └── alerts.yml         # Availability and SLO alerting rules
└── grafana/
    ├── provisioning/
    │   ├── datasources/    # Prometheus datasource (fixed uid)
    │   └── dashboards/     # File-based dashboard provider
    └── dashboards/
        └── microservice-overview.json
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

Grafana opens directly on the **Microservice Overview** dashboard. Generate
traffic against the API (for example through the UI) to populate the panels.

## Metrics

The dashboard and alerts are built on the metrics the backend already exports:

| Metric | Type | Labels | Use |
|--------|------|--------|-----|
| `http_requests_total` | Counter | method, path, status | Throughput, error rate |
| `http_request_duration_seconds` | Histogram | method, path | Latency percentiles |
| `http_requests_in_progress` | Gauge | method | Saturation |
| `app_info` | Info | name, version, environment | Build metadata |

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
