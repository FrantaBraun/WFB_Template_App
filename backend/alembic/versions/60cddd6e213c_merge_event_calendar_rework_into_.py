# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge event_calendar rework into thoughtauction

Revision ID: 60cddd6e213c
Revises: 073e8f08475e, 04271da5afb7
Create Date: 2026-10-20 13:13:06.605593

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60cddd6e213c'
down_revision: Union[str, Sequence[str], None] = ('073e8f08475e', '04271da5afb7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
