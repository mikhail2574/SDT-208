from typing import Iterable, Optional

from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def has_role(user: Optional[User], role_name: str) -> bool:
    if not user:
        return False
    return any(role.name == role_name for role in user.roles)


def ensure_roles(db: Session, user: User, role_names: Iterable[str]) -> None:
    existing = {role.name: role for role in db.query(Role).filter(Role.name.in_(role_names)).all()}
    for name in role_names:
        role = existing.get(name)
        if role and role not in user.roles:
            user.roles.append(role)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return (
        db.query(User)
        .filter(User.id == user_id, User.is_active.is_(True))
        .first()
    )


def require_user(current_user: Optional[User] = Depends(get_current_user)) -> User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in to continue.",
        )
    return current_user


def require_author(current_user: User = Depends(require_user)) -> User:
    if not (has_role(current_user, "AUTHOR") or has_role(current_user, "ADMIN")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Author permissions are required.",
        )
    return current_user
