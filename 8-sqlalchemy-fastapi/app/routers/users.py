from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from ..database import get_db
from .. import crud, models, schemas

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_user(db, user_in)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return crud.get_users(db)


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: int, user_in: schemas.UserUpdate, db: Session = Depends(get_db)):
    try:
        user = crud.update_user(db, user_id, user_in)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(user_id: int, db: Session = Depends(get_db)):
    ok = crud.soft_delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")


# Advanced querying endpoints


@router.get("/with-many-posts/{min_posts}", response_model=List[schemas.UserOut])
def users_with_many_posts(min_posts: int, db: Session = Depends(get_db)):
    """Return users with at least `min_posts` non-archived posts."""
    stmt = (
        select(models.User)
        .join(models.User.posts)
        .where(models.User.archived.is_(False), models.Post.archived.is_(False))
        .group_by(models.User.id)
        .having(func.count(models.Post.id) >= min_posts)
        .options(
            func.nullif(1, 1)  # placeholder; relationships are loaded via default lazy strategy
        )
    )

    # SQLAlchemy does not like non-Loader options like func.nullif here; instead we will not use options.
    stmt = (
        select(models.User)
        .join(models.User.posts)
        .where(models.User.archived.is_(False), models.Post.archived.is_(False))
        .group_by(models.User.id)
        .having(func.count(models.Post.id) >= min_posts)
    )

    users = db.execute(stmt).scalars().unique().all()
    # Eager-load related objects manually if needed
    for user in users:
        _ = user.profile
        _ = user.posts
    return users


@router.get("/avg-title-length", response_model=list[dict])
def users_avg_post_title_length(db: Session = Depends(get_db)):
    """Calculate average post title length per user."""
    stmt = (
        select(
            models.User.id.label("user_id"),
            models.User.full_name.label("full_name"),
            func.avg(func.length(models.Post.title)).label("avg_title_length"),
        )
        .join(models.Post, models.Post.author_id == models.User.id)
        .where(models.User.archived.is_(False), models.Post.archived.is_(False))
        .group_by(models.User.id, models.User.full_name)
        .having(func.count(models.Post.id) > 0)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "user_id": row.user_id,
            "full_name": row.full_name,
            "avg_title_length": float(row.avg_title_length),
        }
        for row in rows
    ]
