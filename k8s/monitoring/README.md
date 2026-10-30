# Monitoring Overlay

An in-cluster monitoring plane — Prometheus for collection and alerting, Grafana
for visualization — deployed to a dedicated `monitoring` namespace. It reuses the
metrics the services already expose and the same dashboards and alert rules as
the Compose stack under [`observability/`](../../observability). CI fails if the
copies here drift from those sources.

## Layout

```
k8s/monitoring/
├── namespace.yaml
├── prometheus/
│   ├── rbac.yaml            # Read-only ServiceAccount/ClusterRole for discovery
│   ├── prometheus.yml       # Annotation-driven pod discovery + rule wiring
│   ├── alerts.yml           # SLO recordings, burn-rate, availability, and event-pipeline rules
│   ├── deployment.yaml
│   └── service.yaml
├── grafana/
│   ├── datasource.yaml          # Prometheus datasource (fixed uid)
│   ├── dashboard-provider.yaml  # File-based dashboard provider
│   ├── dashboards/
│   │   ├── microservice-overview.json
│   │   ├── event-pipeline.json
│   │   └── service-level-objectives.json
│   ├── deployment.yaml
│   └── service.yaml
└── kustomization.yaml
```

## How targets are discovered

Prometheus uses the Kubernetes API (`kubernetes_sd_configs`, pod role) and keeps
only pods carrying `prometheus.io/scrape: "true"`. The items API, outbox relay,
and audit Deployments set that annotation along with `prometheus.io/port` and
`prometheus.io/path`, so nothing is hardcoded. The `job` label is derived from
the workload's `app.kubernetes.io/name`, yielding `job="backend"`,
`job="outbox-relay"`, and `job="audit"`, the same names the Compose scrape
configuration uses, so the shared dashboards and alert rules apply without
change.

The application namespace runs a default-deny NetworkPolicy, so each service's
ingress policy in [`k8s/base/network-policies.yaml`](../base/network-policies.yaml)
explicitly permits the `monitoring` namespace on its metrics port (8000 for the
two APIs, 9000 for the relay).

## Deploy

The overlay assumes the application is already deployed (for example via
`k8s/overlays/dev`).

```bash
kubectl apply -k k8s/monitoring
```

## Access

Both services are ClusterIP. Reach them with a port-forward:

```bash
kubectl -n monitoring port-forward svc/grafana 3000:3000    # http://localhost:3000
kubectl -n monitoring port-forward svc/prometheus 9090:9090 # http://localhost:9090
```

Grafana provisions the **Microservice Overview** and **Event Pipeline**
dashboards with anonymous access; Prometheus exposes its targets and firing
alerts. Both stores
are ephemeral (`emptyDir`), sized for live inspection rather than retention.

## Rendering

```bash
kubectl kustomize k8s/monitoring
```
