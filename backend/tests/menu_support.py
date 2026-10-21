# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What the pub_menu tests share: a throwaway app the router is mounted on (whether
the module is on the real app depends on the branch's backend/modules.json, which a
test must not assume), a fixed "today" handed to the app through its get_today
dependency, and helpers to seed the menus the way the module itself stores them (over
HTTP as an administrator, so what a test sees is what the API produced)."""

from datetime import date, timedelta

from fastapi import FastAPI
from sqlalchemy import delete

from app.database import get_db
from app.modules.pub_menu.config import get_config, load_config
from app.modules.pub_menu.deps import get_today
from app.modules.pub_menu.models import DailyMenu, DailyMenuItem, MenuCategory, MenuItem, MenuPrice, MenuSettings
from app.modules.pub_menu.router import router as menu_router

BASE = "/api/modules/pub_menu"

# A Wednesday, so a week has days both before and after it.
TODAY = date(2027, 3, 10)
MONDAY = date(2027, 3, 8)


def day(offset: int) -> date:
    return TODAY + timedelta(days=offset)


def menu_app() -> FastAPI:
    app = FastAPI()
    app.include_router(menu_router, prefix=BASE)
    return app


def install_overrides(app: FastAPI, db_session, *, today: date = TODAY) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_config] = load_config
    app.dependency_overrides[get_today] = lambda: today


async def clear_tables(db) -> None:
    """Empties everything the module owns, dependants first. The tests run in a
    transaction that is rolled back, so this never outlives a test."""
    for model in (DailyMenuItem, DailyMenu, MenuPrice, MenuItem, MenuCategory, MenuSettings):
        await db.execute(delete(model))


async def add_category(client, headers, name="Hlavní jídla", **fields) -> dict:
    resp = await client.post(f"{BASE}/manage/categories", json={"name": name, **fields}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_item(client, headers, category_id, name="Svíčková", prices=None, **fields) -> dict:
    body = {"category_id": category_id, "name": name, "prices": prices if prices is not None else [{"label": "150 g", "price": 189}], **fields}
    resp = await client.post(f"{BASE}/manage/items", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def daily_body(*items: dict, published: bool = True) -> dict:
    return {"is_published": published, "items": list(items)}


def dish(name: str, kind: str = "main", **fields) -> dict:
    return {"kind": kind, "name": name, **fields}
