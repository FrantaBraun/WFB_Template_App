# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge tickets into showing_pub

Revision ID: c9fc735c3ad8
Revises: 3b463d05f2dc, 0dbc5ac9ffb4
Create Date: 2026-10-27 09:35:47.739484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9fc735c3ad8'
down_revision: Union[str, Sequence[str], None] = ('3b463d05f2dc', '0dbc5ac9ffb4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
