# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.modules.articles.models import Article

SHORT_DESCRIPTION_MAX = 128


class Event(Base):
    """One date (or run of days) in the calendar, always belonging to one article.

    An event is only a *term*: the text, image, type, status, display window
    and pinned flag all live on its article (the articles module), and
    whether the event is visible follows the article's visibility
    (app.modules.articles.visibility). An article can have any number of
    events - one article, several dates.

    start_date .. end_date (open end = a single day) is the day or run of days;
    start_time / end_time are an optional time of day (end_time only with a
    start_time). title defaults to the article's title in the editor form but
    is the event's own; short_description (at most 128 characters) is what the
    calendar shows when you point at the event. search_text is derived on every
    save (title + short description, lowercased and without diacritics) and only
    ever queried.
    """

    # Prefixed like module_notifications, so it can't collide with an
    # application's own table (module models are imported even when the
    # module is disabled).
    __tablename__ = "module_events"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_module_events_end_date_after_start"),
        CheckConstraint("end_time IS NULL OR start_time IS NOT NULL", name="ck_module_events_end_time_needs_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_articles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    short_description: Mapped[str] = mapped_column(String(SHORT_DESCRIPTION_MAX), nullable=False, default="")
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    article: Mapped[Article] = relationship(lazy="selectin")
