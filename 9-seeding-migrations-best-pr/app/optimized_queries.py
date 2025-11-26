from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload, load_only

from .database import SessionLocal
from .models import User, Post


def n_plus_one_bad() -> None:
    """Naive N+1 pattern: one query for parents, one per parent for children."""
    print("\n--- N+1 BAD ---")
    with SessionLocal() as session:
        # This executes a single SELECT * FROM users query and returns ORM User objects.
        users = session.scalars(select(User)).all()

        # For each user, accessing u.posts triggers a separate lazy-load query:
        # SELECT * FROM posts WHERE posts.user_id = <user.id>
        # So with N users we get N extra queries -> "N+1" total.
        for u in users:
            print(f"{u.email} has {len(u.posts)} posts")


def n_plus_one_optimized() -> None:
    """Fix N+1 by eager-loading posts with selectinload."""
    print("\n--- N+1 OPTIMIZED (selectinload) ---")
    with SessionLocal() as session:
        # selectinload(User.posts) tells SQLAlchemy to:
        # 1) Load all users in one query.
        # 2) Then issue a SECOND query:
        #    SELECT * FROM posts WHERE posts.user_id IN (<all user ids>).
        #
        # This reduces N+1 queries to just 2 queries, regardless of how many users we have.
        stmt = select(User).options(selectinload(User.posts))
        users = session.scalars(stmt).all()

        # Now u.posts is already populated in memory; accessing it does NOT trigger
        # additional queries.
        for u in users:
            print(f"{u.email} has {len(u.posts)} posts")


def overfetching_bad() -> None:
    """Fetch full Post objects when only id and title are needed."""
    print("\n--- OVER-FETCHING BAD ---")
    with SessionLocal() as session:
        # This loads full Post objects with all columns:
        # id, user_id, title, body, created_at, ...
        posts = session.scalars(select(Post)).all()

        # But we only use p.id and p.title. The rest of the data is wasted bandwidth and memory.
        for p in posts:
            print(p.id, p.title)


def overfetching_optimized() -> None:
    """Fetch only the fields that are actually needed."""
    print("\n--- OVER-FETCHING OPTIMIZED (projection) ---")
    with SessionLocal() as session:
        # Projection query: we request only Post.id and Post.title from the database.
        # The result is a list of (id, title) tuples instead of full ORM objects.
        rows = session.execute(select(Post.id, Post.title)).all()
        for post_id, title in rows:
            print(post_id, title)

    print("\n--- OVER-FETCHING OPTIMIZED (load_only) ---")
    with SessionLocal() as session:
        # Alternatively, we still want ORM Post objects, but we know that for this code path
        # we only need the id and title fields.
        #
        # load_only tells SQLAlchemy to load only these columns and skip the rest.
        stmt = select(Post).options(load_only(Post.id, Post.title))
        posts = session.scalars(stmt).all()
        for p in posts:
            print(p.id, p.title)


def filtering_bad() -> None:
    """Filter in Python instead of in SQL."""
    print("\n--- FILTERING BAD (Python-side) ---")
    with SessionLocal() as session:
        # This loads ALL users from the database, regardless of their status.
        users = session.scalars(select(User)).all()

        # Filtering is done in Python. The database does extra work sending useless rows,
        # and the application wastes memory and CPU to filter them out.
        active_users = [u for u in users if u.is_active]
        print(f"Active users (Python): {len(active_users)}")


def filtering_optimized() -> None:
    """Filter directly in SQL using WHERE."""
    print("\n--- FILTERING OPTIMIZED (SQL WHERE) ---")
    with SessionLocal() as session:
        # The WHERE clause pushes the filter down to the database.
        # Only matching rows are transferred over the network.
        stmt = select(User).where(User.is_active.is_(True))
        active_users = session.scalars(stmt).all()
        print(f"Active users (SQL): {len(active_users)}")


def pagination_bad() -> None:
    """Load all records at once, no pagination."""
    print("\n--- PAGINATION BAD (no limit) ---")
    with SessionLocal() as session:
        # This loads *all* posts into memory in one go.
        # For a large table this can be extremely slow and memory-heavy.
        posts = session.scalars(select(Post)).all()
        print(f"Loaded {len(posts)} posts in one go (unpaginated).")


def pagination_optimized(page: int = 1, page_size: int = 10) -> None:
    """Use LIMIT/OFFSET for pagination."""
    print("\n--- PAGINATION OPTIMIZED ---")
    # Calculate OFFSET based on the page number and page size.
    offset = (page - 1) * page_size

    with SessionLocal() as session:
        # We request only a single "page" of results: at most `page_size` posts.
        # ORDER BY is important to have stable, deterministic pagination.
        stmt = (
            select(Post)
            .order_by(Post.id)
            .limit(page_size)
            .offset(offset)
        )
        posts = session.scalars(stmt).all()

        print(f"Page {page} (page size {page_size}) -> {len(posts)} posts loaded.")
        for p in posts:
            print(f"- Post {p.id}: {p.title}")


def main() -> None:
    # Demonstrate each pair of naive vs optimized patterns.
    n_plus_one_bad()
    n_plus_one_optimized()

    overfetching_bad()
    overfetching_optimized()

    filtering_bad()
    filtering_optimized()

    pagination_bad()
    pagination_optimized(page=1, page_size=10)


if __name__ == "__main__":
    main()
