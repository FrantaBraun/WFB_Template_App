# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules of the pub menu module, between the router and the database.

Nothing here commits: the router does, so a change is one transaction and a
refusal (every check that can refuse comes before the first write) leaves nothing
behind. Reordering and replacing a lunch menu are whole-list operations on purpose,
like the form questions of the forms module: the client sends the list as it should
be and the server makes it so, so there are no half-applied moves to reason about.

Errors are MenuError(status, detail) (an HTTPException); the 422 / 409 details have
the shape {"errors": {field: code}}.
"""

import uuid
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pub_menu.config import PubMenuConfig
from app.modules.pub_menu.models import (
    DailyMenu,
    DailyMenuItem,
    MenuCategory,
    MenuItem,
    MenuPrice,
    MenuSettings,
)
from app.modules.pub_menu.schemas import (
    MAX_RANGE_DAYS,
    CategoryAdmin,
    CategoryIn,
    CategoryPatch,
    CategoryPublic,
    DailyAdmin,
    DailyDayOut,
    DailyIn,
    DailyItemOut,
    DailyWeekOut,
    ItemAdmin,
    ItemIn,
    ItemPatch,
    ItemPublic,
    OfferOut,
    PriceIn,
    PriceOut,
    SettingsIO,
)


class MenuError(HTTPException):
    """A refusal. It is the HTTP answer itself (FastAPI turns it into the response)."""

    def __init__(self, status_code: int, detail: Any):
        super().__init__(status_code=status_code, detail=detail)


def field_error(status_code: int, field: str, code: str) -> MenuError:
    return MenuError(status_code, {"errors": {field: code}})


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


# --- Settings ---------------------------------------------------------------------------


async def get_settings_row(db: AsyncSession) -> MenuSettings:
    """The one settings row, created empty the first time it is needed."""
    row = await db.get(MenuSettings, 1, populate_existing=True)
    if row is None:
        row = MenuSettings(id=1, daily_note="", offer_note="")
        db.add(row)
        await db.flush()
    return row


async def update_settings(db: AsyncSession, body: SettingsIO) -> SettingsIO:
    row = await get_settings_row(db)
    row.daily_note = body.daily_note
    row.offer_note = body.offer_note
    await db.flush()
    return SettingsIO.model_validate(row)


# --- The standing menu ------------------------------------------------------------------------


async def _prices_by_item(db: AsyncSession, item_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[PriceOut]]:
    if not item_ids:
        return {}
    rows = (
        await db.scalars(
            select(MenuPrice).where(MenuPrice.item_id.in_(list(item_ids))).order_by(MenuPrice.position, MenuPrice.id).execution_options(populate_existing=True)
        )
    ).all()
    result: dict[uuid.UUID, list[PriceOut]] = {}
    for row in rows:
        result.setdefault(row.item_id, []).append(PriceOut(label=row.label, price=row.price))
    return result


async def _items_by_category(db: AsyncSession, category_ids: Sequence[uuid.UUID], *, only_active: bool) -> dict[uuid.UUID, list[ItemAdmin]]:
    if not category_ids:
        return {}
    query = select(MenuItem).where(MenuItem.category_id.in_(list(category_ids))).order_by(MenuItem.position, MenuItem.name, MenuItem.id).execution_options(populate_existing=True)
    if only_active:
        query = query.where(MenuItem.is_active)
    items = list((await db.scalars(query)).all())
    prices = await _prices_by_item(db, [item.id for item in items])
    result: dict[uuid.UUID, list[ItemAdmin]] = {}
    for item in items:
        result.setdefault(item.category_id, []).append(item_admin(item, prices.get(item.id, [])))
    return result


def item_admin(item: MenuItem, prices: list[PriceOut]) -> ItemAdmin:
    return ItemAdmin(
        id=item.id,
        category_id=item.category_id,
        name=item.name,
        description=item.description,
        allergens=list(item.allergens),
        is_available=item.is_available,
        is_active=item.is_active,
        position=item.position,
        prices=prices,
    )


async def public_offer(db: AsyncSession, config: PubMenuConfig) -> OfferOut:
    """The active categories with their active items and prices, in the order the pub set."""
    categories = list(
        (
            await db.scalars(
                select(MenuCategory).where(MenuCategory.is_active).order_by(MenuCategory.position, MenuCategory.name, MenuCategory.id).execution_options(populate_existing=True)
            )
        ).all()
    )
    items = await _items_by_category(db, [category.id for category in categories], only_active=True)
    note = (await get_settings_row(db)).offer_note
    return OfferOut(
        currency=config.currency,
        note=note,
        categories=[
            CategoryPublic(
                id=category.id,
                name=category.name,
                description=category.description,
                kind=category.kind,
                items=[
                    ItemPublic(
                        id=item.id,
                        name=item.name,
                        description=item.description,
                        allergens=item.allergens,
                        is_available=item.is_available,
                        prices=item.prices,
                    )
                    for item in items.get(category.id, [])
                ],
            )
            for category in categories
        ],
    )


async def list_categories(db: AsyncSession) -> list[CategoryAdmin]:
    """Every category (inactive too) with every item (inactive too)."""
    categories = list(
        (await db.scalars(select(MenuCategory).order_by(MenuCategory.position, MenuCategory.name, MenuCategory.id).execution_options(populate_existing=True))).all()
    )
    items = await _items_by_category(db, [category.id for category in categories], only_active=False)
    return [category_admin(category, items.get(category.id, [])) for category in categories]


def category_admin(category: MenuCategory, items: list[ItemAdmin]) -> CategoryAdmin:
    return CategoryAdmin(
        id=category.id,
        name=category.name,
        description=category.description,
        kind=category.kind,
        position=category.position,
        is_active=category.is_active,
        items=items,
    )


async def _next_position(db: AsyncSession, model, *conditions) -> int:
    top = await db.scalar(select(func.max(model.position)).where(*conditions))
    return 0 if top is None else top + 1


async def get_category(db: AsyncSession, category_id: uuid.UUID) -> MenuCategory:
    category = await db.get(MenuCategory, category_id)
    if category is None:
        raise MenuError(404, "Category not found")
    return category


async def create_category(db: AsyncSession, body: CategoryIn) -> MenuCategory:
    category = MenuCategory(
        name=body.name,
        description=body.description,
        kind=body.kind,
        is_active=body.is_active,
        position=await _next_position(db, MenuCategory),
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


async def update_category(db: AsyncSession, category_id: uuid.UUID, body: CategoryPatch) -> MenuCategory:
    category = await get_category(db, category_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is None:
            raise field_error(422, field, "cannot_be_null")
    for field, value in updates.items():
        setattr(category, field, value)
    await db.flush()
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> None:
    """Deletes the category with all its items and their prices (nothing else refers to them)."""
    category = await get_category(db, category_id)
    await db.delete(category)
    await db.flush()


async def _reorder(db: AsyncSession, model, ids: Sequence[uuid.UUID], *conditions) -> None:
    """Sets `position` of the rows of `model` (those matching `conditions`) to the
    order of `ids`, which must be exactly their ids, each once (422 `ids_mismatch`)."""
    existing = set((await db.scalars(select(model.id).where(*conditions))).all())
    if len(ids) != len(set(ids)) or set(ids) != existing:
        raise field_error(422, "ids", "ids_mismatch")
    for position, row_id in enumerate(ids):
        row = await db.get(model, row_id)
        row.position = position
    await db.flush()


async def reorder_categories(db: AsyncSession, ids: Sequence[uuid.UUID]) -> None:
    await _reorder(db, MenuCategory, ids)


async def reorder_items(db: AsyncSession, category_id: uuid.UUID, ids: Sequence[uuid.UUID]) -> None:
    await get_category(db, category_id)
    await _reorder(db, MenuItem, ids, MenuItem.category_id == category_id)


async def _replace_prices(db: AsyncSession, item_id: uuid.UUID, prices: Sequence[PriceIn]) -> None:
    await db.execute(delete(MenuPrice).where(MenuPrice.item_id == item_id))
    db.add_all(MenuPrice(item_id=item_id, label=price.label, price=price.price, position=position) for position, price in enumerate(prices))


async def item_detail(db: AsyncSession, item: MenuItem) -> ItemAdmin:
    await db.refresh(item)
    prices = (await _prices_by_item(db, [item.id])).get(item.id, [])
    return item_admin(item, prices)


async def create_item(db: AsyncSession, body: ItemIn) -> MenuItem:
    if await db.get(MenuCategory, body.category_id) is None:
        raise field_error(422, "category_id", "unknown")
    item = MenuItem(
        category_id=body.category_id,
        name=body.name,
        description=body.description,
        allergens=body.allergens,
        is_available=body.is_available,
        is_active=body.is_active,
        position=await _next_position(db, MenuItem, MenuItem.category_id == body.category_id),
    )
    db.add(item)
    await db.flush()
    await _replace_prices(db, item.id, body.prices)
    await db.flush()
    return item


async def get_item(db: AsyncSession, item_id: uuid.UUID) -> MenuItem:
    item = await db.get(MenuItem, item_id)
    if item is None:
        raise MenuError(404, "Item not found")
    return item


async def update_item(db: AsyncSession, item_id: uuid.UUID, body: ItemPatch) -> MenuItem:
    item = await get_item(db, item_id)
    updates = body.model_dump(exclude_unset=True, exclude={"prices"})
    for field, value in updates.items():
        if value is None:
            raise field_error(422, field, "cannot_be_null")
    if "prices" in body.model_fields_set and body.prices is None:
        raise field_error(422, "prices", "cannot_be_null")
    if "category_id" in updates and updates["category_id"] != item.category_id:
        if await db.get(MenuCategory, updates["category_id"]) is None:
            raise field_error(422, "category_id", "unknown")
        item.position = await _next_position(db, MenuItem, MenuItem.category_id == updates["category_id"])
    for field, value in updates.items():
        setattr(item, field, value)
    if body.prices is not None:
        await _replace_prices(db, item.id, body.prices)
    await db.flush()
    return item


async def delete_item(db: AsyncSession, item_id: uuid.UUID) -> None:
    item = await get_item(db, item_id)
    await db.delete(item)
    await db.flush()


# --- The lunch menu ---------------------------------------------------------------------------------


async def _items_of_days(db: AsyncSession, days: Sequence[date]) -> dict[date, list[DailyItemOut]]:
    if not days:
        return {}
    rows = (
        await db.scalars(
            select(DailyMenuItem).where(DailyMenuItem.day.in_(list(days))).order_by(DailyMenuItem.position, DailyMenuItem.id).execution_options(populate_existing=True)
        )
    ).all()
    result: dict[date, list[DailyItemOut]] = {}
    for row in rows:
        result.setdefault(row.day, []).append(DailyItemOut.model_validate(row))
    return result


async def public_week(db: AsyncSession, on: date, today: date, config: PubMenuConfig) -> DailyWeekOut:
    """The published lunch menus of the week of `on`. 422 when that week is outside
    what the configuration lets a visitor browse."""
    first_allowed = monday_of(today) - timedelta(weeks=config.weeks_back)
    last_allowed = monday_of(today) + timedelta(weeks=config.weeks_ahead)
    week_start = monday_of(on)
    if not first_allowed <= week_start <= last_allowed:
        raise field_error(422, "date", "out_of_range")
    week = [week_start + timedelta(days=offset) for offset in range(7)]
    published = set(
        (await db.scalars(select(DailyMenu.day).where(DailyMenu.day.in_(week), DailyMenu.is_published).execution_options(populate_existing=True))).all()
    )
    items = await _items_of_days(db, [day for day in week if day in published])
    return DailyWeekOut(
        currency=config.currency,
        note=(await get_settings_row(db)).daily_note,
        week_start=week_start,
        week_end=week[-1],
        min_week_start=first_allowed,
        max_week_start=last_allowed,
        days=[DailyDayOut(day=day, items=items.get(day, [])) for day in week],
    )


async def list_days(db: AsyncSession, date_from: date, date_to: date) -> list[DailyAdmin]:
    """The stored lunch menus of a range of days, drafts included, by date."""
    if date_to < date_from or (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise field_error(422, "date_to", "bad_range")
    menus = list(
        (
            await db.scalars(
                select(DailyMenu).where(DailyMenu.day >= date_from, DailyMenu.day <= date_to).order_by(DailyMenu.day).execution_options(populate_existing=True)
            )
        ).all()
    )
    items = await _items_of_days(db, [menu.day for menu in menus])
    return [DailyAdmin(day=menu.day, is_published=menu.is_published, updated_at=menu.updated_at, items=items.get(menu.day, [])) for menu in menus]


async def put_day(db: AsyncSession, day: date, body: DailyIn) -> DailyAdmin:
    """Stores the lunch menu of a date: creates it or replaces the one there, dishes
    and publication, in the order given."""
    menu = await db.get(DailyMenu, day, populate_existing=True)
    if menu is None:
        menu = DailyMenu(day=day, is_published=body.is_published)
        db.add(menu)
        await db.flush()
    else:
        menu.is_published = body.is_published
        await db.execute(delete(DailyMenuItem).where(DailyMenuItem.day == day))
    db.add_all(
        DailyMenuItem(
            day=day,
            kind=item.kind,
            name=item.name,
            description=item.description,
            amount=item.amount,
            allergens=item.allergens,
            price=item.price,
            position=position,
        )
        for position, item in enumerate(body.items)
    )
    await db.flush()
    await db.refresh(menu)
    items = await _items_of_days(db, [day])
    return DailyAdmin(day=menu.day, is_published=menu.is_published, updated_at=menu.updated_at, items=items.get(day, []))


async def delete_day(db: AsyncSession, day: date) -> None:
    menu = await db.get(DailyMenu, day)
    if menu is None:
        raise MenuError(404, "Menu not found")
    await db.delete(menu)
    await db.flush()
