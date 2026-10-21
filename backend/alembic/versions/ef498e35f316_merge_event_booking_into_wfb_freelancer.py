# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge event_booking into wfb-freelancer

Revision ID: ef498e35f316
Revises: b1a9fba1b71f, f537bd78f448
Create Date: 2026-10-21 10:48:01.306908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef498e35f316'
down_revision: Union[str, Sequence[str], None] = ('b1a9fba1b71f', 'f537bd78f448')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
