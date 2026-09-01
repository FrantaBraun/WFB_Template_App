# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import calendar as calendar_module
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.articles.schemas import ArticleOut, ArticleTeaser, DashboardOut
from app.database import get_db
from app.models.article import Article

router = APIRouter()


def _within_display_window(today: date):
    """display_from/display_to are open-ended (no bound) when null."""
    return and_(
        or_(Article.display_from.is_(None), Article.display_from <= today),
        or_(Article.display_to.is_(None), Article.display_to >= today),
    )


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardOut:
    """Declared before GET /{slug} deliberately - FastAPI matches routes in
    declaration order, so {slug} declared first would swallow this path as
    slug="dashboard".

    The display window is applied to `upcoming` too, not just pinned/recent -
    display_from reads as an admin-controlled embargo, and skipping it only
    for the single most prominent slot on the page would make the hero
    position the one place that silently bypasses it."""
    today = date.today()

    upcoming_result = await db.execute(
        select(Article)
        .where(
            Article.status == "published",
            Article.event_date >= today,
            _within_display_window(today),
        )
        .order_by(Article.event_date.asc())
        .limit(1)
    )
    upcoming = upcoming_result.scalar_one_or_none()

    pinned_query = select(Article).where(
        Article.status == "published",
        Article.pinned.is_(True),
        _within_display_window(today),
    )
    if upcoming is not None:
        # An admin pinning their own soonest-upcoming event is the natural
        # thing to do - exclude it here so it doesn't render twice: once as
        # the hero, once again at the top of the pinned list.
        pinned_query = pinned_query.where(Article.id != upcoming.id)
    pinned_result = await db.execute(pinned_query.order_by(Article.event_date.desc()))
    pinned = list(pinned_result.scalars().all())

    recent_past_result = await db.execute(
        select(Article)
        .where(
            Article.status == "published",
            Article.pinned.is_(False),
            Article.event_date < today,
            _within_display_window(today),
        )
        .order_by(Article.event_date.desc())
        .limit(5)
    )
    recent_past = list(recent_past_result.scalars().all())

    return DashboardOut(
        upcoming=ArticleTeaser.model_validate(upcoming) if upcoming else None,
        pinned=[ArticleTeaser.model_validate(a) for a in pinned],
        recent_past=[ArticleTeaser.model_validate(a) for a in recent_past],
    )


@router.get("/calendar", response_model=list[ArticleTeaser])
async def get_calendar(year: int, month: int, db: AsyncSession = Depends(get_db)) -> list[Article]:
    """Declared above /{slug}, same reasoning as /dashboard. Flat list for
    the given month - the frontend groups by day itself. The display window
    is checked against today, not the browsed month - consistent with the
    dashboard, an article isn't shown just because its event date falls in
    the browsed month if its own embargo/expiry doesn't currently allow it
    (browsing a future month doesn't bypass a display_from that hasn't
    arrived yet)."""
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="month must be between 1 and 12")
    today = date.today()
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar_module.monthrange(year, month)[1])

    result = await db.execute(
        select(Article)
        .where(
            Article.status == "published",
            Article.event_date >= first_day,
            Article.event_date <= last_day,
            _within_display_window(today),
        )
        .order_by(Article.event_date.asc())
    )
    return list(result.scalars().all())


@router.get("/search", response_model=list[ArticleTeaser])
async def search_articles(q: str = Query(min_length=1), db: AsyncSession = Depends(get_db)) -> list[Article]:
    """Declared above /{slug}. Published only - matches the detail route's
    own reasoning that once an article is findable, the display window
    shouldn't hide it from an explicit search. Matches title/
    short_description case-insensitively, plus event_date rendered as both
    DD.MM.YYYY and YYYY-MM-DD so a typed date (e.g. "5.9" or "2026-09")
    finds the right articles too."""
    pattern = f"%{q}%"
    date_cz = func.to_char(Article.event_date, "DD.MM.YYYY")
    date_iso = func.to_char(Article.event_date, "YYYY-MM-DD")

    result = await db.execute(
        select(Article)
        .where(
            Article.status == "published",
            or_(
                Article.title.ilike(pattern),
                Article.short_description.ilike(pattern),
                date_cz.ilike(pattern),
                date_iso.ilike(pattern),
            ),
        )
        .order_by(Article.event_date.desc())
        .limit(20)
    )
    return list(result.scalars().all())


@router.get("/{slug}", response_model=ArticleOut)
async def get_article_by_slug(slug: str, db: AsyncSession = Depends(get_db)) -> Article:
    """Public - no auth. Only ever returns a published article; deliberately
    does NOT re-check the display window - that governs what surfaces in
    listings, not whether a direct link works once someone already has it."""
    result = await db.execute(
        select(Article).where(Article.slug == slug, Article.status == "published")
    )
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
