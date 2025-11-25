# FastAPI + SQLAlchemy ORM Demo

This project implements all parts of the SQLAlchemy ORM and FastAPI integration assignment:

- Session management and unit of work
- ORM models with one-to-one, one-to-many, and many-to-many relationships
- Pydantic schemas with nested related objects
- CRUD operations via FastAPI routers
- Joins, filters, aggregations, and HAVING clauses using SQLAlchemy 2.x style

## Quick start (For Mac)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open the interactive docs at `http://127.0.0.1:8000/docs`.

## Domain model

- **User**
  - One-to-one with **UserProfile**
  - One-to-many with **Post**
  - Soft-delete via `archived` flag
- **UserProfile**
  - Holds additional information about a user
- **Post**
  - Belongs to one **User** (`author`)
  - Many-to-many with **Tag**
  - Soft-delete via `archived` flag
- **Tag**
  - Many-to-many with **Post** through `post_tags` association table

## Notable endpoints

- CRUD:
  - `POST /users`, `GET /users`, `GET /users/{id}`, `PUT /users/{id}`, `DELETE /users/{id}`
  - `POST /posts`, `GET /posts`, `GET /posts/{id}`, `PUT /posts/{id}`, `DELETE /posts/{id}`
- Joins and filters:
  - `GET /posts/by-tag/{tag_name}`
  - `GET /users/with-many-posts/{min_posts}`
- Aggregations:
  - `GET /posts/stats?min_posts_per_tag=N`
  - `GET /users/avg-title-length`

The project uses `selectinload` / `joinedload` where appropriate to fetch related entities efficiently.
