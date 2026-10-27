# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.tickets.models import MAX_ENTRY_MINUTES
from app.modules.tickets.storage import MAX_ATTACHMENTS_PER_ENTRY

TicketType = Literal["general", "issue", "order", "internal"]
TicketStatus = Literal["open", "closed"]
TicketSource = Literal["manual", "email", "contact_form"]
EntryKind = Literal["note", "incoming", "outgoing"]

# The editor's HTML of one entry (before it is sanitized).
MAX_CONTENT_CHARS = 200_000


class TicketCreate(BaseModel):
    """`description_html` becomes the first entry of the thread (an internal
    note). With no requester e-mail but a partner, the partner's address and
    name are used."""

    subject: str = Field(min_length=1, max_length=200)
    type: TicketType = "general"
    requester_name: str | None = Field(default=None, max_length=200)
    requester_email: EmailStr | None = None
    partner_id: uuid.UUID | None = None
    description_html: str = Field(default="", max_length=MAX_CONTENT_CHARS)


class TicketUpdate(BaseModel):
    """Every field optional; only the ones sent change. `partner_id: null`
    unlinks the partner, `requester_email: null` removes the address."""

    subject: str | None = Field(default=None, min_length=1, max_length=200)
    type: TicketType | None = None
    status: TicketStatus | None = None
    requester_name: str | None = Field(default=None, max_length=200)
    requester_email: EmailStr | None = None
    partner_id: uuid.UUID | None = None


class PartnerRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    company: str | None = None
    archived: bool = False


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: int
    subject: str
    type: TicketType
    status: TicketStatus
    source: TicketSource
    requester_name: str | None
    requester_email: str | None
    partner_id: uuid.UUID | None
    # None when no partner is linked.
    partner: PartnerRef | None = None
    total_minutes: int = 0
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class TicketListItem(TicketOut):
    entry_count: int = 0


class TicketPage(BaseModel):
    items: list[TicketListItem]
    total: int
    page: int
    page_size: int


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    is_inline: bool
    created_at: datetime


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EntryKind
    content_html: str
    minutes: int
    author_label: str | None
    from_name: str | None
    from_address: str | None
    to_address: str | None
    email_subject: str | None
    created_at: datetime
    attachments: list[AttachmentOut] = []


class TicketDetail(TicketOut):
    entries: list[EntryOut]


class EntryCreate(BaseModel):
    """`kind` is "note" (internal, nobody outside sees it) or "outgoing" (mailed
    to the requester). `attachment_ids` are files uploaded earlier through
    /{number}/attachments that have not been used yet."""

    kind: Literal["note", "outgoing"]
    content_html: str = Field(default="", max_length=MAX_CONTENT_CHARS)
    minutes: int = Field(default=0, ge=0, le=MAX_ENTRY_MINUTES)
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_ATTACHMENTS_PER_ENTRY)


class EntryUpdate(BaseModel):
    """The time of any entry, and the text of a note, can be corrected."""

    content_html: str | None = Field(default=None, max_length=MAX_CONTENT_CHARS)
    minutes: int | None = Field(default=None, ge=0, le=MAX_ENTRY_MINUTES)


class ImageUploadOut(BaseModel):
    url: str


class MailboxPollResult(BaseModel):
    fetched: int = 0
    created: int = 0
    attached: int = 0
    skipped: int = 0
    failed: int = 0


class MailboxStatusOut(BaseModel):
    """`configured` is whether TICKETS_IMAP_HOST is set. Nothing else of the
    connection is ever reported - never the password, user name or host."""

    configured: bool
    address: str | None
    poll_seconds: int
    last_checked_at: datetime | None
    last_error: str | None
    last_result: MailboxPollResult | None
