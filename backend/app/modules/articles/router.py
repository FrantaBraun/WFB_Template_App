# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Public article endpoints plus the administrators' /manage endpoints.

Administrators are this application's own - the local User.is_admin flag
(app.api.deps.require_admin), never the JWT's role_name: that role belongs
to the user across every application on the shared auth service, so it
can't say who administers this one.

Every fixed path is declared before GET /{slug}: FastAPI matches routes in
declaration order, so /{slug} first would swallow e.g. /search as an
article slug (schemas.RESERVED_SLUGS keeps editors from creating articles
that would collide the other way). The /manage router is included before
it for the same reason.

Who sees what is decided in visibility.py: the listing is `listed`
(published, inside the display window as of today), search and the detail
page are `findable` (also archived), drafts are administrators-only.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.modules.articles import search, uploads, visibility
from app.modules.articles.models import STATUS_ARCHIVED, STATUS_PUBLISHED, Article, ArticleType
from app.modules.articles.schemas import (
    ArticleAdminListItem,
    ArticleAdminOut,
    ArticleAdminPage,
    ArticleCreate,
    ArticleOut,
    ArticlePage,
    ArticleTeaser,
    ArticleTypeAdminOut,
    ArticleTypeCreate,
    ArticleTypeOut,
    ArticleTypeUpdate,
    ArticleUpdate,
    Status,
)
from app.services.sanitize import sanitize_html

router = APIRouter()
admin_router = APIRouter(prefix="/manage", dependencies=[Depends(require_admin)])

SEARCH_LIMIT = 30


def _ordered(query):
    return query.order_by(Article.created_at.desc(), Article.id)


# --- Public -------------------------------------------------------------------


@router.get("")
async def list_articles(
    type_id: uuid.UUID | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    q: str | None = Query(default=None, max_length=100),
    include_archived: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> ArticlePage:
    """Newest first. Listed articles only; include_archived adds the archived ones."""
    today = date.today()
    query = select(Article).where(visibility.findable(today) if include_archived else visibility.listed(today))
    if type_id is not None:
        query = query.where(Article.type_id == type_id)
    if created_from is not None:
        query = query.where(func.date(Article.created_at) >= created_from)
    if created_to is not None:
        query = query.where(func.date(Article.created_at) <= created_to)
    if q is not None and q.strip():
        query = query.where(search.matches(q))
    rows = (await db.scalars(_ordered(query).offset(offset).limit(limit + 1))).all()
    return ArticlePage(items=[ArticleTeaser.model_validate(a) for a in rows[:limit]], has_more=len(rows) > limit)


@router.get("/search")
async def search_articles(
    q: str = Query(min_length=1, max_length=100), db: AsyncSession = Depends(get_db)
) -> list[ArticleTeaser]:
    """Title, perex and full content, ignoring case and diacritics; archived articles included."""
    query = select(Article).where(visibility.findable(date.today()), search.matches(q))
    rows = (await db.scalars(_ordered(query).limit(SEARCH_LIMIT))).all()
    return [ArticleTeaser.model_validate(a) for a in rows]


@router.get("/types")
async def list_types(db: AsyncSession = Depends(get_db)) -> list[ArticleTypeOut]:
    """Public: the frontend draws every article in its type's colours."""
    rows = (await db.scalars(select(ArticleType).order_by(ArticleType.name))).all()
    return [ArticleTypeOut.model_validate(t) for t in rows]


@router.get("/uploads/{filename}")
async def get_upload(filename: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    media_type = uploads.media_type_for(filename)
    if media_type is None:
        raise HTTPException(status_code=404, detail="Not found")
    path = uploads.uploads_dir(settings) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


# --- Administrators -----------------------------------------------------------
# Declared on admin_router and included below, ahead of GET /{slug}.


@admin_router.get("")
async def manage_list(
    status: Status | None = None,
    q: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ArticleAdminPage:
    """Every article in every status, drafts included."""
    query = select(Article)
    if status is not None:
        query = query.where(Article.status == status)
    if q is not None and q.strip():
        query = query.where(search.matches(q))
    rows = (await db.scalars(_ordered(query).offset(offset).limit(limit + 1))).all()
    return ArticleAdminPage(
        items=[ArticleAdminListItem.model_validate(a) for a in rows[:limit]], has_more=len(rows) > limit
    )


@admin_router.post("", status_code=201)
async def manage_create(body: ArticleCreate, db: AsyncSession = Depends(get_db)) -> ArticleAdminOut:
    await _require_type(db, body.type_id)
    values = body.model_dump()
    values["content"] = sanitize_html(values["content"])
    article = Article(**values, search_text=search.build_search_text(values["title"], values["perex"], values["content"]))
    db.add(article)
    await _commit_or_409(db, "slug already in use")
    await db.refresh(article)
    return ArticleAdminOut.model_validate(article)


@admin_router.post("/uploads")
async def manage_upload(file: UploadFile, settings: Settings = Depends(get_settings)) -> dict:
    """Thumbnails and in-text images."""
    filename = await uploads.save_image(file, settings)
    return {"url": f"{settings.app_base_url.rstrip('/')}/api/modules/articles/uploads/{filename}"}


@admin_router.get("/types")
async def manage_list_types(db: AsyncSession = Depends(get_db)) -> list[ArticleTypeAdminOut]:
    counts = dict(
        (await db.execute(select(Article.type_id, func.count()).where(Article.type_id.is_not(None)).group_by(Article.type_id))).all()
    )
    rows = (await db.scalars(select(ArticleType).order_by(ArticleType.name))).all()
    return [
        ArticleTypeAdminOut(**ArticleTypeOut.model_validate(t).model_dump(), article_count=counts.get(t.id, 0))
        for t in rows
    ]


@admin_router.post("/types", status_code=201)
async def manage_create_type(body: ArticleTypeCreate, db: AsyncSession = Depends(get_db)) -> ArticleTypeOut:
    article_type = ArticleType(**body.model_dump())
    db.add(article_type)
    await _commit_or_409(db, "a type with this name already exists")
    await db.refresh(article_type)
    return ArticleTypeOut.model_validate(article_type)


@admin_router.patch("/types/{type_id}")
async def manage_update_type(
    type_id: uuid.UUID, body: ArticleTypeUpdate, db: AsyncSession = Depends(get_db)
) -> ArticleTypeOut:
    article_type = await db.get(ArticleType, type_id)
    if article_type is None:
        raise HTTPException(status_code=404, detail="Type not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(article_type, field, value)
    await _commit_or_409(db, "a type with this name already exists")
    await db.refresh(article_type)
    return ArticleTypeOut.model_validate(article_type)


@admin_router.delete("/types/{type_id}", status_code=204)
async def manage_delete_type(
    type_id: uuid.UUID, replace_with: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)
) -> None:
    """A type in use can't just disappear from its articles: 409 unless
    `replace_with` names another type to move them to first."""
    article_type = await db.get(ArticleType, type_id)
    if article_type is None:
        raise HTTPException(status_code=404, detail="Type not found")
    in_use = await db.scalar(select(func.count()).select_from(Article).where(Article.type_id == type_id))
    if in_use:
        if replace_with is None:
            raise HTTPException(status_code=409, detail=f"type is used by {in_use} article(s); pass replace_with")
        if replace_with == type_id:
            raise HTTPException(status_code=422, detail="replace_with must be a different type")
        await _require_type(db, replace_with)
        await db.execute(update(Article).where(Article.type_id == type_id).values(type_id=replace_with))
    await db.delete(article_type)
    await db.commit()


@admin_router.get("/{article_id}")
async def manage_get(article_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ArticleAdminOut:
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleAdminOut.model_validate(article)


@admin_router.patch("/{article_id}")
async def manage_update(
    article_id: uuid.UUID, body: ArticleUpdate, db: AsyncSession = Depends(get_db)
) -> ArticleAdminOut:
    """status="archived" is how an article is taken down; there is no DELETE."""
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    updates = body.model_dump(exclude_unset=True)
    for field in ("title", "slug", "perex", "content", "status", "pinned"):
        if field in updates and updates[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    if updates.get("type_id") is not None:
        await _require_type(db, updates["type_id"])
    if "content" in updates:
        updates["content"] = sanitize_html(updates["content"])
    for field, value in updates.items():
        setattr(article, field, value)
    if article.display_from and article.display_to and article.display_from > article.display_to:
        await db.rollback()
        raise HTTPException(status_code=422, detail="display_from must not be after display_to")
    article.search_text = search.build_search_text(article.title, article.perex, article.content)

    await _commit_or_409(db, "slug already in use")
    await db.refresh(article)
    return ArticleAdminOut.model_validate(article)


router.include_router(admin_router)


# --- Detail (must stay last, see the module docstring) ---------------------------


@router.get("/{slug}")
async def get_article(slug: str, db: AsyncSession = Depends(get_db)) -> ArticleOut:
    """Listed or archived articles. The detail page deliberately skips the
    display window of a published one: the window governs what is listed,
    not whether a link someone already has keeps working - but a draft is
    404 here (administrators preview through /manage)."""
    article = (await db.scalars(select(Article).where(Article.slug == slug))).first()
    if article is None or not _publicly_readable(article):
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleOut.model_validate(article)


def _publicly_readable(article: Article) -> bool:
    return article.status in (STATUS_PUBLISHED, STATUS_ARCHIVED)


async def _require_type(db: AsyncSession, type_id: uuid.UUID | None) -> None:
    if type_id is not None and await db.get(ArticleType, type_id) is None:
        raise HTTPException(status_code=422, detail="unknown type_id")


async def _commit_or_409(db: AsyncSession, detail: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc
