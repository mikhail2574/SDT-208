from __future__ import annotations

import argparse
from typing import Dict

from faker import Faker
from sqlalchemy import select

from .database import session_scope
from .models import User, UserProfile, Post, Comment, Tag


fake = Faker()
Faker.seed(1234)


def get_or_create_tag_map(session) -> Dict[str, Tag]:
    """Ensure a small set of tags exists and return them keyed by name."""
    base_tags = ["python", "sqlalchemy", "fastapi", "alembic", "testing"]
    existing = {
        t.name: t
        for t in session.scalars(
            select(Tag).where(Tag.name.in_(base_tags))
        ).all()
    }

    for name in base_tags:
        if name not in existing:
            tag = Tag(name=name)
            session.add(tag)
            existing[name] = tag

    return existing


def seed(users_count: int, posts_per_user: int) -> None:
    """Seed the database with deterministic, idempotent data.

    - Users are uniquely identified by email: user{n}@example.com
    - Each user gets a 1–1 UserProfile
    - Each user gets N posts with deterministic titles
    - Each post gets a couple of comments
    """
    with session_scope() as session:
        tag_map = get_or_create_tag_map(session)

        # Preload existing users keyed by email
        existing_users = {
            u.email: u for u in session.scalars(select(User)).all()
        }

        for i in range(1, users_count + 1):
            email = f"user{i}@example.com"
            user = existing_users.get(email)
            if not user:
                user = User(
                    email=email,
                    name=fake.name(),
                )
                session.add(user)
                session.flush()  # assign user.id
                profile = UserProfile(
                    user=user,
                    bio=fake.text(max_nb_chars=200),
                    birthday=fake.date_of_birth(minimum_age=18, maximum_age=70),
                )
                session.add(profile)
                existing_users[email] = user

            # Posts for this user
            for j in range(1, posts_per_user + 1):
                title = f"Post {j} by {email}"
                existing_post = session.scalar(
                    select(Post).where(
                        Post.user_id == user.id,
                        Post.title == title,
                    )
                )
                if existing_post:
                    continue

                post = Post(
                    author=user,
                    title=title,
                    body=fake.paragraph(nb_sentences=5),
                )
                # Attach a couple of tags in a semi-random but deterministic way
                post.tags.append(tag_map["python"])
                if i % 2 == 0:
                    post.tags.append(tag_map["sqlalchemy"])
                if j % 2 == 1:
                    post.tags.append(tag_map["alembic"])

                session.add(post)
                session.flush()

                # Comments
                for _ in range(2):
                    c = Comment(
                        post=post,
                        author_name=fake.name(),
                        body=fake.sentence(),
                    )
                    session.add(c)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the database.")
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Number of users to create (default: 10).",
    )
    parser.add_argument(
        "--posts-per-user",
        type=int,
        default=3,
        help="Number of posts per user (default: 3).",
    )
    args = parser.parse_args()

    seed(users_count=args.users, posts_per_user=args.posts_per_user)
    print("Seeding complete.")


if __name__ == "__main__":
    main()
