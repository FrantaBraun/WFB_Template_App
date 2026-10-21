# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge event_booking into thoughtauction

Revision ID: 71b0631d7b8a
Revises: 9a1e8e4bb88e, f537bd78f448
Create Date: 2026-10-21 10:38:19.217237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71b0631d7b8a'
down_revision: Union[str, Sequence[str], None] = ('9a1e8e4bb88e', 'f537bd78f448')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
