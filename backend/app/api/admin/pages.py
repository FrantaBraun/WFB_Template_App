# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pages.schemas import PageCreate, PageOut, PageUpdate
from app.database import get_db
from app.models.page import Page
from app.services.sanitize import sanitize_html

router = APIRouter()


@router.get("/", response_model=list[PageOut])
async def list_pages(db: AsyncSession = Depends(get_db)) -> list[Page]:
    """All statuses - unlike the public router, the admin list is how an
    admin finds a draft to keep editing."""
    result = await db.execute(select(Page).order_by(Page.updated_at.desc()))
    return list(result.scalars().all())


@router.post("/", response_model=PageOut, status_code=201)
async def create_page(body: PageCreate, db: AsyncSession = Depends(get_db)) -> Page:
    page = Page(**{**body.model_dump(), "content": sanitize_html(body.content)})
    db.add(page)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="slug already in use") from exc
    await db.refresh(page)
    return page


@router.get("/{page_id}", response_model=PageOut)
async def get_page(page_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Page:
    page = await db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.patch("/{page_id}", response_model=PageOut)
async def update_page(page_id: uuid.UUID, body: PageUpdate, db: AsyncSession = Depends(get_db)) -> Page:
    """Keyed by id, not slug - an admin changing a page's own slug mid-edit
    shouldn't break the edit session itself."""
    page = await db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    updates = body.model_dump(exclude_unset=True)
    if "content" in updates:
        updates["content"] = sanitize_html(updates["content"])
    for field, value in updates.items():
        setattr(page, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="slug already in use") from exc
    await db.refresh(page)
    return page
