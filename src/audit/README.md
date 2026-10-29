# Audit Service

Asynchronous FastAPI service that consumes the item events published by the
items API and serves each item's change history. It owns its own database and
never calls the items API: the history is built entirely from the events, so it
outlives the items it describes.

## Architecture

- **Consumption:** a durable JetStream pull consumer (`audit-service`) with
  explicit acknowledgement reads the `ITEMS` stream. Replicas pull from the same
  consumer, so JetStream spreads messages across them and each event is
  processed by one replica at a time.
- **Settlement:** every message ends in exactly one of three outcomes.

  | Outcome | When | Effect |
  |---------|------|--------|
  | `ack` | Recorded, or already recorded | Removed from the consumer's pending set |
  | `term` | Malformed; it would fail identically on every delivery | Never redelivered |
  | `nak` with delay | The database rejected the write | Redelivered after 1, 2, 4, 8 … seconds (capped at 30), at most five deliveries |

- **Idempotency:** the event id is the history entry's `_id`, so a redelivered or
  republished event hits the unique index and is acknowledged as a duplicate.
  Delivery is at-least-once end to end; processing is effectively once.
- **Isolation:** the service connects with its own credential to its own
  `audit` database (database per service). Readiness depends on that database
  only, so history remains available while the broker is unreachable; the
  consumer reconnects in the background with jittered backoff. Its reported
  binding state (`audit_consumer_connected`) follows the client's connection
  events, because a reconnecting client raises no error and its fetches only
  time out, exactly as on an idle stream.
- **Tracing:** each message's processing span continues the trace carried in its
  `traceparent` header, so one trace links the originating request, the relay's
  publish, and the history write.

The consumed contract is [`docs/api/asyncapi.yaml`](../../docs/api/asyncapi.yaml).
The consumer validates only the CloudEvents attributes it relies on and ignores
the rest, so the producer can add attributes without breaking it.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/audit/items/{id}/events` | History of an item, oldest first (`limit` 1–500) |
| GET | `/health/live` | Liveness; process health only |
| GET | `/health/ready` | Readiness; gated on the audit database, reports the consumer state |
| GET | `/metrics` | Prometheus exposition |

The frontend reverse proxy routes `/api/v1/audit/` to this service, under the
same per-client rate limit as the items API.

## Metrics

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `audit_events_consumed_total` | Counter | outcome | `recorded`, `duplicate`, `retried`, or `rejected` |
| `audit_consumer_connected` | Gauge | — | 1 while bound to the stream, 0 while reconnecting |

## Configuration

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MONGODB_URI` | yes | — | Connection string for the audit database |
| `MONGODB_DB_NAME` | no | `audit` | Database name |
| `NATS_URL` | no | `nats://nats:4222` | Broker address |
| `CONSUMER_ENABLED` | no | `true` | Run the consumer (tests disable it) |
| `CONSUMER_DURABLE_NAME` | no | `audit-service` | Durable consumer name |
| `CONSUMER_BATCH_SIZE` | no | `50` | Messages fetched per pull |
| `CONSUMER_MAX_DELIVER` | no | `5` | Deliveries before a message is abandoned |
| `CONSUMER_ACK_WAIT_SECONDS` | no | `30` | Time before an unacknowledged message is redelivered |
| `OTEL_ENABLED` | no | `false` | Distributed tracing on/off |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | empty | OTLP/HTTP traces endpoint |

## Local Development

Commands run from `src/audit`. The suite is hermetic: MongoDB and NATS are
replaced with doubles.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
mypy app tests
pytest
```

Run the service against a reachable MongoDB and NATS:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
