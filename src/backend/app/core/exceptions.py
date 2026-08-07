"""Domain-level exceptions decoupled from the transport layer."""

from __future__ import annotations


class InvalidObjectIdError(ValueError):
    """Raised when a supplied identifier is not a valid MongoDB ObjectId."""


class EntityNotFoundError(Exception):
    """Raised when a requested entity does not exist."""
