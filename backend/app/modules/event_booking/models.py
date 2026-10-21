# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import secrets
import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

ACCESS_PUBLIC = "public"
ACCESS_AUTHENTICATED = "authenticated"
ACCESS_LINK = "link"
ACCESS_MODES = (ACCESS_PUBLIC, ACCESS_AUTHENTICATED, ACCESS_LINK)

STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"

CHANGE_UPDATED = "updated"
CHANGE_CANCELLED = "cancelled"

NOTE_MAX = 1000


def new_token() -> str:
    """An unguessable token for a link or a cancellation (192 random bits)."""
    return secrets.token_urlsafe(24)


class Registration(Base):
    """The registration for ONE event: who may book, how many per slot, which
    questions they answer. Which slots exist is decided by its blocks (slots.py),
    never stored. `link_token` is generated for every registration, but only
    matters for access "link" (the registration is then offered only to someone
    who has it in the address of the article page). The form of questions is
    created with the registration and removed with it."""

    # Prefixed like the other modules' tables (module models are imported even
    # when the module is disabled).
    __tablename__ = "module_booking_registrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_events.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    access: Mapped[str] = mapped_column(String(20), nullable=False, default=ACCESS_PUBLIC)
    link_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_token)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_forms.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RegistrationBlock(Base):
    """One block of a registration's offer (see slots.Block for what the fields mean)."""

    __tablename__ = "module_booking_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_booking_registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    days_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    dates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    weekdays: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    range_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    range_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    time_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    times: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    slot_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    time_to: Mapped[time | None] = mapped_column(Time, nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Booking(Base):
    """One person's place in one slot. `slot_time` NULL is the whole day. It
    takes up capacity only while `status` is "confirmed". `language` is the
    one the visitor booked in, so every later e-mail about it - including those
    after an administrator changes or cancels it - comes in that language.
    `submission_id` holds the answers (module forms); an administrator's edit of
    the answers stores a new snapshot and replaces it. Personal data: removed
    by retention (service.purge_expired)."""

    __tablename__ = "module_booking_bookings"
    __table_args__ = (Index("ix_module_booking_bookings_slot", "registration_id", "slot_date", "slot_time"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_booking_registrations.id", ondelete="RESTRICT"), nullable=False
    )
    slot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    user_sub: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_form_submissions.id", ondelete="RESTRICT"), nullable=True
    )
    cancel_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=new_token)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_CONFIRMED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BookingChange(Base):
    """What an administrator did to a booking: a change or a cancellation, the
    note meant for the person, which fields changed (`changes`: {field: {from,
    to}}, only those that did), and whether the e-mail about it went out (and if
    not, why). Removed with the booking."""

    __tablename__ = "module_booking_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_booking_bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_sub: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
