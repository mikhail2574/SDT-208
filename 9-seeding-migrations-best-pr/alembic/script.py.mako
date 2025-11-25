"""Generic Alembic revision template."""
from alembic import op
import sqlalchemy as sa


revision = ${repr(revision_id)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Apply this migration."""
    pass


def downgrade() -> None:
    """Revert this migration."""
    pass
