"""Operator command that resolves dead letters.

Runs inside an audit service container, which already holds the service's
database credential and broker address, so no further secret is distributed:

    python3 -m app.replay [--dry-run] [--discard-unrecoverable]

The command prints a JSON summary and exits non-zero while dead letters remain,
so it can gate an automated recovery. It is not exposed over HTTP: a replay
writes to the history, and the service's HTTP surface is read-only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import nats
from pymongo import AsyncMongoClient

from app.config import get_settings
from app.consumer import STREAM_NAME
from app.deadletter import DeadLetterReplayer, ReplayReport
from app.logs import configure_logging
from app.repository import AuditRepository
from app.tracing import configure_command_tracing


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python3 -m app.replay", description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what a replay would do without changing anything.",
    )
    parser.add_argument(
        "--discard-unrecoverable",
        action="store_true",
        help="Remove dead letters whose event is malformed or no longer in the stream.",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> ReplayReport:
    settings = get_settings()
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        connectTimeoutMS=settings.mongodb_connect_timeout_ms,
        socketTimeoutMS=settings.mongodb_socket_timeout_ms,
        tz_aware=True,
        appname=f"{settings.app_name}-replay",
    )
    broker = await nats.connect(
        servers=[settings.nats_url], name=f"{settings.app_name}-replay", connect_timeout=5
    )
    try:
        replayer = DeadLetterReplayer(
            broker.jetstream(), AuditRepository(client[settings.mongodb_db_name]), STREAM_NAME
        )
        return await replayer.replay(
            dry_run=args.dry_run, discard_unrecoverable=args.discard_unrecoverable
        )
    finally:
        await broker.close()
        await client.close()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    provider = configure_command_tracing(settings)
    try:
        report = asyncio.run(_run(args))
    finally:
        # Spans are exported in batches; the process exits right after the
        # replay, so pending spans are flushed explicitly.
        if provider is not None:
            provider.shutdown()
    summary = {"outcomes": dict(report.outcomes), "remaining": report.remaining}
    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
    return 1 if report.remaining else 0


if __name__ == "__main__":
    sys.exit(main())
