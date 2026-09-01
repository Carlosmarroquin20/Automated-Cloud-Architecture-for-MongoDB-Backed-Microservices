# Contributing

Thank you for your interest in improving this project. This guide describes the
development workflow and the quality gates every change is expected to meet.

## Repository layout

| Path | Contents |
|------|----------|
| `src/backend/` | Asynchronous FastAPI microservice |
| `src/frontend/` | Vite + TypeScript static client |
| `terraform/` | Modular AWS infrastructure as code |
| `k8s/` | Kustomize base, dev overlay, monitoring overlay |
| `observability/` | Prometheus and Grafana configuration |
| `.github/` | CI/CD workflows and dependency automation |

## Development setup

### Backend

```bash
cd src/backend
python -m venv .venv
. .venv/Scripts/activate          # Git Bash on Windows; use bin/activate on Unix
pip install -r requirements-dev.txt
cp .env.example .env               # set MONGODB_URI and MONGODB_DB_NAME
uvicorn app.main:app --reload
```

### Frontend

```bash
cd src/frontend
npm install
npm run dev                        # proxies /api and /health to localhost:8000
```

### Full stack

```bash
docker compose up --build
docker compose --profile observability up --build   # with Prometheus and Grafana
```

## Quality gates

A change must pass the same gates the CI pipeline enforces. Run them locally
before opening a pull request.

Backend (`src/backend/`):

```bash
ruff check .
mypy app tests
pytest
```

Frontend (`src/frontend/`):

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Infrastructure and manifests, when touched:

```bash
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform validate
kubectl kustomize k8s/base
kubectl kustomize k8s/overlays/dev
kubectl kustomize k8s/monitoring
```

The test suites are hermetic and require no database or cloud credentials.

## Commit and pull request conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`, `chore`.
- Keep each pull request scoped to a single concern.
- Branch from `main`, open a pull request, and ensure the CI pipeline is green.
  The pull request template lists the expected checks; code owners are requested
  for review automatically.
- Do not introduce secrets, credentials, tokens, or private hosts. Configuration
  is injected at runtime through environment variables and Kubernetes Secrets.
  A secret scan runs on every change.

## Security

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md), not
through public issues or pull requests.
