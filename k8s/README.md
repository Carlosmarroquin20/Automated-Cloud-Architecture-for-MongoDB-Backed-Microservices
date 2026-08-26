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
│   ├── frontend-deployment, frontend-service, ingress
│   ├── pdb, network-policies
│   └── kustomization.yaml
└── overlays/
    └── dev/              # Self-contained local stack with an in-cluster MongoDB
```

## Deploy

### Production-style (external MongoDB Atlas)

The base expects a `mongodb-credentials` Secret to exist; it is never committed.

```bash
kubectl create namespace microservice
kubectl -n microservice create secret generic mongodb-credentials \
  --from-literal=mongodb-uri='mongodb+srv://<user>:<password>@<cluster-host>/...'
kubectl apply -k k8s/base
```

### Local (in-cluster MongoDB, for example kind or minikube)

The dev overlay adds a MongoDB StatefulSet and a credential-free Secret, so no
Atlas cluster is required.

```bash
# Load the locally built images into the cluster first (kind example):
kind load docker-image mongodb-microservice-backend:latest
kind load docker-image mongodb-microservice-frontend:latest

kubectl apply -k k8s/overlays/dev
```

An ingress controller (for example ingress-nginx) exposes the frontend on the
`microservice.local` host.

## Rendering

```bash
kubectl kustomize k8s/base
kubectl kustomize k8s/overlays/dev
```
