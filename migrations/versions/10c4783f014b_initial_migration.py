"""Initial migration

Revision ID: 10c4783f014b
Revises:
Create Date: 2026-08-22 18:58:16.205848

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "10c4783f014b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
