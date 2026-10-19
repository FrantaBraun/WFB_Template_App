# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The portfolio's endpoints.

Two routers, joined into the module's `router`:

- `public_router` - GET /items and GET /items/{slug}, open to everybody and
  showing only `published` items, with every text already resolved for the
  requested language. Nothing but the fields of PublicItem / PublicItemDetail
  leaves through it.
- `admin_router` - everything under /manage. It carries require_admin itself
  (the local User.is_admin flag, never the JWT's role_name: that role
  belongs to the user across every application on the shared auth service),
  so a route added to it later can't forget the gate.

Items are ordered by (sort_order, id) everywhere. sort_order is not unique,
so the writes that depend on the order (appending an item, moving one, a new
slug) first take one transaction-level advisory lock: two editors can't both
append "max + 1", swap a stale pair or claim the same slug at once.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import BigInteger, func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.database import get_db
from app.modules.portfolio import service
from app.modules.portfolio.models import PortfolioItem
from app.modules.portfolio.schemas import (
    AdminItem,
    ItemCreate,
    ItemUpdate,
    MoveRequest,
    PublicItem,
    PublicItemDetail,
    has_slug_shape,
)

public_router = APIRouter()
admin_router = APIRouter(prefix="/manage", dependencies=[Depends(require_admin)])

# Arbitrary but fixed ("portfoli" in ASCII); only has to be this module's own.
_ORDER_LOCK_KEY = 0x706F7274666F6C69

_ORDER = (PortfolioItem.sort_order, PortfolioItem.id)


async def _lock_items(db: AsyncSession) -> None:
    """Held until the transaction ends (commit, rollback or error)."""
    await db.execute(select(func.pg_advisory_xact_lock(literal(_ORDER_LOCK_KEY, BigInteger))))


async def _get_item(db: AsyncSession, item_id: uuid.UUID) -> PortfolioItem:
    item = await db.get(PortfolioItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


async def _commit_or_409(db: AsyncSession) -> None:
    """The unique index is the last word on slugs (the pre-checks cannot see
    a writer that does not hold the lock)."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="slug already in use") from exc


async def _all_items(db: AsyncSession) -> list[PortfolioItem]:
    return list((await db.scalars(select(PortfolioItem).order_by(*_ORDER))).all())


def _public(item: PortfolioItem, language: str) -> dict:
    return {
        "slug": item.slug,
        "title": service.pick(language, item.title_cs, item.title_en),
        "summary": service.pick(language, item.summary_cs, item.summary_en),
        "url": item.url,
        "status": item.status,
        "tags": list(item.tags),
    }


# --- Public -------------------------------------------------------------------


@public_router.get("/items")
async def list_items(
    language: str | None = Query(default=None, max_length=35),
    limit: int | None = Query(default=None, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[PublicItem]:
    """Published items in their display order, without the description."""
    query = select(PortfolioItem).where(PortfolioItem.published.is_(True)).order_by(*_ORDER)
    if limit is not None:
        query = query.limit(limit)
    resolved = service.resolve_language(language)
    return [PublicItem(**_public(item, resolved)) for item in (await db.scalars(query)).all()]


@public_router.get("/items/{slug}")
async def get_item(
    slug: str,
    language: str | None = Query(default=None, max_length=35),
    db: AsyncSession = Depends(get_db),
) -> PublicItemDetail:
    """One published item with its description. An unpublished item and an
    unknown slug answer exactly the same 404."""
    # Nothing that is not shaped like a slug can exist - and a NUL in the path
    # must not reach the database, which cannot store it (a 500, not a 404).
    item = None
    if has_slug_shape(slug):
        item = (
            await db.scalars(
                select(PortfolioItem).where(PortfolioItem.slug == slug, PortfolioItem.published.is_(True))
            )
        ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    resolved = service.resolve_language(language)
    return PublicItemDetail(
        **_public(item, resolved), description=service.pick(resolved, item.description_cs, item.description_en)
    )


# --- Administrators -----------------------------------------------------------


@admin_router.get("/items")
async def manage_list_items(db: AsyncSession = Depends(get_db)) -> list[AdminItem]:
    """Every item, unpublished ones too, with both languages."""
    return [AdminItem.model_validate(item) for item in await _all_items(db)]


@admin_router.post("/items", status_code=201)
async def manage_create_item(body: ItemCreate, db: AsyncSession = Depends(get_db)) -> AdminItem:
    """Without a slug, one is made from the title (-2, -3 ... on a collision);
    a slug that is sent and taken is a 409. Without a sort_order the item goes
    last."""
    data = body.model_dump()
    slug = data.pop("slug")
    sort_order = data.pop("sort_order")

    await _lock_items(db)
    if slug is None:
        slug = await service.unique_slug(db, service.base_slug(body.title_en, body.title_cs))
    elif await service.slug_taken(db, slug):
        raise HTTPException(status_code=409, detail="slug already in use")
    if sort_order is None:
        sort_order = (await db.scalar(select(func.coalesce(func.max(PortfolioItem.sort_order), 0)))) + 1

    item = PortfolioItem(slug=slug, sort_order=sort_order, **data)
    db.add(item)
    await _commit_or_409(db)
    await db.refresh(item)
    return AdminItem.model_validate(item)


@admin_router.get("/items/{item_id}")
async def manage_get_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> AdminItem:
    return AdminItem.model_validate(await _get_item(db, item_id))


@admin_router.patch("/items/{item_id}")
async def manage_update_item(item_id: uuid.UUID, body: ItemUpdate, db: AsyncSession = Depends(get_db)) -> AdminItem:
    updates = body.model_dump(exclude_unset=True)
    if "slug" in updates:
        await _lock_items(db)
    item = await _get_item(db, item_id)
    new_slug = updates.get("slug")
    if new_slug is not None and new_slug != item.slug and await service.slug_taken(db, new_slug, exclude_id=item.id):
        raise HTTPException(status_code=409, detail="slug already in use")
    for field, value in updates.items():
        setattr(item, field, value)
    await _commit_or_409(db)
    await db.refresh(item)
    return AdminItem.model_validate(item)


@admin_router.delete("/items/{item_id}", status_code=204)
async def manage_delete_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    item = await _get_item(db, item_id)
    await db.delete(item)
    await db.commit()


@admin_router.post("/items/{item_id}/move")
async def manage_move_item(item_id: uuid.UUID, body: MoveRequest, db: AsyncSession = Depends(get_db)) -> list[AdminItem]:
    """Swaps the item's place with its neighbour's - in the order the public
    list uses, among every item (an unpublished one is a neighbour too, the
    editor's list shows it) - and answers with the whole list in its new
    order. The first item up and the last item down change nothing.

    sort_order values may tie (two items created with the same one): then
    every item is first renumbered 1..n in the current display order, so
    that swapping two values really swaps two places."""
    await _lock_items(db)
    items = await _all_items(db)
    index = next((i for i, item in enumerate(items) if item.id == item_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Item not found")

    neighbour = index - 1 if body.direction == "up" else index + 1
    if 0 <= neighbour < len(items):
        if len({item.sort_order for item in items}) != len(items):
            for position, item in enumerate(items, start=1):
                item.sort_order = position
        moved, other = items[index], items[neighbour]
        moved.sort_order, other.sort_order = other.sort_order, moved.sort_order
        await db.commit()
        items = await _all_items(db)
    return [AdminItem.model_validate(item) for item in items]


router = APIRouter()
router.include_router(public_router)
router.include_router(admin_router)
