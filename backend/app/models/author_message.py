# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthorMessage(Base):
    """A message one signed-in user sent to the author of an ApiDocument or a
    Collection (its created_by_user_id) through the app, see
    app/services/author_contact.py. Exactly one of documentation_id /
    collection_id is set - the same exactly-one-target shape as
    app/models/notification.py's Subscription, enforced the same way by the
    CheckConstraint below.

    Both ends are User rows (never deleted), so the sender's and the author's
    names are read live instead of being copied here. email_sent records
    whether the e-mail copy went out: the message and its in-app Notification
    stand either way. Deleting the target cascades the message away with it,
    as it does for Subscription and Notification."""

    __tablename__ = "author_messages"
    __table_args__ = (
        CheckConstraint(
            "(documentation_id IS NOT NULL AND collection_id IS NULL) "
            "OR (documentation_id IS NULL AND collection_id IS NOT NULL)",
            name="ck_author_messages_exactly_one_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
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
    body: Mapped[str] = mapped_column(Text, nullable=False)
    email_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
