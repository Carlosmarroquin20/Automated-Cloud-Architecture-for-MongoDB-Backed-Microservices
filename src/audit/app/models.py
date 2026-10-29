"""Event and history models.

``ItemEvent`` is this service's view of the published contract: it validates only
the CloudEvents attributes it relies on and ignores anything else, so the
producer can add attributes without breaking this consumer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str = Field(min_length=1, max_length=64)
    specversion: Literal["1.0"]
    type: str = Field(pattern=r"^item\.(created|updated|deleted)$")
    source: str
    subject: str = Field(min_length=1, max_length=64)
    time: datetime
    data: dict[str, Any]


class AuditEntry(BaseModel):
    id: str = Field(description="Event identifier, unique per change.")
    type: str = Field(description="Event type, for example item.updated.")
    source: str
    subject: str = Field(description="Identifier of the item the event describes.")
    time: datetime = Field(description="When the change was committed.")
    data: dict[str, Any] = Field(description="Item state carried by the event.")
    received_at: datetime = Field(description="When this service recorded the event.")
