# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
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
    """One row per recipient per event, shown under the header bell. kind
    says which event:

    - "new_version" (the default): a version was archived - see
      app/services/notifications.py's notify_new_version. Carries
      documentation_id and version_id.
    - "author_message": another user wrote to the recipient as the author of
      a document or collection - see app/services/author_contact.py. Carries
      only message_id (the AuthorMessage knows its target); documentation_id
      stays NULL, which is also why the per-document banner
      (GET /api/notifications?documentation_id=...) never counts it.

    The CheckConstraint below keeps each kind's columns together. Read/unread
    only, no richer state machine per the locked-in plan. user_id is the
    recipient, not the actor who triggered the event."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'new_version' AND documentation_id IS NOT NULL AND version_id IS NOT NULL "
            "AND message_id IS NULL) "
            "OR (kind = 'author_message' AND message_id IS NOT NULL AND documentation_id IS NULL "
            "AND version_id IS NULL)",
            name="ck_notifications_kind_columns",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new_version", server_default="new_version"
    )
    documentation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_documents.id", ondelete="CASCADE"), nullable=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_document_versions.id", ondelete="CASCADE"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("author_messages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
