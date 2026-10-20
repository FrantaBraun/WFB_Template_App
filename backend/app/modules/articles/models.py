# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_ARCHIVED = "archived"


class ArticleType(Base):
    """A kind of article ("Report", "Announcement", ...) with the colours its
    articles are drawn in. Four colours, because the app has a light and a
    dark theme: a frame (border) and a tint (background) for each."""

    # Prefixed like module_events / module_notifications, so it can't collide
    # with an application's own table (module models are imported even when
    # the module is disabled).
    __tablename__ = "module_article_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    border_light: Mapped[str] = mapped_column(String(7), nullable=False)
    background_light: Mapped[str] = mapped_column(String(7), nullable=False)
    border_dark: Mapped[str] = mapped_column(String(7), nullable=False)
    background_dark: Mapped[str] = mapped_column(String(7), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Article(Base):
    """One article, rendered as its own page (/articles/<slug>).

    status: "draft" is visible to administrators only, "published" is listed
    while today falls inside the display window (display_from / display_to
    are open-ended when null, so an article can be embargoed before a date or
    hidden after one), "archived" is out of the listings but still found
    through calendars and search (see visibility.py - the one place those
    rules live). content is editor HTML, always stored sanitized
    (app/services/sanitize.py). search_text is derived on every save (title,
    perex and the plain text of content, lowercased and without diacritics)
    and is only ever queried, never shown.
    """

    __tablename__ = "module_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    perex: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_article_types.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT, index=True)
    display_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    display_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    article_type: Mapped[ArticleType | None] = relationship(lazy="selectin")
