# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge articles into thoughtauction

Revision ID: 073e8f08475e
Revises: c540bc4742d5, af103a743023
Create Date: 2026-10-20 12:13:42.329930

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '073e8f08475e'
down_revision: Union[str, Sequence[str], None] = ('c540bc4742d5', 'af103a743023')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
