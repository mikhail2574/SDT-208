"""Add user_profiles table and users.is_premium column

Revision ID: 0002_user_profile_and_premium
Revises: 0001_initial_schema
Create Date: 2025-11-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_user_profile_and_premium"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    op.add_column(
        "users",
        sa.Column(
            "is_premium",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_premium")
    op.drop_table("user_profiles")
