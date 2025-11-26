from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user, has_role, require_user
from ..database import get_db

router = APIRouter(tags=["attempts"])

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

    return templates.TemplateResponse(
        "attempts/take.html",
        {
            "request": request,
            "attempt": attempt,
            "test": test,
            "errors": [],
            "current_user": current_user,
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
    answers_map: Dict[int, models.AttemptAnswer] = {
        ans.question_id: ans for ans in attempt.answers
    }

    question_results = []
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

    return templates.TemplateResponse(
        "attempts/result.html",
        {
            "request": request,
            "attempt": attempt,
            "test": test,
            "question_results": question_results,
            "current_user": current_user,
            "page_title": "Attempt result",
        },
    )
