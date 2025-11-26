from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user, has_role, require_user
from ..database import get_db

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.globals["has_role"] = has_role


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
):
    attempts = (
        db.query(models.Attempt)
        .filter(models.Attempt.user_id == current_user.id)
        .order_by(models.Attempt.finished_at.desc().nullslast(), models.Attempt.id.desc())
        .limit(10)
        .all()
    )
    can_author = has_role(current_user, "AUTHOR") or has_role(current_user, "ADMIN")
    my_tests = []
    if can_author:
        my_tests = (
            db.query(models.Test)
            .filter(models.Test.created_by == current_user.id)
            .order_by(models.Test.created_at.desc())
            .all()
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "attempts": attempts,
            "my_tests": my_tests,
            "can_author": can_author,
            "page_title": "Dashboard",
        },
    )
