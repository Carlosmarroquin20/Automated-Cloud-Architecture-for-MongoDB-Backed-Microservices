"""Item resource endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_and_get_item(client: TestClient) -> None:
    created = client.post(
        "/api/v1/items",
        json={"name": "Widget", "quantity": 3, "tags": ["alpha", "beta"]},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Widget"
    assert body["quantity"] == 3
    assert body["id"]

    fetched = client.get(f"/api/v1/items/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_list_items_returns_created(client: TestClient) -> None:
    client.post("/api/v1/items", json={"name": "First"})
    client.post("/api/v1/items", json={"name": "Second"})
    response = client.get("/api/v1/items", params={"limit": 10, "skip": 0})
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"First", "Second"} <= names


def test_update_item_applies_partial_changes(client: TestClient) -> None:
    created = client.post("/api/v1/items", json={"name": "Editable", "quantity": 1}).json()
    response = client.patch(f"/api/v1/items/{created['id']}", json={"quantity": 9})
    assert response.status_code == 200
    assert response.json()["quantity"] == 9
    assert response.json()["name"] == "Editable"


def test_delete_item_removes_resource(client: TestClient) -> None:
    created = client.post("/api/v1/items", json={"name": "Temporary"}).json()
    deleted = client.delete(f"/api/v1/items/{created['id']}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/items/{created['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_invalid_identifier_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/items/not-a-valid-id")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_identifier"


def test_missing_required_field_fails_validation(client: TestClient) -> None:
    response = client.post("/api/v1/items", json={"quantity": 1})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_field_is_forbidden(client: TestClient) -> None:
    response = client.post("/api/v1/items", json={"name": "X", "unexpected": True})
    assert response.status_code == 422


def test_list_filters_by_tag(client: TestClient) -> None:
    client.post("/api/v1/items", json={"name": "Alpha", "tags": ["x"]})
    client.post("/api/v1/items", json={"name": "Beta", "tags": ["y"]})
    response = client.get("/api/v1/items", params={"tag": "x"})
    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"Alpha"}


def test_list_searches_by_name(client: TestClient) -> None:
    client.post("/api/v1/items", json={"name": "Alpha"})
    client.post("/api/v1/items", json={"name": "Beta"})
    response = client.get("/api/v1/items", params={"q": "alph"})
    assert [item["name"] for item in response.json()] == ["Alpha"]


def test_list_publishes_total_count_header(client: TestClient) -> None:
    client.post("/api/v1/items", json={"name": "Only"})
    response = client.get("/api/v1/items")
    assert response.headers["X-Total-Count"] == "1"
