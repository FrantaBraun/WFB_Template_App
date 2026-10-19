# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge crm into thoughtauction

Revision ID: c540bc4742d5
Revises: 2148e8844cda, f15376a45263
Create Date: 2026-10-19 11:48:49.373202

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c540bc4742d5'
down_revision: Union[str, Sequence[str], None] = ('2148e8844cda', 'f15376a45263')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
