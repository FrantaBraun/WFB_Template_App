# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge forms into wfb-freelancer

Revision ID: b1a9fba1b71f
Revises: 7b08fc8509e3, ee947960f942
Create Date: 2026-10-20 15:13:41.809658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1a9fba1b71f'
down_revision: Union[str, Sequence[str], None] = ('7b08fc8509e3', 'ee947960f942')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
