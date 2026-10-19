# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge crm into api_hub

Revision ID: 72402af046a3
Revises: 2148e8844cda, 0de1b3f35eac
Create Date: 2026-10-19 11:47:09.736056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72402af046a3'
down_revision: Union[str, Sequence[str], None] = ('2148e8844cda', '0de1b3f35eac')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
