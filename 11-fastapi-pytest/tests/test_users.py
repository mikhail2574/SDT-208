from http import HTTPStatus


def test_get_users_initially_empty(client):
    """GET /users/ should return an empty list before any users exist."""
    response = client.get("/users/")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


def test_create_user_and_list(client):
    """POST /users/ should create a user and GET /users/ should return it."""
    payload = {
        "email": "alice@example.com",
        "full_name": "Alice Example",
    }

    # Create the user
    response = client.post("/users/", json=payload)
    assert response.status_code == HTTPStatus.CREATED

    data = response.json()
    assert data["id"] is not None
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert data["is_active"] is True

    # Fetch list of users and verify the new user is present
    list_response = client.get("/users/")
    assert list_response.status_code == HTTPStatus.OK

    users = list_response.json()
    assert len(users) == 1
    assert users[0]["email"] == payload["email"]


def test_get_users_after_factory(client, user_factory):
    """GET /users/ should reflect users created via the factory fixture."""
    user_factory(email="bob@example.com", full_name="Bob Builder")
    user_factory(email="jane@example.com", full_name="Jane Doe")

    response = client.get("/users/")
    assert response.status_code == HTTPStatus.OK

    users = response.json()
    emails = {u["email"] for u in users}
    assert {"bob@example.com", "jane@example.com"} <= emails


def test_delete_non_existing_user_returns_404(client):
    """Deleting a user that does not exist should return 404."""
    response = client.delete("/users/999")
    assert response.status_code == HTTPStatus.NOT_FOUND

    body = response.json()
    assert body["detail"] == "User not found."
