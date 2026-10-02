# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Column sizes are the text limits the API enforces (schemas.py).
CATEGORY_TITLE_MAX = 120
CATEGORY_DESCRIPTION_MAX = 4096
POST_TITLE_MAX = 120
POST_BODY_MAX = 2048
SLUG_MAX = 140


class Category(Base):
    """One publication board: a title (its slug is generated from it) and a
    short description of what belongs there. created_by_id is kept for
    moderation and never leaves the backend - boards show no authors."""

    # Prefixed like module_events / module_notifications, so it can't collide
    # with an application's own table (module models are imported even when
    # the module is disabled).
    __tablename__ = "module_boards_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(CATEGORY_TITLE_MAX), nullable=False)
    slug: Mapped[str] = mapped_column(String(SLUG_MAX), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(CATEGORY_DESCRIPTION_MAX), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    """A post on one board - only a title and a text, no author shown.

    Its *value* is not stored: it is computed from paid_cents,
    resonance_count and the post's age (see service.py), and the listing
    orders by that value. resonance_count is denormalized from the
    Resonance rows (kept in step in the same transaction) so ordering needs
    no per-post count. paid_cents is the running total of what has been paid
    for the post; nothing writes it until payments are built, so it is 0.
    author_id is kept for moderation and never exposed.
    """

    __tablename__ = "module_boards_posts"
    __table_args__ = (
        CheckConstraint("paid_cents >= 0", name="ck_module_boards_posts_paid_cents_nonneg"),
        CheckConstraint("resonance_count >= 0", name="ck_module_boards_posts_resonance_count_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_boards_categories.id"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(POST_TITLE_MAX), nullable=False)
    body: Mapped[str] = mapped_column(String(POST_BODY_MAX), nullable=False)
    paid_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    resonance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Resonance(Base):
    """One user's agreement with one post. The composite primary key is what
    makes a resonance count only once per user and post. Nothing outside the
    backend ever reads user_id back out - who resonated is hidden, even from
    the post's author."""

    __tablename__ = "module_boards_resonances"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_boards_posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
