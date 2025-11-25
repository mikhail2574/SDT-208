from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from .. import crud, models, schemas

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/", response_model=schemas.PostOut, status_code=status.HTTP_201_CREATED)
def create_post(post_in: schemas.PostCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_post(db, post_in)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/", response_model=List[schemas.PostOut])
def list_posts(db: Session = Depends(get_db)):
    posts = crud.get_posts(db)
    return posts


@router.get("/{post_id}", response_model=schemas.PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.put("/{post_id}", response_model=schemas.PostOut)
def update_post(post_id: int, post_in: schemas.PostUpdate, db: Session = Depends(get_db)):
    try:
        post = crud.update_post(db, post_id, post_in)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_post(post_id: int, db: Session = Depends(get_db)):
    ok = crud.soft_delete_post(db, post_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")


# Part 5: Query with joins and filters


@router.get("/by-tag/{tag_name}", response_model=List[schemas.PostOut])
def posts_by_tag(tag_name: str, db: Session = Depends(get_db)):
    stmt = (
        select(models.Post)
        .join(models.Post.tags)
        .options(
            joinedload(models.Post.author).joinedload(models.User.profile),
            selectinload(models.Post.tags),
        )
        .where(
            models.Tag.name == tag_name,
            models.Post.archived.is_(False),
        )
    )
    posts = db.execute(stmt).scalars().unique().all()
    return posts


@router.get("/stats", response_model=list[dict])
def post_stats(db: Session = Depends(get_db), min_posts_per_tag: int = Query(1, ge=1)):
    """Return tags with count of posts, filtered by a minimum threshold."""
    stmt = (
        select(
            models.Tag.id.label("tag_id"),
            models.Tag.name.label("tag_name"),
            func.count(models.Post.id).label("post_count"),
        )
        .join(models.Tag.posts)
        .where(models.Post.archived.is_(False))
        .group_by(models.Tag.id, models.Tag.name)
        .having(func.count(models.Post.id) >= min_posts_per_tag)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "tag_id": row.tag_id,
            "tag_name": row.tag_name,
            "post_count": int(row.post_count),
        }
        for row in rows
    ]
