# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge core module migrations

Revision ID: cde59370f63e
Revises: 3eb07a820059, d441a1e03154
Create Date: 2026-09-27 20:49:36.978616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cde59370f63e'
down_revision: Union[str, Sequence[str], None] = ('3eb07a820059', 'd441a1e03154')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
