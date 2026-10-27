# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge tickets into slavickovy-knihohratky

Revision ID: de5f36a9c2be
Revises: 3b463d05f2dc, 318a7064907f
Create Date: 2026-10-27 09:12:33.898749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de5f36a9c2be'
down_revision: Union[str, Sequence[str], None] = ('3b463d05f2dc', '318a7064907f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
