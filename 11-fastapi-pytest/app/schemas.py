from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    """Schema used for incoming create requests."""
    pass


class UserOut(UserBase):
    """Schema used for responses.

    Includes server-generated fields like id and is_active.
    """

    id: int
    is_active: bool

    class Config:
        from_attributes = True  # Pydantic v2: enables ORM mode
