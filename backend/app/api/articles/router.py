# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
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
