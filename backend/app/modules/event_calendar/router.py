# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Public calendar endpoints plus the administrators' /manage endpoints.

An event is a term belonging to an article (the articles module), so what
may be seen is decided by the article: app.modules.articles.visibility, never
restated here. Browsing a past or future month never bypasses an article's
display window - it is always judged as of *today*.

- GET "" (the upcoming list) shows `listed` articles' events: it is a listing
  of what is current, like the wall.
- The month calendar, the archive tree, the per-article list and search show
  `findable` ones: an archived article is out of the listings but its dates
  stay in the calendar and in search.

Administrators are this application's own - the local User.is_admin flag
(app.api.deps.require_admin), never the JWT's role_name: that role belongs to
the user across every application on the shared auth service.

Fixed paths are declared before anything with a path parameter, and /manage/me
before /manage/{event_id}, because FastAPI matches routes in declaration order.
"""

import calendar as calendar_module
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, case, cast, extract, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.modules.articles import search, visibility
from app.modules.articles.models import Article
from app.modules.articles.schemas import ArticleTeaser
from app.modules.event_calendar.config import EventCalendarConfig, get_config
from app.modules.event_calendar.models import Event
from app.modules.event_calendar.schemas import (
    ArchiveMonth,
    ArchiveYear,
    DashboardOut,
    DatedArticle,
    EditorStatus,
    EventAdminOut,
    EventCreate,
    EventPage,
    EventTeaser,
    EventUpdate,
    check_term,
)

router = APIRouter()
admin_router = APIRouter(prefix="/manage", dependencies=[Depends(require_admin)])

SEARCH_LIMIT = 30
RECENT_PAST_COUNT = 5

# The last day an event still takes up: its end, or its only day.
_last_day = func.coalesce(Event.end_date, Event.start_date)


def _chronological():
    return (Event.start_date.asc(), Event.start_time.asc().nulls_first(), Event.title.asc(), Event.id)


def _events(*conditions):
    """Events joined with their article, so the article's visibility can be a condition."""
    return select(Event).join(Event.article).where(*conditions)


def _dated_articles(today: date):
    """Articles with the date they are sorted by, as (query, shown date, nearest upcoming event date).

    The date is the start of the nearest event that has not finished
    (`next_date`) - the article is "upcoming" while there is one; once none is
    left, the start of its latest event; for an article with no events at
    all, the day it was created. `date_kind` tells which of those it was.
    The caller adds the visibility condition and ordering."""
    next_events = (
        select(Event.article_id.label("article_id"), func.min(Event.start_date).label("next_date"))
        .where(_last_day >= today)
        .group_by(Event.article_id)
        .subquery()
    )
    last_events = (
        select(Event.article_id.label("article_id"), func.max(Event.start_date).label("last_date"))
        .group_by(Event.article_id)
        .subquery()
    )
    event_date = func.coalesce(next_events.c.next_date, last_events.c.last_date)
    shown_date = func.coalesce(event_date, cast(Article.created_at, Date))
    kind = case((event_date.is_not(None), "event"), else_="created")
    query = (
        select(Article, shown_date.label("shown_date"), kind.label("date_kind"))
        .outerjoin(next_events, next_events.c.article_id == Article.id)
        .outerjoin(last_events, last_events.c.article_id == Article.id)
    )
    return query, shown_date, next_events.c.next_date


def _dated(row) -> DatedArticle:
    article, shown_date, kind = row
    return DatedArticle.model_validate(
        {**ArticleTeaser.model_validate(article).model_dump(), "date": shown_date, "date_kind": kind}
    )


# --- Public -------------------------------------------------------------------


@router.get("")
async def list_upcoming(
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    config: EventCalendarConfig = Depends(get_config),
) -> EventPage:
    """The next `page_size` events that have not finished, soonest first; the
    "Load more" button asks for the next page via offset."""
    today = date.today()
    rows = (
        await db.scalars(
            _events(visibility.listed(today), _last_day >= today)
            .order_by(*_chronological())
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
    """Year -> month tree of every month in which at least one event *starts*
    (past or future), newest year first, months in calendar order."""
    year_col = extract("year", Event.start_date)
    month_col = extract("month", Event.start_date)
    rows = (
        await db.execute(
            select(year_col, month_col, func.count())
            .join(Event.article)
            .where(visibility.findable(date.today()))
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
    """Every event that touches one month - one that starts earlier or ends
    later is included too, so a multi-day event shows on all its days. Backs
    both the calendar widget and the month listing (unpaginated)."""
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar_module.monthrange(year, month)[1])
    rows = (
        await db.scalars(
            _events(visibility.findable(date.today()), Event.start_date <= last_day, _last_day >= first_day).order_by(
                *_chronological()
            )
        )
    ).all()
    return [EventTeaser.model_validate(e) for e in rows]


@router.get("/by-article/{article_id}")
async def get_events_of_article(article_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[EventTeaser]:
    """All dates of one article, in date order - for the article's own page.
    404 unless the article may be seen (listed or archived)."""
    visible = await db.scalar(select(Article.id).where(Article.id == article_id, visibility.findable(date.today())))
    if visible is None:
        raise HTTPException(status_code=404, detail="Article not found")
    rows = (await db.scalars(select(Event).where(Event.article_id == article_id).order_by(*_chronological()))).all()
    return [EventTeaser.model_validate(e) for e in rows]


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardOut:
    """For an application's home page: the article with the nearest upcoming
    event, the other pinned articles, and the five latest past unpinned ones.
    Only `listed` articles - archived ones and drafts never reach the wall.

    An article is *upcoming* while it has an event that has not finished,
    *past* otherwise (see _dated_articles for the date). The upcoming one is
    left out of `pinned` so it never renders twice."""
    today = date.today()
    query, shown_date, next_date = _dated_articles(today)
    listed_query = query.where(visibility.listed(today))

    upcoming_row = (
        await db.execute(
            listed_query.where(next_date.is_not(None)).order_by(next_date.asc(), Article.created_at.desc()).limit(1)
        )
    ).first()

    pinned_query = listed_query.where(Article.pinned.is_(True))
    if upcoming_row is not None:
        pinned_query = pinned_query.where(Article.id != upcoming_row[0].id)
    pinned_rows = (await db.execute(pinned_query.order_by(shown_date.desc(), Article.created_at.desc()))).all()

    past_rows = (
        await db.execute(
            listed_query.where(Article.pinned.is_(False), next_date.is_(None))
            .order_by(shown_date.desc(), Article.created_at.desc())
            .limit(RECENT_PAST_COUNT)
        )
    ).all()

    return DashboardOut(
        upcoming=_dated(upcoming_row) if upcoming_row else None,
        pinned=[_dated(r) for r in pinned_rows],
        recent_past=[_dated(r) for r in past_rows],
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/search")
async def search_events(
    q: str = Query(min_length=1, max_length=100), db: AsyncSession = Depends(get_db)
) -> list[DatedArticle]:
    """Articles to open: those whose title, perex or content match (ignoring
    case and diacritics, every word must appear), or that have an event whose
    title or short description matches, or whose start date matches as typed
    in either DD.MM.YYYY or YYYY-MM-DD (so "5.9" or "2026-09" work). Archived
    articles are found, drafts and out-of-window ones are not."""
    today = date.today()
    date_pattern = f"%{_escape_like(q.strip())}%"
    matching_events = select(Event.article_id).where(
        or_(
            search.matches(q, Event.search_text),
            func.to_char(Event.start_date, "DD.MM.YYYY").ilike(date_pattern, escape="\\"),
            func.to_char(Event.start_date, "YYYY-MM-DD").ilike(date_pattern, escape="\\"),
        )
    )
    query, shown_date, _ = _dated_articles(today)
    rows = (
        await db.execute(
            query.where(visibility.findable(today), or_(search.matches(q), Article.id.in_(matching_events)))
            .order_by(shown_date.desc(), Article.created_at.desc())
            .limit(SEARCH_LIMIT)
        )
    ).all()
    return [_dated(r) for r in rows]


# --- Administrators -----------------------------------------------------------


@router.get("/manage/me")
async def get_editor_status(user: User = Depends(get_current_user)) -> EditorStatus:
    """Lets the frontend decide whether to show the management links."""
    return EditorStatus(is_editor=user.is_admin)


@admin_router.get("")
async def manage_list(article_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)) -> list[EventAdminOut]:
    """Every event of every article, drafts' included; newest date first."""
    query = select(Event)
    if article_id is not None:
        query = query.where(Event.article_id == article_id)
    rows = (
        await db.scalars(query.order_by(Event.start_date.desc(), Event.start_time.desc().nulls_last(), Event.title))
    ).all()
    return [EventAdminOut.model_validate(e) for e in rows]


@admin_router.post("", status_code=201)
async def manage_create(body: EventCreate, db: AsyncSession = Depends(get_db)) -> EventAdminOut:
    await _require_article(db, body.article_id)
    event = Event(**body.model_dump(), search_text=search.normalize_text(f"{body.title} {body.short_description}"))
    db.add(event)
    await _commit_or_409(db, "could not save the event")
    await db.refresh(event)
    return EventAdminOut.model_validate(event)


@admin_router.get("/{event_id}")
async def manage_get(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> EventAdminOut:
    return EventAdminOut.model_validate(await _get_event(db, event_id))


@admin_router.patch("/{event_id}")
async def manage_update(event_id: uuid.UUID, body: EventUpdate, db: AsyncSession = Depends(get_db)) -> EventAdminOut:
    event = await _get_event(db, event_id)
    updates = body.model_dump(exclude_unset=True)
    for field in ("article_id", "title", "short_description", "start_date"):
        if field in updates and updates[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    if updates.get("article_id") is not None:
        await _require_article(db, updates["article_id"])

    # The term is checked as a whole - the request may send only some of its fields.
    term = {f: updates.get(f, getattr(event, f)) for f in ("start_date", "end_date", "start_time", "end_time")}
    try:
        check_term(**term)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    for field, value in updates.items():
        setattr(event, field, value)
    event.search_text = search.normalize_text(f"{event.title} {event.short_description}")
    await _commit_or_409(db, "could not save the event")
    await db.refresh(event)
    return EventAdminOut.model_validate(event)


@admin_router.delete("/{event_id}", status_code=204)
async def manage_delete(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Really deletes the date (the article is untouched). Something built on
    events - a registration, say - may refer to it and refuse: 409."""
    event = await _get_event(db, event_id)
    await db.delete(event)
    await _commit_or_409(db, "the event is in use and cannot be deleted")


router.include_router(admin_router)


async def _get_event(db: AsyncSession, event_id: uuid.UUID) -> Event:
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


async def _require_article(db: AsyncSession, article_id: uuid.UUID) -> None:
    if await db.get(Article, article_id) is None:
        raise HTTPException(status_code=422, detail="unknown article_id")


async def _commit_or_409(db: AsyncSession, detail: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc
