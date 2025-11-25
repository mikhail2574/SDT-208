from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/tags", tags=["tags"])


@router.post("/", response_model=schemas.TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(tag_in: schemas.TagCreate, db: Session = Depends(get_db)):
    stmt = select(models.Tag).where(models.Tag.name == tag_in.name)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Tag with this name already exists")

    tag = models.Tag(name=tag_in.name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.get("/", response_model=List[schemas.TagOut])
def list_tags(db: Session = Depends(get_db)):
    stmt = select(models.Tag).order_by(models.Tag.name)
    return list(db.execute(stmt).scalars().all())
