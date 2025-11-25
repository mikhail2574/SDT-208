from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ----- Tag Schemas -----


class TagBase(BaseModel):
    name: str = Field(..., max_length=100)


class TagCreate(TagBase):
    pass


class TagOut(TagBase):
    id: int

    class Config:
        orm_mode = True


# ----- User Profile Schemas -----


class UserProfileBase(BaseModel):
    bio: Optional[str] = None
    website: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileOut(UserProfileBase):
    id: int

    class Config:
        orm_mode = True


# ----- Post Schemas -----


class PostBase(BaseModel):
    title: str = Field(..., max_length=255)
    content: str


class PostCreate(PostBase):
    author_id: int
    tag_ids: List[int] = []


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    tag_ids: Optional[List[int]] = None


class PostOut(PostBase):
    id: int
    archived: bool
    created_at: datetime
    author_id: int
    tags: List[TagOut] = []

    class Config:
        orm_mode = True


# ----- User Schemas -----


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., max_length=255)


class UserCreate(UserBase):
    profile: Optional[UserProfileCreate] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    profile: Optional[UserProfileCreate] = None


class UserOut(UserBase):
    id: int
    archived: bool
    created_at: datetime
    profile: Optional[UserProfileOut] = None
    posts: List[PostOut] = []

    class Config:
        orm_mode = True
