# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.articles.schemas import ArticleCreate, ArticleOut, ArticleUpdate
from app.database import get_db
from app.models.article import Article
from app.services.sanitize import sanitize_html

router = APIRouter()


@router.get("/", response_model=list[ArticleOut])
async def list_articles(db: AsyncSession = Depends(get_db)) -> list[Article]:
    """All statuses, including deleted - this is how an admin finds a
    soft-deleted or draft article to keep editing."""
    result = await db.execute(select(Article).order_by(Article.updated_at.desc()))
    return list(result.scalars().all())


@router.post("/", response_model=ArticleOut, status_code=201)
async def create_article(body: ArticleCreate, db: AsyncSession = Depends(get_db)) -> Article:
    article = Article(**{**body.model_dump(), "full_text": sanitize_html(body.full_text)})
    db.add(article)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="slug already in use") from exc
    await db.refresh(article)
    return article


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Article:
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.patch("/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: uuid.UUID, body: ArticleUpdate, db: AsyncSession = Depends(get_db)
) -> Article:
    """Keyed by id, not slug - same rationale as admin/pages.py. Setting
    status="deleted" here is this app's soft-delete mechanism; there's no
    separate hard-DELETE route."""
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    updates = body.model_dump(exclude_unset=True)
    if "full_text" in updates:
        updates["full_text"] = sanitize_html(updates["full_text"])
    for field, value in updates.items():
        setattr(article, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="slug already in use") from exc
    await db.refresh(article)
    return article
