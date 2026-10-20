# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge forms into thoughtauction

Revision ID: 9a1e8e4bb88e
Revises: 60cddd6e213c, ee947960f942
Create Date: 2026-10-20 15:08:45.459455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1e8e4bb88e'
down_revision: Union[str, Sequence[str], None] = ('60cddd6e213c', 'ee947960f942')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
