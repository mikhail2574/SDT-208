from fastapi import FastAPI

from .database import Base, engine
from .routers import posts, tags, users

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SQLAlchemy ORM & FastAPI Demo",
    description=(
        "Demo project showing session management, relationships, "
        "ORM-style queries and aggregations."
    ),
)

app.include_router(users.router)
app.include_router(posts.router)
app.include_router(tags.router)


@app.get("/")
def read_root():
    return {"message": "FastAPI + SQLAlchemy ORM demo is up"}
