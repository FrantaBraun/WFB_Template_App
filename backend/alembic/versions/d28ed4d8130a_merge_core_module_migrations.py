# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge core module migrations

Revision ID: d28ed4d8130a
Revises: 50f53ca87eb4, cde59370f63e
Create Date: 2026-10-01 13:31:36.677572

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd28ed4d8130a'
down_revision: Union[str, Sequence[str], None] = ('50f53ca87eb4', 'cde59370f63e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
