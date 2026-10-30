# Backend Microservice

Asynchronous FastAPI service exposing a versioned REST API backed by MongoDB
Atlas. The service emits structured JSON logs, exposes liveness and readiness
probes for orchestrated environments, and establishes database connectivity with
bounded retries and explicit timeouts.

## Architecture

- **Framework:** FastAPI with Pydantic v2 for strict request and response
  validation.
- **Persistence:** MongoDB accessed through the native PyMongo asynchronous
  client. TLS is enforced by the Atlas SRV connection string.
- **Resilience:** startup connectivity is validated with exponential backoff;
  transient database unavailability degrades readiness rather than crashing the
  process.
- **Events:** every create, update, and delete writes a CloudEvents 1.0 event to
  a transactional outbox in the same MongoDB transaction as the change. A
  separate relay process, built from the same image, publishes pending events to
  NATS JetStream. The event contract is
  [`docs/api/asyncapi.yaml`](../../docs/api/asyncapi.yaml).
- **Observability:** every log record is JSON-formatted and carries a request
  correlation identifier propagated via the `X-Request-ID` header. Prometheus
  metrics are served on `/metrics`, and OpenTelemetry tracing is available
  behind `OTEL_ENABLED`; the trace context is stored with each event so the
  relay and consumers continue the originating request's trace.
- **Security posture:** configuration is environment-driven with no embedded
  secrets, unknown request fields are rejected, and internal error details are
  never returned to clients.

## Project Structure

```
src/backend/
├── app/
│   ├── api/                # Routers, dependencies, versioned endpoints
│   │   ├── deps.py
│   │   ├── health.py       # /health/live and /health/ready
│   │   ├── router.py
│   │   └── v1/items.py     # Example persisted resource
│   ├── core/               # Configuration, logging, context, error handling
│   ├── db/mongodb.py       # Async connection manager with retry and timeouts
│   ├── messaging/          # JetStream stream definition and the outbox relay
│   ├── middleware/         # Request correlation and access logging
│   ├── models/item.py      # Pydantic schemas
│   ├── repositories/       # Data access; items and the transactional outbox
│   └── main.py             # Composition root and lifespan management
├── scripts/                # OpenAPI contract export and drift check
├── tests/                  # Hermetic test suite (no live database required)
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

## API

| Method | Path                  | Description                          |
|--------|-----------------------|--------------------------------------|
| GET    | `/health/live`        | Liveness; process health only        |
| GET    | `/health/ready`       | Readiness; gated on MongoDB          |
| POST   | `/api/v1/items`       | Create an item                       |
| GET    | `/api/v1/items`       | List items (`limit`, `skip`)         |
| GET    | `/api/v1/items/{id}`  | Retrieve an item                     |
| PATCH  | `/api/v1/items/{id}`  | Partially update an item             |
| DELETE | `/api/v1/items/{id}`  | Delete an item                       |

Interactive documentation is served at `/docs` in non-production environments and
is disabled when `APP_ENV=production` to reduce the exposed surface.

### Health Check Semantics

Liveness returns `200` whenever the process is running and is safe for a
Kubernetes liveness probe. Readiness returns `200` only when MongoDB responds to
a ping and `503` otherwise, ensuring traffic is withheld from an instance that
cannot serve requests.

## Configuration

All configuration is supplied through environment variables. `.env.example`
enumerates the complete set. No default is provided for credential-bearing
values.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `APP_ENV` | no | `development` | Runtime environment selector |
| `LOG_LEVEL` | no | `INFO` | Structured logging verbosity |
| `APP_PORT` | no | `8000` | Service listen port |
| `MONGODB_URI` | yes | — | Atlas TLS connection string |
| `MONGODB_DB_NAME` | yes | — | Target database name |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS` | no | `5000` | Server selection timeout |
| `MONGODB_CONNECT_TIMEOUT_MS` | no | `10000` | Socket connect timeout |
| `MONGODB_SOCKET_TIMEOUT_MS` | no | `10000` | Socket operation timeout |
| `MONGODB_TRANSACTION_TIMEOUT_MS` | no | `10000` | Deadline for a write including transaction retries; 503 once it expires |
| `MONGODB_MAX_POOL_SIZE` | no | `50` | Maximum pooled connections |
| `MONGODB_MIN_POOL_SIZE` | no | `0` | Minimum pooled connections |
| `MONGODB_PING_ON_STARTUP` | no | `true` | Validate connectivity at startup |
| `MONGODB_CONNECT_MAX_RETRIES` | no | `5` | Startup retry attempts |
| `MONGODB_CONNECT_RETRY_BASE_DELAY_SECONDS` | no | `0.5` | Initial backoff delay |
| `CORS_ALLOW_ORIGINS` | no | empty | Comma-separated allowed origins |
| `NATS_URL` | no | `nats://nats:4222` | Broker address (relay only) |
| `OUTBOX_RELAY_BATCH_SIZE` | no | `100` | Events published per relay pass |
| `OUTBOX_RELAY_POLL_INTERVAL_SECONDS` | no | `1.0` | Idle wait between relay passes |
| `OUTBOX_RELAY_METRICS_PORT` | no | `9000` | Relay Prometheus endpoint port |
| `OTEL_ENABLED` | no | `false` | Distributed tracing on/off |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | empty | OTLP/HTTP traces endpoint |
| `OTEL_CONSOLE_EXPORT` | no | `false` | Also print spans to stdout |

## Local Development

Commands are executed from the `src/backend` directory. Use of an isolated
virtual environment is assumed.

Install development dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
pytest
```

Lint and type-check:

```bash
ruff check .
mypy app tests scripts
```

Run the service (requires a reachable MongoDB instance and populated
environment):

```bash
uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}"
```

Run the outbox relay (additionally requires a reachable NATS server with
JetStream enabled):

```bash
python -m app.messaging.relay
```

Both processes need MongoDB running as a replica set, because the outbox is
written in a multi-document transaction. Atlas clusters are replica sets; a
local server is started with `--replSet` and initiated once, as the Compose
stack does.

The test suite is hermetic: persistence and connectivity dependencies are
substituted with in-memory doubles, so no MongoDB instance is required to run it.
