# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Notification(Base):
    """A generic, application-agnostic notification for one recipient.

    message_key/message_params are an opaque i18next key plus interpolation
    params that the caller defines and owns - this module never renders or
    interprets them. That's deliberate: it preserves live, per-viewer UI
    language, since the caller's own t(message_key, message_params) call
    runs at render time in whatever language the *viewer* currently has
    active, not whatever language was active when the notification was
    created. reference_id is a plain opaque UUID with no ForeignKey, since
    this module doesn't know what table a reference might point to - it
    only lets a caller filter/scope notifications (e.g. "all notifications
    about this one thing of mine") without this module needing to
    understand what that thing is.
    """

    # Prefixed so it can't collide with an application's own "notifications"
    # table (api-hub has one) - this module's models are always imported,
    # even where the module is disabled.
    __tablename__ = "module_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    message_key: Mapped[str] = mapped_column(String(255), nullable=False)
    message_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
