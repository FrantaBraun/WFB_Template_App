# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge articles into slavickovy-knihohratky

Revision ID: 5795c81eca42
Revises: 64afc6d3aff3, af103a743023
Create Date: 2026-10-20 11:59:32.644730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5795c81eca42'
down_revision: Union[str, Sequence[str], None] = ('64afc6d3aff3', 'af103a743023')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
