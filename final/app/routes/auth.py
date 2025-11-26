from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..auth import ensure_roles, get_current_user, hash_password, verify_password, has_role
from ..database import get_db

router = APIRouter(tags=["auth"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.globals["has_role"] = has_role


def _render(request: Request, template: str, context: dict, current_user=None) -> HTMLResponse:
    base_context = {"request": request, "current_user": current_user}
    base_context.update(context)
    return templates.TemplateResponse(template, base_context)


def _require_logged_out(current_user):
    if current_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already logged in.",
        )


@router.get("/auth/register", response_class=HTMLResponse)
def register_form(request: Request, current_user=Depends(get_current_user)):
    _require_logged_out(current_user)
    return _render(
        request,
        "auth/register.html",
        {"errors": [], "form_values": {}, "page_title": "Create account"},
        current_user=current_user,
    )


@router.post("/auth/register", response_class=HTMLResponse)
async def register(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require_logged_out(current_user)
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    full_name = (form.get("full_name") or "").strip()
    wants_author = form.get("wants_author") == "on"

    errors = []
    if not email or "@" not in email:
        errors.append("Valid email is required.")
    if not full_name:
        errors.append("Full name is required.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")

    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        errors.append("This email is already registered.")

    if errors:
        return _render(
            request,
            "auth/register.html",
            {
                "errors": errors,
                "form_values": dict(form),
                "page_title": "Create account",
            },
            current_user=current_user,
        )

    user = models.User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    db.flush()
    ensure_roles(db, user, ["TEST_TAKER"])
    if wants_author:
        ensure_roles(db, user, ["AUTHOR"])
    db.commit()
    request.session["user_id"] = user.id

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/auth/login", response_class=HTMLResponse)
def login_form(request: Request, current_user=Depends(get_current_user)):
    _require_logged_out(current_user)
    return _render(
        request,
        "auth/login.html",
        {"errors": [], "form_values": {}, "page_title": "Login"},
        current_user=current_user,
    )


@router.post("/auth/login", response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require_logged_out(current_user)
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    errors = []
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        errors.append("Invalid email or password.")
    if errors:
        return _render(
            request,
            "auth/login.html",
            {"errors": errors, "form_values": dict(form), "page_title": "Login"},
            current_user=current_user,
        )

    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
