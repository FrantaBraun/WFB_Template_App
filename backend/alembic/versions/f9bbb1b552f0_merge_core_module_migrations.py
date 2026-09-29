# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge core module migrations

Revision ID: f9bbb1b552f0
Revises: 3eb07a820059, 425ac1f23494
Create Date: 2026-09-29 08:17:45.188415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9bbb1b552f0'
down_revision: Union[str, Sequence[str], None] = ('3eb07a820059', '425ac1f23494')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
