from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import models
from .auth import has_role
from .config import settings
from .database import Base, SessionLocal, engine
from .routes import auth as auth_routes
from .routes import attempts as attempts_routes
from .routes import pages as pages_routes
from .routes import tests as tests_routes

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="testhub_session",
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

base_path = Path(__file__).resolve().parent
static_dir = base_path / "static"
templates = Jinja2Templates(directory=str(base_path / "templates"))
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["has_role"] = has_role
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def _seed_defaults(db: Session) -> None:
    role_names = {
        "ADMIN": "Platform administrator",
        "AUTHOR": "Can create and manage own tests",
        "TEST_TAKER": "Can browse and take tests",
    }
    existing_roles = {role.name: role for role in db.query(models.Role).all()}
    for name, description in role_names.items():
        if name not in existing_roles:
            role = models.Role(name=name, description=description)
            db.add(role)
            existing_roles[name] = role

    admin = (
        db.query(models.User)
        .filter(models.User.email == settings.default_admin_email)
        .first()
    )
    if not admin:
        admin = models.User(
            email=settings.default_admin_email,
            full_name=settings.default_admin_name,
            password_hash=pwd_context.hash(settings.default_admin_password),
        )
        db.add(admin)
        db.flush()

    admin_role = existing_roles.get("ADMIN")
    if admin_role and admin_role not in admin.roles:
        admin.roles.append(admin_role)
    author_role = existing_roles.get("AUTHOR")
    if author_role and author_role not in admin.roles:
        admin.roles.append(author_role)
    test_taker_role = existing_roles.get("TEST_TAKER")
    if test_taker_role and test_taker_role not in admin.roles:
        admin.roles.append(test_taker_role)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_defaults(db)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "*/*" in accept


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    if _wants_html(request):
        template_name = "errors/404.html" if exc.status_code == 404 else "errors/generic.html"
        return templates.TemplateResponse(
            template_name,
            {"request": request, "detail": exc.detail, "status_code": exc.status_code},
            status_code=exc.status_code,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error", exc_info=exc)
    if _wants_html(request):
        return templates.TemplateResponse(
            "errors/generic.html",
            {"request": request, "detail": "Internal server error", "status_code": 500},
            status_code=500,
        )
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


app.include_router(tests_routes.router)
app.include_router(auth_routes.router)
app.include_router(attempts_routes.router)
app.include_router(pages_routes.router)
