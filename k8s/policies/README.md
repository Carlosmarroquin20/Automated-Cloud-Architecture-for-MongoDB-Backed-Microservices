# Admission Policies

Rules every workload in the project's namespaces must satisfy, enforced by the
Kubernetes API server when a workload is created or updated. Two native
mechanisms share the work, so no policy controller runs in the cluster:

- **Pod Security Admission** enforces the `restricted` profile through labels on
  the `microservice` and `monitoring` namespaces: non-root users, no privilege
  escalation, every capability dropped, the runtime's default seccomp profile,
  and no host namespaces, host ports, or host paths.
- **ValidatingAdmissionPolicy** (CEL, GA since Kubernetes 1.30) enforces what
  the profile does not cover.

| Policy | Rule | Why |
|--------|------|-----|
| `require-read-only-root-filesystem` | Every container, init containers included, sets `readOnlyRootFilesystem: true` | A compromised process cannot alter the image's binaries or configuration; writable paths are mounted explicitly |
| `require-resources` | CPU and memory requests and a memory limit on every container | Scheduling and autoscaling need requests; a memory limit confines a leak to its container. CPU limits are not required: throttling with spare capacity only adds latency |
| `require-image-digest` | Third-party images are pinned by digest | A tag can be moved after review; a digest cannot. The project's own images are exempt: the pipeline that deploys them builds them from the same commit |
| `require-probes` | Liveness and readiness probes on every container | Without them a hung process is never restarted and a rollout counts broken pods as available |
| `restrict-service-account-token` | Pods under the default service account set `automountServiceAccountToken: false` | A mounted token is an API credential; only Prometheus calls the API, under its own account with read-only RBAC |

Each policy file holds the policy and its binding. Bindings select namespaces
by the immutable `kubernetes.io/metadata.name` label, so editing a namespace's
labels cannot opt it out, and components the project does not own, in
`kube-system` for example, are never blocked.

## Apply

The policies must exist before the workloads they govern:

```bash
kubectl apply -k k8s/policies
kubectl apply -k k8s/overlays/dev
```

## Test

The tests run offline with the Kyverno CLI, which evaluates
ValidatingAdmissionPolicy CEL the way the API server does. Fixtures in
[`tests/resources.yaml`](tests/resources.yaml) include a compliant workload,
exempt ones, one violation per policy, and a workload outside the project's
namespaces:

```bash
docker run --rm -v "$PWD/k8s/policies:/policies:ro" \
  ghcr.io/kyverno/kyverno-cli:v1.19.1 test /policies/tests
```

CI runs these tests, evaluates every workload the overlays deploy against the
policies, and, in the ephemeral cluster, submits the same fixtures to the API
server: compliant ones must be admitted and each violation refused by its own
policy, and a pod running as root must be refused by Pod Security Admission.
