import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User

# In-memory SQLite database shared across connections via StaticPool.
TEST_DATABASE_URL = "sqlite://"


engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_test,
)


@pytest.fixture()
def db_session():
    """Provide a fresh test database session for each test.

    The schema is dropped and recreated for every test function,
    ensuring complete isolation between tests.
    """
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient that uses the in-memory test database.

    We override the application's `get_db` dependency so all requests
    inside tests are served using the in-memory SQLite instead of the
    real on-disk database.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            # Session cleanup is handled by the db_session fixture.
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def user_factory(db_session):
    """Factory fixture that creates users directly in the test database.

    This is useful when a test needs pre-existing data without going
    through the HTTP API.
    """

    def _create_user(email: str, full_name: str) -> User:
        user = User(email=email, full_name=full_name, is_active=True)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user
