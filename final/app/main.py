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
from .auth import ensure_roles, has_role
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


def _seed_author_content(db: Session) -> None:
    """Seed requested author account and two sample tests if missing."""
    target_email = "author@gmail.com"
    user = (
        db.query(models.User)
        .filter(models.User.email == target_email)
        .first()
    )
    if not user:
        user = models.User(
            email=target_email,
            full_name="Ralf Author",
            password_hash=pwd_context.hash("AuthorPass123!"),
            is_active=True,
        )
        db.add(user)
        db.flush()

    ensure_roles(db, user, ["AUTHOR", "TEST_TAKER"])

    tests_payload = [
        {
            "title": "Linear Geometry Deep Dive",
            "description": "Vectors, transformations, and spatial intuition for linear algebra and geometry.",
            "difficulty": 4,
            "time_limit_seconds": 1800,
            "questions": [
                {
                    "text": "What does the dot product of two vectors represent?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "A measure of their parallel alignment (projection magnitude)", "is_correct": True},
                        {"text": "The area of the parallelogram they span", "is_correct": False},
                        {"text": "The angle bisector between the vectors", "is_correct": False},
                        {"text": "The length of the cross product", "is_correct": False},
                    ],
                },
                {
                    "text": "When are two non-zero vectors in R^n orthogonal?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "Their dot product is zero", "is_correct": True},
                        {"text": "Their magnitudes are equal", "is_correct": False},
                        {"text": "Their cross product is zero", "is_correct": False},
                        {"text": "They have no shared components", "is_correct": False},
                    ],
                },
                {
                    "text": "Which transformations are distance-preserving isometries in the plane? (Select all that apply.)",
                    "type": "multiple_choice",
                    "points": 1.5,
                    "options": [
                        {"text": "Translation", "is_correct": True},
                        {"text": "Rotation", "is_correct": True},
                        {"text": "Reflection", "is_correct": True},
                        {"text": "Uniform scaling by factor 2", "is_correct": False},
                    ],
                },
                {
                    "text": "The magnitude of the cross product |a × b| equals:",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "|a||b|sin(theta), the area of the parallelogram they span", "is_correct": True},
                        {"text": "|a||b|cos(theta), the projection length", "is_correct": False},
                        {"text": "The volume of the tetrahedron they form", "is_correct": False},
                        {"text": "Always 1 for unit vectors", "is_correct": False},
                    ],
                },
                {
                    "text": "Which pairs form a valid basis for R^2? (Select all that apply.)",
                    "type": "multiple_choice",
                    "points": 1.5,
                    "options": [
                        {"text": "(1, 0) and (0, 1)", "is_correct": True},
                        {"text": "(1, 0) and (2, 0)", "is_correct": False},
                        {"text": "(1, 1) and (1, -1)", "is_correct": True},
                        {"text": "(0, 0) and (1, 1)", "is_correct": False},
                    ],
                },
                {
                    "text": "What is the determinant of a linear transformation in R^2 geometrically?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "Signed area scale factor of the unit square", "is_correct": True},
                        {"text": "The trace of the matrix", "is_correct": False},
                        {"text": "Always positive for rotations", "is_correct": False},
                        {"text": "Sum of eigenvalues", "is_correct": False},
                    ],
                },
                {
                    "text": "Which equation represents the unit circle in R^2?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "x^2 + y^2 = 1", "is_correct": True},
                        {"text": "x + y = 1", "is_correct": False},
                        {"text": "x^2 - y^2 = 1", "is_correct": False},
                        {"text": "x^2 + y^2 = r^2 with r=2", "is_correct": False},
                    ],
                },
                {
                    "text": "For line 3x - 2y + 4 = 0, what is the slope?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "1.5", "is_correct": True},
                        {"text": "-1.5", "is_correct": False},
                        {"text": "0.5", "is_correct": False},
                        {"text": "-0.5", "is_correct": False},
                    ],
                },
                {
                    "text": "In R^2, two vectors u and v are linearly independent if:",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "Neither is a scalar multiple of the other", "is_correct": True},
                        {"text": "They have the same magnitude", "is_correct": False},
                        {"text": "Their dot product equals 1", "is_correct": False},
                        {"text": "They are both unit vectors", "is_correct": False},
                    ],
                },
                {
                    "text": "Select all true statements about eigenvalues of a 2D rotation matrix (non-zero angle).",
                    "type": "multiple_choice",
                    "points": 1.5,
                    "options": [
                        {"text": "There are no real eigenvalues unless the angle is 0 or pi", "is_correct": True},
                        {"text": "Complex eigenvalues have magnitude 1", "is_correct": True},
                        {"text": "Determinant is always -1", "is_correct": False},
                        {"text": "Trace fully determines the rotation angle", "is_correct": True},
                    ],
                },
                {
                    "text": "Which statements about projections onto a subspace are correct? (Select all that apply.)",
                    "type": "multiple_choice",
                    "points": 1.5,
                    "options": [
                        {"text": "Orthogonal projection minimizes distance to the subspace", "is_correct": True},
                        {"text": "Projection matrix P satisfies P^2 = P", "is_correct": True},
                        {"text": "Projection always increases vector length", "is_correct": False},
                        {"text": "Projection onto a line can be written using an outer product", "is_correct": True},
                    ],
                },
            ],
        },
        {
            "title": "Advanced Python Engineering",
            "description": "Async patterns, typing, and production-grade Python techniques.",
            "difficulty": 4,
            "time_limit_seconds": 1800,
            "questions": [
                {
                    "text": "Which standard library module provides the event loop primitives for async I/O?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "asyncio", "is_correct": True},
                        {"text": "multiprocessing", "is_correct": False},
                        {"text": "threading", "is_correct": False},
                        {"text": "subprocess", "is_correct": False},
                    ],
                },
                {
                    "text": "What must an object implement to be used in an 'async with' block?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "__aenter__ and __aexit__", "is_correct": True},
                        {"text": "__enter__ and __exit__", "is_correct": False},
                        {"text": "__await__", "is_correct": False},
                        {"text": "__call__", "is_correct": False},
                    ],
                },
                {
                    "text": "Which tool lets you manage a dynamic set of context managers safely?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "contextlib.ExitStack", "is_correct": True},
                        {"text": "contextvars.copy_context", "is_correct": False},
                        {"text": "functools.partial", "is_correct": False},
                        {"text": "itertools.chain", "is_correct": False},
                    ],
                },
                {
                    "text": "Which start method is safest on macOS to avoid fork-related issues?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "spawn", "is_correct": True},
                        {"text": "fork", "is_correct": False},
                        {"text": "forkserver", "is_correct": False},
                        {"text": "thread", "is_correct": False},
                    ],
                },
                {
                    "text": "Pick all statements that describe functools.lru_cache correctly.",
                    "type": "multiple_choice",
                    "points": 1.5,
                    "options": [
                        {"text": "It memoizes function calls based on arguments", "is_correct": True},
                        {"text": "Cached results can be cleared with .cache_clear()", "is_correct": True},
                        {"text": "It supports maxsize limits", "is_correct": True},
                        {"text": "It works only on async functions", "is_correct": False},
                    ],
                },
                {
                    "text": "Which typing annotation fits a callable taking an int and returning str?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "Callable[[int], str]", "is_correct": True},
                        {"text": "Function[int, str]", "is_correct": False},
                        {"text": "callable<int, str>", "is_correct": False},
                        {"text": "Typing[int -> str]", "is_correct": False},
                    ],
                },
                {
                    "text": "How do you create a modified copy of a dataclass instance without mutating the original?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "Use dataclasses.replace(instance, field=value)", "is_correct": True},
                        {"text": "Directly assign to the field", "is_correct": False},
                        {"text": "Call instance.copy()", "is_correct": False},
                        {"text": "Re-run __init__", "is_correct": False},
                    ],
                },
                {
                    "text": "Select all safe practices for SQL query execution.",
                    "type": "multiple_choice",
                    "points": 1.5,
                    "options": [
                        {"text": "Use parameterized queries/placeholders", "is_correct": True},
                        {"text": "Concatenate user input into SQL strings", "is_correct": False},
                        {"text": "Limit privileges of the DB user", "is_correct": True},
                        {"text": "Validate untrusted input before using it", "is_correct": True},
                    ],
                },
                {
                    "text": "Which statement about asyncio.gather is true?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "It aggregates awaitables and raises on the first exception by default", "is_correct": True},
                        {"text": "It always ignores exceptions", "is_correct": False},
                        {"text": "It cancels all tasks immediately on completion", "is_correct": False},
                        {"text": "It serializes awaitables", "is_correct": False},
                    ],
                },
                {
                    "text": "When should you define a typing.Protocol?",
                    "type": "single_choice",
                    "points": 1.0,
                    "options": [
                        {"text": "When you want structural subtyping contracts for implementers", "is_correct": True},
                        {"text": "When you need a runtime ABC check", "is_correct": False},
                        {"text": "Only for numeric types", "is_correct": False},
                        {"text": "Never; Protocol is deprecated", "is_correct": False},
                    ],
                },
                {
                    "text": "Which features are shared by dataclasses and attrs? (Select all that apply.)",
                    "type": "multiple_choice",
                    "points": 1.5,
                    "options": [
                        {"text": "Auto-generated __init__", "is_correct": True},
                        {"text": "Field defaults and validators", "is_correct": True},
                        {"text": "Pattern matching support via __match_args__", "is_correct": True},
                        {"text": "Singleton enforcement", "is_correct": False},
                    ],
                },
            ],
        },
    ]

    for test_payload in tests_payload:
        existing_test = (
            db.query(models.Test)
            .filter(
                models.Test.title == test_payload["title"],
                models.Test.created_by == user.id,
            )
            .first()
        )
        if existing_test:
            continue

        test = models.Test(
            title=test_payload["title"],
            description=test_payload.get("description"),
            difficulty=test_payload.get("difficulty"),
            time_limit_seconds=test_payload.get("time_limit_seconds"),
            is_published=True,
            created_by=user.id,
        )
        db.add(test)
        db.flush()

        for idx, q in enumerate(test_payload["questions"]):
            question = models.Question(
                test_id=test.id,
                text=q["text"],
                type=q["type"],
                order_index=idx,
                points=q.get("points", 1.0),
            )
            db.add(question)
            db.flush()
            for opt_idx, opt in enumerate(q["options"]):
                db.add(
                    models.AnswerOption(
                        question_id=question.id,
                        text=opt["text"],
                        is_correct=opt.get("is_correct", False),
                        order_index=opt_idx,
                    )
                )


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_defaults(db)
        _seed_author_content(db)
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
