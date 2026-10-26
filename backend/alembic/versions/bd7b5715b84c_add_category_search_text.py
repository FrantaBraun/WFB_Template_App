# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""add category search text

Revision ID: bd7b5715b84c
Revises: 71b0631d7b8a
Create Date: 2026-10-26 11:02:41.508217

"""
import re
import unicodedata
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd7b5715b84c'
down_revision: Union[str, Sequence[str], None] = '71b0631d7b8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SPACES = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """app.modules.boards.search.normalize_text as it is today. Copied, not
    imported: a migration must keep doing what it did when it was written,
    however that function changes later (a test keeps the two equal for now)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _SPACES.sub(" ", stripped.casefold()).strip()


def upgrade() -> None:
    """Upgrade schema."""
    # The default only lets the column be added to rows that exist; the model
    # fills it in for new ones, so it is dropped again below.
    op.add_column(
        'module_boards_categories',
        sa.Column('search_text', sa.Text(), nullable=False, server_default=''),
    )
    categories = sa.table(
        'module_boards_categories',
        sa.column('id', sa.Uuid()),
        sa.column('title', sa.String()),
        sa.column('description', sa.String()),
        sa.column('search_text', sa.Text()),
    )
    bind = op.get_bind()
    for row in bind.execute(sa.select(categories.c.id, categories.c.title, categories.c.description)).all():
        bind.execute(
            sa.update(categories)
            .where(categories.c.id == row.id)
            .values(search_text=_normalize(f"{row.title} {row.description}"))
        )
    op.alter_column('module_boards_categories', 'search_text', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('module_boards_categories', 'search_text')
