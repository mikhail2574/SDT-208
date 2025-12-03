from app import models


def _register_author(client):
    return client.post(
        "/auth/register",
        data={
            "email": "author@example.com",
            "password": "AuthorPass123!",
            "full_name": "Author User",
            "wants_author": "on",
        },
        follow_redirects=False,
    )


def test_author_can_create_test_and_submit_attempt(client, db_session):
    register_resp = _register_author(client)
    assert register_resp.status_code == 303

    create_resp = client.post(
        "/tests/new",
        data={
            "title": "Math Sprint",
            "description": "Quick arithmetic check",
            "difficulty": "2",
            "time_limit_minutes": "10",
            "is_published": "on",
        },
        follow_redirects=False,
    )
    assert create_resp.status_code == 303
    test_id = int(create_resp.headers["location"].split("/")[-1])

    question_resp = client.post(
        f"/tests/{test_id}/questions/new",
        data={
            "text": "What is 2 + 2?",
            "type": "single_choice",
            "order_index": "0",
            "points": "2",
            "option_text_1": "4",
            "option_correct_1": "on",
            "option_text_2": "3",
            "option_text_3": "5",
        },
        follow_redirects=False,
    )
    assert question_resp.status_code == 303

    db_session.expire_all()
    test = db_session.query(models.Test).filter_by(id=test_id).first()
    assert test is not None
    question = test.questions[0]
    correct_option = next(opt for opt in question.answer_options if opt.is_correct)

    start_resp = client.post(f"/tests/{test_id}/attempts", follow_redirects=False)
    assert start_resp.status_code == 303
    attempt_id = int(start_resp.headers["location"].split("/")[-1])

    submit_resp = client.post(
        f"/attempts/{attempt_id}/submit",
        data={f"q_{question.id}": str(correct_option.id)},
        follow_redirects=False,
    )
    assert submit_resp.status_code == 303

    result_page = client.get(f"/attempts/{attempt_id}/result")
    assert result_page.status_code == 200
    assert "Result" in result_page.text

    db_session.expire_all()
    attempt = db_session.query(models.Attempt).filter_by(id=attempt_id).first()
    assert attempt is not None
    assert float(attempt.score_obtained) == float(question.points)
    assert attempt.status == "completed"


def test_question_validation_requires_correct_option(client):
    _register_author(client)
    create_resp = client.post(
        "/tests/new",
        data={
            "title": "Validation Test",
            "description": "Check validation",
            "difficulty": "3",
            "is_published": "on",
        },
        follow_redirects=False,
    )
    assert create_resp.status_code == 303
    test_id = int(create_resp.headers["location"].split("/")[-1])

    invalid_resp = client.post(
        f"/tests/{test_id}/questions/new",
        data={
            "text": "Pick the prime numbers",
            "type": "single_choice",
            "order_index": "0",
            "points": "1",
            "option_text_1": "4",
            "option_text_2": "6",
            "option_text_3": "8",
            # No correct option set
        },
        follow_redirects=False,
    )

    assert invalid_resp.status_code == 400
    assert "Mark at least one option as correct" in invalid_resp.text


def test_start_attempt_requires_authentication(client, db_session):
    # Seeder adds published tests; pick the first one to attempt.
    db_session.expire_all()
    seeded_test = db_session.query(models.Test).first()
    assert seeded_test is not None

    resp = client.post(f"/tests/{seeded_test.id}/attempts", follow_redirects=False)
    assert resp.status_code == 401
