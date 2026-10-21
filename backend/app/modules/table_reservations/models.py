# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import secrets
import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

KIND_TABLE = "table"
KIND_WHOLE_VENUE = "whole_venue"
KINDS = (KIND_TABLE, KIND_WHOLE_VENUE)

STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"

CANCELLED_BY_GUEST = "guest"
CANCELLED_BY_ADMIN = "admin"

NOTE_MAX = 1000


def new_token() -> str:
    """An unguessable token for the cancellation link (192 random bits)."""
    return secrets.token_urlsafe(24)


class DiningTable(Base):
    """One table of the pub: how many people it seats and whether it takes
    part in assigning (an inactive one is kept for the history of its
    reservations, but nobody is seated there any more). Guests never choose a
    table - the system assigns the smallest free one that is big enough."""

    __tablename__ = "module_res_tables"
    __table_args__ = (CheckConstraint("seats >= 1", name="ck_module_res_tables_seats"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpeningHours(Base):
    """The regular opening hours of one weekday (Monday = 0). A day with no
    row, or with `is_closed`, is closed. Opening and closing are on the same
    day (closing after midnight is not supported)."""

    __tablename__ = "module_res_opening_hours"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_module_res_hours_weekday"),
        CheckConstraint("is_closed OR (opens IS NOT NULL AND closes IS NOT NULL AND closes > opens)", name="ck_module_res_hours_times"),
    )

    weekday: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opens: Mapped[time | None] = mapped_column(Time, nullable=True)
    closes: Mapped[time | None] = mapped_column(Time, nullable=True)


class OpeningException(Base):
    """A one-off change of ONE date's hours: closed (with a reason shown to
    visitors) or open at other hours. It wins over the weekday's regular hours."""

    __tablename__ = "module_res_opening_exceptions"
    __table_args__ = (
        CheckConstraint("is_closed OR (opens IS NOT NULL AND closes IS NOT NULL AND closes > opens)", name="ck_module_res_exceptions_times"),
    )

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    opens: Mapped[time | None] = mapped_column(Time, nullable=True)
    closes: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reservation(Base):
    """A reservation of one table (`kind` "table": `table_id` set, for
    `party_size` people) or of the whole pub (`kind` "whole_venue": no table,
    from `start_time` to the closing time of the day, which is stored as
    `end_time`). Times are local (Europe/Prague), `end_time` is exclusive.
    Personal data (name, e-mail, phone, note): removed by retention
    (service.purge_expired).

    `cancelled_by` is who ended it; for the pub's own cancellation `cancel_note`
    is the message that went to the guest and `notified` / `email_error` say
    whether that e-mail went out. `language` is the one the guest reserved in,
    so every later e-mail is in it."""

    __tablename__ = "module_res_reservations"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_module_res_reservations_times"),
        CheckConstraint("party_size >= 1", name="ck_module_res_reservations_party"),
        CheckConstraint(
            "(kind = 'table' AND table_id IS NOT NULL) OR (kind = 'whole_venue' AND table_id IS NULL)",
            name="ck_module_res_reservations_kind",
        ),
        Index("ix_module_res_reservations_day_status", "day", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_res_tables.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    cancel_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_token)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_CONFIRMED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cancel_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    email_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by_sub: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
