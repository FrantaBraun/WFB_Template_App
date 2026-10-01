# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge core module migrations

Revision ID: 0de1b3f35eac
Revises: 040d6c1653cd, 4c65bdefdd5e
Create Date: 2026-10-01 13:51:21.284745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0de1b3f35eac'
down_revision: Union[str, Sequence[str], None] = ('040d6c1653cd', '4c65bdefdd5e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
