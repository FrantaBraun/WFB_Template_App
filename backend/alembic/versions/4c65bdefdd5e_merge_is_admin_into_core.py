# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge is_admin into core

Revision ID: 4c65bdefdd5e
Revises: 50f53ca87eb4, dab618205f33
Create Date: 2026-10-01 13:45:25.759781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c65bdefdd5e'
down_revision: Union[str, Sequence[str], None] = ('50f53ca87eb4', 'dab618205f33')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
