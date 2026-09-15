# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeBasePage(Base):
    """One Markdown KB page, owned by exactly one Collection or one
    Integration (app/models/collection.py, app/models/integration.py) - see
    CLAUDE.md's domain model. Same exactly-one-owner shape as
    app/models/notification.py's Subscription, enforced the same way via the
    CheckConstraint below (no partial unique indexes needed here, unlike
    Subscription - position has no uniqueness requirement, duplicates and
    gaps are both fine).

    content is raw Markdown source - this backend never parses or renders it
    as HTML, that happens frontend-side only (marked + DOMPurify), matching
    CLAUDE.md's "freeform text is never rendered as raw HTML" rule. position
    is a plain manual-ordering hint with no reorder endpoint this phase."""

    __tablename__ = "knowledge_base_pages"
    __table_args__ = (
        CheckConstraint(
            "(collection_id IS NOT NULL AND integration_id IS NULL) "
            "OR (collection_id IS NULL AND integration_id IS NOT NULL)",
            name="ck_knowledge_base_pages_exactly_one_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
