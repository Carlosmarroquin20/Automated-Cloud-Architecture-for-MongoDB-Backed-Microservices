"""NATS JetStream connectivity and the item event stream definition.

The stream is declared by the publisher at startup, so a fresh broker needs no
separate provisioning step. The declaration is idempotent: an existing stream
with a different configuration is updated in place to match this definition.
"""

from __future__ import annotations

import asyncio
import logging

import nats
from nats.aio.client import Client
from nats.errors import Error as NatsError
from nats.js import JetStreamContext
from nats.js.api import RetentionPolicy, StorageType, StreamConfig
from nats.js.errors import BadRequestError

from app.core.backoff import backoff_delays

logger = logging.getLogger(__name__)

STREAM_NAME = "ITEMS"
SUBJECT_PREFIX = "items"

# Event types map to subjects one level below the stream prefix, so consumers
# filter with standard subject wildcards (for example items.deleted).
_SUBJECTS = {
    "item.created": f"{SUBJECT_PREFIX}.created",
    "item.updated": f"{SUBJECT_PREFIX}.updated",
    "item.deleted": f"{SUBJECT_PREFIX}.deleted",
}

STREAM_CONFIG = StreamConfig(
    name=STREAM_NAME,
    subjects=[f"{SUBJECT_PREFIX}.>"],
    # File storage survives a broker restart; limits retention keeps messages for
    # replay by new consumers rather than deleting them once acknowledged.
    storage=StorageType.FILE,
    retention=RetentionPolicy.LIMITS,
    max_age=7 * 24 * 60 * 60,
    # Messages carrying a Nats-Msg-Id already seen inside this window are
    # dropped by the server, which absorbs relay retries after a crash between
    # publishing and recording publication.
    duplicate_window=120,
    num_replicas=1,
)

_CONNECT_ATTEMPTS = 10
_CONNECT_BASE_DELAY_SECONDS = 0.5


def subject_for(event_type: str) -> str:
    try:
        return _SUBJECTS[event_type]
    except KeyError:
        raise ValueError(f"no subject is mapped for event type '{event_type}'") from None


async def connect(url: str, name: str) -> Client:
    """Connect with jittered retries; the client reconnects on its own afterwards."""
    delays = backoff_delays(_CONNECT_BASE_DELAY_SECONDS)
    for attempt in range(1, _CONNECT_ATTEMPTS + 1):
        try:
            client = await nats.connect(
                servers=[url],
                name=name,
                connect_timeout=5,
                # After the first successful connection the client reconnects
                # indefinitely, so a broker restart never terminates the relay.
                allow_reconnect=True,
                max_reconnect_attempts=-1,
                reconnect_time_wait=2,
            )
        except (NatsError, OSError) as exc:
            if attempt == _CONNECT_ATTEMPTS:
                raise
            delay = next(delays)
            logger.warning(
                "nats connection attempt failed; retrying",
                extra={"attempt": attempt, "retry_in_seconds": round(delay, 3), "error": str(exc)},
            )
            await asyncio.sleep(delay)
        else:
            logger.info("nats connection established", extra={"attempt": attempt})
            return client
    raise RuntimeError("unreachable")  # pragma: no cover


async def ensure_stream(jetstream: JetStreamContext) -> None:
    try:
        await jetstream.add_stream(config=STREAM_CONFIG)
    except BadRequestError:
        # The stream exists with a different configuration; converge it.
        await jetstream.update_stream(config=STREAM_CONFIG)
    logger.info("jetstream stream ready", extra={"stream": STREAM_NAME})
