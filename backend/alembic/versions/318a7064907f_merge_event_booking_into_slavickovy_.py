# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge event_booking into slavickovy-knihohratky

Revision ID: 318a7064907f
Revises: d0130d231e3d, f537bd78f448
Create Date: 2026-10-21 10:22:35.278567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '318a7064907f'
down_revision: Union[str, Sequence[str], None] = ('d0130d231e3d', 'f537bd78f448')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
