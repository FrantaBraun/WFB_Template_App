# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge event_calendar rework into slavickovy-knihohratky

Revision ID: 77fd97a2fb1c
Revises: 5795c81eca42, 04271da5afb7
Create Date: 2026-10-20 13:02:47.665060

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77fd97a2fb1c'
down_revision: Union[str, Sequence[str], None] = ('5795c81eca42', '04271da5afb7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
