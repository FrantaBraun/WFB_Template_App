# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pages.schemas import PageOut
from app.database import get_db
from app.models.page import Page

router = APIRouter()


@router.get("/{slug}", response_model=PageOut)
async def get_page_by_slug(slug: str, db: AsyncSession = Depends(get_db)) -> Page:
    """Public - no auth. Only ever returns a published page; draft/unknown
    slugs 404 identically, so a probing request can't distinguish the two."""
    result = await db.execute(select(Page).where(Page.slug == slug, Page.status == "published"))
    page = result.scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page
