# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Public event endpoints plus the editors' /manage endpoints.

Every fixed path is declared before GET /{slug}: FastAPI matches routes in
declaration order, so /{slug} first would swallow e.g. /archive as an
event slug (schemas.RESERVED_SLUGS keeps editors from creating events that
would collide the other way).

"Visible" everywhere below means published and inside the display window
*as of today* - browsing a past or future month never bypasses an embargo
(display_from) or expiry (display_to). The detail page deliberately skips
the window: it governs what is listed, not whether a link someone already
has keeps working.
"""

import calendar as calendar_module
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR, Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.event_calendar.config import EventCalendarConfig, get_config
from app.modules.event_calendar.models import STATUS_PUBLISHED, Event
from app.modules.event_calendar.permissions import current_user_and_claims, is_editor, require_editor
from app.modules.event_calendar.schemas import (
    ArchiveMonth,
    ArchiveYear,
    DashboardOut,
    EditorStatus,
    EventAdminOut,
    EventCreate,
    EventOut,
    EventPage,
    EventTeaser,
    EventUpdate,
)
from app.services.sanitize import sanitize_html

router = APIRouter()

# Image types accepted for upload, by declared Content-Type, with the magic
# bytes the file must actually start with - files are served back with the
# Content-Type derived from this same mapping, never from the client.
_IMAGE_TYPES = {
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/webp": (".webp", (b"RIFF",)),
    "image/gif": (".gif", (b"GIF87a", b"GIF89a")),
}
_MEDIA_TYPES = {ext: content_type for content_type, (ext, _) in _IMAGE_TYPES.items()}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_UPLOAD_NAME_LEN = 32  # uuid4().hex


def _visible(today: date):
    return and_(
        Event.status == STATUS_PUBLISHED,
        or_(Event.display_from.is_(None), Event.display_from <= today),
        or_(Event.display_to.is_(None), Event.display_to >= today),
    )


def _uploads_dir(settings: Settings) -> Path:
    base = Path(settings.uploads_dir)
    if not base.is_absolute():
        base = BASE_DIR / base
    return base / "event_calendar"


# --- Public -------------------------------------------------------------------


@router.get("")
async def list_upcoming(
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    config: EventCalendarConfig = Depends(get_config),
) -> EventPage:
    """The next `page_size` visible events from today on, soonest first;
    the "Load more" button asks for the next page via offset."""
    today = date.today()
    rows = (
        await db.scalars(
            select(Event)
            .where(_visible(today), Event.event_date >= today)
            .order_by(Event.event_date.asc(), Event.title.asc())
            .offset(offset)
            .limit(config.page_size + 1)
        )
    ).all()
    return EventPage(
        items=[EventTeaser.model_validate(e) for e in rows[: config.page_size]],
        has_more=len(rows) > config.page_size,
    )


@router.get("/archive")
async def get_archive(db: AsyncSession = Depends(get_db)) -> list[ArchiveYear]:
    """Year -> month tree of every month that has at least one visible
    event (past or future), newest year first, months in calendar order."""
    year_col = extract("year", Event.event_date)
    month_col = extract("month", Event.event_date)
    rows = (
        await db.execute(
            select(year_col, month_col, func.count())
            .where(_visible(date.today()))
            .group_by(year_col, month_col)
            .order_by(year_col.desc(), month_col.asc())
        )
    ).all()
    years: dict[int, list[ArchiveMonth]] = {}
    for year, month, count in rows:
        years.setdefault(int(year), []).append(ArchiveMonth(month=int(month), count=count))
    return [ArchiveYear(year=year, months=months) for year, months in years.items()]


@router.get("/month")
async def get_month(
    year: int = Query(ge=1, le=9999),
    month: int = Query(ge=1, le=12),
    db: AsyncSession = Depends(get_db),
) -> list[EventTeaser]:
    """Every visible event in one month - backs both the calendar widget
    and the month listing (unpaginated: a month can have more than 10)."""
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar_module.monthrange(year, month)[1])
    rows = (
        await db.scalars(
            select(Event)
            .where(_visible(date.today()), Event.event_date >= first_day, Event.event_date <= last_day)
            .order_by(Event.event_date.asc(), Event.title.asc())
        )
    ).all()
    return [EventTeaser.model_validate(e) for e in rows]


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardOut:
    """For an application's home page: the soonest upcoming visible event,
    the other pinned ones, and the five latest past unpinned ones. The
    soonest event is excluded from `pinned` so it never renders twice."""
    today = date.today()
    upcoming = (
        await db.scalars(
            select(Event)
            .where(_visible(today), Event.event_date >= today)
            .order_by(Event.event_date.asc())
            .limit(1)
        )
    ).first()

    pinned_query = select(Event).where(_visible(today), Event.pinned.is_(True))
    if upcoming is not None:
        pinned_query = pinned_query.where(Event.id != upcoming.id)
    pinned = (await db.scalars(pinned_query.order_by(Event.event_date.desc()))).all()

    recent_past = (
        await db.scalars(
            select(Event)
            .where(_visible(today), Event.pinned.is_(False), Event.event_date < today)
            .order_by(Event.event_date.desc())
            .limit(5)
        )
    ).all()

    return DashboardOut(
        upcoming=EventTeaser.model_validate(upcoming) if upcoming else None,
        pinned=[EventTeaser.model_validate(e) for e in pinned],
        recent_past=[EventTeaser.model_validate(e) for e in recent_past],
    )


@router.get("/search")
async def search_events(q: str = Query(min_length=1, max_length=100), db: AsyncSession = Depends(get_db)) -> list[EventTeaser]:
    """Published events (any display window, like the detail page) whose
    title or short description matches, or whose date matches as typed in
    either DD.MM.YYYY or YYYY-MM-DD (so "5.9" or "2026-09" work)."""
    pattern = f"%{q}%"
    rows = (
        await db.scalars(
            select(Event)
            .where(
                Event.status == STATUS_PUBLISHED,
                or_(
                    Event.title.ilike(pattern),
                    Event.short_description.ilike(pattern),
                    func.to_char(Event.event_date, "DD.MM.YYYY").ilike(pattern),
                    func.to_char(Event.event_date, "YYYY-MM-DD").ilike(pattern),
                ),
            )
            .order_by(Event.event_date.desc())
            .limit(20)
        )
    ).all()
    return [EventTeaser.model_validate(e) for e in rows]


@router.get("/uploads/{filename}")
async def get_upload(filename: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    stem, _, ext = filename.partition(".")
    media_type = _MEDIA_TYPES.get(f".{ext}")
    if media_type is None or len(stem) != _UPLOAD_NAME_LEN or not all(c in "0123456789abcdef" for c in stem):
        raise HTTPException(status_code=404, detail="Not found")
    path = _uploads_dir(settings) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


# --- Editors ------------------------------------------------------------------


@router.get("/manage/me")
async def get_editor_status(auth: tuple[User, dict] = Depends(current_user_and_claims)) -> EditorStatus:
    """Lets the frontend decide whether to show the management links."""
    user, claims = auth
    return EditorStatus(is_editor=await is_editor(user, claims))


@router.get("/manage", dependencies=[Depends(require_editor)])
async def manage_list(db: AsyncSession = Depends(get_db)) -> list[EventAdminOut]:
    """Every event in every status, including drafts and soft-deleted ones."""
    rows = (await db.scalars(select(Event).order_by(Event.event_date.desc(), Event.title.asc()))).all()
    return [EventAdminOut.model_validate(e) for e in rows]


@router.post("/manage", status_code=201, dependencies=[Depends(require_editor)])
async def manage_create(body: EventCreate, db: AsyncSession = Depends(get_db)) -> EventAdminOut:
    event = Event(**{**body.model_dump(), "full_text": sanitize_html(body.full_text)})
    db.add(event)
    await _commit_or_409(db)
    await db.refresh(event)
    return EventAdminOut.model_validate(event)


@router.post("/manage/uploads", dependencies=[Depends(require_editor)])
async def manage_upload(file: UploadFile, settings: Settings = Depends(get_settings)) -> dict:
    """Thumbnail and in-text images. Never uses the client's filename (no
    path traversal, no collisions) and checks the bytes match the type."""
    entry = _IMAGE_TYPES.get(file.content_type or "")
    if entry is None:
        raise HTTPException(status_code=415, detail="Unsupported image type")
    ext, signatures = entry
    contents = await file.read(_MAX_IMAGE_BYTES + 1)
    if len(contents) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 5 MB)")
    if not contents.startswith(signatures):
        raise HTTPException(status_code=415, detail="File content does not match its image type")

    directory = _uploads_dir(settings)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (directory / filename).write_bytes(contents)
    return {"url": f"{settings.app_base_url.rstrip('/')}/api/modules/event_calendar/uploads/{filename}"}


@router.get("/manage/{event_id}", dependencies=[Depends(require_editor)])
async def manage_get(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> EventAdminOut:
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventAdminOut.model_validate(event)


@router.patch("/manage/{event_id}", dependencies=[Depends(require_editor)])
async def manage_update(event_id: uuid.UUID, body: EventUpdate, db: AsyncSession = Depends(get_db)) -> EventAdminOut:
    """status="deleted" is the soft delete; there is no DELETE route."""
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = body.model_dump(exclude_unset=True)
    for field in ("title", "slug", "event_date", "status", "pinned", "short_description", "full_text"):
        if field in updates and updates[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    if "full_text" in updates:
        updates["full_text"] = sanitize_html(updates["full_text"])
    for field, value in updates.items():
        setattr(event, field, value)
    if event.display_from and event.display_to and event.display_from > event.display_to:
        await db.rollback()
        raise HTTPException(status_code=422, detail="display_from must not be after display_to")

    await _commit_or_409(db)
    await db.refresh(event)
    return EventAdminOut.model_validate(event)


@router.get("/{slug}")
async def get_event(slug: str, db: AsyncSession = Depends(get_db)) -> EventOut:
    event = (
        await db.scalars(select(Event).where(Event.slug == slug, Event.status == STATUS_PUBLISHED))
    ).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventOut.model_validate(event)


async def _commit_or_409(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="slug already in use") from exc
