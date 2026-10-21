# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.modules.table_reservations import rules
from app.modules.table_reservations.models import NOTE_MAX

# A person's name as typed: surrounding blanks dropped, and not just blanks.
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

Kind = Literal["table", "whole_venue"]
Status = Literal["confirmed", "cancelled"]

MAX_TABLE_SEATS = 50
MAX_PARTY_SIZE = 200  # the whole pub


# --- Opening hours (public and administrators') -------------------------------------


class WeekdayHours(BaseModel):
    """The regular hours of one weekday (Monday = 0). `opens` / `closes` are None when closed."""

    model_config = ConfigDict(from_attributes=True)

    weekday: int = Field(ge=0, le=6)
    is_closed: bool
    opens: time | None = None
    closes: time | None = None


class HoursUpdate(BaseModel):
    """The whole week at once: every weekday exactly once."""

    model_config = ConfigDict(extra="forbid")

    days: list[WeekdayHours] = Field(min_length=7, max_length=7)


class ExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    is_closed: bool
    opens: time | None
    closes: time | None
    reason: str | None


class ExceptionIn(BaseModel):
    """A one-off change of one date. `reason` is shown to visitors."""

    model_config = ConfigDict(extra="forbid")

    is_closed: bool = True
    opens: time | None = None
    closes: time | None = None
    reason: str | None = Field(default=None, max_length=200)

    @field_validator("reason")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


# --- Public -------------------------------------------------------------------------


class InfoOut(BaseModel):
    """What the reservation form needs to know before the guest picks a day."""

    weekly: list[WeekdayHours]
    exceptions: list[ExceptionOut]
    # The most people one table seats (0 = there is no active table) and the
    # most the whole pub is reserved for.
    max_party_size: int
    max_whole_venue_party: int
    max_days_ahead: int
    lead_minutes: int
    default_duration: int
    duration_options: list[int]
    min_duration: int
    step_minutes: int
    privacy_url: str | None
    # Whether anything can be reserved at all (there is a table and an open day).
    can_reserve: bool


class DayOut(BaseModel):
    day: date
    is_open: bool
    opens: time | None
    closes: time | None
    # Why a day is closed or open at other hours, when an administrator said so.
    reason: str | None
    # Whether a guest may reserve on this day (open, not past, not too far ahead).
    bookable: bool


class DaysOut(BaseModel):
    days: list[DayOut]


class AvailabilityOut(BaseModel):
    """What can be reserved on one day for one party: every start time at which a
    table is free, and when the whole pub can be reserved from."""

    day: date
    is_open: bool
    bookable: bool
    opens: time | None
    closes: time | None
    reason: str | None
    starts: list[time]
    # Why there is no start, when there is none: party_too_large, venue_reserved, no_table.
    table_reason: str | None
    whole_venue_from: time | None
    # Why the whole pub cannot be reserved: venue_reserved, tables_reserved, too_soon.
    whole_venue_reason: str | None


class ReservationCreate(BaseModel):
    """A guest's reservation. For `table`, the end is start + `duration_minutes`
    (default from the configuration) cut at closing time; for `whole_venue` it is
    always closing time. `fax` is the honeypot: invisible in the form, so a human
    leaves it empty and a bot that fills every field does not."""

    model_config = ConfigDict(extra="forbid")

    kind: Kind
    day: date
    start_time: time
    duration_minutes: int | None = Field(default=None, ge=rules.MIN_DURATION, le=rules.MAX_DURATION)
    party_size: int = Field(ge=1, le=MAX_PARTY_SIZE)
    name: PersonName
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=500)
    consent: bool
    language: str | None = Field(default=None, max_length=35)
    fax: str = Field(default="", max_length=200)

    @field_validator("phone", "note")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class ReservationCreated(BaseModel):
    cancel_token: str
    kind: Kind
    day: date
    start_time: time
    end_time: time


class ReservationPublic(BaseModel):
    """A reservation as the guest who made it sees it on the cancellation page.
    No e-mail address, no table and never the pub's message."""

    kind: Kind
    day: date
    start_time: time
    end_time: time
    party_size: int
    name: str
    status: Status
    cancelled_at: datetime | None


# --- Administrators -----------------------------------------------------------------


class ReservationAdmin(BaseModel):
    id: uuid.UUID
    kind: Kind
    table_id: uuid.UUID | None
    table_name: str | None
    day: date
    start_time: time
    end_time: time
    party_size: int
    name: str
    email: str
    phone: str | None
    note: str | None
    language: str
    consent_at: datetime
    created_at: datetime
    status: Status
    cancelled_at: datetime | None
    cancelled_by: str | None
    cancel_note: str | None
    notified: bool | None
    email_error: str | None


class CancelBody(BaseModel):
    """The pub cancels a reservation: `note` is the message that goes to the guest
    in the e-mail (and is kept with the reservation), `notify` whether to send it."""

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=NOTE_MAX)
    notify: bool = True


class CancelOut(BaseModel):
    """`email_sent` is None when no e-mail was asked for; otherwise whether it
    went out (the cancellation stands either way)."""

    reservation: ReservationAdmin
    email_sent: bool | None


class PurgeOut(BaseModel):
    deleted_reservations: int


class TableIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    seats: int = Field(ge=1, le=MAX_TABLE_SEATS)
    position: int = Field(default=0, ge=0, le=10000)
    is_active: bool = True


class TablePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    seats: int | None = Field(default=None, ge=1, le=MAX_TABLE_SEATS)
    position: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    seats: int
    position: int
    is_active: bool
    # Confirmed reservations of this table from today on.
    upcoming_count: int = 0
