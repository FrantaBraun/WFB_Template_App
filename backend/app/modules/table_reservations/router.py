# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Reserving a table (or the whole pub): the public endpoints (opening hours, what
is free, reserving, cancelling by the link in the e-mail) and the administrators'
/manage ones (the calendar of reservations, cancelling with a message to the
guest, opening hours and one-off changes of a day, tables).

Anyone may reserve, signed in or not. Administrators are this application's own -
the local User.is_admin flag (require_admin), never the JWT's role_name.

The rules live in service.py (and rules.py), which never commits; the handlers here
commit once the whole change is done and only then send e-mails, which never fail a
request (see mail.py).

Fixed paths are declared before the ones with a parameter where both could match
(FastAPI matches in declaration order).
"""

import logging
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.table_reservations import rules, service
from app.modules.table_reservations.config import TableReservationsConfig, get_config
from app.modules.table_reservations.deps import get_now
from app.modules.table_reservations.models import STATUS_CANCELLED, STATUS_CONFIRMED, Reservation, new_token
from app.modules.table_reservations.schemas import (
    MAX_PARTY_SIZE,
    AvailabilityOut,
    CancelBody,
    CancelOut,
    DaysOut,
    ExceptionIn,
    ExceptionOut,
    HoursUpdate,
    InfoOut,
    PurgeOut,
    ReservationAdmin,
    ReservationCreate,
    ReservationCreated,
    ReservationPublic,
    TableIn,
    TableOut,
    TablePatch,
    WeekdayHours,
)

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter(prefix="/manage", dependencies=[Depends(require_admin)])

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
MAX_RANGE_DAYS = 62


# --- Public ------------------------------------------------------------------------


@router.get("/info")
async def get_info(
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: TableReservationsConfig = Depends(get_config),
) -> InfoOut:
    """The opening hours (regular and the coming one-off changes) and the limits
    the reservation form needs: everything public about the pub's hours."""
    return await service.info(db, config, now)


@router.get("/days")
async def get_days(
    month: str = Query(pattern=MONTH_PATTERN),
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: TableReservationsConfig = Depends(get_config),
) -> DaysOut:
    """The hours of every day of a month (YYYY-MM) and which days can be reserved."""
    return await service.public_days(db, month, config, now)


@router.get("/availability")
async def get_availability(
    day: date = Query(),
    party_size: int = Query(ge=1, le=MAX_PARTY_SIZE),
    duration: int | None = Query(default=None, ge=rules.MIN_DURATION, le=rules.MAX_DURATION),
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: TableReservationsConfig = Depends(get_config),
) -> AvailabilityOut:
    """What a party of `party_size` can reserve on a day: every start at which a
    table is free for `duration` minutes (default from the configuration), and the
    time from which the whole pub can be reserved. A hint only - whether a start
    still works is decided when it is reserved."""
    return await service.availability(db, day, party_size, duration or config.default_duration, config, now)


@router.post("/reservations", status_code=201)
async def create_reservation(
    body: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: TableReservationsConfig = Depends(get_config),
    settings: Settings = Depends(get_settings),
) -> ReservationCreated:
    """Reserves a table for the party (the system picks it) or the whole pub. The
    honeypot (`fax`) filled in means a bot: it is told "created" and nothing is
    stored. Otherwise the day, the time, the table (or the whole pub) and the limit
    per e-mail address are checked under the lock and the reservation is saved in one
    transaction; then the e-mails go out."""
    if body.fax.strip():
        logger.info("Reservation refused: the honeypot field was filled in")
        return ReservationCreated(cancel_token=new_token(), kind=body.kind, day=body.day, start_time=body.start_time, end_time=body.start_time)
    await service.maybe_purge(db, now.date(), config)
    reservation = await service.create_reservation(db, body, config=config, now=now)
    await db.commit()
    await service.send_new_reservation_mails(db, reservation, config, settings)
    return ReservationCreated(
        cancel_token=reservation.cancel_token,
        kind=reservation.kind,
        day=reservation.day,
        start_time=reservation.start_time,
        end_time=reservation.end_time,
    )


@router.get("/reservations/{cancel_token}")
async def get_reservation(cancel_token: str, db: AsyncSession = Depends(get_db)) -> ReservationPublic:
    reservation = await service.get_by_token(db, cancel_token)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return service.public_reservation(reservation)


@router.post("/reservations/{cancel_token}/cancel")
async def cancel_reservation(
    cancel_token: str,
    db: AsyncSession = Depends(get_db),
    config: TableReservationsConfig = Depends(get_config),
    settings: Settings = Depends(get_settings),
) -> ReservationPublic:
    """Cancels the reservation by its token (a POST - a link in an e-mail that a
    bot opens must not cancel anything). Pressing it again changes nothing."""
    reservation, cancelled_now = await service.cancel_by_guest(db, cancel_token)
    await db.commit()
    if cancelled_now:
        await service.send_guest_cancellation_mail(reservation, config, settings)
    return service.public_reservation(reservation)


# --- Administrators ---------------------------------------------------------------------


@admin_router.get("/reservations")
async def manage_list(
    date_from: date,
    date_to: date,
    status: str | None = Query(default=None, pattern=f"^({STATUS_CONFIRMED}|{STATUS_CANCELLED})$"),
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: TableReservationsConfig = Depends(get_config),
) -> list[ReservationAdmin]:
    """The reservations of a range of days (at most 62), by day and start; with
    `status` only confirmed or only cancelled ones."""
    if date_to < date_from or (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail={"errors": {"date_to": "bad_range"}})
    await service.maybe_purge(db, now.date(), config)
    return await service.list_reservations(db, date_from=date_from, date_to=date_to, status=status)


@admin_router.post("/purge")
async def manage_purge(
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: TableReservationsConfig = Depends(get_config),
) -> PurgeOut:
    """Deletes the reservations older than the retention (with the personal data in them) now."""
    deleted = await service.purge_expired(db, now.date(), config.retention_months)
    await db.commit()
    return PurgeOut(deleted_reservations=deleted)


@admin_router.get("/reservations/{reservation_id}")
async def manage_get(reservation_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ReservationAdmin:
    reservation = await db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return await service.reservation_detail(db, reservation)


@admin_router.post("/reservations/{reservation_id}/cancel")
async def manage_cancel(
    reservation_id: uuid.UUID,
    body: CancelBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    config: TableReservationsConfig = Depends(get_config),
    settings: Settings = Depends(get_settings),
) -> CancelOut:
    """The pub cancels a reservation (freeing its table) and keeps its message. With
    `notify` the guest gets an e-mail that the reservation is cancelled, with the
    message; whether that worked is `email_sent` - the cancellation stands either way.
    Cancelling one that is already cancelled changes and sends nothing."""
    reservation, cancelled_now = await service.cancel_by_admin(db, reservation_id, body, admin=admin)
    await db.commit()
    email_sent = None
    if cancelled_now and body.notify:
        email_sent = await service.send_admin_cancellation_mail(db, reservation, config, settings)
        await db.commit()
    return CancelOut(reservation=await service.reservation_detail(db, reservation), email_sent=email_sent)


@admin_router.get("/opening-hours")
async def manage_get_hours(db: AsyncSession = Depends(get_db)) -> list[WeekdayHours]:
    """The regular hours of all seven weekdays (Monday = 0)."""
    return await service.weekly_hours_out(db)


@admin_router.put("/opening-hours")
async def manage_put_hours(
    body: HoursUpdate,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
) -> list[WeekdayHours]:
    """Sets the regular hours of the whole week. 409 (listing the reservations) while
    an upcoming reservation would fall outside them - the pub cancels those first."""
    result = await service.replace_weekly_hours(db, body, now)
    await db.commit()
    return result


@admin_router.get("/exceptions")
async def manage_list_exceptions(
    date_from: date | None = None,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
) -> list[ExceptionOut]:
    """The one-off changes of a day from `date_from` (default today) on."""
    return await service.list_exceptions(db, date_from or now.date())


@admin_router.put("/exceptions/{day}")
async def manage_put_exception(
    day: date,
    body: ExceptionIn,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ExceptionOut:
    """Closes a date (with a reason shown to visitors) or sets other hours for it. 409
    (listing the reservations) while a reservation of that day would not fit - the pub
    cancels each of them first."""
    result = await service.put_exception(db, day, body, now)
    await db.commit()
    return result


@admin_router.delete("/exceptions/{day}", status_code=204)
async def manage_delete_exception(day: date, db: AsyncSession = Depends(get_db), now: datetime = Depends(get_now)) -> None:
    """Removes a date's one-off change, so the regular hours of that weekday apply again."""
    await service.delete_exception(db, day, now)
    await db.commit()


@admin_router.get("/tables")
async def manage_list_tables(db: AsyncSession = Depends(get_db), now: datetime = Depends(get_now)) -> list[TableOut]:
    return await service.list_tables_out(db, now)


@admin_router.post("/tables", status_code=201)
async def manage_create_table(body: TableIn, db: AsyncSession = Depends(get_db), now: datetime = Depends(get_now)) -> TableOut:
    table = await service.create_table(db, body)
    await db.commit()
    return await service.table_out(db, table, now)


@admin_router.patch("/tables/{table_id}")
async def manage_update_table(
    table_id: uuid.UUID, body: TablePatch, db: AsyncSession = Depends(get_db), now: datetime = Depends(get_now)
) -> TableOut:
    """Changes a table. 409 (listing the reservations) when taking it out of use, or
    seating fewer people, would leave an upcoming reservation without a fitting table."""
    table = await service.update_table(db, table_id, body, now)
    await db.commit()
    return await service.table_out(db, table, now)


@admin_router.delete("/tables/{table_id}", status_code=204)
async def manage_delete_table(table_id: uuid.UUID, db: AsyncSession = Depends(get_db), now: datetime = Depends(get_now)) -> None:
    """Deletes a table with no reservation at all; one with any (cancelled and past ones
    too) answers 409 - take it out of use instead."""
    await service.delete_table(db, table_id, now)
    await db.commit()


router.include_router(admin_router)
