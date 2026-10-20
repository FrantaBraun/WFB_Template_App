# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""events belong to articles

An event used to be a whole article (slug, text, image, status, display
window, pinned flag, one date). Now the text lives on the article (the
articles module) and an event is a date - or a run of days, with optional
times - belonging to exactly one article. The two shapes share almost no
columns and an event now needs an article that old rows don't have, so this
drops the table and creates it anew: the old rows are deliberately NOT
carried over (there was no production data; development data is discarded).
Run it only where that is acceptable.

Revision ID: 04271da5afb7
Revises: af103a743023
Create Date: 2026-10-20 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04271da5afb7'
down_revision: Union[str, Sequence[str], None] = 'af103a743023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_module_events_slug'), table_name='module_events')
    op.drop_index(op.f('ix_module_events_event_date'), table_name='module_events')
    op.drop_table('module_events')

    op.create_table('module_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('article_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('short_description', sa.String(length=128), nullable=False),
    sa.Column('search_text', sa.Text(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('start_time', sa.Time(), nullable=True),
    sa.Column('end_time', sa.Time(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_module_events_end_date_after_start'),
    sa.CheckConstraint('end_time IS NULL OR start_time IS NOT NULL', name='ck_module_events_end_time_needs_start'),
    sa.ForeignKeyConstraint(['article_id'], ['module_articles.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_module_events_article_id'), 'module_events', ['article_id'], unique=False)
    op.create_index(op.f('ix_module_events_start_date'), 'module_events', ['start_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema (to the empty table of the old shape - the events are not restored)."""
    op.drop_index(op.f('ix_module_events_start_date'), table_name='module_events')
    op.drop_index(op.f('ix_module_events_article_id'), table_name='module_events')
    op.drop_table('module_events')

    op.create_table('module_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=200), nullable=False),
    sa.Column('short_description', sa.String(length=500), nullable=False),
    sa.Column('full_text', sa.Text(), nullable=False),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('display_from', sa.Date(), nullable=True),
    sa.Column('display_to', sa.Date(), nullable=True),
    sa.Column('pinned', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_module_events_event_date'), 'module_events', ['event_date'], unique=False)
    op.create_index(op.f('ix_module_events_slug'), 'module_events', ['slug'], unique=True)
