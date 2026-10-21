# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge articles into wfb-freelancer

Revision ID: 3eca78d0d20a
Revises: 7b2b78afd56d, af103a743023
Create Date: 2026-10-20 12:22:43.499439

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3eca78d0d20a'
down_revision: Union[str, Sequence[str], None] = ('7b2b78afd56d', 'af103a743023')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
