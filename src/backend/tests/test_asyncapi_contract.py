"""Event contract tests.

The AsyncAPI document is written by hand, unlike the generated OpenAPI one, so
these tests hold it to the producer: every event type has a channel on its
subject, and the envelope, headers, and item state the relay publishes match
the declared schemas field for field.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from app.messaging.relay import OutboxRelay
from app.messaging.stream import subject_for
from app.models.item import ItemResponse
from app.repositories.outbox import EVENT_SOURCE, EventType, build_event

_SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "api" / "asyncapi.yaml"
_ITEM_ID = "6720f0c2a1b2c3d4e5f60718"
_NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
_TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))
    return document


def _resolve(spec: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        target: Any = spec
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def _messages(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Messages keyed by event type, resolved through their channels."""
    found = {}
    for channel in spec["channels"].values():
        for ref in channel["messages"].values():
            message = _resolve(spec, ref)
            found[message["name"]] = {"address": channel["address"], **message}
    return found


def _item_document() -> dict[str, Any]:
    return {
        "id": _ITEM_ID,
        "name": "Fibre spool",
        "description": None,
        "quantity": 3,
        "tags": ["optics"],
        "created_at": _NOW,
        "updated_at": _NOW,
    }


class _Recorder:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, dict[str, str]]] = []

    async def publish(self, subject: str, payload: bytes, headers: dict[str, str]) -> bool:
        self.sent.append((payload, headers))
        return False


async def _published(
    event_type: EventType, data: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Publish one outbox event through the relay and return what reached the broker."""
    event = build_event(event_type, _ITEM_ID, data)
    event["traceparent"] = _TRACEPARENT
    outbox = MagicMock()
    outbox.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(
        return_value=[event]
    )
    outbox.update_one = AsyncMock()
    outbox.find_one = AsyncMock(return_value=None)
    recorder = _Recorder()

    await OutboxRelay(outbox, recorder, batch_size=10, poll_interval=1.0).publish_pending()

    payload, headers = recorder.sent[0]
    message: dict[str, Any] = json.loads(payload)
    return message, headers


def test_every_event_type_has_a_channel_on_its_subject(spec: dict[str, Any]) -> None:
    messages = _messages(spec)

    assert set(messages) == {event_type.value for event_type in EventType}
    for event_type in EventType:
        assert messages[event_type.value]["address"] == subject_for(event_type.value)


async def test_the_envelope_matches_the_cloudevent_schema(spec: dict[str, Any]) -> None:
    envelope = spec["components"]["schemas"]["CloudEvent"]
    message, _ = await _published(EventType.ITEM_CREATED, {"item": _item_document()})

    assert set(message) == set(envelope["required"]) == set(envelope["properties"])
    assert envelope["properties"]["source"]["const"] == EVENT_SOURCE == message["source"]
    assert envelope["properties"]["specversion"]["const"] == message["specversion"]
    assert envelope["properties"]["datacontenttype"]["const"] == message["datacontenttype"]
    assert set(envelope["properties"]["type"]["enum"]) == {t.value for t in EventType}


def test_each_message_declares_its_own_type(spec: dict[str, Any]) -> None:
    for name, message in _messages(spec).items():
        refinement = message["payload"]["allOf"][1]
        assert refinement["properties"]["type"]["const"] == name


async def test_published_headers_match_the_declared_headers(spec: dict[str, Any]) -> None:
    declared = spec["components"]["schemas"]["MessageHeaders"]
    _, headers = await _published(EventType.ITEM_DELETED, {"item": _item_document()})

    assert set(declared["required"]) <= set(headers) <= set(declared["properties"])
    assert headers["Content-Type"] == declared["properties"]["Content-Type"]["const"]
    correlation = spec["components"]["correlationIds"]["traceparent"]["location"]
    assert headers[correlation.rsplit("/", 1)[1]] == _TRACEPARENT


def test_item_state_matches_the_api_representation(spec: dict[str, Any]) -> None:
    item = spec["components"]["schemas"]["Item"]

    # Events carry the item exactly as the REST API returns it.
    assert set(item["required"]) == set(item["properties"]) == set(ItemResponse.model_fields)


async def test_update_data_lists_only_declared_fields(spec: dict[str, Any]) -> None:
    update = spec["components"]["schemas"]["ItemUpdate"]
    allowed = set(update["properties"]["changed_fields"]["items"]["enum"])

    # Every client-settable field, plus the timestamp the update always sets.
    assert allowed == set(ItemResponse.model_fields) - {"id", "created_at"}
    message, _ = await _published(
        EventType.ITEM_UPDATED,
        {"item": _item_document(), "changed_fields": ["quantity", "updated_at"]},
    )
    assert set(message["data"]) == set(update["required"])
