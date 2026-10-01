# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_DELETED = "deleted"


class Event(Base):
    """One event, rendered as its own page (/events/<slug>).

    An event is *visible* (listed, shown in the calendar) when it is
    published and today falls inside its display window - display_from /
    display_to are open-ended when null, so an admin can embargo an event
    before a date or hide it after one. "deleted" is a soft-delete status;
    there is no hard delete. full_text is editor HTML, always stored
    sanitized (app/services/sanitize.py). image_url is the thumbnail shown
    in listings and at the top of the event page.
    """

    # Prefixed like module_notifications, so it can't collide with an
    # application's own table (module models are imported even when the
    # module is disabled).
    __tablename__ = "module_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    short_description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    display_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    display_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
