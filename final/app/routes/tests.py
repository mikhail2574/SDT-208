from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, has_role, require_author, require_user
from ..database import get_db

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.globals["has_role"] = has_role


def _extract_form_values(form_data) -> dict:
    if hasattr(form_data, "multi_items"):
        return {key: value for key, value in form_data.multi_items()}
    return dict(form_data)


def _can_manage_test(test: models.Test, current_user: Optional[models.User]) -> bool:
    if not current_user:
        return False
    return current_user.id == test.created_by or has_role(current_user, "ADMIN")


def _can_view_test(test: models.Test, current_user: Optional[models.User]) -> bool:
    if test.is_published:
        return True
    return _can_manage_test(test, current_user)


def _parse_test_form(form_data) -> Tuple[schemas.TestForm | None, List[schemas.ValidationResult]]:
    payload = {
        "title": (form_data.get("title") or "").strip(),
        "description": (form_data.get("description") or "").strip() or None,
        "difficulty": None,
        "time_limit_minutes": None,
        "is_published": form_data.get("is_published") == "on",
    }
    difficulty_raw = form_data.get("difficulty")
    if difficulty_raw not in (None, ""):
        try:
            payload["difficulty"] = int(difficulty_raw)
        except ValueError:
            return None, [
                schemas.ValidationResult(
                    loc="difficulty", msg="Difficulty must be a number between 1 and 5"
                )
            ]

    time_limit_raw = form_data.get("time_limit_minutes")
    if time_limit_raw not in (None, ""):
        try:
            payload["time_limit_minutes"] = int(time_limit_raw)
        except ValueError:
            return None, [
                schemas.ValidationResult(
                    loc="time_limit_minutes", msg="Time limit must be a whole number"
                )
            ]

    try:
        form = schemas.TestForm(**payload)
        return form, []
    except ValidationError as exc:
        return None, schemas.format_errors(exc)


def _parse_question_form(form_data) -> Tuple[schemas.QuestionForm | None, List[schemas.ValidationResult]]:
    options_payload = []
    for idx in range(1, 4):
        text = (form_data.get(f"option_text_{idx}") or "").strip()
        if not text:
            continue
        options_payload.append(
            {
                "text": text,
                "is_correct": form_data.get(f"option_correct_{idx}") == "on",
                "order_index": idx - 1,
            }
        )

    payload = {
        "text": (form_data.get("text") or "").strip(),
        "type": form_data.get("type") or "single_choice",
        "order_index": form_data.get("order_index") or 0,
        "points": form_data.get("points") or 1,
        "options": options_payload,
    }

    try:
        payload["order_index"] = int(payload["order_index"])
    except ValueError:
        return None, [
            schemas.ValidationResult(
                loc="order_index", msg="Order must be a whole number"
            )
        ]

    try:
        payload["points"] = float(payload["points"])
    except ValueError:
        return None, [
            schemas.ValidationResult(loc="points", msg="Points must be a number")
        ]

    try:
        form = schemas.QuestionForm(**payload)
        return form, []
    except ValidationError as exc:
        return None, schemas.format_errors(exc)


@router.get("/", response_class=HTMLResponse)
def landing() -> RedirectResponse:
    return RedirectResponse(url="/tests", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/tests", response_class=HTMLResponse)
def list_tests(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    base_query = db.query(models.Test)
    if current_user and has_role(current_user, "ADMIN"):
        visible_tests = base_query.order_by(models.Test.created_at.desc()).all()
    elif current_user and has_role(current_user, "AUTHOR"):
        visible_tests = (
            base_query.filter(
                or_(
                    models.Test.is_published.is_(True),
                    models.Test.created_by == current_user.id,
                )
            )
            .order_by(models.Test.created_at.desc())
            .all()
        )
    else:
        visible_tests = (
            base_query.filter(models.Test.is_published.is_(True))
            .order_by(models.Test.created_at.desc())
            .all()
        )

    my_tests = []
    if current_user and has_role(current_user, "AUTHOR"):
        my_tests = (
            base_query.filter(models.Test.created_by == current_user.id)
            .order_by(models.Test.created_at.desc())
            .all()
        )

    return templates.TemplateResponse(
        "tests/list.html",
        {
            "request": request,
            "tests": visible_tests,
            "my_tests": my_tests,
            "current_user": current_user,
            "page_title": "Tests",
        },
    )


@router.get("/tests/new", response_class=HTMLResponse)
def create_test_form(
    request: Request, current_user=Depends(require_author)
):
    return templates.TemplateResponse(
        "tests/form.html",
        {
            "request": request,
            "test": None,
            "form_values": {},
            "errors": [],
            "page_title": "Create Test",
            "current_user": current_user,
        },
    )


@router.post("/tests/new", response_class=HTMLResponse)
async def create_test(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    form_data = await request.form()
    validated, errors = _parse_test_form(form_data)
    if errors or validated is None:
        return templates.TemplateResponse(
            "tests/form.html",
            {
                "request": request,
                "test": None,
                "form_values": _extract_form_values(form_data),
                "errors": errors,
                "page_title": "Create Test",
                "current_user": current_user,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    test = models.Test(
        title=validated.title,
        description=validated.description,
        difficulty=validated.difficulty,
        time_limit_seconds=validated.time_limit_seconds,
        is_published=validated.is_published,
        created_by=current_user.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    return RedirectResponse(
        url=f"/tests/{test.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/tests/{test_id}", response_class=HTMLResponse)
def test_detail(
    request: Request,
    test_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test or not _can_view_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    can_manage = _can_manage_test(test, current_user)
    can_take = bool(current_user) and test.is_published and len(test.questions) > 0
    return templates.TemplateResponse(
        "tests/detail.html",
        {
            "request": request,
            "test": test,
            "can_manage": can_manage,
            "can_take": can_take,
            "current_user": current_user,
            "page_title": test.title,
        },
    )


@router.get("/tests/{test_id}/edit", response_class=HTMLResponse)
def edit_test_form(
    request: Request,
    test_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test or not _can_manage_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return templates.TemplateResponse(
        "tests/form.html",
        {
            "request": request,
            "test": test,
            "form_values": {
                "title": test.title,
                "description": test.description or "",
                "difficulty": "" if test.difficulty is None else str(test.difficulty),
                "time_limit_minutes": ""
                if test.time_limit_seconds is None
                else str(int(test.time_limit_seconds / 60)),
                "is_published": "on" if test.is_published else "",
            },
            "errors": [],
            "page_title": f"Edit {test.title}",
            "current_user": current_user,
        },
    )


@router.post("/tests/{test_id}/edit", response_class=HTMLResponse)
async def update_test(
    request: Request,
    test_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test or not _can_manage_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    form_data = await request.form()
    validated, errors = _parse_test_form(form_data)
    if errors or validated is None:
        return templates.TemplateResponse(
            "tests/form.html",
            {
                "request": request,
                "test": test,
                "form_values": _extract_form_values(form_data),
                "errors": errors,
                "page_title": f"Edit {test.title}",
                "current_user": current_user,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    test.title = validated.title
    test.description = validated.description
    test.difficulty = validated.difficulty
    test.time_limit_seconds = validated.time_limit_seconds
    test.is_published = validated.is_published
    db.add(test)
    db.commit()
    db.refresh(test)

    return RedirectResponse(
        url=f"/tests/{test.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/tests/{test_id}/delete", response_class=HTMLResponse)
def delete_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test or not _can_manage_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    # Ensure attempts (and their answers) are removed before deleting the test to satisfy FK constraints.
    attempt_ids = [
        row.id
        for row in db.query(models.Attempt.id).filter(models.Attempt.test_id == test.id).all()
    ]
    if attempt_ids:
        db.query(models.AttemptAnswer).filter(models.AttemptAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        db.query(models.Attempt).filter(models.Attempt.id.in_(attempt_ids)).delete(synchronize_session=False)

    db.delete(test)
    db.commit()
    return RedirectResponse(url="/tests", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/tests/{test_id}/questions/new", response_class=HTMLResponse)
def create_question_form(
    request: Request,
    test_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test or not _can_manage_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return templates.TemplateResponse(
        "tests/question_form.html",
        {
            "request": request,
            "test": test,
            "form_values": {},
            "errors": [],
            "page_title": f"Add question to {test.title}",
            "action_url": f"/tests/{test.id}/questions/new",
            "current_user": current_user,
        },
    )


@router.post("/tests/{test_id}/questions/new", response_class=HTMLResponse)
async def create_question(
    request: Request,
    test_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test or not _can_manage_test(test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    form_data = await request.form()
    validated, errors = _parse_question_form(form_data)
    if errors or validated is None:
        return templates.TemplateResponse(
            "tests/question_form.html",
            {
                "request": request,
                "test": test,
                "form_values": _extract_form_values(form_data),
                "errors": errors,
                "page_title": f"Add question to {test.title}",
                "action_url": f"/tests/{test.id}/questions/new",
                "current_user": current_user,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    question = models.Question(
        test_id=test.id,
        text=validated.text,
        type=validated.type,
        order_index=validated.order_index,
        points=validated.points,
    )
    db.add(question)
    db.flush()

    for option in validated.options:
        db.add(
            models.AnswerOption(
                question_id=question.id,
                text=option.text,
                is_correct=option.is_correct,
                order_index=option.order_index,
            )
        )

    db.commit()

    return RedirectResponse(
        url=f"/tests/{test.id}", status_code=status.HTTP_303_SEE_OTHER
    )


def _question_to_form_values(question: models.Question) -> dict:
    values = {
        "text": question.text,
        "type": question.type,
        "order_index": str(question.order_index),
        "points": str(question.points),
    }
    for idx, option in enumerate(question.answer_options[:3], start=1):
        values[f"option_text_{idx}"] = option.text
        if option.is_correct:
            values[f"option_correct_{idx}"] = "on"
    return values


def _get_question(db: Session, question_id: int) -> models.Question:
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id)
        .first()
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )
    return question


@router.get("/questions/{question_id}", response_class=HTMLResponse)
def question_detail(
    request: Request,
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    question = _get_question(db, question_id)
    if not _can_view_test(question.test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    can_manage = _can_manage_test(question.test, current_user)
    return templates.TemplateResponse(
        "tests/question_detail.html",
        {
            "request": request,
            "question": question,
            "test": question.test,
            "current_user": current_user,
            "can_manage": can_manage,
            "page_title": f"Question {question.id}",
        },
    )


@router.get("/questions/{question_id}/edit", response_class=HTMLResponse)
def edit_question_form(
    request: Request,
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    question = _get_question(db, question_id)
    if not _can_manage_test(question.test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return templates.TemplateResponse(
        "tests/question_form.html",
        {
            "request": request,
            "test": question.test,
            "form_values": _question_to_form_values(question),
            "errors": [],
            "page_title": f"Edit question #{question.id}",
            "action_url": f"/questions/{question.id}/edit",
            "current_user": current_user,
        },
    )


@router.post("/questions/{question_id}/edit", response_class=HTMLResponse)
async def update_question(
    request: Request,
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    question = _get_question(db, question_id)
    if not _can_manage_test(question.test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    form_data = await request.form()
    validated, errors = _parse_question_form(form_data)
    if errors or validated is None:
        return templates.TemplateResponse(
            "tests/question_form.html",
            {
                "request": request,
                "test": question.test,
                "form_values": _extract_form_values(form_data),
                "errors": errors,
                "page_title": f"Edit question #{question.id}",
                "action_url": f"/questions/{question.id}/edit",
                "current_user": current_user,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    question.text = validated.text
    question.type = validated.type
    question.order_index = validated.order_index
    question.points = validated.points
    question.answer_options.clear()
    if validated.type != "free_text":
        for option in validated.options:
            question.answer_options.append(
                models.AnswerOption(
                    text=option.text,
                    is_correct=option.is_correct,
                    order_index=option.order_index,
                )
            )

    db.add(question)
    db.commit()
    db.refresh(question)

    return RedirectResponse(
        url=f"/tests/{question.test_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/questions/{question_id}/delete", response_class=HTMLResponse)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_author),
):
    question = _get_question(db, question_id)
    if not _can_manage_test(question.test, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    test_id = question.test_id
    db.delete(question)
    db.commit()
    return RedirectResponse(
        url=f"/tests/{test_id}", status_code=status.HTTP_303_SEE_OTHER
    )
