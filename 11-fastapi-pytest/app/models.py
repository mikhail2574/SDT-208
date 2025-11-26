from sqlalchemy import Boolean, Column, Integer, String
from .database import Base


class User(Base):
    """Simple User model used for testing.

    In a real project you would include authentication fields,
    password hashes, timestamps, etc. Here we keep it deliberately small.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    full_name = Column(String(256), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
