# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge tickets into homerepository

Revision ID: f0b5f0c66a4d
Revises: 3b463d05f2dc, 068c0b207d4c
Create Date: 2026-10-27 09:40:46.629844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0b5f0c66a4d'
down_revision: Union[str, Sequence[str], None] = ('3b463d05f2dc', '068c0b207d4c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
