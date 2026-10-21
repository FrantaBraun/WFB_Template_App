# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules of the booking module, between the router and the database.

Nothing here commits: the router does, so a booking, its answers and the
history entry of an administrator's change are one transaction. Every check
that can refuse something is done BEFORE the first write, so a refusal leaves
nothing behind (the request's session rolls back when it closes).

Capacity (the whole point of the lock): a slot may hold more than one person,
so a unique constraint cannot guard it. Everything that adds a confirmed
booking to a slot - a visitor booking, an administrator moving a booking -
first takes `SELECT ... FOR UPDATE` on the REGISTRATION row, counts the slot's
confirmed bookings and only then writes, so two requests for the last place
are serialised and the second sees the first. The registration is always
locked before a booking is (and a booking never before its registration), so
two requests cannot deadlock.

Errors are BookingError(status, detail) (an HTTPException); the 422 / 409
details have the shape {"errors": {field_or_question_id: code}} - the same one
the forms module uses for answers - so a client has one way to put a message
at a field.
"""

import calendar
import csv
import io
import logging
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.user import User
from app.modules.articles import visibility
from app.modules.articles.models import Article
from app.modules.event_booking import mail, slots
from app.modules.event_booking.config import EventBookingConfig, for_language, get_config
from app.modules.event_booking.models import (
    ACCESS_AUTHENTICATED,
    ACCESS_LINK,
    CHANGE_CANCELLED,
    CHANGE_UPDATED,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    Booking,
    BookingChange,
    Registration,
    RegistrationBlock,
    new_token,
)
from app.modules.event_booking.schemas import (
    BlockIn,
    BookingAdminOut,
    BookingCancelBody,
    BookingCreate,
    BookingPatch,
    BookingPublic,
    BookingRow,
    BookingRowPage,
    ChangeOut,
    DaysOut,
    FreeDay,
    PreviewOut,
    PreviewSlot,
    RegistrationAdminOut,
    RegistrationBrief,
    RegistrationCreate,
    RegistrationListItem,
    RegistrationPublic,
    RegistrationUpdate,
    SlotOut,
    SlotsOut,
)
from app.modules.event_booking.slots import Block, Slot
from app.modules.event_calendar.models import Event
from app.modules.forms import service as forms_service
from app.modules.forms.logic import FormValidationError
from app.modules.forms.schemas import QuestionOut
from app.modules.forms.service import FormInUseError, to_logic_questions

logger = logging.getLogger(__name__)

# The first characters that make a spreadsheet read a cell as a formula.
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

CSV_HEADERS = {
    "cs": ["Datum", "Čas", "Jméno", "E-mail", "Stav", "Vytvořeno", "Souhlas udělen"],
    "en": ["Date", "Time", "Name", "Email", "Status", "Created", "Consent given"],
}
CSV_STATUSES = {
    "cs": {STATUS_CONFIRMED: "potvrzená", STATUS_CANCELLED: "zrušená"},
    "en": {STATUS_CONFIRMED: "confirmed", STATUS_CANCELLED: "cancelled"},
}


class BookingError(HTTPException):
    """A refusal. It is the HTTP answer itself (FastAPI turns it into the
    response), so the router needs no translation of its own."""

    def __init__(self, status_code: int, detail: Any, *, headers: dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


def field_error(status_code: int, field: str, code: str) -> BookingError:
    return BookingError(status_code, {"errors": {field: code}})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clean_note(note: str | None) -> str | None:
    return (note or "").strip() or None


# --- Blocks <-> rows ---------------------------------------------------------------


def block_row(registration_id: uuid.UUID, position: int, block: BlockIn) -> RegistrationBlock:
    """A block as a row. JSONB holds plain JSON, so days and times are stored as text."""
    return RegistrationBlock(
        registration_id=registration_id,
        position=position,
        days_mode=block.days_mode,
        dates=[day.isoformat() for day in sorted(block.dates)],
        weekdays=sorted(block.weekdays),
        range_from=block.range_from,
        range_to=block.range_to,
        time_mode=block.time_mode,
        times=[value.strftime("%H:%M") for value in sorted(block.times)],
        slot_minutes=block.slot_minutes,
        time_from=block.time_from,
        time_to=block.time_to,
        capacity=block.capacity,
    )


def row_block(row: RegistrationBlock) -> Block:
    return Block(
        days_mode=row.days_mode,
        dates=tuple(date.fromisoformat(value) for value in row.dates),
        weekdays=tuple(row.weekdays),
        range_from=row.range_from,
        range_to=row.range_to,
        time_mode=row.time_mode,
        times=tuple(time.fromisoformat(value) for value in row.times),
        slot_minutes=row.slot_minutes,
        time_from=row.time_from,
        time_to=row.time_to,
        capacity=row.capacity,
    )


def check_blocks(blocks: Sequence[BlockIn]) -> None:
    problems = slots.validate_blocks([block.to_block() for block in blocks])
    if problems:
        raise BookingError(422, {"errors": {"blocks": problems}})


PREVIEW_LIMIT = 300


def preview_slots(blocks: Sequence[BlockIn], capacity: int, config: EventBookingConfig, now: datetime) -> PreviewOut:
    """What these blocks would offer from now on, for the editor's live preview:
    the problems when they are not acceptable, else the first PREVIEW_LIMIT slots."""
    problems = slots.validate_blocks([block.to_block() for block in blocks])
    if problems:
        return PreviewOut(problems=problems, slots=[], total=0)
    listing = slots.expand_slots([block.to_block() for block in blocks], capacity, now=now, horizon_days=config.max_days_ahead)
    return PreviewOut(
        problems=[],
        slots=[PreviewSlot(date=slot.day, time=slot.time, capacity=slot.capacity) for slot in listing[:PREVIEW_LIMIT]],
        total=len(listing),
    )


async def blocks_of(db: AsyncSession, registration_id: uuid.UUID) -> list[RegistrationBlock]:
    return list(
        (
            await db.scalars(
                select(RegistrationBlock).where(RegistrationBlock.registration_id == registration_id).order_by(RegistrationBlock.position)
            )
        ).all()
    )


def finite_days(blocks: Sequence[Block]) -> bool:
    """Every block is an explicit list of days (and there is at least one)."""
    return bool(blocks) and all(block.days_mode == "dates" for block in blocks)


# --- Registration and what it is allowed to do now -----------------------------------


def token_matches(registration: Registration, token: str | None) -> bool:
    """Whether `token` (the ?r= of the article page) lets a visitor know of the
    registration: always for public and authenticated ones, only the right
    token for a "link" one."""
    if registration.access != ACCESS_LINK:
        return True
    return token is not None and secrets.compare_digest(token.encode(), registration.link_token.encode())


def open_now(registration: Registration, event: Event, listed: bool, today: date) -> bool:
    """Whether people may register today: the registration is open, the event's
    article is listed (published, inside its display window - not archived) and
    the event is not over (its last day, else its only day, is today or later)."""
    return registration.is_open and listed and (event.end_date or event.start_date) >= today


@dataclass
class Context:
    """A registration with its event and what is true of it today."""

    registration: Registration
    event: Event
    blocks: list[Block]
    today: date
    listed: bool  # the event's article is published and inside its display window
    findable: bool  # ... or archived (still reachable, but nothing new may be booked)

    @property
    def can_register(self) -> bool:
        return open_now(self.registration, self.event, self.listed, self.today)

    def visible_to(self, token: str | None) -> bool:
        return self.findable and token_matches(self.registration, token)


async def get_registration(db: AsyncSession, registration_id: uuid.UUID, *, lock: bool = False) -> Registration | None:
    query = select(Registration).where(Registration.id == registration_id)
    if lock:
        # populate_existing: what was loaded earlier in the session may be stale by now.
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await db.scalars(query)).first()


async def load_context(db: AsyncSession, registration_id: uuid.UUID, *, now: datetime, lock: bool = False) -> Context | None:
    registration = await get_registration(db, registration_id, lock=lock)
    if registration is None:
        return None
    event = await db.get(Event, registration.event_id)
    today = now.date()
    flags = (
        await db.execute(select(visibility.listed(today), visibility.findable(today)).where(Article.id == event.article_id))
    ).one()
    return Context(
        registration=registration,
        event=event,
        blocks=[row_block(row) for row in await blocks_of(db, registration_id)],
        today=today,
        listed=bool(flags[0]),
        findable=bool(flags[1]),
    )


async def public_context(db: AsyncSession, registration_id: uuid.UUID, token: str | None, *, now: datetime, lock: bool = False) -> Context:
    """The context a visitor may see, else 404 - the same 404 for a registration
    that does not exist and one that is not theirs to know about."""
    ctx = await load_context(db, registration_id, now=now, lock=lock)
    if ctx is None or not ctx.visible_to(token):
        raise BookingError(404, "Registration not found")
    return ctx


async def briefs_for_events(
    db: AsyncSession, event_ids: Sequence[uuid.UUID], token: str | None, *, now: datetime
) -> list[RegistrationBrief]:
    """The registration of each of these events that this caller may know of:
    the event's article must be reachable (listed or archived) and a "link"
    registration is left out without its token, as if it did not exist."""
    if not event_ids:
        return []
    today = now.date()
    rows = (
        await db.execute(
            select(Registration, Event, visibility.listed(today))
            .join(Event, Event.id == Registration.event_id)
            .join(Article, Article.id == Event.article_id)
            .where(Registration.event_id.in_(list(event_ids)), visibility.findable(today))
            .order_by(Event.start_date, Registration.id)
        )
    ).all()
    return [
        RegistrationBrief(
            event_id=event.id,
            registration_id=registration.id,
            name=registration.name,
            description=registration.description,
            access=registration.access,
            is_open=open_now(registration, event, bool(listed), today),
            requires_login=registration.access == ACCESS_AUTHENTICATED,
        )
        for registration, event, listed in rows
        if token_matches(registration, token)
    ]


async def public_registration(db: AsyncSession, ctx: Context, config: EventBookingConfig) -> RegistrationPublic:
    """The definition a visitor fills in: what is offered and the questions."""
    registration = ctx.registration
    return RegistrationPublic(
        id=registration.id,
        event_id=ctx.event.id,
        event_title=ctx.event.title,
        name=registration.name,
        description=registration.description,
        access=registration.access,
        is_open=ctx.can_register,
        requires_login=registration.access == ACCESS_AUTHENTICATED,
        finite_days=finite_days(ctx.blocks),
        privacy_url=config.privacy_url,
        max_days_ahead=config.max_days_ahead,
        questions=[QuestionOut.model_validate(question) for question in await forms_service.get_questions(db, registration.form_id)],
    )


async def labels_of(db: AsyncSession, registration_id: uuid.UUID) -> tuple[str, str]:
    """(event title, registration name) - what the e-mails and pages call it."""
    row = (
        await db.execute(
            select(Event.title, Registration.name).join(Event, Event.id == Registration.event_id).where(Registration.id == registration_id)
        )
    ).one()
    return row[0], row[1]


# --- Slots and capacity --------------------------------------------------------------


def slot_clause(slot_date: date, slot_time: time | None):
    return and_(Booking.slot_date == slot_date, Booking.slot_time.is_(None) if slot_time is None else Booking.slot_time == slot_time)


async def taken_counts(db: AsyncSession, registration_id: uuid.UUID, date_from: date, date_to: date) -> dict[tuple[date, time | None], int]:
    """Confirmed bookings per slot (day, time or None for the whole day) in date_from..date_to."""
    rows = await db.execute(
        select(Booking.slot_date, Booking.slot_time, func.count())
        .where(
            Booking.registration_id == registration_id,
            Booking.status == STATUS_CONFIRMED,
            Booking.slot_date >= date_from,
            Booking.slot_date <= date_to,
        )
        .group_by(Booking.slot_date, Booking.slot_time)
    )
    return {(day, slot_time): count for day, slot_time, count in rows}


async def offers(
    db: AsyncSession,
    ctx: Context,
    config: EventBookingConfig,
    *,
    now: datetime,
    date_from: date | None = None,
    date_to: date | None = None,
    include: Booking | None = None,
) -> list[tuple[Slot, int]]:
    """Every slot on offer in date_from..date_to with its free places (full
    slots included, with 0).

    `include` is a booking being moved by an administrator: its own slot is
    listed even if it is no longer on offer (past, or dropped from the blocks)
    and does not count itself as taking a place there."""
    listing = slots.expand_slots(
        ctx.blocks,
        ctx.registration.capacity,
        now=now,
        horizon_days=config.max_days_ahead,
        date_from=date_from,
        date_to=date_to,
    )
    own_key = None
    if include is not None and include.status == STATUS_CONFIRMED:
        own_key = (include.slot_date, include.slot_time)
        in_range = (date_from is None or include.slot_date >= date_from) and (date_to is None or include.slot_date <= date_to)
        if in_range and own_key not in {slot.key for slot in listing}:
            listing = sorted(
                [*listing, Slot(include.slot_date, include.slot_time, ctx.registration.capacity)],
                key=lambda slot: (slot.day, slot.time or time.min),
            )
    if not listing:
        return []
    taken = await taken_counts(db, ctx.registration.id, listing[0].day, listing[-1].day)
    if own_key is not None and taken.get(own_key):
        taken[own_key] -= 1
    return [(slot, slots.free_places(slot, taken)) for slot in listing]


def month_range(month: str | None) -> tuple[date | None, date | None]:
    """The first and last day of "YYYY-MM" (the router has checked its shape); (None, None) without one."""
    if not month:
        return None, None
    year, number = int(month[:4]), int(month[5:7])
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


async def free_days_out(
    db: AsyncSession, ctx: Context, config: EventBookingConfig, *, now: datetime, month: str | None = None, include: Booking | None = None
) -> DaysOut:
    """The days that still have a free slot (all of them, or those of one month)."""
    date_from, date_to = month_range(month)
    listing = await offers(db, ctx, config, now=now, date_from=date_from, date_to=date_to, include=include)
    return DaysOut(days=[FreeDay(date=day, free_slots=count) for day, count in sorted(slots.free_days(listing).items())])


async def free_slots_out(
    db: AsyncSession, ctx: Context, config: EventBookingConfig, *, now: datetime, day: date, include: Booking | None = None
) -> SlotsOut:
    """The slots of one day that still have room; a whole-day slot is one with time None."""
    listing = await offers(db, ctx, config, now=now, date_from=day, date_to=day, include=include)
    return SlotsOut(
        date=day,
        slots=[SlotOut(time=slot.time, capacity=slot.capacity, free=places) for slot, places in listing if places > 0],
    )


def find_slot(ctx: Context, config: EventBookingConfig, now: datetime, slot_date: date, slot_time: time | None) -> Slot:
    """The slot on offer at that day and time, else 422 "not_offered"."""
    for slot in slots.expand_slots(
        ctx.blocks, ctx.registration.capacity, now=now, horizon_days=config.max_days_ahead, date_from=slot_date, date_to=slot_date
    ):
        if slot.key == (slot_date, slot_time):
            return slot
    raise field_error(422, "slot", "not_offered")


async def ensure_room(db: AsyncSession, registration_id: uuid.UUID, slot: Slot) -> None:
    """409 "full" unless the slot has a place left. Only meaningful under the registration's lock."""
    used = await db.scalar(
        select(func.count()).where(Booking.registration_id == registration_id, Booking.status == STATUS_CONFIRMED, slot_clause(slot.day, slot.time))
    )
    if (used or 0) >= slot.capacity:
        raise field_error(409, "slot", "full")


# --- A visitor's booking -------------------------------------------------------------


async def create_booking(
    db: AsyncSession,
    registration_id: uuid.UUID,
    body: BookingCreate,
    *,
    user: User | None,
    token: str | None,
    config: EventBookingConfig,
    now: datetime,
) -> Booking:
    """Books the slot, or raises. Holds the registration's lock from the first
    check to the caller's commit."""
    ctx = await public_context(db, registration_id, token, now=now, lock=True)
    registration = ctx.registration
    if registration.access == ACCESS_AUTHENTICATED and user is None:
        raise BookingError(401, "Login required", headers={"WWW-Authenticate": "Bearer"})
    if not ctx.can_register:
        raise field_error(409, "_form", "closed")

    errors: dict[str, str] = {}
    if not body.consent:
        errors["consent"] = "required"
    questions = to_logic_questions(await forms_service.get_questions(db, registration.form_id))
    entries: list[dict] = []
    try:
        entries = forms_service.validate_answers(questions, body.answers)
    except FormValidationError as exc:
        errors.update(exc.errors)
    if errors:
        raise BookingError(422, {"errors": errors})

    slot = find_slot(ctx, config, now, body.slot_date, body.slot_time)
    await ensure_room(db, registration.id, slot)

    email = str(body.email)
    active = await db.scalar(
        select(func.count()).where(
            Booking.registration_id == registration.id,
            Booking.status == STATUS_CONFIRMED,
            func.lower(Booking.email) == email.lower(),
            Booking.slot_date >= ctx.today,
        )
    )
    if (active or 0) >= config.max_active_per_email:
        raise field_error(422, "email", "too_many")

    submission = await forms_service.store_submission(db, registration.form_id, entries)
    booking = Booking(
        registration_id=registration.id,
        slot_date=slot.day,
        slot_time=slot.time,
        name=body.name,
        email=email,
        user_sub=user.auth_sub if user else None,
        consent_at=utcnow(),
        submission_id=submission.id,
        language=config.resolve_language(body.language),
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


async def send_new_booking_mails(
    db: AsyncSession, booking: Booking, config: EventBookingConfig, settings: Settings
) -> None:
    """The confirmation to the person and the notice to the administrator,
    each when switched on. A failure is logged and goes no further."""
    event_title, registration_name = await labels_of(db, booking.registration_id)
    values = mail.template_values(
        config,
        settings,
        booking.language,
        name=booking.name,
        email=booking.email,
        event_title=event_title,
        registration_name=registration_name,
        slot_date=booking.slot_date,
        slot_time=booking.slot_time,
        cancel_token=booking.cancel_token,
    )
    if config.send_confirmation:
        await mail.deliver(config, settings, "confirmation", booking.language, booking.email, values)
    if config.notify_admin:
        address = mail.notify_address(settings)
        if not address:
            logger.warning("A booking was made but neither BOOKING_NOTIFY_MAIL nor CONTACT_MAIL is set - nobody is notified")
        else:
            admin_values = mail.template_values(
                config,
                settings,
                config.default_language,
                name=booking.name,
                email=booking.email,
                event_title=event_title,
                registration_name=registration_name,
                slot_date=booking.slot_date,
                slot_time=booking.slot_time,
                cancel_token=booking.cancel_token,
            )
            await mail.deliver(config, settings, "admin_notification", config.default_language, address, admin_values)


async def get_booking_by_token(db: AsyncSession, cancel_token: str) -> Booking | None:
    return (await db.scalars(select(Booking).where(Booking.cancel_token == cancel_token))).first()


async def public_booking(db: AsyncSession, booking: Booking) -> BookingPublic:
    """A booking as its owner sees it: no e-mail address and nothing an administrator wrote."""
    event_title, registration_name = await labels_of(db, booking.registration_id)
    return BookingPublic(
        event_title=event_title,
        registration_name=registration_name,
        slot_date=booking.slot_date,
        slot_time=booking.slot_time,
        name=booking.name,
        status=booking.status,
        cancelled_at=booking.cancelled_at,
    )


async def _lock_registration_of(db: AsyncSession, booking: Booking) -> Registration:
    """Takes the registration's lock (before touching the booking) and re-reads the booking."""
    registration = await get_registration(db, booking.registration_id, lock=True)
    await db.refresh(booking)
    return registration


async def cancel_by_visitor(db: AsyncSession, cancel_token: str) -> tuple[Booking, bool]:
    """Cancels the booking its token belongs to; (booking, True) if it was
    cancelled now, (booking, False) if it already was - so the same link is
    safe to press twice. 404 for an unknown token."""
    booking = await get_booking_by_token(db, cancel_token)
    if booking is None:
        raise BookingError(404, "Booking not found")
    await _lock_registration_of(db, booking)
    if booking.status == STATUS_CANCELLED:
        return booking, False
    booking.status = STATUS_CANCELLED
    booking.cancelled_at = utcnow()
    await db.flush()
    return booking, True


async def send_cancellation_mail(db: AsyncSession, booking: Booking, config: EventBookingConfig, settings: Settings) -> None:
    if not config.send_confirmation:
        return
    event_title, registration_name = await labels_of(db, booking.registration_id)
    values = mail.template_values(
        config,
        settings,
        booking.language,
        name=booking.name,
        email=booking.email,
        event_title=event_title,
        registration_name=registration_name,
        slot_date=booking.slot_date,
        slot_time=booking.slot_time,
        cancel_token=booking.cancel_token,
    )
    await mail.deliver(config, settings, "cancellation", booking.language, booking.email, values)


# --- An administrator's changes to a booking ---------------------------------------------


def _slot_text(day: date, slot_time: time | None) -> tuple[str, str | None]:
    return day.isoformat(), slot_time.strftime("%H:%M") if slot_time else None


def changed_questions(old: Sequence[dict], new: Sequence[dict]) -> list[dict[str, str]]:
    """The questions whose answer differs between two snapshots (shown or not,
    and the value), as {id, label} - by the newer wording, the older for a
    question that is gone from the form."""
    old_by_id = {entry["question_id"]: entry for entry in old}
    new_by_id = {entry["question_id"]: entry for entry in new}

    def state(entry: dict | None):
        if entry is None or not entry.get("shown"):
            return None
        return entry.get("value")

    result = []
    for question_id in [*new_by_id, *(key for key in old_by_id if key not in new_by_id)]:
        before, after = old_by_id.get(question_id), new_by_id.get(question_id)
        if state(before) != state(after):
            result.append({"id": question_id, "label": (after or before)["label"]})
    return result


async def update_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    body: BookingPatch,
    *,
    admin: User,
    config: EventBookingConfig,
    now: datetime,
) -> tuple[Booking, BookingChange, tuple[date, time | None]]:
    """Applies an administrator's changes; returns the booking, its history
    entry and the slot it had before. A new slot goes through the same checks
    and the same lock as a visitor's booking and the capacity is NOT overridden;
    answers are validated against the form and stored as a new snapshot."""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise BookingError(404, "Booking not found")
    ctx = await load_context(db, booking.registration_id, now=now, lock=True)
    await db.refresh(booking)
    if booking.status == STATUS_CANCELLED:
        raise field_error(409, "_form", "cancelled")

    fields = body.model_fields_set
    old_slot = (booking.slot_date, booking.slot_time)
    changes: dict[str, Any] = {}

    new_name = body.name if "name" in fields and body.name is not None else booking.name
    if new_name != booking.name:
        changes["name"] = {"from": booking.name, "to": new_name}
    new_email = str(body.email) if "email" in fields and body.email is not None else booking.email
    if new_email != booking.email:
        changes["email"] = {"from": booking.email, "to": new_email}

    new_day = body.slot_date if "slot_date" in fields and body.slot_date is not None else booking.slot_date
    new_time = body.slot_time if "slot_time" in fields else booking.slot_time
    if (new_day, new_time) != old_slot:
        slot = find_slot(ctx, config, now, new_day, new_time)
        await ensure_room(db, ctx.registration.id, slot)
        before, after = _slot_text(*old_slot), _slot_text(new_day, new_time)
        if before[0] != after[0]:
            changes["slot_date"] = {"from": before[0], "to": after[0]}
        if before[1] != after[1]:
            changes["slot_time"] = {"from": before[1], "to": after[1]}

    new_entries: list[dict] | None = None
    if body.answers is not None:
        questions = to_logic_questions(await forms_service.get_questions(db, ctx.registration.form_id))
        try:
            new_entries = forms_service.validate_answers(questions, body.answers)
        except FormValidationError as exc:
            raise BookingError(422, exc.as_detail()) from exc
        old_submission = (
            await forms_service.get_submission(db, ctx.registration.form_id, booking.submission_id) if booking.submission_id else None
        )
        different = changed_questions(old_submission.answers if old_submission else [], new_entries)
        if different:
            changes["answers"] = {"questions": different}
        else:
            new_entries = None

    if not changes:
        raise field_error(422, "_form", "no_change")

    booking.name = new_name
    booking.email = new_email
    booking.slot_date = new_day
    booking.slot_time = new_time
    if new_entries is not None:
        previous = booking.submission_id
        booking.submission_id = (await forms_service.store_submission(db, ctx.registration.form_id, new_entries)).id
        await db.flush()
        if previous:
            await forms_service.delete_submissions(db, [previous])
    change = BookingChange(
        booking_id=booking.id,
        kind=CHANGE_UPDATED,
        note=clean_note(body.note),
        changes=changes,
        user_sub=admin.auth_sub,
    )
    db.add(change)
    await db.flush()
    await db.refresh(change)
    await db.refresh(booking)
    return booking, change, old_slot


async def cancel_by_admin(
    db: AsyncSession, booking_id: uuid.UUID, body: BookingCancelBody, *, admin: User
) -> tuple[Booking, BookingChange | None]:
    """Cancels a booking and records it; (booking, None) when it was cancelled
    already (the call is idempotent and leaves no second entry)."""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise BookingError(404, "Booking not found")
    await _lock_registration_of(db, booking)
    if booking.status == STATUS_CANCELLED:
        return booking, None
    booking.status = STATUS_CANCELLED
    booking.cancelled_at = utcnow()
    change = BookingChange(
        booking_id=booking.id,
        kind=CHANGE_CANCELLED,
        note=clean_note(body.note),
        changes={"status": {"from": STATUS_CONFIRMED, "to": STATUS_CANCELLED}},
        user_sub=admin.auth_sub,
    )
    db.add(change)
    await db.flush()
    await db.refresh(change)
    await db.refresh(booking)
    return booking, change


async def send_admin_action_mail(
    db: AsyncSession,
    booking: Booking,
    change: BookingChange,
    old_slot: tuple[date, time | None],
    config: EventBookingConfig,
    settings: Settings,
) -> bool:
    """Tells the person what an administrator did - "changed" or "cancelled_by_admin",
    in the language they booked in, with the note - and records on the history
    entry whether it went out. Returns that. The caller commits."""
    event_title, registration_name = await labels_of(db, booking.registration_id)
    values = mail.template_values(
        config,
        settings,
        booking.language,
        name=booking.name,
        email=booking.email,
        event_title=event_title,
        registration_name=registration_name,
        slot_date=booking.slot_date,
        slot_time=booking.slot_time,
        cancel_token=booking.cancel_token,
        old_slot=old_slot,
        note=change.note,
    )
    template_type = "changed" if change.kind == CHANGE_UPDATED else "cancelled_by_admin"
    sent, error = await mail.deliver(config, settings, template_type, booking.language, booking.email, values)
    change.notified = sent
    change.email_error = error
    return sent


# --- Reading bookings --------------------------------------------------------------


async def booking_detail(db: AsyncSession, booking: Booking) -> BookingAdminOut:
    registration = await db.get(Registration, booking.registration_id)
    event_title, registration_name = await labels_of(db, booking.registration_id)
    submission = (
        await forms_service.get_submission(db, registration.form_id, booking.submission_id) if booking.submission_id else None
    )
    history = (
        await db.scalars(select(BookingChange).where(BookingChange.booking_id == booking.id).order_by(BookingChange.created_at.desc(), BookingChange.id))
    ).all()
    await db.refresh(booking)
    return BookingAdminOut(
        id=booking.id,
        registration_id=booking.registration_id,
        event_title=event_title,
        registration_name=registration_name,
        slot_date=booking.slot_date,
        slot_time=booking.slot_time,
        name=booking.name,
        email=booking.email,
        user_sub=booking.user_sub,
        language=booking.language,
        status=booking.status,
        consent_at=booking.consent_at,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        cancelled_at=booking.cancelled_at,
        answers=submission.answers if submission else [],
        history=[ChangeOut.model_validate(change) for change in history],
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _booking_filters(
    registration_id: uuid.UUID,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> list:
    filters = [Booking.registration_id == registration_id]
    if status:
        filters.append(Booking.status == status)
    if date_from:
        filters.append(Booking.slot_date >= date_from)
    if date_to:
        filters.append(Booking.slot_date <= date_to)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        filters.append(or_(Booking.name.ilike(pattern, escape="\\"), Booking.email.ilike(pattern, escape="\\")))
    return filters


async def list_bookings(
    db: AsyncSession,
    registration_id: uuid.UUID,
    *,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    descending: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> BookingRowPage:
    filters = _booking_filters(registration_id, status, date_from, date_to, q)
    total = await db.scalar(select(func.count()).select_from(Booking).where(*filters))
    has_history = exists().where(BookingChange.booking_id == Booking.id)
    order = (
        (Booking.slot_date.desc(), Booking.slot_time.desc().nulls_last(), Booking.created_at.desc())
        if descending
        else (Booking.slot_date.asc(), Booking.slot_time.asc().nulls_first(), Booking.created_at.asc())
    )
    rows = (
        await db.execute(select(Booking, has_history).where(*filters).order_by(*order, Booking.id).offset(offset).limit(limit))
    ).all()
    return BookingRowPage(
        items=[
            BookingRow(
                id=booking.id,
                slot_date=booking.slot_date,
                slot_time=booking.slot_time,
                name=booking.name,
                email=booking.email,
                status=booking.status,
                created_at=booking.created_at,
                has_history=bool(history),
            )
            for booking, history in rows
        ],
        total=total or 0,
    )


def csv_cell(value: Any) -> str:
    """A cell as text, safe to open in a spreadsheet: one that would start a
    formula (= + - @) is prefixed with an apostrophe so it stays text."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(CSV_FORMULA_PREFIXES) else text


async def bookings_csv(db: AsyncSession, registration: Registration, config: EventBookingConfig) -> str:
    """Every booking of the registration as CSV: UTF-8 with a BOM and ';' as the
    separator (what a Czech Excel opens without asking), the answers one column
    per question - the form's current questions first, then any that are only
    in older answers - and every cell passed through csv_cell."""
    language = config.default_language
    headers = list(for_language(CSV_HEADERS, language) or CSV_HEADERS["en"])
    statuses = for_language(CSV_STATUSES, language) or CSV_STATUSES["en"]

    bookings = list(
        (
            await db.scalars(
                select(Booking)
                .where(Booking.registration_id == registration.id)
                .order_by(Booking.slot_date, Booking.slot_time.asc().nulls_first(), Booking.created_at, Booking.id)
            )
        ).all()
    )
    snapshots: dict[uuid.UUID, list[dict]] = {}
    for booking in bookings:
        if booking.submission_id:
            submission = await forms_service.get_submission(db, registration.form_id, booking.submission_id)
            snapshots[booking.id] = submission.answers if submission else []

    columns: dict[str, str] = {
        str(question.id): question.label for question in await forms_service.get_questions(db, registration.form_id)
    }
    for entries in snapshots.values():
        for entry in entries:
            columns.setdefault(entry["question_id"], entry["label"])

    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([csv_cell(header) for header in [*headers, *columns.values()]])
    for booking in bookings:
        answers = {entry["question_id"]: entry for entry in snapshots.get(booking.id, [])}
        row = [
            mail.format_date(booking.slot_date, language),
            mail.format_time(booking.slot_time, config, language),
            booking.name,
            booking.email,
            statuses[booking.status],
            slots.to_local(booking.created_at).strftime("%Y-%m-%d %H:%M"),
            slots.to_local(booking.consent_at).strftime("%Y-%m-%d %H:%M"),
        ]
        for question_id in columns:
            entry = answers.get(question_id)
            row.append(entry.get("display", "") if entry and entry.get("shown") else "")
        writer.writerow([csv_cell(cell) for cell in row])
    return buffer.getvalue()


async def confirmed_submission_ids(db: AsyncSession, registration_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await db.scalars(
                select(Booking.submission_id).where(
                    Booking.registration_id == registration_id,
                    Booking.status == STATUS_CONFIRMED,
                    Booking.submission_id.is_not(None),
                )
            )
        ).all()
    )


# --- Registrations (administrators) --------------------------------------------------


async def booking_counts(db: AsyncSession, registration_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    """registration id -> (confirmed, cancelled)."""
    if not registration_ids:
        return {}
    rows = await db.execute(
        select(Booking.registration_id, Booking.status, func.count())
        .where(Booking.registration_id.in_(list(registration_ids)))
        .group_by(Booking.registration_id, Booking.status)
    )
    counts: dict[uuid.UUID, list[int]] = {}
    for registration_id, status, count in rows:
        entry = counts.setdefault(registration_id, [0, 0])
        entry[0 if status == STATUS_CONFIRMED else 1] = count
    return {key: (value[0], value[1]) for key, value in counts.items()}


async def registration_admin_out(db: AsyncSession, registration: Registration) -> RegistrationAdminOut:
    await db.refresh(registration)
    event = await db.get(Event, registration.event_id)
    rows = await blocks_of(db, registration.id)
    confirmed, cancelled = (await booking_counts(db, [registration.id])).get(registration.id, (0, 0))
    return RegistrationAdminOut(
        id=registration.id,
        event_id=registration.event_id,
        event_title=event.title,
        event_start_date=event.start_date,
        event_end_date=event.end_date,
        event_start_time=event.start_time,
        event_end_time=event.end_time,
        article_id=event.article_id,
        article_slug=event.article.slug,
        name=registration.name,
        description=registration.description,
        access=registration.access,
        link_token=registration.link_token,
        capacity=registration.capacity,
        form_id=registration.form_id,
        is_open=registration.is_open,
        blocks=rows,
        confirmed_count=confirmed,
        cancelled_count=cancelled,
        created_at=registration.created_at,
        updated_at=registration.updated_at,
    )


async def list_registrations(db: AsyncSession, event_id: uuid.UUID | None = None) -> list[RegistrationListItem]:
    query = select(Registration, Event).join(Event, Event.id == Registration.event_id)
    if event_id is not None:
        query = query.where(Registration.event_id == event_id)
    rows = (await db.execute(query.order_by(Event.start_date.desc(), Event.title, Registration.id))).all()
    counts = await booking_counts(db, [registration.id for registration, _ in rows])
    return [
        RegistrationListItem(
            id=registration.id,
            event_id=event.id,
            event_title=event.title,
            event_start_date=event.start_date,
            event_end_date=event.end_date,
            name=registration.name,
            access=registration.access,
            is_open=registration.is_open,
            confirmed_count=counts.get(registration.id, (0, 0))[0],
            cancelled_count=counts.get(registration.id, (0, 0))[1],
        )
        for registration, event in rows
    ]


async def create_registration(db: AsyncSession, body: RegistrationCreate) -> Registration:
    """The registration of an event with its (empty) form of questions. 422 for
    an unknown event or invalid blocks, 409 when the event already has one."""
    if await db.get(Event, body.event_id) is None:
        raise field_error(422, "event_id", "unknown")
    if await db.scalar(select(Registration.id).where(Registration.event_id == body.event_id)) is not None:
        raise field_error(409, "event_id", "has_registration")
    check_blocks(body.blocks)

    form = await forms_service.create_form(db, body.name)
    registration = Registration(
        event_id=body.event_id,
        name=body.name,
        description=body.description,
        access=body.access,
        capacity=body.capacity,
        is_open=body.is_open,
        form_id=form.id,
    )
    db.add(registration)
    await db.flush()
    db.add_all(block_row(registration.id, position, block) for position, block in enumerate(body.blocks))
    await db.flush()
    return registration


async def update_registration(db: AsyncSession, registration_id: uuid.UUID, body: RegistrationUpdate) -> Registration:
    registration = await get_registration(db, registration_id, lock=True)
    if registration is None:
        raise BookingError(404, "Registration not found")
    updates = body.model_dump(exclude_unset=True, exclude={"blocks"})
    for field, value in updates.items():
        if value is None:
            raise field_error(422, field, "cannot_be_null")
    if body.blocks is not None:
        check_blocks(body.blocks)

    for field, value in updates.items():
        setattr(registration, field, value)
    if "name" in updates:
        form = await forms_service.get_form(db, registration.form_id)
        if form is not None:
            form.name = updates["name"]
    if body.blocks is not None:
        await db.execute(delete(RegistrationBlock).where(RegistrationBlock.registration_id == registration.id))
        db.add_all(block_row(registration.id, position, block) for position, block in enumerate(body.blocks))
        registration.updated_at = utcnow()
    await db.flush()
    return registration


async def regenerate_link(db: AsyncSession, registration_id: uuid.UUID) -> Registration:
    """A new link token: the old link stops working (an access-"link" registration is shown only to its holders)."""
    registration = await get_registration(db, registration_id, lock=True)
    if registration is None:
        raise BookingError(404, "Registration not found")
    registration.link_token = new_token()
    registration.updated_at = utcnow()
    await db.flush()
    return registration


async def delete_registration(db: AsyncSession, registration_id: uuid.UUID) -> None:
    """Deletes a registration that has no bookings (cancelled ones count: they
    are kept until retention removes them) together with its form."""
    registration = await get_registration(db, registration_id, lock=True)
    if registration is None:
        raise BookingError(404, "Registration not found")
    if await db.scalar(select(func.count()).select_from(Booking).where(Booking.registration_id == registration.id)):
        raise field_error(409, "_form", "has_bookings")
    form_id = registration.form_id
    await db.delete(registration)
    await db.flush()
    try:
        await forms_service.delete_form(db, form_id)
    except FormInUseError as exc:
        raise field_error(409, "_form", "form_has_answers") from exc


# --- Retention (GDPR) ---------------------------------------------------------------------

_last_purge: date | None = None


def months_ago(today: date, months: int) -> date:
    """The day `months` calendar months before `today` (the day clamped to the month's length)."""
    year, month_index = divmod(today.year * 12 + today.month - 1 - months, 12)
    month = month_index + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


async def purge_expired(db: AsyncSession, today: date, *, retention_months: int | None = None) -> int:
    """Deletes every booking whose slot was more than `retention_months`
    (the config's, 12) ago - with its history (cascade) and its answers.
    Returns how many bookings went. Flushes, does not commit."""
    months = get_config().retention_months if retention_months is None else retention_months
    result = await db.execute(delete(Booking).where(Booking.slot_date < months_ago(today, months)).returning(Booking.submission_id))
    rows = result.all()
    await forms_service.delete_submissions(db, [row[0] for row in rows if row[0] is not None])
    return len(rows)


async def maybe_purge(db: AsyncSession, today: date, config: EventBookingConfig) -> None:
    """purge_expired at most once a day per process, called from the places
    that are busy anyway (a new booking, the administrators' list) - there is
    no scheduler. A failure is logged and never reaches the caller."""
    global _last_purge
    if _last_purge == today:
        return
    try:
        deleted = await purge_expired(db, today, retention_months=config.retention_months)
        await db.commit()
    except Exception:  # noqa: BLE001 - the purge must never break a booking
        logger.exception("Purging expired bookings failed")
        await db.rollback()
        return
    _last_purge = today
    if deleted:
        logger.info("Purged %d expired bookings", deleted)


def reset_purge_throttle() -> None:
    """For tests: forget that the purge already ran today."""
    global _last_purge
    _last_purge = None
