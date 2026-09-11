# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """Local account linked to a user authenticated via auth.withfbraun.com.

    Identity fields (name, role, ...) are owned by the auth service and read
    fresh from the JWT / GET /api/auth/me, never duplicated here - this model
    otherwise only holds the link (auth_sub) plus data genuinely local to
    this app. `email` is a deliberate, narrow exception to that rule: API Hub
    needs to bulk-email team members/subscribers and the auth service exposes
    no user directory / lookup-by-id for other users, so it's cached here and
    kept fresh from the JWT's email claim on every get_current_user resolve
    (see app/api/deps.py). `nickname` is a deliberately minimal example of
    genuinely local data: a template extending this model adds fields here,
    not identity data.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    auth_sub: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, index=True, nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
