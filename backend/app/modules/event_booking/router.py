# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Registration for events: the public endpoints (offering slots, booking,
cancelling by the link in the e-mail) and the administrators' /manage ones.

What a visitor may know of is decided in service.py (an event's article must
be reachable, a "link" registration needs its token, registering needs the
registration open, the article listed and the event not over). Administrators
are this application's own - the local User.is_admin flag (require_admin),
never the JWT's role_name.

The rules live in service.py, which never commits; the handlers here commit
once the whole change is done and only then send e-mails, which never fail a
request (see mail.py).

Fixed paths are declared before the ones with a parameter where both could
match (FastAPI matches in declaration order).
"""

import logging
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.event_booking import service
from app.modules.event_booking.config import EventBookingConfig, get_config
from app.modules.event_booking.deps import get_now, get_optional_user
from app.modules.event_booking.models import STATUS_CANCELLED, STATUS_CONFIRMED, Booking, new_token
from app.modules.event_booking.schemas import (
    BookingAdminOut,
    BookingCancelBody,
    BookingCreate,
    BookingCreated,
    BookingMutationOut,
    BookingPatch,
    BookingPublic,
    BookingRowPage,
    DaysOut,
    PreviewIn,
    PreviewOut,
    PurgeOut,
    RegistrationAdminOut,
    RegistrationBrief,
    RegistrationCreate,
    RegistrationListItem,
    RegistrationPublic,
    RegistrationUpdate,
    SlotsOut,
)
from app.modules.forms import service as forms_service
from app.modules.forms.schemas import StatsOut

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter(prefix="/manage", dependencies=[Depends(require_admin)])

MAX_EVENT_IDS = 100
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

# `?token=` is the ?r= of the article page: it lets a visitor see a "link" registration.
TokenParam = Query(default=None, max_length=100)


async def _commit_or_409(db: AsyncSession, detail: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail={"errors": {"_form": detail}}) from exc


# --- Public ------------------------------------------------------------------------


@router.get("/by-events")
async def by_events(
    ids: str = Query(min_length=1, max_length=4000),
    token: str | None = TokenParam,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
) -> list[RegistrationBrief]:
    """The registration of each of these events (a comma-separated list of ids)
    that this caller may know of. A "link" registration appears only with its
    token and is otherwise not mentioned at all; `is_open` says whether people
    can register right now (open, article listed, event not over)."""
    try:
        event_ids = [uuid.UUID(part) for part in ids.split(",") if part.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ids must be a comma-separated list of event ids") from exc
    if len(event_ids) > MAX_EVENT_IDS:
        raise HTTPException(status_code=422, detail=f"at most {MAX_EVENT_IDS} ids")
    return await service.briefs_for_events(db, event_ids, token, now=now)


@router.get("/registrations/{registration_id}")
async def get_registration(
    registration_id: uuid.UUID,
    token: str | None = TokenParam,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> RegistrationPublic:
    ctx = await service.public_context(db, registration_id, token, now=now)
    return await service.public_registration(db, ctx, config)


@router.get("/registrations/{registration_id}/days")
async def get_free_days(
    registration_id: uuid.UUID,
    month: str | None = Query(default=None, pattern=MONTH_PATTERN),
    token: str | None = TokenParam,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> DaysOut:
    """The days with a free place (every day on offer, or those of one month, YYYY-MM)."""
    ctx = await service.public_context(db, registration_id, token, now=now)
    if not ctx.can_register:
        return DaysOut(days=[])
    return await service.free_days_out(db, ctx, config, now=now, month=month)


@router.get("/registrations/{registration_id}/slots")
async def get_free_slots(
    registration_id: uuid.UUID,
    day: date = Query(alias="date"),
    token: str | None = TokenParam,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> SlotsOut:
    """The times of one day that still have room, with the places left; a
    whole-day slot has no time."""
    ctx = await service.public_context(db, registration_id, token, now=now)
    if not ctx.can_register:
        return SlotsOut(date=day, slots=[])
    return await service.free_slots_out(db, ctx, config, now=now, day=day)


@router.post("/registrations/{registration_id}/bookings", status_code=201)
async def create_booking(
    registration_id: uuid.UUID,
    body: BookingCreate,
    token: str | None = TokenParam,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
    settings: Settings = Depends(get_settings),
) -> BookingCreated:
    """Books a slot. The honeypot (`fax`) filled in means a bot: it is told
    "created" and nothing is stored. Otherwise access, the slot, its capacity
    (under the registration's lock) and the answers are checked and the booking
    and its answers are saved in one transaction; then the e-mails go out."""
    if body.fax.strip():
        logger.info("Booking refused: the honeypot field was filled in")
        return BookingCreated(cancel_token=new_token(), slot_date=body.slot_date, slot_time=body.slot_time)
    await service.maybe_purge(db, now.date(), config)
    booking = await service.create_booking(db, registration_id, body, user=user, token=token, config=config, now=now)
    await db.commit()
    await service.send_new_booking_mails(db, booking, config, settings)
    return BookingCreated(cancel_token=booking.cancel_token, slot_date=booking.slot_date, slot_time=booking.slot_time)


@router.get("/bookings/{cancel_token}")
async def get_booking(cancel_token: str, db: AsyncSession = Depends(get_db)) -> BookingPublic:
    booking = await service.get_booking_by_token(db, cancel_token)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return await service.public_booking(db, booking)


@router.post("/bookings/{cancel_token}/cancel")
async def cancel_booking(
    cancel_token: str,
    db: AsyncSession = Depends(get_db),
    config: EventBookingConfig = Depends(get_config),
    settings: Settings = Depends(get_settings),
) -> BookingPublic:
    """Cancels the booking by its token (a POST - a link in an e-mail that a
    bot opens must not cancel anything). Pressing it again changes nothing."""
    booking, cancelled_now = await service.cancel_by_visitor(db, cancel_token)
    await db.commit()
    if cancelled_now:
        await service.send_cancellation_mail(db, booking, config, settings)
    return await service.public_booking(db, booking)


# --- Administrators ---------------------------------------------------------------------


@admin_router.get("/registrations")
async def manage_list(event_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)) -> list[RegistrationListItem]:
    """Every registration with its booking counts (those of one event with `event_id`)."""
    return await service.list_registrations(db, event_id)


@admin_router.post("/registrations", status_code=201)
async def manage_create(body: RegistrationCreate, db: AsyncSession = Depends(get_db)) -> RegistrationAdminOut:
    registration = await service.create_registration(db, body)
    await _commit_or_409(db, "has_registration")
    return await service.registration_admin_out(db, registration)


@admin_router.post("/purge")
async def manage_purge(
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> PurgeOut:
    """Deletes the bookings older than the retention (with their answers and history) now."""
    deleted = await service.purge_expired(db, now.date(), retention_months=config.retention_months)
    await db.commit()
    return PurgeOut(deleted_bookings=deleted)


@admin_router.post("/preview-slots")
async def manage_preview_slots(
    body: PreviewIn,
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> PreviewOut:
    """What the blocks in the editor would offer (the first slots and how many
    there are in all), or why they are not acceptable - nothing is saved. The
    editor calls this as the blocks change; the slots are computed by the same
    function that serves the visitors."""
    return service.preview_slots(body.blocks, body.capacity, config, now)


async def _admin_registration(db: AsyncSession, registration_id: uuid.UUID):
    registration = await service.get_registration(db, registration_id)
    if registration is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return registration


@admin_router.get("/registrations/{registration_id}")
async def manage_get(registration_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> RegistrationAdminOut:
    return await service.registration_admin_out(db, await _admin_registration(db, registration_id))


@admin_router.patch("/registrations/{registration_id}")
async def manage_update(registration_id: uuid.UUID, body: RegistrationUpdate, db: AsyncSession = Depends(get_db)) -> RegistrationAdminOut:
    registration = await service.update_registration(db, registration_id, body)
    await db.commit()
    return await service.registration_admin_out(db, registration)


@admin_router.delete("/registrations/{registration_id}", status_code=204)
async def manage_delete(registration_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """409 while the registration has bookings (cancelled ones too, until retention removes them)."""
    await service.delete_registration(db, registration_id)
    await _commit_or_409(db, "in_use")


@admin_router.post("/registrations/{registration_id}/regenerate-link")
async def manage_regenerate_link(registration_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> RegistrationAdminOut:
    """A new link token; the old link stops working."""
    registration = await service.regenerate_link(db, registration_id)
    await db.commit()
    return await service.registration_admin_out(db, registration)


async def _including(db: AsyncSession, registration_id: uuid.UUID, booking_id: uuid.UUID | None) -> Booking | None:
    """The booking an administrator is moving (it must be one of this registration's), if any."""
    if booking_id is None:
        return None
    booking = await db.get(Booking, booking_id)
    if booking is None or booking.registration_id != registration_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@admin_router.get("/registrations/{registration_id}/days")
async def manage_free_days(
    registration_id: uuid.UUID,
    month: str | None = Query(default=None, pattern=MONTH_PATTERN),
    booking_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> DaysOut:
    """The days an administrator can move a booking to: free ones, and with
    `booking_id` the booking's own day too. Not limited by the registration
    being open - only by the same rules of what is on offer."""
    ctx = await service.load_context(db, registration_id, now=now)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    include = await _including(db, registration_id, booking_id)
    return await service.free_days_out(db, ctx, config, now=now, month=month, include=include)


@admin_router.get("/registrations/{registration_id}/slots")
async def manage_free_slots(
    registration_id: uuid.UUID,
    day: date = Query(alias="date"),
    booking_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> SlotsOut:
    ctx = await service.load_context(db, registration_id, now=now)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    include = await _including(db, registration_id, booking_id)
    return await service.free_slots_out(db, ctx, config, now=now, day=day, include=include)


@admin_router.get("/registrations/{registration_id}/bookings")
async def manage_bookings(
    registration_id: uuid.UUID,
    status: str | None = Query(default=None, pattern=f"^({STATUS_CONFIRMED}|{STATUS_CANCELLED})$"),
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=100),
    sort: str = Query(default="asc", pattern="^(asc|desc)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
) -> BookingRowPage:
    """The registration's bookings, by their slot; filter by status, slot date
    range and text in the name or e-mail."""
    await _admin_registration(db, registration_id)
    await service.maybe_purge(db, now.date(), config)
    return await service.list_bookings(
        db, registration_id, status=status, date_from=date_from, date_to=date_to, q=q, descending=sort == "desc", offset=offset, limit=limit
    )


@admin_router.get("/registrations/{registration_id}/bookings.csv")
async def manage_bookings_csv(
    registration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    config: EventBookingConfig = Depends(get_config),
) -> Response:
    """Every booking as CSV (UTF-8 with a BOM, ';' separated, formula-safe cells)."""
    registration = await _admin_registration(db, registration_id)
    content = await service.bookings_csv(db, registration, config)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="bookings-{str(registration_id)[:8]}.csv"',
            "Cache-Control": "no-store",
        },
    )


@admin_router.get("/registrations/{registration_id}/answers/stats")
async def manage_answers_stats(registration_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StatsOut:
    """The summary of the answers of the CONFIRMED bookings (a cancelled one is not counted)."""
    registration = await _admin_registration(db, registration_id)
    ids = await service.confirmed_submission_ids(db, registration_id)
    return StatsOut(**await forms_service.compute_stats(db, registration.form_id, submission_ids=ids))


async def _admin_booking(db: AsyncSession, booking_id: uuid.UUID) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@admin_router.get("/bookings/{booking_id}")
async def manage_get_booking(booking_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BookingAdminOut:
    """Everything about a booking: its fields, the answers (a snapshot) and the history of changes."""
    return await service.booking_detail(db, await _admin_booking(db, booking_id))


@admin_router.patch("/bookings/{booking_id}")
async def manage_update_booking(
    booking_id: uuid.UUID,
    body: BookingPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    config: EventBookingConfig = Depends(get_config),
    settings: Settings = Depends(get_settings),
) -> BookingMutationOut:
    """Changes a booking's slot, name, e-mail and / or answers. A new slot must
    be on offer and free (the capacity is not overridden: 409 when full, 422
    when there is no such slot); nothing actually changing is a 422. With
    `notify` the person is told by e-mail, with the `note`; whether that worked
    is `email_sent` - the change stands either way."""
    booking, change, old_slot = await service.update_booking(db, booking_id, body, admin=admin, config=config, now=now)
    await db.commit()
    email_sent = None
    if body.notify:
        email_sent = await service.send_admin_action_mail(db, booking, change, old_slot, config, settings)
        await db.commit()
    return BookingMutationOut(booking=await service.booking_detail(db, booking), email_sent=email_sent)


@admin_router.post("/bookings/{booking_id}/cancel")
async def manage_cancel_booking(
    booking_id: uuid.UUID,
    body: BookingCancelBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    config: EventBookingConfig = Depends(get_config),
    settings: Settings = Depends(get_settings),
) -> BookingMutationOut:
    """Cancels a booking (freeing its place) and records it with the note.
    Cancelling one that is already cancelled changes and sends nothing."""
    booking, change = await service.cancel_by_admin(db, booking_id, body, admin=admin)
    await db.commit()
    email_sent = None
    if change is not None and body.notify:
        email_sent = await service.send_admin_action_mail(db, booking, change, (booking.slot_date, booking.slot_time), config, settings)
        await db.commit()
    return BookingMutationOut(booking=await service.booking_detail(db, booking), email_sent=email_sent)


router.include_router(admin_router)
