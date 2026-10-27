# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""merge tickets into wfb-freelancer

Revision ID: f8880273b0dc
Revises: 3b463d05f2dc, ef498e35f316
Create Date: 2026-10-27 09:31:07.182093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8880273b0dc'
down_revision: Union[str, Sequence[str], None] = ('3b463d05f2dc', 'ef498e35f316')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
