from http import HTTPStatus
from unittest.mock import MagicMock

import pytest

from app import crud


@pytest.mark.usefixtures("client")
def test_create_user_db_failure_returns_500(client, monkeypatch):
    """Simulate a DB failure during user creation.

    Scenario:
        We monkeypatch `crud.create_user` to raise RuntimeError.
        The endpoint must translate this into a clean HTTP 500 response
        instead of crashing, and our patched function must be called.
    """

    def _fake_create_user(db, user_in):
        raise RuntimeError("Database commit failed in test")

    mock = MagicMock(side_effect=_fake_create_user)
    monkeypatch.setattr(crud, "create_user", mock)

    payload = {
        "email": "fail@example.com",
        "full_name": "Should Fail",
    }

    response = client.post("/users/", json=payload)

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Internal server error during user creation."
    # Ensure our patched function was actually used.
    assert mock.called
