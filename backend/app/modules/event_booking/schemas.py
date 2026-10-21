# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.modules.event_booking.models import NOTE_MAX
from app.modules.event_booking.slots import MAX_CAPACITY, Block
from app.modules.forms.schemas import QuestionOut

# A person's name as typed: surrounding blanks dropped, and not just blanks.
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

Access = Literal["public", "authenticated", "link"]
DaysMode = Literal["dates", "weekdays", "any_future"]
TimeMode = Literal["all_day", "manual", "generated"]
BookingStatus = Literal["confirmed", "cancelled"]


# --- Blocks -----------------------------------------------------------------------


class BlockIn(BaseModel):
    """One block as the editor sends it (see slots.Block). Whether the set of
    blocks makes sense as a whole is checked by slots.validate_blocks."""

    model_config = ConfigDict(extra="forbid")

    days_mode: DaysMode
    dates: list[date] = Field(default_factory=list)
    weekdays: list[int] = Field(default_factory=list)
    range_from: date | None = None
    range_to: date | None = None
    time_mode: TimeMode
    times: list[time] = Field(default_factory=list)
    slot_minutes: int | None = None
    time_from: time | None = None
    time_to: time | None = None
    capacity: int | None = Field(default=None, ge=1, le=MAX_CAPACITY)

    def to_block(self) -> Block:
        """The same block as the plain object slots.py works on."""
        return Block(
            days_mode=self.days_mode,
            dates=tuple(self.dates),
            weekdays=tuple(self.weekdays),
            range_from=self.range_from,
            range_to=self.range_to,
            time_mode=self.time_mode,
            times=tuple(self.times),
            slot_minutes=self.slot_minutes,
            time_from=self.time_from,
            time_to=self.time_to,
            capacity=self.capacity,
        )


class BlockOut(BlockIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int


# --- Public -----------------------------------------------------------------------


class RegistrationBrief(BaseModel):
    """What the event list needs to offer a registration."""

    event_id: uuid.UUID
    registration_id: uuid.UUID
    name: str
    description: str
    access: Access
    is_open: bool
    requires_login: bool


class RegistrationPublic(BaseModel):
    """The registration a visitor fills in: its definition, the questions, and
    what the form needs to know to render itself."""

    id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    name: str
    description: str
    access: Access
    is_open: bool
    requires_login: bool
    # Every block is an explicit list of days (and there is at least one): the
    # form then offers a plain list of them instead of a calendar.
    finite_days: bool
    # The configured link of the consent text (None = no link) and how far ahead
    # slots are offered (the calendar's last month).
    privacy_url: str | None
    max_days_ahead: int
    questions: list[QuestionOut]


class FreeDay(BaseModel):
    date: date
    free_slots: int


class DaysOut(BaseModel):
    days: list[FreeDay]


class SlotOut(BaseModel):
    time: time | None
    capacity: int
    free: int


class SlotsOut(BaseModel):
    date: date
    slots: list[SlotOut]


class BookingCreate(BaseModel):
    """The visitor's booking. `fax` is the honeypot: invisible in the form, so
    a human leaves it empty and a bot that fills every field does not."""

    model_config = ConfigDict(extra="forbid")

    slot_date: date
    slot_time: time | None = None
    name: PersonName
    email: EmailStr
    consent: bool
    answers: dict[str, Any] = Field(default_factory=dict)
    language: str | None = Field(default=None, max_length=35)
    fax: str = Field(default="", max_length=200)


class BookingCreated(BaseModel):
    cancel_token: str
    slot_date: date
    slot_time: time | None


class BookingPublic(BaseModel):
    """A booking as the person who made it sees it on the cancellation page. No
    e-mail address, and never an administrator's note."""

    event_title: str
    registration_name: str
    slot_date: date
    slot_time: time | None
    name: str
    status: BookingStatus
    cancelled_at: datetime | None


# --- Administrators ---------------------------------------------------------------


class RegistrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    access: Access = "public"
    capacity: int = Field(default=1, ge=1, le=MAX_CAPACITY)
    is_open: bool = True
    blocks: list[BlockIn] = Field(default_factory=list)


class RegistrationUpdate(BaseModel):
    """All optional, applied with exclude_unset. `blocks`, when sent, replaces
    the whole list. The event cannot be changed: a registration belongs to one."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    access: Access | None = None
    capacity: int | None = Field(default=None, ge=1, le=MAX_CAPACITY)
    is_open: bool | None = None
    blocks: list[BlockIn] | None = None


class PreviewIn(BaseModel):
    """Blocks as they stand in the editor, to see what they would offer."""

    model_config = ConfigDict(extra="forbid")

    blocks: list[BlockIn] = Field(default_factory=list)
    capacity: int = Field(default=1, ge=1, le=MAX_CAPACITY)


class PreviewSlot(BaseModel):
    date: date
    time: time | None
    capacity: int


class PreviewOut(BaseModel):
    """`problems` is why the blocks are not acceptable (then there are no slots);
    otherwise the first slots on offer and how many there are in all."""

    problems: list[str]
    slots: list[PreviewSlot]
    total: int


class RegistrationListItem(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    event_start_date: date
    event_end_date: date | None
    name: str
    access: Access
    is_open: bool
    confirmed_count: int
    cancelled_count: int


class RegistrationAdminOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    event_start_date: date
    event_end_date: date | None
    event_start_time: time | None
    event_end_time: time | None
    article_id: uuid.UUID
    article_slug: str
    name: str
    description: str
    access: Access
    link_token: str
    capacity: int
    form_id: uuid.UUID
    is_open: bool
    blocks: list[BlockOut]
    confirmed_count: int
    cancelled_count: int
    created_at: datetime
    updated_at: datetime


class BookingRow(BaseModel):
    id: uuid.UUID
    slot_date: date
    slot_time: time | None
    name: str
    email: str
    status: BookingStatus
    created_at: datetime
    has_history: bool


class BookingRowPage(BaseModel):
    items: list[BookingRow]
    total: int


class ChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["updated", "cancelled"]
    note: str | None
    changes: dict[str, Any]
    notified: bool
    email_error: str | None
    user_sub: uuid.UUID | None
    created_at: datetime


class BookingAdminOut(BaseModel):
    id: uuid.UUID
    registration_id: uuid.UUID
    event_title: str
    registration_name: str
    slot_date: date
    slot_time: time | None
    name: str
    email: str
    user_sub: uuid.UUID | None
    language: str
    status: BookingStatus
    consent_at: datetime
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    # The answers as a snapshot (the shape of the forms module's SubmissionView).
    answers: list[dict[str, Any]]
    history: list[ChangeOut]


class BookingPatch(BaseModel):
    """What an administrator changes. Only what is sent is changed - a slot_time
    of null (sent, not omitted) moves the booking to the whole day. `note` is
    meant for the person and goes into the e-mail; `notify` says whether to
    send it at all (the default, since most changes concern the person)."""

    model_config = ConfigDict(extra="forbid")

    slot_date: date | None = None
    slot_time: time | None = None
    name: PersonName | None = None
    email: EmailStr | None = None
    answers: dict[str, Any] | None = None
    note: str | None = Field(default=None, max_length=NOTE_MAX)
    notify: bool = True


class BookingCancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=NOTE_MAX)
    notify: bool = True


class BookingMutationOut(BaseModel):
    """The booking after an administrator's change or cancellation. `email_sent`
    is None when no e-mail was asked for, True when it went out, False when it
    failed (the change stands; BookingChange.email_error has the reason)."""

    booking: BookingAdminOut
    email_sent: bool | None


class PurgeOut(BaseModel):
    deleted_bookings: int
