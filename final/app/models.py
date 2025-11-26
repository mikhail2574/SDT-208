from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    roles = relationship("Role", secondary="user_roles", back_populates="users")
    tests = relationship("Test", back_populates="creator")
    attempts = relationship("Attempt", back_populates="user")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)

    users = relationship("User", secondary="user_roles", back_populates="roles")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="user_role_uc"),)

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)


class Test(Base, TimestampMixin):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    difficulty = Column(SmallInteger)
    time_limit_seconds = Column(Integer)
    is_published = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    creator = relationship("User", back_populates="tests")
    questions = relationship(
        "Question",
        back_populates="test",
        order_by="Question.order_index",
        cascade="all, delete-orphan",
    )
    attempts = relationship("Attempt", back_populates="test")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    type = Column(String, nullable=False)  # single_choice, multiple_choice, free_text
    order_index = Column(Integer, nullable=False, default=0)
    points = Column(Numeric(5, 2), nullable=False, default=1.0)

    test = relationship("Test", back_populates="questions")
    answer_options = relationship(
        "AnswerOption",
        back_populates="question",
        order_by="AnswerOption.order_index",
        cascade="all, delete-orphan",
    )
    attempt_answers = relationship("AttemptAnswer", back_populates="question")


class AnswerOption(Base):
    __tablename__ = "answer_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)

    question = relationship("Question", back_populates="answer_options")
    selected_in_answers = relationship(
        "AttemptAnswer", back_populates="selected_option"
    )


class Attempt(Base, TimestampMixin):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime)
    status = Column(String, nullable=False)  # in_progress, completed, cancelled
    score_obtained = Column(Numeric(6, 2))
    max_score_cached = Column(Numeric(6, 2), nullable=False, default=0)

    user = relationship("User", back_populates="attempts")
    test = relationship("Test", back_populates="attempts")
    answers = relationship("AttemptAnswer", back_populates="attempt")


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_option_id = Column(Integer, ForeignKey("answer_options.id"))
    free_text_answer = Column(Text)
    is_correct = Column(Boolean)
    points_obtained = Column(Numeric(5, 2))

    attempt = relationship("Attempt", back_populates="answers")
    question = relationship("Question", back_populates="attempt_answers")
    selected_option = relationship("AnswerOption", back_populates="selected_in_answers")
