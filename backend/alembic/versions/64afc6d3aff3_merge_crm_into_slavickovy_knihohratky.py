# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge crm into slavickovy_knihohratky

Revision ID: 64afc6d3aff3
Revises: 2148e8844cda, 9f544fee8936
Create Date: 2026-10-19 11:42:35.294157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64afc6d3aff3'
down_revision: Union[str, Sequence[str], None] = ('2148e8844cda', '9f544fee8936')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
