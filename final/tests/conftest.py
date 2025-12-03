import os
import time
from typing import Generator

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine.url import make_url

# Ensure the test database URL is set before importing the app
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/testhub_test",
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("SECRET_KEY", "test-secret-key")


def _ensure_test_database() -> None:
    """Create the dedicated test database if it does not exist."""
    url = make_url(TEST_DATABASE_URL)
    admin_url = url.set(database="postgres")
    conn_str = admin_url.render_as_string(hide_password=False).replace("+psycopg", "")

    try:
        with psycopg.connect(conn_str) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,))
                exists = cur.fetchone()
                if not exists:
                    cur.execute(f"CREATE DATABASE {url.database}")
    except Exception:
        # CI will create the DB explicitly; locally we best-effort create and continue.
        pass


_ensure_test_database()

from sqlalchemy.exc import OperationalError

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    """Reset schema for each test for isolation."""
    last_error: OperationalError | None = None
    for _ in range(3):
        try:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            last_error = None
            break
        except OperationalError as exc:
            last_error = exc
            time.sleep(1)

    if last_error:
        pytest.skip(f"PostgreSQL is not available for tests: {last_error}")
    yield


@pytest.fixture()
def client(clean_db) -> Generator[TestClient, None, None]:
    """FastAPI test client that also triggers startup/shutdown hooks."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(client):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
