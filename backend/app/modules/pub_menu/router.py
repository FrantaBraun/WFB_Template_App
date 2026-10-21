# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The pub's menus: the public endpoints (the standing menu - food and drinks - and
the lunch menu by week) and the administrators' /manage ones (categories, items,
lunch menus by date, the notes). Administrators are this application's own - the
local User.is_admin flag (require_admin), never the JWT's role_name.

The rules live in service.py, which never commits; the handlers here commit once the
whole change is done.

Fixed paths are declared before the ones with a parameter where both could match
(FastAPI matches in declaration order).
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.database import get_db
from app.modules.pub_menu import service
from app.modules.pub_menu.config import PubMenuConfig, get_config
from app.modules.pub_menu.deps import get_today
from app.modules.pub_menu.schemas import (
    CategoryAdmin,
    CategoryIn,
    CategoryPatch,
    DailyAdmin,
    DailyIn,
    DailyWeekOut,
    ItemAdmin,
    ItemIn,
    ItemPatch,
    OfferOut,
    ReorderBody,
    SettingsIO,
)

router = APIRouter()
admin_router = APIRouter(prefix="/manage", dependencies=[Depends(require_admin)])


# --- Public ------------------------------------------------------------------------


@router.get("/offer")
async def get_offer(db: AsyncSession = Depends(get_db), config: PubMenuConfig = Depends(get_config)) -> OfferOut:
    """The standing menu: the active categories (food and drinks) with their active
    items, prices and allergens, in the order the pub set."""
    return await service.public_offer(db, config)


@router.get("/daily")
async def get_daily(
    on: date | None = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
    today: date = Depends(get_today),
    config: PubMenuConfig = Depends(get_config),
) -> DailyWeekOut:
    """The published lunch menus of the week (Monday-Sunday) that contains `date`
    (default today). 422 for a week outside what the configuration lets a visitor see."""
    return await service.public_week(db, on or today, today, config)


# --- Administrators: the standing menu ------------------------------------------------------


@admin_router.get("/categories")
async def manage_list_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryAdmin]:
    """Every category with every item, inactive ones too."""
    return await service.list_categories(db)


@admin_router.post("/categories", status_code=201)
async def manage_create_category(body: CategoryIn, db: AsyncSession = Depends(get_db)) -> CategoryAdmin:
    category = await service.create_category(db, body)
    await db.commit()
    return service.category_admin(category, [])


@admin_router.post("/categories/order")
async def manage_reorder_categories(body: ReorderBody, db: AsyncSession = Depends(get_db)) -> list[CategoryAdmin]:
    """Puts the categories in this order (exactly the ones that exist, each once)."""
    await service.reorder_categories(db, body.ids)
    await db.commit()
    return await service.list_categories(db)


@admin_router.patch("/categories/{category_id}")
async def manage_update_category(category_id: uuid.UUID, body: CategoryPatch, db: AsyncSession = Depends(get_db)) -> CategoryAdmin:
    category = await service.update_category(db, category_id, body)
    await db.commit()
    return next(entry for entry in await service.list_categories(db) if entry.id == category.id)


@admin_router.delete("/categories/{category_id}", status_code=204)
async def manage_delete_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Deletes the category together with its items and their prices."""
    await service.delete_category(db, category_id)
    await db.commit()


@admin_router.post("/categories/{category_id}/items/order")
async def manage_reorder_items(category_id: uuid.UUID, body: ReorderBody, db: AsyncSession = Depends(get_db)) -> list[CategoryAdmin]:
    """Puts the items of the category in this order (exactly the ones it has, each once)."""
    await service.reorder_items(db, category_id, body.ids)
    await db.commit()
    return await service.list_categories(db)


@admin_router.post("/items", status_code=201)
async def manage_create_item(body: ItemIn, db: AsyncSession = Depends(get_db)) -> ItemAdmin:
    item = await service.create_item(db, body)
    await db.commit()
    return await service.item_detail(db, item)


@admin_router.patch("/items/{item_id}")
async def manage_update_item(item_id: uuid.UUID, body: ItemPatch, db: AsyncSession = Depends(get_db)) -> ItemAdmin:
    """Changes the fields sent; `category_id` moves the item to the end of another
    category, `prices` replaces all its prices."""
    item = await service.update_item(db, item_id, body)
    await db.commit()
    return await service.item_detail(db, item)


@admin_router.delete("/items/{item_id}", status_code=204)
async def manage_delete_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    await service.delete_item(db, item_id)
    await db.commit()


# --- Administrators: the lunch menu and the notes ------------------------------------------------------


@admin_router.get("/daily")
async def manage_list_days(
    date_from: date,
    date_to: date,
    db: AsyncSession = Depends(get_db),
) -> list[DailyAdmin]:
    """The stored lunch menus of a range of days (at most 62), drafts included."""
    return await service.list_days(db, date_from, date_to)


@admin_router.put("/daily/{day}")
async def manage_put_day(day: date, body: DailyIn, db: AsyncSession = Depends(get_db)) -> DailyAdmin:
    """Stores the lunch menu of a date: the dishes replace those there, in the order
    given, and `is_published` decides whether visitors see it (a draft is not shown)."""
    result = await service.put_day(db, day, body)
    await db.commit()
    return result


@admin_router.delete("/daily/{day}", status_code=204)
async def manage_delete_day(day: date, db: AsyncSession = Depends(get_db)) -> None:
    await service.delete_day(db, day)
    await db.commit()


@admin_router.get("/settings")
async def manage_get_settings(db: AsyncSession = Depends(get_db)) -> SettingsIO:
    row = await service.get_settings_row(db)
    await db.commit()
    return SettingsIO.model_validate(row)


@admin_router.put("/settings")
async def manage_put_settings(body: SettingsIO, db: AsyncSession = Depends(get_db)) -> SettingsIO:
    """The notes shown under the lunch menu and under the standing menu."""
    result = await service.update_settings(db, body)
    await db.commit()
    return result


router.include_router(admin_router)
