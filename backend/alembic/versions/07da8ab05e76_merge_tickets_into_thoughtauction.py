# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge tickets into thoughtauction

Revision ID: 07da8ab05e76
Revises: 3b463d05f2dc, bd7b5715b84c
Create Date: 2026-10-27 09:24:28.342235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07da8ab05e76'
down_revision: Union[str, Sequence[str], None] = ('3b463d05f2dc', 'bd7b5715b84c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
