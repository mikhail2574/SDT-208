from app import ai, models


def _complete_attempt(client, db_session) -> models.Attempt:
    client.post(
        "/auth/register",
        data={
            "email": "learner@example.com",
            "password": "LearnerPass123!",
            "full_name": "Learner",
            "wants_author": "on",
        },
        follow_redirects=False,
    )

    create_resp = client.post(
        "/tests/new",
        data={
            "title": "AI Coaching Test",
            "description": "Check AI path",
            "difficulty": "1",
            "is_published": "on",
        },
        follow_redirects=False,
    )
    test_id = int(create_resp.headers["location"].split("/")[-1])

    question_resp = client.post(
        f"/tests/{test_id}/questions/new",
        data={
            "text": "What color is the sky on a clear day?",
            "type": "single_choice",
            "order_index": "0",
            "points": "1",
            "option_text_1": "Blue",
            "option_correct_1": "on",
            "option_text_2": "Red",
            "option_text_3": "Green",
        },
        follow_redirects=False,
    )
    assert question_resp.status_code == 303

    db_session.expire_all()
    test = db_session.query(models.Test).filter_by(id=test_id).first()
    assert test is not None
    assert test.questions
    question = test.questions[0]
    correct_option = next(opt for opt in question.answer_options if opt.is_correct)

    start_resp = client.post(f"/tests/{test_id}/attempts", follow_redirects=False)
    attempt_id = int(start_resp.headers["location"].split("/")[-1])
    submit_resp = client.post(
        f"/attempts/{attempt_id}/submit",
        data={f"q_{question.id}": str(correct_option.id)},
        follow_redirects=False,
    )
    assert submit_resp.status_code == 303

    db_session.expire_all()
    attempt = db_session.query(models.Attempt).filter_by(id=attempt_id).first()
    return attempt


def test_shorten_truncates():
    short = ai._shorten("abc", limit=5)
    assert short == "abc"
    truncated = ai._shorten("abcdefghij", limit=6)
    assert truncated.endswith("...")
    assert len(truncated) == 6


def test_ai_feedback_error_message(monkeypatch, client, db_session):
    attempt = _complete_attempt(client, db_session)

    def fake_feedback(_payload):
        raise ai.AIServiceError("OpenAI API key is missing")

    monkeypatch.setattr(ai, "generate_attempt_feedback", fake_feedback)

    resp = client.post(f"/attempts/{attempt.id}/ai-feedback", follow_redirects=True)
    assert resp.status_code == 200
    assert "OpenAI API key is missing" in resp.text
