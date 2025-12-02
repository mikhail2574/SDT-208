import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import ai, models
from ..auth import get_current_user, has_role, require_user
from ..database import get_db

router = APIRouter(tags=["attempts"])
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.globals["has_role"] = has_role


def _can_view_test(test: models.Test, current_user) -> bool:
    if test.is_published:
        return True
    if not current_user:
        return False
    return current_user.id == test.created_by or has_role(current_user, "ADMIN")


def _compute_max_score(test: models.Test) -> float:
    return float(sum(float(q.points) for q in test.questions))


def _get_attempt(db: Session, attempt_id: int) -> models.Attempt:
    attempt = (
        db.query(models.Attempt)
        .filter(models.Attempt.id == attempt_id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


def _require_attempt_owner(attempt: models.Attempt, current_user) -> None:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in.")
    if attempt.user_id != current_user.id and not has_role(current_user, "ADMIN"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")


@router.post("/tests/{test_id}/attempts", response_class=HTMLResponse)
def start_attempt(
    test_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
):
    test = (
        db.query(models.Test)
        .filter(models.Test.id == test_id)
        .first()
    )
    if not test or not _can_view_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if not test.questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test has no questions yet.",
        )

    attempt = models.Attempt(
        user_id=current_user.id,
        test_id=test.id,
        status="in_progress",
        started_at=datetime.utcnow(),
        max_score_cached=_compute_max_score(test),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return RedirectResponse(
        url=f"/attempts/{attempt.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/attempts/{attempt_id}", response_class=HTMLResponse)
def attempt_detail(
    request: Request,
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    attempt = _get_attempt(db, attempt_id)
    _require_attempt_owner(attempt, current_user)
    test = attempt.test

    if attempt.status == "completed":
        return RedirectResponse(
            url=f"/attempts/{attempt.id}/result",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not _can_view_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    remaining_seconds = None
    if test.time_limit_seconds:
        elapsed = (datetime.utcnow() - attempt.started_at).total_seconds()
        remaining_seconds = max(0, test.time_limit_seconds - elapsed)

    return templates.TemplateResponse(
        "attempts/take.html",
        {
            "request": request,
            "attempt": attempt,
            "test": test,
            "errors": [],
            "current_user": current_user,
            "remaining_seconds": remaining_seconds,
            "page_title": f"Attempt #{attempt.id}",
        },
    )


def _parse_answers(
    form_data, test: models.Test
) -> Tuple[Dict[int, List[int]], Dict[int, Optional[str]], List[str]]:
    """Returns selected option ids per question, free text per question, and errors."""
    selected: Dict[int, List[int]] = {}
    free_text: Dict[int, Optional[str]] = {}
    errors: List[str] = []
    for question in test.questions:
        if question.type == "free_text":
            free_text[question.id] = (form_data.get(f"q_{question.id}_text") or "").strip()
            continue

        if question.type == "single_choice":
            raw = form_data.get(f"q_{question.id}")
            if raw:
                try:
                    selected[question.id] = [int(raw)]
                except ValueError:
                    errors.append("Invalid answer submitted.")
            else:
                selected[question.id] = []
        else:
            raw_multi = form_data.getlist(f"q_{question.id}")
            try:
                selected[question.id] = [int(val) for val in raw_multi]
            except ValueError:
                errors.append("Invalid answer submitted.")
    return selected, free_text, errors


def _score_question(
    question: models.Question, selected_ids: List[int], free_text: Optional[str]
) -> Tuple[bool | None, float]:
    correct_ids = {opt.id for opt in question.answer_options if opt.is_correct}
    if question.type == "free_text":
        return None, 0.0

    if question.type == "single_choice":
        if not selected_ids:
            return False, 0.0
        is_correct = selected_ids[0] in correct_ids
        return is_correct, float(question.points) if is_correct else 0.0

    selected_set = set(selected_ids)
    is_correct = selected_set == correct_ids and len(selected_set) > 0
    return is_correct, float(question.points) if is_correct else 0.0


def _build_question_results(
    test: models.Test, attempt: models.Attempt
) -> List[Dict[str, object]]:
    answers_map: Dict[int, models.AttemptAnswer] = {
        ans.question_id: ans for ans in attempt.answers
    }
    question_results: List[Dict[str, object]] = []
    for question in test.questions:
        ans = answers_map.get(question.id)
        selected_ids: List[int] = []
        if question.type == "single_choice" and ans and ans.selected_option_id:
            selected_ids = [ans.selected_option_id]
        elif question.type == "multiple_choice" and ans and ans.free_text_answer:
            try:
                selected_ids = [int(val) for val in ans.free_text_answer.split(",") if val]
            except ValueError:
                selected_ids = []

        question_results.append(
            {
                "question": question,
                "answer": ans,
                "selected_ids": selected_ids,
            }
        )
    return question_results


def _build_ai_request(
    test: models.Test,
    attempt: models.Attempt,
    question_results: List[Dict[str, object]],
) -> ai.AttemptInsightRequest:
    max_score = float(attempt.max_score_cached or _compute_max_score(test))
    score_obtained = float(attempt.score_obtained or 0)

    questions_payload: List[ai.QuestionInsight] = []
    for item in question_results:
        question: models.Question = item["question"]  # type: ignore
        answer: Optional[models.AttemptAnswer] = item.get("answer")  # type: ignore
        selected_ids: List[int] = item.get("selected_ids", [])  # type: ignore

        correct_options = [opt.text for opt in question.answer_options if opt.is_correct]
        correct_answer = ", ".join(correct_options) if correct_options else ""
        if question.type == "free_text" and not correct_answer:
            correct_answer = "Manual review needed"

        if question.type == "free_text":
            user_answer = (
                answer.free_text_answer
                if answer and answer.free_text_answer
                else "No answer provided."
            )
        else:
            selected_texts = [
                opt.text for opt in question.answer_options if opt.id in selected_ids
            ]
            user_answer = ", ".join(selected_texts) if selected_texts else "No answer provided."

        status = "Not answered"
        if answer:
            if answer.is_correct is None:
                status = "Pending manual review"
            elif answer.is_correct:
                status = "Correct"
            else:
                status = "Incorrect"

        questions_payload.append(
            ai.QuestionInsight(
                question_text=question.text,
                type=question.type,
                user_answer=user_answer,
                correct_answer=correct_answer,
                status=status,
                points=float(question.points),
            )
        )

    return ai.AttemptInsightRequest(
        test_title=test.title,
        score_obtained=score_obtained,
        max_score=max_score,
        questions=questions_payload,
    )


def _create_practice_quiz(
    db: Session,
    owner: models.User,
    quiz: ai.PracticeQuiz,
) -> models.Test:
    test = models.Test(
        title=quiz.title[:255],
        description=quiz.description[:2000],
        difficulty=quiz.questions and 3 or 1,
        time_limit_seconds=900,
        is_published=True,
        created_by=owner.id,
    )
    db.add(test)
    db.flush()

    for idx, q in enumerate(quiz.questions):
        text = str(q.get("text") or f"Question {idx + 1}")
        options = q.get("options") or []
        if not isinstance(options, list) or len(options) < 2:
            options = [f"Option {i+1}" for i in range(4)]
        correct_index = q.get("correct_option", 0)
        try:
            correct_index = int(correct_index)
        except (TypeError, ValueError):
            correct_index = 0
        points = float(q.get("points") or 1.0)

        question = models.Question(
            test_id=test.id,
            text=text[:4000],
            type="single_choice",
            order_index=idx,
            points=points,
        )
        db.add(question)
        db.flush()
        for opt_idx, opt_text in enumerate(options[:4]):
            db.add(
                models.AnswerOption(
                    question_id=question.id,
                    text=str(opt_text)[:500],
                    is_correct=opt_idx == correct_index,
                    order_index=opt_idx,
                )
            )

    db.commit()
    db.refresh(test)
    return test


@router.post("/attempts/{attempt_id}/submit", response_class=HTMLResponse)
async def submit_attempt(
    request: Request,
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
):
    attempt = _get_attempt(db, attempt_id)
    _require_attempt_owner(attempt, current_user)
    test = attempt.test
    if attempt.status == "completed":
        return RedirectResponse(
            url=f"/attempts/{attempt.id}/result",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    form = await request.form()
    selected, free_text, errors = _parse_answers(form, test)
    if errors:
        return templates.TemplateResponse(
            "attempts/take.html",
            {
                "request": request,
                "attempt": attempt,
                "test": test,
                "errors": errors,
                "current_user": current_user,
                "page_title": f"Attempt #{attempt.id}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Clear previous answers if any
    db.query(models.AttemptAnswer).filter(models.AttemptAnswer.attempt_id == attempt.id).delete()

    total_score = 0.0
    for question in test.questions:
        q_selected = selected.get(question.id, [])
        q_text = free_text.get(question.id)
        option_ids = {opt.id for opt in question.answer_options}
        if question.type != "free_text":
            invalid = [sid for sid in q_selected if sid not in option_ids]
            if invalid:
                errors.append("Invalid answer submitted.")
                continue
        is_correct, points_obtained = _score_question(question, q_selected, q_text)
        total_score += points_obtained

        if question.type == "free_text":
            answer = models.AttemptAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                free_text_answer=q_text,
                is_correct=is_correct,
                points_obtained=points_obtained,
            )
            db.add(answer)
        elif question.type == "single_choice":
            selected_id = q_selected[0] if q_selected else None
            answer = models.AttemptAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option_id=selected_id,
                is_correct=is_correct,
                points_obtained=points_obtained,
            )
            db.add(answer)
        else:
            # Store comma-separated selections for multiple choice
            selected_str = ",".join(str(item) for item in q_selected)
            answer = models.AttemptAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                free_text_answer=selected_str,
                is_correct=is_correct,
                points_obtained=points_obtained,
            )
            db.add(answer)

    if errors:
        db.rollback()
        return templates.TemplateResponse(
            "attempts/take.html",
            {
                "request": request,
                "attempt": attempt,
                "test": test,
                "errors": errors,
                "current_user": current_user,
                "page_title": f"Attempt #{attempt.id}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    attempt.score_obtained = total_score
    attempt.status = "completed"
    attempt.finished_at = datetime.utcnow()
    if attempt.max_score_cached is None or attempt.max_score_cached == 0:
        attempt.max_score_cached = _compute_max_score(test)

    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return RedirectResponse(
        url=f"/attempts/{attempt.id}/result", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/attempts/{attempt_id}/result", response_class=HTMLResponse)
def view_result(
    request: Request,
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    attempt = _get_attempt(db, attempt_id)
    _require_attempt_owner(attempt, current_user)
    if attempt.status != "completed":
        return RedirectResponse(
            url=f"/attempts/{attempt.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    test = attempt.test
    question_results = _build_question_results(test, attempt)

    return templates.TemplateResponse(
        "attempts/result.html",
        {
            "request": request,
            "attempt": attempt,
            "test": test,
            "question_results": question_results,
            "current_user": current_user,
            "ai_feedback": None,
            "ai_error": None,
            "ai_quiz_error": None,
            "ai_quiz_link": None,
            "page_title": "Attempt result",
        },
    )


@router.post("/attempts/{attempt_id}/ai-feedback", response_class=HTMLResponse)
async def attempt_ai_feedback(
    request: Request,
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
):
    attempt = _get_attempt(db, attempt_id)
    _require_attempt_owner(attempt, current_user)
    if attempt.status != "completed":
        return RedirectResponse(
            url=f"/attempts/{attempt.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    test = attempt.test
    question_results = _build_question_results(test, attempt)
    ai_feedback_text = None
    ai_error = None

    try:
        ai_request = _build_ai_request(test, attempt, question_results)
        ai_feedback_text = await ai.generate_attempt_feedback(ai_request)
    except ai.AIServiceError as exc:
        ai_error = str(exc)
    except Exception as exc:  # pragma: no cover - network failures vary
        logger.exception("AI feedback failed unexpectedly", exc_info=exc)
        ai_error = "AI feedback failed unexpectedly. Please try again."

    return templates.TemplateResponse(
        "attempts/result.html",
        {
            "request": request,
            "attempt": attempt,
            "test": test,
            "question_results": question_results,
            "ai_feedback": ai_feedback_text,
            "ai_error": ai_error,
            "ai_quiz_error": None,
            "ai_quiz_link": None,
            "current_user": current_user,
            "page_title": "Attempt result",
        },
    )


@router.post("/attempts/{attempt_id}/ai-quiz", response_class=HTMLResponse)
async def attempt_ai_quiz(
    request: Request,
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
):
    attempt = _get_attempt(db, attempt_id)
    _require_attempt_owner(attempt, current_user)
    if attempt.status != "completed":
        return RedirectResponse(
            url=f"/attempts/{attempt.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    test = attempt.test
    question_results = _build_question_results(test, attempt)

    ai_feedback_text = None
    ai_error = None
    ai_quiz_error = None
    ai_quiz_link = None

    try:
        ai_request = _build_ai_request(test, attempt, question_results)
        practice_quiz = await ai.generate_practice_quiz(ai_request)
        new_test = _create_practice_quiz(db, current_user, practice_quiz)
        ai_quiz_link = f"/tests/{new_test.id}"
    except ai.AIServiceError as exc:
        ai_quiz_error = str(exc)
    except Exception as exc:  # pragma: no cover - network failures vary
        logger.exception("AI practice quiz failed unexpectedly", exc_info=exc)
        ai_quiz_error = "AI practice quiz failed unexpectedly. Please try again."

    return templates.TemplateResponse(
        "attempts/result.html",
        {
            "request": request,
            "attempt": attempt,
            "test": test,
            "question_results": question_results,
            "ai_feedback": ai_feedback_text,
            "ai_error": ai_error,
            "ai_quiz_error": ai_quiz_error,
            "ai_quiz_link": ai_quiz_link,
            "current_user": current_user,
            "page_title": "Attempt result",
        },
    )
