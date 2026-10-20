# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge articles into api-hub

Revision ID: 7c702e74a9d5
Revises: 72402af046a3, af103a743023
Create Date: 2026-10-20 12:05:10.406120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c702e74a9d5'
down_revision: Union[str, Sequence[str], None] = ('72402af046a3', 'af103a743023')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
