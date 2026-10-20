# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge forms into slavickovy-knihohratky

Revision ID: d0130d231e3d
Revises: 77fd97a2fb1c, ee947960f942
Create Date: 2026-10-20 14:56:35.630966

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0130d231e3d'
down_revision: Union[str, Sequence[str], None] = ('77fd97a2fb1c', 'ee947960f942')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
