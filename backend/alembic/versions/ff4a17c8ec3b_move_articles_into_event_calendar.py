# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""move articles into event_calendar

Revision ID: ff4a17c8ec3b
Revises: d28ed4d8130a
Create Date: 2026-10-01 13:35:45.261195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ff4a17c8ec3b'
down_revision: Union[str, Sequence[str], None] = 'd28ed4d8130a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Article and Event share every column (Event adds image_url), so the copy
# is 1:1 and keeps ids and timestamps.
_COLUMNS = (
    "id, title, slug, short_description, full_text, event_date, "
    "display_from, display_to, pinned, status, created_at, updated_at"
)
# Path segments the event_calendar module's own routes use
# (app.modules.event_calendar.schemas.RESERVED_SLUGS, frozen here so this
# migration doesn't change meaning if that list ever does).
_RESERVED_SLUGS = ("manage", "uploads", "archive", "month", "dashboard", "search")


def upgrade() -> None:
    """Move every article into the event_calendar module's table, point
    editor-HTML links at the new /events/<slug> pages, then drop articles.

    Fails (and rolls back, articles untouched) rather than guessing when an
    article can't move as-is: a slug the module reserves for its own routes,
    or one an event created since the module was enabled already uses."""
    bind = op.get_bind()
    reserved = bind.execute(
        sa.text("SELECT slug FROM articles WHERE slug = ANY(:reserved)"),
        {"reserved": list(_RESERVED_SLUGS)},
    ).scalars().all()
    if reserved:
        raise RuntimeError(f"Rename these articles before migrating - their slugs are reserved by event_calendar: {reserved}")
    taken = bind.execute(
        sa.text("SELECT a.slug FROM articles a JOIN module_events e ON e.slug = a.slug")
    ).scalars().all()
    if taken:
        raise RuntimeError(f"Rename these articles before migrating - an event already uses their slug: {taken}")

    op.execute(f"INSERT INTO module_events ({_COLUMNS}, image_url) SELECT {_COLUMNS}, NULL FROM articles")
    # /clanek/<slug> also keeps working through a frontend redirect; this
    # just makes stored links point straight at the new pages.
    op.execute("UPDATE module_events SET full_text = replace(full_text, 'href=\"/clanek/', 'href=\"/events/')")
    op.execute("UPDATE pages SET content = replace(content, 'href=\"/clanek/', 'href=\"/events/')")

    op.drop_index(op.f('ix_articles_slug'), table_name='articles')
    op.drop_index(op.f('ix_articles_event_date'), table_name='articles')
    op.drop_table('articles')


def downgrade() -> None:
    """Recreate articles and move every event back (thumbnails are lost -
    articles had no image column)."""
    op.create_table('articles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=200), nullable=False),
    sa.Column('short_description', sa.String(length=500), nullable=False),
    sa.Column('full_text', sa.Text(), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('display_from', sa.Date(), nullable=True),
    sa.Column('display_to', sa.Date(), nullable=True),
    sa.Column('pinned', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_articles_event_date'), 'articles', ['event_date'], unique=False)
    op.create_index(op.f('ix_articles_slug'), 'articles', ['slug'], unique=True)

    op.execute(f"INSERT INTO articles ({_COLUMNS}) SELECT {_COLUMNS} FROM module_events")
    op.execute("DELETE FROM module_events")
    op.execute("UPDATE articles SET full_text = replace(full_text, 'href=\"/events/', 'href=\"/clanek/')")
    op.execute("UPDATE pages SET content = replace(content, 'href=\"/events/', 'href=\"/clanek/')")
