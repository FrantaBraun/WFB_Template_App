# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.models.page import Page

router = APIRouter()


class MentionableItem(BaseModel):
    type: Literal["page", "article"]
    id: str
    label: str
    slug: str


@router.get("/", response_model=list[MentionableItem])
async def list_mentionable(db: AsyncSession = Depends(get_db)) -> list[MentionableItem]:
    """Combined Page+Article list backing the WYSIWYG editor's @-mention
    suggestions. All statuses included, including drafts - an admin should
    be able to cross-link two drafts being written together. That's exactly
    why this lives under /api/admin rather than being public: a public
    version would leak unpublished titles/slugs even though the draft's own
    detail route 404s for them."""
    pages_result = await db.execute(select(Page.id, Page.heading, Page.slug))
    articles_result = await db.execute(select(Article.id, Article.title, Article.slug))

    items = [
        MentionableItem(type="page", id=str(row.id), label=row.heading, slug=row.slug)
        for row in pages_result
    ]
    items += [
        MentionableItem(type="article", id=str(row.id), label=row.title, slug=row.slug)
        for row in articles_result
    ]
    return items
