# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# The partner link points at the CRM module's table. Its models are imported
# whether or not the CRM is enabled (see registry.import_all_module_models),
# so the table always exists; importing it here only makes sure the foreign
# key target is in the metadata before this table is created.
from app.modules.crm.models import Partner  # noqa: F401

# "general" is what a ticket is unless said otherwise; "internal" is work
# that has no customer behind it.
TICKET_TYPES = ("general", "issue", "order", "internal")
DEFAULT_TYPE = "general"
TICKET_STATUSES = ("open", "closed")
# Where a ticket came from: typed in by an administrator, read from the
# mailbox, or sent through the contact form.
TICKET_SOURCES = ("manual", "email", "contact_form")
# What an entry of the ticket's thread is: an internal note, something the
# requester sent us (a mail, a contact form message) or a mail we sent them.
ENTRY_KINDS = ("note", "incoming", "outgoing")
# One entry's time is capped at a week of work; anything more is a typo.
MAX_ENTRY_MINUTES = 7 * 24 * 60

# Tables are prefixed like module_events / module_crm_*, so they can't
# collide with an application's own tables.


class Ticket(Base):
    """One request. `number` is what people see and what replies are matched
    by ("[Ticket#100253]" in a subject); it comes from an identity column, so
    it is unique, only ever grows and is never reused. `requester_*` is who
    the mails of this ticket go to; `partner_id` is the CRM partner it is
    linked to (optional, and unset when the CRM is not in use or no partner
    has the requester's address). Deleting a partner unlinks its tickets."""

    __tablename__ = "module_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[int] = mapped_column(Integer, Identity(start=100001), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default=DEFAULT_TYPE)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    requester_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requester_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_crm_partners.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # When something last happened in the thread; what the list is sorted by.
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class TicketEntry(Base):
    """One item of a ticket's thread. `content_html` is always sanitized
    (app.services.sanitize). `minutes` is the time spent, summed in the
    ticket's header. `seq` orders entries made in the same instant (a
    transaction's now() is one value), `created_at` is when it happened - for
    a received mail, when it was written. `message_id` is the RFC Message-ID
    of a received mail (unique, so reading the same mail twice never adds it
    twice); `author_*` is the administrator who wrote an entry, as a label
    taken from their token (the identity itself lives in the auth service)."""

    __tablename__ = "module_ticket_entries"
    __table_args__ = (CheckConstraint("minutes >= 0", name="ck_module_ticket_entries_minutes"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_label: Mapped[str | None] = mapped_column(String(254), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(254), nullable=True)
    to_address: Mapped[str | None] = mapped_column(String(254), nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketAttachment(Base):
    """A file of a ticket. `stored_name` is generated by the server (never the
    client's name) under Settings.uploads_dir/tickets/; `original_filename` is
    only what the file is called when downloaded or mailed. `entry_id` is empty
    while an uploaded file waits for the entry it is attached to, and for
    inline images (pictures in the text of an entry, whether pasted in the
    editor or sent inline in a received mail), which belong to the ticket and
    are shown through their own address (see the router's /files route).
    Everything else is private: it is only readable through the
    administrators' download route."""

    __tablename__ = "module_ticket_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_ticket_entries.id", ondelete="CASCADE"), index=True, nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_inline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
