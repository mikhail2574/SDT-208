from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from . import models, schemas


def get_users(db: Session) -> list[models.User]:
    """Return all users in the database."""
    return db.query(models.User).all()


def create_user(db: Session, user_in: schemas.UserCreate) -> models.User:
    """Create a new user.

    This function deliberately wraps low-level SQLAlchemy errors into a
    generic RuntimeError so the API layer can translate it into a clean
    HTTP response.
    """
    user = models.User(
        email=user_in.email,
        full_name=user_in.full_name,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        # Re-raise a simplified error for the API layer to handle.
        raise RuntimeError("Database commit failed") from exc

    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user by id.

    Returns:
        True if a user was deleted, False if the user did not exist.

    Raises:
        RuntimeError: if the database commit fails.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        return False

    db.delete(user)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError("Database commit failed") from exc

    return True
