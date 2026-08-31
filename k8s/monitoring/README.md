# Monitoring Overlay

An in-cluster monitoring plane — Prometheus for collection and alerting, Grafana
for visualization — deployed to a dedicated `monitoring` namespace. It reuses the
metrics the backend already exposes and the same dashboard and alert rules as the
Compose stack under [`observability/`](../../observability).

## Layout

```
k8s/monitoring/
├── namespace.yaml
├── prometheus/
│   ├── rbac.yaml            # Read-only ServiceAccount/ClusterRole for discovery
│   ├── prometheus.yml       # Annotation-driven pod discovery + rule wiring
│   ├── alerts.yml           # Availability and SLO alert rules
│   ├── deployment.yaml
│   └── service.yaml
├── grafana/
│   ├── datasource.yaml          # Prometheus datasource (fixed uid)
│   ├── dashboard-provider.yaml  # File-based dashboard provider
│   ├── dashboards/
│   │   └── microservice-overview.json
│   ├── deployment.yaml
│   └── service.yaml
└── kustomization.yaml
```

## How targets are discovered

Prometheus uses the Kubernetes API (`kubernetes_sd_configs`, pod role) and keeps
only pods carrying `prometheus.io/scrape: "true"`. The backend Deployment already
sets that annotation along with `prometheus.io/port` and `prometheus.io/path`, so
nothing is hardcoded. The `job` label is derived from the workload's
`app.kubernetes.io/name`, yielding `job="backend"` so the shared dashboard and
alert rules apply without change.

The application namespace runs a default-deny NetworkPolicy, so the backend's
ingress policy in [`k8s/base/network-policies.yaml`](../base/network-policies.yaml)
explicitly permits the `monitoring` namespace to reach port 8000.

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

Grafana opens on the provisioned **Microservice Overview** dashboard with
anonymous access; Prometheus exposes its targets and firing alerts. Both stores
are ephemeral (`emptyDir`), sized for live inspection rather than retention.

## Rendering

```bash
kubectl kustomize k8s/monitoring
```
