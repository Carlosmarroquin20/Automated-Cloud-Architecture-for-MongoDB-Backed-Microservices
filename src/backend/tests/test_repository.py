"""Item repository helper tests."""

from __future__ import annotations

import pytest
from bson import ObjectId

from app.core.exceptions import InvalidObjectIdError
from app.repositories.item_repository import _serialize, _to_object_id


def test_to_object_id_accepts_valid_hex() -> None:
    identifier = "0123456789abcdef01234567"
    assert str(_to_object_id(identifier)) == identifier


def test_to_object_id_rejects_malformed_input() -> None:
    with pytest.raises(InvalidObjectIdError):
        _to_object_id("not-an-object-id")


def test_serialize_projects_identifier_to_string() -> None:
    identifier = ObjectId()
    result = _serialize({"_id": identifier, "name": "sample"})
    assert result["id"] == str(identifier)
    assert "_id" not in result
    assert result["name"] == "sample"
