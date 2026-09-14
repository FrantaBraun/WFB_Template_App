# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Subscription(Base):
    """A user's subscription to new-version notifications for either one
    ApiDocument or one Collection (app/models/collection.py) - exactly one
    of documentation_id/collection_id is set, never both or neither (see the
    CheckConstraint below), per CLAUDE.md's domain model. Open to any
    logged-in user, not gated by TeamMembership on the target's owning team.

    A plain UniqueConstraint can't express "unique only when the column is
    non-null", so the (user_id, documentation_id) and (user_id,
    collection_id) pairs are each enforced by their own partial unique index
    below instead - each only applies to rows where its own target column is
    non-null, so the two kinds of subscription row never collide with each
    other regardless of which target column they leave NULL."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index(
            "uq_subscriptions_user_id_documentation_id",
            "user_id",
            "documentation_id",
            unique=True,
            postgresql_where=text("documentation_id IS NOT NULL"),
        ),
        Index(
            "uq_subscriptions_user_id_collection_id",
            "user_id",
            "collection_id",
            unique=True,
            postgresql_where=text("collection_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(documentation_id IS NOT NULL AND collection_id IS NULL) "
            "OR (documentation_id IS NULL AND collection_id IS NOT NULL)",
            name="ck_subscriptions_exactly_one_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    documentation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Notification(Base):
    """One row per recipient per version-archive event (see
    app/services/notifications.py's notify_new_version) - read/unread only,
    no richer state machine per the locked-in plan. user_id is the
    recipient, not the actor who triggered the check."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    documentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_document_versions.id", ondelete="CASCADE"), nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
