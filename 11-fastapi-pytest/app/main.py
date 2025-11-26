from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import Base, engine, get_db

# Create tables on startup so the app is immediately usable.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FastAPI Testing Demo")


@app.post(
    "/users/",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    """Create a new user.

    A small wrapper around the CRUD layer that converts internal errors
    into proper HTTP responses.
    """
    try:
        user = crud.create_user(db, user_in)
    except RuntimeError:
        # In a real system you would log the original exception.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during user creation.",
        )

    return user


@app.get("/users/", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    """Return all users."""
    return crud.get_users(db)


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user.

    Returns 204 on success, 404 if the user does not exist.
    """
    try:
        deleted = crud.delete_user(db, user_id)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during user deletion.",
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # 204 → empty response body
    return None
