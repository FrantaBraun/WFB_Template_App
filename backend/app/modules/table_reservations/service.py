# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules of the table reservations module, between the router and the
database. The pure rules (which table, how long, what overlaps) are in rules.py;
this file loads what they need, applies them and writes.

Nothing here commits: the router does, so a reservation (or a cancellation) is one
transaction. Every check that can refuse something is done BEFORE the first write,
so a refusal leaves nothing behind (the request's session rolls back when it closes).

Concurrency - why there is ONE lock. A reservation is accepted only if it does not
collide with the others of its day, and a collision is a relation between rows (two
tables' reservations, a table and the whole pub, a reservation and the day's hours),
so no unique constraint can guard it. Everything that decides on the strength of
the reservations that exist - a guest reserving, the pub cancelling, a change of
the opening hours, of a day's exception or of a table - first takes ONE
transaction-level advisory lock (`pg_advisory_xact_lock`), reads, decides and writes,
and the lock is released by the commit. Two requests are therefore serialised and
the second sees the first; closing a day cannot slip past a reservation made at the
same moment. For one pub the throughput this gives up is irrelevant, and a single
lock cannot deadlock.

Errors are ReservationError(status, detail) (an HTTPException); the 422 / 409
details have the shape {"errors": {field: code}} - the same one the forms module
uses - so a client has one way to put a message at a field. A refusal because
reservations stand in the way (closing a day, taking a table out of use) also
carries them: {"errors": {"_form": "has_reservations"}, "reservations": [...]}.
"""

import calendar
import logging
import uuid
from collections.abc import Sequence
from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.user import User
from app.modules.table_reservations import mail, rules
from app.modules.table_reservations.config import TableReservationsConfig
from app.modules.table_reservations.models import (
    CANCELLED_BY_ADMIN,
    CANCELLED_BY_GUEST,
    KIND_TABLE,
    KIND_WHOLE_VENUE,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    DiningTable,
    OpeningException,
    OpeningHours,
    Reservation,
)
from app.modules.table_reservations.rules import DayOverride, Held, Hours, Seating
from app.modules.table_reservations.schemas import (
    MAX_PARTY_SIZE,
    AvailabilityOut,
    CancelBody,
    DayOut,
    DaysOut,
    ExceptionIn,
    ExceptionOut,
    HoursUpdate,
    InfoOut,
    ReservationAdmin,
    ReservationCreate,
    ReservationPublic,
    TableIn,
    TableOut,
    TablePatch,
    WeekdayHours,
)

logger = logging.getLogger(__name__)

# The key of the one advisory lock (see the module docstring).
LOCK_KEY = 7_311_001

# How many upcoming reservations a refusal lists (the administrator resolves
# them one by one, so a few hundred is more than a pub will ever have).
CONFLICT_LIMIT = 200


class ReservationError(HTTPException):
    """A refusal. It is the HTTP answer itself (FastAPI turns it into the
    response), so the router needs no translation of its own."""

    def __init__(self, status_code: int, detail: Any):
        super().__init__(status_code=status_code, detail=detail)


def field_error(status_code: int, field: str, code: str) -> ReservationError:
    return ReservationError(status_code, {"errors": {field: code}})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def lock_reservations(db: AsyncSession) -> None:
    """Takes the one lock; it is held until the transaction ends."""
    await db.execute(select(func.pg_advisory_xact_lock(LOCK_KEY)))


# --- Hours, tables and what is reserved: rows <-> rules ------------------------------


def row_hours(opens: time | None, closes: time | None) -> Hours | None:
    if opens is None or closes is None:
        return None
    return Hours(rules.minutes(opens), rules.minutes(closes))


async def load_weekly(db: AsyncSession) -> dict[int, Hours | None]:
    rows = (await db.scalars(select(OpeningHours).execution_options(populate_existing=True))).all()
    return {row.weekday: None if row.is_closed else row_hours(row.opens, row.closes) for row in rows}


async def load_overrides(db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None) -> dict[date, DayOverride]:
    query = select(OpeningException).execution_options(populate_existing=True)
    if date_from is not None:
        query = query.where(OpeningException.day >= date_from)
    if date_to is not None:
        query = query.where(OpeningException.day <= date_to)
    return {
        row.day: DayOverride(closed=row.is_closed, hours=None if row.is_closed else row_hours(row.opens, row.closes), reason=row.reason)
        for row in (await db.scalars(query)).all()
    }


async def load_tables(db: AsyncSession) -> list[DiningTable]:
    return list((await db.scalars(select(DiningTable).order_by(DiningTable.position, DiningTable.name, DiningTable.id).execution_options(populate_existing=True))).all())


def seating(tables: Sequence[DiningTable]) -> list[Seating]:
    return [Seating(id=table.id, seats=table.seats, position=table.position, is_active=table.is_active) for table in tables]


async def confirmed_on(db: AsyncSession, day: date) -> list[Reservation]:
    return list(
        (
            await db.scalars(
                select(Reservation)
                .where(Reservation.day == day, Reservation.status == STATUS_CONFIRMED)
                .order_by(Reservation.start_time, Reservation.id)
                .execution_options(populate_existing=True)
            )
        ).all()
    )


def to_held(reservation: Reservation) -> Held:
    return Held(
        kind=reservation.kind,
        table_id=reservation.table_id,
        start=rules.minutes(reservation.start_time),
        end=rules.minutes(reservation.end_time),
    )


def month_range(month: str) -> tuple[date, date]:
    """The first and last day of "YYYY-MM" (the router has checked its shape)."""
    year, number = int(month[:4]), int(month[5:7])
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


# --- What visitors see -----------------------------------------------------------------


def _weekly_out(rows: Sequence[OpeningHours]) -> list[WeekdayHours]:
    """All seven weekdays: one with no row is closed."""
    by_day = {row.weekday: row for row in rows}
    return [
        WeekdayHours(weekday=n, is_closed=True) if n not in by_day or by_day[n].is_closed else WeekdayHours.model_validate(by_day[n])
        for n in range(7)
    ]


async def info(db: AsyncSession, config: TableReservationsConfig, now: datetime) -> InfoOut:
    today = now.date()
    rows = (await db.scalars(select(OpeningHours).order_by(OpeningHours.weekday))).all()
    weekly = _weekly_out(rows)
    exceptions = (
        await db.scalars(
            select(OpeningException)
            .where(OpeningException.day >= today)
            .order_by(OpeningException.day)
            .limit(400)
        )
    ).all()
    tables = [table for table in await load_tables(db) if table.is_active]
    max_party = max((table.seats for table in tables), default=0)
    any_open = any(not day.is_closed for day in weekly) or any(not row.is_closed for row in exceptions)
    return InfoOut(
        weekly=weekly,
        exceptions=[ExceptionOut.model_validate(row) for row in exceptions],
        max_party_size=max_party,
        max_whole_venue_party=MAX_PARTY_SIZE,
        max_days_ahead=config.max_days_ahead,
        lead_minutes=config.lead_minutes,
        default_duration=config.default_duration,
        duration_options=config.duration_options,
        min_duration=rules.MIN_DURATION,
        step_minutes=rules.STEP_MINUTES,
        privacy_url=config.privacy_url,
        can_reserve=bool(tables) and any_open,
    )


def _bookable(day: date, hours: Hours | None, config: TableReservationsConfig, now: datetime) -> bool:
    today = now.date()
    return hours is not None and today <= day <= date.fromordinal(today.toordinal() + config.max_days_ahead)


async def public_days(db: AsyncSession, month: str, config: TableReservationsConfig, now: datetime) -> DaysOut:
    """The hours of every day of a month, and which days can be reserved."""
    first, last = month_range(month)
    weekly = await load_weekly(db)
    overrides = await load_overrides(db, date_from=first, date_to=last)
    days: list[DayOut] = []
    for ordinal in range(first.toordinal(), last.toordinal() + 1):
        day = date.fromordinal(ordinal)
        hours = rules.day_hours(day, weekly, overrides)
        override = overrides.get(day)
        days.append(
            DayOut(
                day=day,
                is_open=hours is not None,
                opens=rules.at(hours.opens) if hours else None,
                closes=rules.at(hours.closes) if hours else None,
                reason=override.reason if override else None,
                bookable=_bookable(day, hours, config, now),
            )
        )
    return DaysOut(days=days)


async def availability(
    db: AsyncSession, day: date, party_size: int, duration: int, config: TableReservationsConfig, now: datetime
) -> AvailabilityOut:
    """Every start at which `party_size` people could sit for `duration` minutes on
    `day`, and when the whole pub can be reserved from. Read-only: whether a start
    still works is decided again, under the lock, when someone reserves it."""
    weekly = await load_weekly(db)
    overrides = await load_overrides(db, date_from=day, date_to=day)
    hours = rules.day_hours(day, weekly, overrides)
    override = overrides.get(day)
    earliest = rules.earliest_start(day, now, config.lead_minutes)
    base = {
        "day": day,
        "is_open": hours is not None,
        "opens": rules.at(hours.opens) if hours else None,
        "closes": rules.at(hours.closes) if hours else None,
        "reason": override.reason if override else None,
    }
    if hours is None or earliest is None or not _bookable(day, hours, config, now):
        return AvailabilityOut(**base, bookable=False, starts=[], table_reason=None, whole_venue_from=None, whole_venue_reason=None)

    tables = seating(await load_tables(db))
    held = [to_held(reservation) for reservation in await confirmed_on(db, day)]
    starts = rules.available_starts(hours, held, tables, party_size, duration, earliest)
    table_reason = None
    if not starts:
        if rules.round_up(max(hours.opens, earliest)) > hours.closes - rules.MIN_DURATION:
            table_reason = rules.TOO_SOON  # nothing of the day is left
        elif not any(table.is_active and table.seats >= party_size for table in tables):
            table_reason = rules.PARTY_TOO_LARGE
        elif any(h.kind == KIND_WHOLE_VENUE for h in held):
            table_reason = rules.VENUE_RESERVED
        else:
            table_reason = rules.NO_TABLE
    whole_from, whole_reason = rules.whole_venue_from(hours, held, earliest)
    return AvailabilityOut(
        **base,
        bookable=True,
        starts=[rules.at(start) for start in starts],
        table_reason=table_reason,
        whole_venue_from=rules.at(whole_from) if whole_from is not None else None,
        whole_venue_reason=whole_reason,
    )


# --- A guest's reservation -------------------------------------------------------------


async def create_reservation(
    db: AsyncSession, body: ReservationCreate, *, config: TableReservationsConfig, now: datetime
) -> Reservation:
    """Reserves a table (or the whole pub), or raises. Holds the lock from the
    first check to the caller's commit."""
    await lock_reservations(db)
    today = now.date()

    errors: dict[str, str] = {}
    if not body.consent:
        errors["consent"] = "required"
    if body.start_time.second or body.start_time.microsecond:
        errors["start_time"] = rules.BAD_START
    if body.kind == KIND_TABLE and body.duration_minutes is not None and body.duration_minutes % rules.STEP_MINUTES:
        errors["duration_minutes"] = "bad_duration"
    if errors:
        raise ReservationError(422, {"errors": errors})

    if not today <= body.day <= date.fromordinal(today.toordinal() + config.max_days_ahead):
        raise field_error(422, "day", "out_of_range")
    weekly = await load_weekly(db)
    overrides = await load_overrides(db, date_from=body.day, date_to=body.day)
    hours = rules.day_hours(body.day, weekly, overrides)
    if hours is None:
        raise field_error(422, "day", rules.CLOSED)
    earliest = rules.earliest_start(body.day, now, config.lead_minutes)
    start = rules.minutes(body.start_time)
    problem = rules.start_problem(start, hours, earliest if earliest is not None else 0)
    if problem:
        raise field_error(422, "start_time", problem)

    held = [to_held(reservation) for reservation in await confirmed_on(db, body.day)]
    table_id: uuid.UUID | None = None
    if body.kind == KIND_TABLE:
        end = rules.planned_end(start, body.duration_minutes or config.default_duration, hours)
        if end is None:  # start_problem allows a start MIN_DURATION before closing, so this is a guard
            raise field_error(422, "start_time", rules.OUTSIDE_HOURS)
        table, reason = rules.assign_table(seating(await load_tables(db)), held, start, end, body.party_size)
        if table is None:
            if reason == rules.PARTY_TOO_LARGE:
                raise field_error(422, "party_size", reason)
            raise field_error(409, "start_time", reason or rules.NO_TABLE)
        table_id = table.id
    else:
        end = hours.closes
        reason = rules.whole_venue_problem(start, hours, held)
        if reason:
            raise field_error(409, "start_time", reason)

    email = str(body.email)
    active = await db.scalar(
        select(func.count()).where(
            Reservation.status == STATUS_CONFIRMED,
            func.lower(Reservation.email) == email.lower(),
            Reservation.day >= today,
        )
    )
    if (active or 0) >= config.max_active_per_email:
        raise field_error(422, "email", "too_many")

    reservation = Reservation(
        kind=body.kind,
        table_id=table_id,
        day=body.day,
        start_time=rules.at(start),
        end_time=rules.at(end),
        party_size=body.party_size,
        name=body.name,
        email=email,
        phone=body.phone,
        note=body.note,
        consent_at=utcnow(),
        language=config.resolve_language(body.language),
    )
    db.add(reservation)
    await db.flush()
    await db.refresh(reservation)
    return reservation


async def table_name_of(db: AsyncSession, reservation: Reservation) -> str | None:
    if reservation.table_id is None:
        return None
    return await db.scalar(select(DiningTable.name).where(DiningTable.id == reservation.table_id))


async def send_new_reservation_mails(db: AsyncSession, reservation: Reservation, config: TableReservationsConfig, settings: Settings) -> None:
    """The confirmation to the guest and the notice to the pub, each when switched
    on. A failure is logged and goes no further."""
    if config.send_confirmation:
        values = mail.template_values(config, settings, reservation.language, reservation)
        await mail.deliver(config, settings, "confirmation", reservation.language, reservation.email, values)
    if config.notify_admin:
        address = mail.notify_address(settings)
        if not address:
            logger.warning("A reservation was made but neither BOOKING_NOTIFY_MAIL nor CONTACT_MAIL is set - nobody is notified")
        else:
            admin_values = mail.template_values(
                config, settings, config.default_language, reservation, table_name=await table_name_of(db, reservation)
            )
            await mail.deliver(config, settings, "admin_notification", config.default_language, address, admin_values)


async def get_by_token(db: AsyncSession, cancel_token: str) -> Reservation | None:
    return (await db.scalars(select(Reservation).where(Reservation.cancel_token == cancel_token))).first()


def public_reservation(reservation: Reservation) -> ReservationPublic:
    """A reservation as its owner sees it: no e-mail address, no table and nothing the pub wrote."""
    return ReservationPublic(
        kind=reservation.kind,
        day=reservation.day,
        start_time=reservation.start_time,
        end_time=reservation.end_time,
        party_size=reservation.party_size,
        name=reservation.name,
        status=reservation.status,
        cancelled_at=reservation.cancelled_at,
    )


async def cancel_by_guest(db: AsyncSession, cancel_token: str) -> tuple[Reservation, bool]:
    """Cancels the reservation its token belongs to; (reservation, True) if it was
    cancelled now, (reservation, False) if it already was - so the same link is safe
    to press twice. 404 for an unknown token."""
    reservation = await get_by_token(db, cancel_token)
    if reservation is None:
        raise ReservationError(404, "Reservation not found")
    await lock_reservations(db)
    await db.refresh(reservation)
    if reservation.status == STATUS_CANCELLED:
        return reservation, False
    reservation.status = STATUS_CANCELLED
    reservation.cancelled_at = utcnow()
    reservation.cancelled_by = CANCELLED_BY_GUEST
    await db.flush()
    return reservation, True


async def send_guest_cancellation_mail(reservation: Reservation, config: TableReservationsConfig, settings: Settings) -> None:
    if not config.send_confirmation:
        return
    values = mail.template_values(config, settings, reservation.language, reservation)
    await mail.deliver(config, settings, "cancellation", reservation.language, reservation.email, values)


# --- The pub's own view and changes ---------------------------------------------------------


def admin_out(reservation: Reservation, table_name: str | None) -> ReservationAdmin:
    return ReservationAdmin(
        id=reservation.id,
        kind=reservation.kind,
        table_id=reservation.table_id,
        table_name=table_name,
        day=reservation.day,
        start_time=reservation.start_time,
        end_time=reservation.end_time,
        party_size=reservation.party_size,
        name=reservation.name,
        email=reservation.email,
        phone=reservation.phone,
        note=reservation.note,
        language=reservation.language,
        consent_at=reservation.consent_at,
        created_at=reservation.created_at,
        status=reservation.status,
        cancelled_at=reservation.cancelled_at,
        cancelled_by=reservation.cancelled_by,
        cancel_note=reservation.cancel_note,
        notified=reservation.notified,
        email_error=reservation.email_error,
    )


async def reservation_detail(db: AsyncSession, reservation: Reservation) -> ReservationAdmin:
    await db.refresh(reservation)
    return admin_out(reservation, await table_name_of(db, reservation))


async def list_reservations(
    db: AsyncSession, *, date_from: date, date_to: date, status: str | None = None, limit: int = 1000
) -> list[ReservationAdmin]:
    """The reservations of a range of days (by day, then start), with the table's name."""
    query = (
        select(Reservation, DiningTable.name)
        .outerjoin(DiningTable, DiningTable.id == Reservation.table_id)
        .where(Reservation.day >= date_from, Reservation.day <= date_to)
        .order_by(Reservation.day, Reservation.start_time, Reservation.created_at, Reservation.id)
        .limit(limit)
        .execution_options(populate_existing=True)
    )
    if status:
        query = query.where(Reservation.status == status)
    return [admin_out(reservation, name) for reservation, name in (await db.execute(query)).all()]


async def cancel_by_admin(db: AsyncSession, reservation_id: uuid.UUID, body: CancelBody, *, admin: User) -> tuple[Reservation, bool]:
    """The pub cancels a reservation and keeps its message; (reservation, True)
    when it was cancelled now, (reservation, False) when it already was (the call
    is idempotent and changes nothing the second time). 404 when it does not exist."""
    reservation = await db.get(Reservation, reservation_id)
    if reservation is None:
        raise ReservationError(404, "Reservation not found")
    await lock_reservations(db)
    await db.refresh(reservation)
    if reservation.status == STATUS_CANCELLED:
        return reservation, False
    reservation.status = STATUS_CANCELLED
    reservation.cancelled_at = utcnow()
    reservation.cancelled_by = CANCELLED_BY_ADMIN
    reservation.cancel_note = (body.note or "").strip() or None
    reservation.cancelled_by_sub = admin.auth_sub
    await db.flush()
    return reservation, True


async def send_admin_cancellation_mail(db: AsyncSession, reservation: Reservation, config: TableReservationsConfig, settings: Settings) -> bool:
    """Tells the guest the pub cancelled their reservation - in the language they
    reserved in, with the pub's message - and records on the reservation whether
    it went out. Returns that. The caller commits."""
    values = mail.template_values(config, settings, reservation.language, reservation, note=reservation.cancel_note)
    sent, error = await mail.deliver(config, settings, "cancelled_by_admin", reservation.language, reservation.email, values)
    reservation.notified = sent
    reservation.email_error = error
    return sent


# --- What stands in the way of a change ---------------------------------------------------


async def confirmed_from(
    db: AsyncSession, now: datetime, *, days: set[date] | None = None, table_id: uuid.UUID | None = None
) -> list[tuple[Reservation, str | None]]:
    """The confirmed reservations that have not ended yet (a reservation of today
    counts until its end) - those of `days` or of one table, if given - with the
    table's name."""
    query = (
        select(Reservation, DiningTable.name)
        .outerjoin(DiningTable, DiningTable.id == Reservation.table_id)
        .where(Reservation.status == STATUS_CONFIRMED, Reservation.day >= now.date())
        .order_by(Reservation.day, Reservation.start_time, Reservation.id)
        .execution_options(populate_existing=True)
    )
    if days is not None:
        query = query.where(Reservation.day.in_(days))
    if table_id is not None:
        query = query.where(Reservation.table_id == table_id)
    rows = (await db.execute(query)).all()
    return [(reservation, name) for reservation, name in rows if reservation.day > now.date() or reservation.end_time > now.time()]


def conflict_error(rows: Sequence[tuple[Reservation, str | None]]) -> ReservationError:
    """409: these reservations must be resolved (cancelled by the pub, one by one) first."""
    return ReservationError(
        409,
        {
            "errors": {"_form": "has_reservations"},
            "reservations": jsonable_encoder([admin_out(reservation, name) for reservation, name in rows[:CONFLICT_LIMIT]]),
            "total": len(rows),
        },
    )


async def ensure_hours_allow(
    db: AsyncSession, weekly: dict[int, Hours | None], overrides: dict[date, DayOverride], now: datetime, *, days: set[date] | None = None
) -> None:
    """409 when any confirmed upcoming reservation (of `days` only, if given) would
    no longer lie within the hours these `weekly` hours and `overrides` give."""
    bad = [
        (reservation, name)
        for reservation, name in await confirmed_from(db, now, days=days)
        if not rules.fits_hours(
            rules.minutes(reservation.start_time), rules.minutes(reservation.end_time), rules.day_hours(reservation.day, weekly, overrides)
        )
    ]
    if bad:
        raise conflict_error(bad)


# --- Opening hours ---------------------------------------------------------------------------


def _hours_input_error(prefix: str, is_closed: bool, opens: time | None, closes: time | None) -> dict[str, str]:
    """The problems of one entry of opening hours: {field: code}, empty when it is fine."""
    if is_closed:
        return {}
    if opens is None or closes is None:
        return {f"{prefix}opens" if opens is None else f"{prefix}closes": "required"}
    problem = rules.hours_problem(rules.minutes(opens), rules.minutes(closes))
    return {f"{prefix}closes": problem} if problem else {}


async def weekly_hours_out(db: AsyncSession) -> list[WeekdayHours]:
    return _weekly_out((await db.scalars(select(OpeningHours).order_by(OpeningHours.weekday).execution_options(populate_existing=True))).all())


async def replace_weekly_hours(db: AsyncSession, body: HoursUpdate, now: datetime) -> list[WeekdayHours]:
    """Sets the regular hours of the whole week. 422 for hours that make no sense,
    409 (with the reservations) when an upcoming reservation would fall outside them."""
    if sorted(day.weekday for day in body.days) != list(range(7)):
        raise field_error(422, "days", "every_weekday_once")
    errors: dict[str, str] = {}
    for day in body.days:
        errors.update(_hours_input_error(f"weekday_{day.weekday}_", day.is_closed, day.opens, day.closes))
    if errors:
        raise ReservationError(422, {"errors": errors})

    await lock_reservations(db)
    weekly = {day.weekday: None if day.is_closed else row_hours(day.opens, day.closes) for day in body.days}
    await ensure_hours_allow(db, weekly, await load_overrides(db, date_from=now.date()), now)

    await db.execute(delete(OpeningHours))
    db.add_all(
        OpeningHours(
            weekday=day.weekday,
            is_closed=day.is_closed,
            opens=None if day.is_closed else day.opens.replace(second=0, microsecond=0),
            closes=None if day.is_closed else day.closes.replace(second=0, microsecond=0),
        )
        for day in body.days
    )
    await db.flush()
    return await weekly_hours_out(db)


async def list_exceptions(db: AsyncSession, date_from: date) -> list[ExceptionOut]:
    rows = (await db.scalars(select(OpeningException).where(OpeningException.day >= date_from).order_by(OpeningException.day).execution_options(populate_existing=True))).all()
    return [ExceptionOut.model_validate(row) for row in rows]


async def put_exception(db: AsyncSession, day: date, body: ExceptionIn, now: datetime) -> ExceptionOut:
    """Sets the one-off hours (or closing) of a date from today on. 422 for hours that
    make no sense or a past date, 409 (with the reservations) when an upcoming
    reservation of that day would fall outside them - the pub resolves those first."""
    if day < now.date():
        raise field_error(422, "day", "in_past")
    errors = _hours_input_error("", body.is_closed, body.opens, body.closes)
    if errors:
        raise ReservationError(422, {"errors": errors})

    await lock_reservations(db)
    weekly = await load_weekly(db)
    overrides = await load_overrides(db, date_from=day, date_to=day)
    overrides[day] = DayOverride(
        closed=body.is_closed,
        hours=None if body.is_closed else row_hours(body.opens, body.closes),
        reason=body.reason,
    )
    await ensure_hours_allow(db, weekly, overrides, now, days={day})

    row = await db.get(OpeningException, day)
    if row is None:
        row = OpeningException(day=day)
        db.add(row)
    row.is_closed = body.is_closed
    row.opens = None if body.is_closed else body.opens.replace(second=0, microsecond=0)
    row.closes = None if body.is_closed else body.closes.replace(second=0, microsecond=0)
    row.reason = body.reason
    await db.flush()
    return ExceptionOut.model_validate(row)


async def delete_exception(db: AsyncSession, day: date, now: datetime) -> None:
    """Removes a date's one-off hours, so the weekday's regular hours apply again.
    409 when an upcoming reservation of that day would not fit those."""
    await lock_reservations(db)
    row = await db.get(OpeningException, day)
    if row is None:
        raise ReservationError(404, "Exception not found")
    weekly = await load_weekly(db)
    await ensure_hours_allow(db, weekly, {}, now, days={day})
    await db.delete(row)
    await db.flush()


# --- Tables ---------------------------------------------------------------------------------


async def list_tables_out(db: AsyncSession, now: datetime) -> list[TableOut]:
    tables = await load_tables(db)
    upcoming: dict[uuid.UUID, int] = {}
    for reservation, _ in await confirmed_from(db, now):
        if reservation.table_id is not None:
            upcoming[reservation.table_id] = upcoming.get(reservation.table_id, 0) + 1
    return [
        TableOut(id=table.id, name=table.name, seats=table.seats, position=table.position, is_active=table.is_active, upcoming_count=upcoming.get(table.id, 0))
        for table in tables
    ]


async def table_out(db: AsyncSession, table: DiningTable, now: datetime) -> TableOut:
    rows = await confirmed_from(db, now, table_id=table.id)
    return TableOut(id=table.id, name=table.name, seats=table.seats, position=table.position, is_active=table.is_active, upcoming_count=len(rows))


async def create_table(db: AsyncSession, body: TableIn) -> DiningTable:
    table = DiningTable(name=body.name, seats=body.seats, position=body.position, is_active=body.is_active)
    db.add(table)
    await db.flush()
    await db.refresh(table)
    return table


async def _get_table(db: AsyncSession, table_id: uuid.UUID) -> DiningTable:
    table = await db.get(DiningTable, table_id)
    if table is None:
        raise ReservationError(404, "Table not found")
    return table


async def update_table(db: AsyncSession, table_id: uuid.UUID, body: TablePatch, now: datetime) -> DiningTable:
    """Changes a table. Taking it out of use or seating fewer people is refused (409,
    with the reservations) while an upcoming reservation of it would no longer fit."""
    await lock_reservations(db)
    table = await _get_table(db, table_id)
    await db.refresh(table)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is None:
            raise field_error(422, field, "cannot_be_null")
    new_seats = updates.get("seats", table.seats)
    new_active = updates.get("is_active", table.is_active)
    if (table.is_active and not new_active) or new_seats < table.seats:
        stuck = [
            (reservation, name)
            for reservation, name in await confirmed_from(db, now, table_id=table.id)
            if not new_active or reservation.party_size > new_seats
        ]
        if stuck:
            raise conflict_error(stuck)
    for field, value in updates.items():
        setattr(table, field, value)
    await db.flush()
    return table


async def delete_table(db: AsyncSession, table_id: uuid.UUID, now: datetime) -> None:
    """Deletes a table that has no reservation at all (cancelled and past ones count:
    they keep the table's name in the history until retention removes them) -
    409 otherwise; an upcoming one is listed so the pub can resolve it first."""
    await lock_reservations(db)
    table = await _get_table(db, table_id)
    upcoming = await confirmed_from(db, now, table_id=table.id)
    if upcoming:
        raise conflict_error(upcoming)
    if await db.scalar(select(func.count()).select_from(Reservation).where(Reservation.table_id == table.id)):
        raise field_error(409, "_form", "in_use")
    await db.delete(table)
    await db.flush()


# --- Retention (GDPR) ---------------------------------------------------------------------------

_last_purge: date | None = None


def months_ago(today: date, months: int) -> date:
    """The day `months` calendar months before `today` (the day clamped to the month's length)."""
    year, month_index = divmod(today.year * 12 + today.month - 1 - months, 12)
    month = month_index + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


async def purge_expired(db: AsyncSession, today: date, retention_months: int) -> int:
    """Deletes every reservation whose day was more than `retention_months` ago.
    Returns how many went. Flushes, does not commit."""
    result = await db.execute(delete(Reservation).where(Reservation.day < months_ago(today, retention_months)).returning(Reservation.id))
    return len(result.all())


async def maybe_purge(db: AsyncSession, today: date, config: TableReservationsConfig) -> None:
    """purge_expired at most once a day per process, called from the places that
    are busy anyway (a new reservation, the administrators' list) - there is no
    scheduler. A failure is logged and never reaches the caller."""
    global _last_purge
    if _last_purge == today:
        return
    try:
        deleted = await purge_expired(db, today, config.retention_months)
        await db.commit()
    except Exception:  # noqa: BLE001 - the purge must never break a reservation
        logger.exception("Purging expired reservations failed")
        await db.rollback()
        return
    _last_purge = today
    if deleted:
        logger.info("Purged %d expired reservations", deleted)


def reset_purge_throttle() -> None:
    """For tests: forget that the purge already ran today."""
    global _last_purge
    _last_purge = None
