# Kubernetes Manifests

Kustomize-based manifests that orchestrate the stack with rolling updates,
resource governance, health probes, autoscaling, a zero-trust network posture,
and Kubernetes-native secret handling.

## Layout

```
k8s/
├── base/                 # Environment-agnostic manifests
│   ├── namespace, configmap, secret.example
│   ├── backend-deployment, backend-service, backend-hpa
│   ├── outbox-relay-deployment   # Publishes outbox events (single replica)
│   ├── nats                      # JetStream StatefulSet + Service
│   ├── audit                     # Audit service ConfigMap, Deployment, Service
│   ├── frontend-deployment, frontend-service, ingress
│   ├── pdb, network-policies
│   └── kustomization.yaml
├── overlays/
│   └── dev/             # Self-contained stack: in-cluster MongoDB replica set,
│                        # Jaeger, and tracing enabled for all services
└── monitoring/          # In-cluster Prometheus + Grafana (own namespace)
```

## Event pipeline

The items API writes each change and its event to MongoDB in one transaction;
the `outbox-relay` Deployment publishes pending events to the `nats`
StatefulSet (JetStream, file storage on a PersistentVolumeClaim), and the
`audit` Deployment consumes them. The relay runs one replica with the `Recreate`
strategy, so two relays never overlap during a rollout; its liveness probe checks
a heartbeat file, because a worker has no HTTP endpoint to probe. The two audit
replicas share one durable consumer.

Network policies admit only the flows the pipeline needs: the relay and the
audit service to NATS on 4222, both to MongoDB, the frontend to the audit
service on 8000, and the monitoring namespace to each service's metrics port.
NATS initiates no connections, so its egress stays denied.

## Monitoring

An optional in-cluster monitoring plane (Prometheus + Grafana) lives under
[`monitoring/`](monitoring) in its own `monitoring` namespace. Prometheus
discovers the items API, the relay, and the audit service through their scrape
annotations; each service's ingress policy permits the monitoring namespace on
its metrics port. See [`monitoring/README.md`](monitoring/README.md).

```bash
kubectl apply -k k8s/monitoring
```

## Deploy

### Production-style (external MongoDB Atlas)

The base expects two Secrets, one per service, so each can hold a credential
scoped to its own database; neither is ever committed.

```bash
kubectl create namespace microservice
kubectl -n microservice create secret generic mongodb-credentials \
  --from-literal=mongodb-uri='mongodb+srv://<user>:<password>@<cluster-host>/...'
kubectl -n microservice create secret generic audit-mongodb-credentials \
  --from-literal=mongodb-uri='mongodb+srv://<audit-user>:<password>@<cluster-host>/...'
kubectl apply -k k8s/base
```

### Local (in-cluster MongoDB, for example kind or minikube)

The dev overlay adds a MongoDB StatefulSet, initiated as a single-member
replica set because the outbox needs transactions, and credential-free Secrets
for both services, so no Atlas cluster is required. It also runs Jaeger and
enables tracing in every service.

```bash
# Load the locally built images into the cluster first (kind example):
kind load docker-image mongodb-microservice-backend:latest
kind load docker-image mongodb-microservice-frontend:latest
kind load docker-image mongodb-microservice-audit:latest

kubectl apply -k k8s/overlays/dev
kubectl -n microservice port-forward svc/jaeger 16686:16686   # trace UI
```

This is what CI deploys on every push; see the `deploy-sim` job in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

An ingress controller (for example ingress-nginx) exposes the frontend on the
`microservice.local` host.

## Rendering

```bash
kubectl kustomize k8s/base
kubectl kustomize k8s/overlays/dev
```
