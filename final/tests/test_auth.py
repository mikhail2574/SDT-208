from app import models


def test_register_and_login_flow(client, db_session):
    resp = client.post(
        "/auth/register",
        data={
            "email": "student@example.com",
            "password": "Secret123!",
            "full_name": "Student One",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    user = db_session.query(models.User).filter_by(email="student@example.com").first()
    assert user is not None
    assert any(role.name == "TEST_TAKER" for role in user.roles)

    # Clear the session then log back in to verify credentials work.
    client.post("/auth/logout", follow_redirects=False)
    login_resp = client.post(
        "/auth/login",
        data={"email": "student@example.com", "password": "Secret123!"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303
