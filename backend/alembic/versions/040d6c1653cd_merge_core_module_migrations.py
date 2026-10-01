# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge core module migrations

Revision ID: 040d6c1653cd
Revises: 50f53ca87eb4, f9bbb1b552f0
Create Date: 2026-10-01 13:28:21.262318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '040d6c1653cd'
down_revision: Union[str, Sequence[str], None] = ('50f53ca87eb4', 'f9bbb1b552f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
