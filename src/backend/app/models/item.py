"""Item resource schemas with strict validation.

Distinct input and output models enforce a clear contract: clients cannot set
server-managed fields, and responses expose a stable serialized representation
independent of the persistence layer.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    # Unknown fields are rejected to prevent silent acceptance of malformed input.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    quantity: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    # Every field is optional to support partial updates; absent fields are left
    # unchanged rather than reset to defaults.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    quantity: int | None = Field(default=None, ge=0)
    tags: list[str] | None = Field(default=None)


class ItemResponse(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
