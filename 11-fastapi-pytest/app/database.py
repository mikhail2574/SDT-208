from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# File-based SQLite for the real application runtime.
SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Yield a database session and make sure it is always closed.

    Endpoints are responsible for doing commit / rollback explicitly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
