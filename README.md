# Automated Cloud Architecture for MongoDB-Backed Microservices

Production-grade reference architecture for an asynchronous, MongoDB-backed
microservice — engineered for automation, resilience, security, and
observability, and delivered strictly within provider free tiers.

[![CI](https://github.com/Carlosmarroquin20/Automated-Cloud-Architecture-for-MongoDB-Backed-Microservices/actions/workflows/ci.yml/badge.svg)](https://github.com/Carlosmarroquin20/Automated-Cloud-Architecture-for-MongoDB-Backed-Microservices/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Carlosmarroquin20/Automated-Cloud-Architecture-for-MongoDB-Backed-Microservices/actions/workflows/codeql.yml/badge.svg)](https://github.com/Carlosmarroquin20/Automated-Cloud-Architecture-for-MongoDB-Backed-Microservices/actions/workflows/codeql.yml)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-multi--stage-2496ED?logo=docker&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-modular-7B42BC?logo=terraform&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Kustomize-326CE5?logo=kubernetes&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue)

## Overview

This repository demonstrates the design and delivery of a cloud-native
microservice from first commit to production topology. It targets SOC 2 and
ISO 27001 operational hygiene and aligns with the AWS Well-Architected Framework
pillars of Operational Excellence, Security, Reliability, Performance Efficiency,
and Cost Optimization.

Delivery is modular: each layer is implemented, verified, and reviewed
independently. The application, containerization, infrastructure-as-code,
orchestration, and CI/CD layers are complete; observability follows as the
final layer.

## Architecture

```mermaid
flowchart LR
    user(["Client browser"])

    subgraph edge ["Static frontend (nginx)"]
        spa["Vite + TypeScript client"]
    end

    subgraph svc ["FastAPI microservice"]
        api["Async REST API (/api/v1)"]
        health["Health probes (/health/*)"]
    end

    db[("MongoDB Atlas M0 - TLS")]

    user -->|HTTPS| spa
    spa -->|"same-origin /api"| api
    spa -->|"same-origin /health"| health
    api -->|"pooled, timeouts, retries"| db
    health -.->|"readiness ping"| db
```

The frontend is served as optimized static assets behind a reverse proxy that
forwards `/api` and `/health` to the backend, so the browser issues only
same-origin requests and no backend host is embedded in the shipped assets. The
service persists to a multi-node MongoDB Atlas cluster over TLS with pooled
connections, explicit timeouts, and bounded retries.

## Technology

| Concern | Technology |
|---------|------------|
| API | Python 3.10+, FastAPI, Pydantic v2, PyMongo (async client) |
| Frontend | TypeScript, Vite — framework-free, zero runtime dependencies |
| Database | MongoDB Atlas (M0 free tier, TLS-only) |
| Backend quality | ruff, mypy (`--strict`), pytest |
| Frontend quality | ESLint, tsc (strict), Vitest |
| Containers | Multi-stage Docker (distroless backend, nginx frontend), Compose |
| Infrastructure | Terraform (modular AWS, free-tier), SSM Session Manager |
| Orchestration | Kubernetes, Kustomize, HPA, NetworkPolicies |
| CI/CD | GitHub Actions (lint, test, scan, build, deploy simulation) |
| Planned | Prometheus, Grafana |

## Repository Structure

```
.
├── src/
│   ├── backend/          # Async FastAPI microservice
│   └── frontend/         # Vite + TypeScript static client
├── .github/              # CI/CD pipelines and dependency automation
├── terraform/            # Infrastructure as Code (modular AWS)
├── k8s/                  # Kubernetes manifests (Kustomize base + overlay)
├── docker-compose.yml    # Local multi-service orchestration
├── .gitattributes        # LF normalization for portable builds
└── .gitignore            # Zero-trust exclusion policy
```

## Delivery Roadmap

| Layer | Scope | Status |
|-------|-------|--------|
| 0 | Repository baseline · zero-trust ignore policy | ✅ Complete |
| 1 | Application — async FastAPI API + MongoDB persistence | ✅ Complete |
| 1 | Application — static Vite + TypeScript client | ✅ Complete |
| 2 | Containerization — multi-stage Docker, Compose | ✅ Complete |
| 3 | Infrastructure as Code — Terraform modules | ✅ Complete |
| 4 | Orchestration — Kubernetes probes, limits, policies | ✅ Complete |
| 5 | CI/CD — GitHub Actions (lint, test, scan, deploy) | ✅ Complete |
| 6 | Observability — Prometheus metrics, Grafana dashboards | ⬜ Planned |

## Getting Started

### Backend

```bash
cd src/backend
python -m venv .venv
. .venv/Scripts/activate         # Git Bash on Windows; use bin/activate on Unix
pip install -r requirements-dev.txt
cp .env.example .env             # set MONGODB_URI and MONGODB_DB_NAME
uvicorn app.main:app --reload
```

Interactive API documentation is served at `/docs` in non-production
environments. See [`src/backend/README.md`](src/backend/README.md) for details.

### Frontend

```bash
cd src/frontend
npm install
npm run dev                      # proxies /api and /health to localhost:8000
```

See [`src/frontend/README.md`](src/frontend/README.md) for details.

## Quality Gates

Every layer ships with automated verification.

| Component | Gates |
|-----------|-------|
| Backend | `ruff check` · `mypy --strict` (27 modules) · `pytest` (35 tests) |
| Frontend | `eslint` · `tsc --noEmit` (strict) · `vitest` (18 tests) · `vite build` |

The frontend production bundle is approximately 6.6 kB gzipped (JavaScript and
CSS combined). Both test suites are hermetic and require no database.

## Continuous Integration and Delivery

Every push and pull request runs a parallel quality-gate graph in GitHub Actions,
followed by container build, vulnerability scanning, and a simulated deployment.

| Stage | Tooling |
|-------|---------|
| Lint · type-check · test | ruff, mypy `--strict`, pytest (Python 3.10–3.12 matrix); ESLint, tsc, Vitest |
| IaC validation | `terraform fmt`/`validate`; Kustomize render validated with kubeconform |
| Static analysis | CodeQL (Python, TypeScript); Hadolint (Dockerfiles) |
| Supply chain | gitleaks secret scan, dependency review, Dependabot |
| Image security | Trivy configuration and image scans (results as SARIF) |
| Deploy simulation | Server-side dry run against an ephemeral kind cluster |

Tagged releases (`vX.Y.Z`) build and publish semantically versioned images to the
GitHub Container Registry with build provenance and an SBOM. All scanners surface
findings in the repository Security tab. The pipeline runs entirely on
GitHub-hosted runners within the free tier and requires no external secrets — the
registry credential is the ephemeral `GITHUB_TOKEN`.

## Engineering Principles

- **Zero-trust secrets** — no credentials, keys, or hosts in the repository;
  configuration is injected at runtime through environment variables.
- **Minimal attack surface** — a framework-free frontend and a distroless image
  target keep dependencies and exposure low.
- **Resilience** — bounded retries, explicit timeouts, and readiness gating so a
  transient database outage degrades gracefully instead of crashing.
- **Observability** — structured JSON logs with per-request correlation
  identifiers, ready for aggregation.
- **12-factor configuration** — strictly separated config, validated at startup.
- **Zero cost** — every component fits provider free tiers and open-source tools.

## License

Released under the [MIT License](LICENSE).
