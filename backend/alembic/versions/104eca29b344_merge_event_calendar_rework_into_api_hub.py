# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge event_calendar rework into api-hub

Revision ID: 104eca29b344
Revises: 7c702e74a9d5, 04271da5afb7
Create Date: 2026-10-20 13:09:09.655158

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '104eca29b344'
down_revision: Union[str, Sequence[str], None] = ('7c702e74a9d5', '04271da5afb7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
