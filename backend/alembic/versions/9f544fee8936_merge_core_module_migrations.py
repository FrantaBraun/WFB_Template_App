# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge core module migrations

Revision ID: 9f544fee8936
Revises: 4c65bdefdd5e, ff4a17c8ec3b
Create Date: 2026-10-01 13:54:26.915958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f544fee8936'
down_revision: Union[str, Sequence[str], None] = ('4c65bdefdd5e', 'ff4a17c8ec3b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
