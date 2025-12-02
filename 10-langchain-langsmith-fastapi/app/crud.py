from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from . import models


DEMO_USER_EMAIL = "demo.user@example.com"
DEMO_USER_NAME = "Demo User"


def get_or_create_demo_user(db: Session) -> models.User:
    """Return a single demo user; create and seed tasks on first run."""
    user = db.query(models.User).filter(models.User.email == DEMO_USER_EMAIL).first()
    if user is None:
        user = models.User(email=DEMO_USER_EMAIL, name=DEMO_USER_NAME)
        db.add(user)
        db.commit()
        db.refresh(user)

        # Seed some simple demo tasks for DB context
        seed_titles = [
            "Finish LangChain + FastAPI homework",
            "Review pull requests from the backend team",
            "Plan a short weekend trip",
            "Clean up the inbox and respond to priority emails",
        ]
        for title in seed_titles:
            task = models.Task(user_id=user.id, title=title, is_done=False)
            db.add(task)
        db.commit()
    return user


def get_top_tasks_for_user(db: Session, user: models.User, limit: int = 3) -> List[models.Task]:
    return (
        db.query(models.Task)
        .filter(models.Task.user_id == user.id)
        .order_by(models.Task.created_at.desc())
        .limit(limit)
        .all()
    )


def format_tasks_context(tasks: List[models.Task]) -> str:
    if not tasks:
        return "This user currently has no tasks stored in the database."

    lines = []
    for idx, task in enumerate(tasks, start=1):
        status = "done" if task.is_done else "open"
        lines.append(f"{idx}. ({status}) {task.title}")
    return "\n".join(lines)


def get_recent_messages(db: Session, user: models.User, limit: int = 10) -> List[models.ChatMessage]:
    """Return the most recent `limit` messages for this user, ordered oldest → newest."""
    records = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.user_id == user.id)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    # We fetched newest first; reverse to oldest first for a natural history order.
    return list(reversed(records))


def save_chat_messages(
    db: Session,
    user: models.User,
    user_message: str,
    assistant_answer: str,
) -> None:
    """Persist one conversation turn (user + assistant messages)."""
    now = datetime.now()
    user_msg = models.ChatMessage(
        user_id=user.id,
        role="user",
        content=user_message,
        created_at=now,
    )
    assistant_msg = models.ChatMessage(
        user_id=user.id,
        role="assistant",
        content=assistant_answer,
        created_at=now,
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()
