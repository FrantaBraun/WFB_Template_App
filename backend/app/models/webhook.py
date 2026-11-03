# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TeamWebhook(Base):
    """Somewhere a team wants to hear about new versions: a chat channel or
    its own endpoint, called by the server (app/services/webhooks.py) when a
    document the team owns - or a public one an integration of the team uses -
    gets a new version. It is the team's counterpart of the e-mail and bell
    notifications, which go to people.

    kind "slack" is a Slack incoming webhook (its URL is itself the secret that
    lets anyone post to the channel) and gets a chat message; kind "generic"
    gets a JSON body signed with `secret` (HMAC-SHA256, so the receiver knows it
    came from here and was not replayed) - the secret is made here and shown
    once, when the webhook is created. The URL is secret-like in both cases, so
    the API only ever returns it masked.

    last_attempt_at / last_status / last_error / consecutive_failures record how
    the last delivery went, so a channel that has silently stopped working is
    visible. The URL is checked against calling the server's own network when it
    is saved and again on every delivery (app/services/safe_http.py)."""

    __tablename__ = "team_webhooks"
    __table_args__ = (
        CheckConstraint("kind IN ('slack', 'generic')", name="ck_team_webhooks_kind"),
        CheckConstraint("kind = 'slack' OR secret IS NOT NULL", name="ck_team_webhooks_generic_has_secret"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    only_breaking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
