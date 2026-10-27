# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge tickets into api-hub

Revision ID: 03ecdf3e2f8a
Revises: 3b463d05f2dc, c51bb98f084f
Create Date: 2026-10-27 09:17:45.540231

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03ecdf3e2f8a'
down_revision: Union[str, Sequence[str], None] = ('3b463d05f2dc', 'c51bb98f084f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
