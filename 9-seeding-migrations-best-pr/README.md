# SQLAlchemy ORM + Alembic: Migrations, Seeding, and Query Optimization

This project demonstrates:

- Alembic migrations (new table, relationships, and column modification)
- Database seeding with Faker, parameters, and idempotency
- Query optimization patterns using SQLAlchemy 2.0 ORM

## Setup (MacOS)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running Alembic migrations

The database URL is configured for a local SQLite file `app.db` in the project root.

```bash
# Upgrade all migrations
alembic upgrade head
```

This will create:

- `users`, `posts`, `comments`, `tags`, `post_tags` tables (initial schema)
- `user_profiles` table (1-1 to `users`)
- `users.is_premium` column with a default of `0` / `False`

## Seeding the database

Run the seeder after applying migrations:

```bash
python -m app.seeds --users 10 --posts-per-user 3
```

Parameters:

- `--users`: number of user records to create (default: 10)
- `--posts-per-user`: number of posts per user (default: 3)

The seeder is idempotent:

- Users are keyed by deterministic emails like `user1@example.com`.
- Posts are keyed by `(user_id, title)` combinations.
- Re-running the seeder will not create duplicates.

## Query optimization examples

To see optimized vs. naive queries (with SQL echo output enabled):

```bash
python -m app.optimized_queries
```

This script demonstrates:

- Fixing N+1 query problems using `selectinload`
- Avoiding over-fetching using `select(Post.id, Post.title)`
- Filtering in SQL instead of in Python
- Adding pagination with `limit` / `offset`

```

```
