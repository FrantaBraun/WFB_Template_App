# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge event_booking into api-hub

Revision ID: c51bb98f084f
Revises: 7d715ab0a491, f537bd78f448
Create Date: 2026-10-21 10:28:30.597989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c51bb98f084f'
down_revision: Union[str, Sequence[str], None] = ('7d715ab0a491', 'f537bd78f448')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
