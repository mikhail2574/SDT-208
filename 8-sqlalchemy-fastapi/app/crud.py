from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from . import models, schemas


# User CRUD


def create_user(db: Session, user_in: schemas.UserCreate) -> models.User:
    user = models.User(email=user_in.email, full_name=user_in.full_name)
    if user_in.profile:
        user.profile = models.UserProfile(
            bio=user_in.profile.bio,
            website=user_in.profile.website,
        )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> Optional[models.User]:
    stmt = (
        select(models.User)
        .options(
            joinedload(models.User.profile), # left outer join, for 1:1
            selectinload(models.User.posts).selectinload(models.Post.tags), # for 1:n
        )
        .where(models.User.id == user_id, models.User.archived.is_(False))
    )
    return db.execute(stmt).scalar_one_or_none()


def get_users(db: Session) -> List[models.User]:
    stmt = (
        select(models.User)
        .options(
            joinedload(models.User.profile),
            selectinload(models.User.posts).selectinload(models.Post.tags),
        )
        .where(models.User.archived.is_(False))
        .order_by(models.User.id)
    )
    return list(db.execute(stmt).scalars().all())


def update_user(db: Session, user_id: int, user_in: schemas.UserUpdate) -> Optional[models.User]:
    user = db.get(models.User, user_id)
    if not user or user.archived:
        return None

    if user_in.full_name is not None:
        user.full_name = user_in.full_name

    if user_in.profile is not None:
        if user.profile is None:
            user.profile = models.UserProfile(
                bio=user_in.profile.bio,
                website=user_in.profile.website,
            )
        else:
            user.profile.bio = user_in.profile.bio
            user.profile.website = user_in.profile.website

    db.commit()
    db.refresh(user)
    return user


def soft_delete_user(db: Session, user_id: int) -> bool:
    user = db.get(models.User, user_id)
    if not user or user.archived:
        return False
    user.archived = True
    db.commit()
    return True


# Tag CRUD


def get_or_create_tags(db: Session, tag_ids: List[int]) -> List[models.Tag]:
    if not tag_ids:
        return []
    stmt = select(models.Tag).where(models.Tag.id.in_(tag_ids))
    tags = list(db.execute(stmt).scalars().all())
    return tags


# Post CRUD


def create_post(db: Session, post_in: schemas.PostCreate) -> models.Post:
    author = db.get(models.User, post_in.author_id)
    if not author or author.archived:
        raise ValueError("Author not found or archived")

    post = models.Post(
        author_id=post_in.author_id,
        title=post_in.title,
        content=post_in.content,
    )
    if post_in.tag_ids:
        post.tags = get_or_create_tags(db, post_in.tag_ids)

    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def get_post(db: Session, post_id: int) -> Optional[models.Post]:
    stmt = (
        select(models.Post)
        .options(
            joinedload(models.Post.author).joinedload(models.User.profile),
            selectinload(models.Post.tags),
        )
        .where(models.Post.id == post_id, models.Post.archived.is_(False))
    )
    return db.execute(stmt).scalar_one_or_none()


def get_posts(db: Session) -> List[models.Post]:
    stmt = (
        select(models.Post)
        .options(
            joinedload(models.Post.author).joinedload(models.User.profile),
            selectinload(models.Post.tags),
        )
        .where(models.Post.archived.is_(False))
        .order_by(models.Post.id)
    )
    return list(db.execute(stmt).scalars().all())


def update_post(db: Session, post_id: int, post_in: schemas.PostUpdate) -> Optional[models.Post]:
    post = db.get(models.Post, post_id)
    if not post or post.archived:
        return None

    if post_in.title is not None:
        post.title = post_in.title
    if post_in.content is not None:
        post.content = post_in.content
    if post_in.tag_ids is not None:
        post.tags = get_or_create_tags(db, post_in.tag_ids)

    db.commit()
    db.refresh(post)
    return post


def soft_delete_post(db: Session, post_id: int) -> bool:
    post = db.get(models.Post, post_id)
    if not post or post.archived:
        return False
    post.archived = True
    db.commit()
    return True
