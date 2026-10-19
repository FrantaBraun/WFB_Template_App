# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

STATUS_LIVE = "live"
STATUS_IN_PREPARATION = "in_preparation"
STATUSES = (STATUS_LIVE, STATUS_IN_PREPARATION)

# Tables are prefixed like module_crm_* / module_events, so they can't
# collide with an application's own tables (module models are imported even
# when the module is disabled).


class PortfolioItem(Base):
    """One project in the portfolio, shown on /portfolio and as its own page
    (/portfolio/<slug>) when `published`. Every text exists in Czech (`*_cs`,
    required) and English (`*_en`, may be empty - the public side then falls
    back to the Czech one, see service.pick). Items are shown by
    (`sort_order`, `id`); `sort_order` is not unique, so two items can tie
    and `id` decides - the move endpoint renumbers when that happens.
    `description_*` is plain text, paragraphs separated by a blank line.
    `tags` is a Postgres array of short labels (technologies)."""

    __tablename__ = "module_portfolio_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title_cs: Mapped[str] = mapped_column(String(120), nullable=False)
    title_en: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    summary_cs: Mapped[str] = mapped_column(String(400), nullable=False)
    summary_en: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    description_cs: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_LIVE)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
