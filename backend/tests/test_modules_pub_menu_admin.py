# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The administrators' side of the pub menu module: the gate on every /manage
route, the standing menu (categories and items, their order and prices), the lunch
menu by date (a draft until published) and the notes. What visitors see of all this
is in test_modules_pub_menu_public.py.

Mounts just this module's router on a throwaway app (see menu_support.py), with
"today" fixed and the database a rolled-back session."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.models.user import User
from app.modules.pub_menu.models import DailyMenuItem, MenuCategory, MenuItem, MenuPrice
from tests.menu_support import (
    BASE,
    add_category,
    add_item,
    clear_tables,
    daily_body,
    day,
    dish,
    install_overrides,
    menu_app,
)

_app = menu_app()


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await clear_tables(db_session)
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    install_overrides(_app, db_session)
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    """An administrator of this application (local User.is_admin) - with a plain
    auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    """Not an administrator here - even though the auth service calls them "admin":
    role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


async def count(db, model) -> int:
    return await db.scalar(select(func.count()).select_from(model))


# --- The gate ------------------------------------------------------------------------------


PUBLIC_ROUTES = {("GET", "/offer"), ("GET", "/daily")}


def _all_routes():
    """Every (method, path) of the module, read from the OpenAPI schema - the router
    is mounted as one object on newer FastAPI."""
    paths = _app.openapi()["paths"]
    return [(method.upper(), path.removeprefix(BASE)) for path, operations in paths.items() for method in operations]


def _manage_routes():
    return [route for route in _all_routes() if route[1].startswith("/manage")]


def test_every_route_is_either_a_known_public_one_or_under_manage():
    routes = _all_routes()

    assert {route for route in routes if not route[1].startswith("/manage")} == PUBLIC_ROUTES
    assert len(_manage_routes()) == 14


async def _call(client, method: str, path: str, headers: dict):
    concrete = (
        path.replace("{category_id}", str(uuid.uuid4()))
        .replace("{item_id}", str(uuid.uuid4()))
        .replace("{day}", day(1).isoformat())
    )
    return await client.request(method, f"{BASE}{concrete}", headers=headers)


@pytest.mark.parametrize(("method", "path"), _manage_routes())
async def test_anonymous_requests_are_rejected_on_every_manage_route(client, method, path):
    assert (await _call(client, method, path, headers={})).status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _manage_routes())
async def test_non_admins_are_rejected_on_every_manage_route(client, non_admin, method, path):
    resp = await _call(client, method, path, headers=non_admin)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


# --- Categories ---------------------------------------------------------------------------------


async def test_a_category_is_created_listed_changed_and_ordered_after_the_others(client, admin):
    first = await add_category(client, admin, "Předkrmy", description="  Na začátek  ", kind="food")
    second = await add_category(client, admin, "Výčepní piva", kind="drink")

    assert (first["name"], first["description"], first["kind"], first["is_active"], first["position"], first["items"]) == ("Předkrmy", "Na začátek", "food", True, 0, [])
    assert (second["kind"], second["position"]) == ("drink", 1)
    assert [c["name"] for c in (await client.get(f"{BASE}/manage/categories", headers=admin)).json()] == ["Předkrmy", "Výčepní piva"]

    changed = await client.patch(f"{BASE}/manage/categories/{first['id']}", json={"name": "Studená kuchyně", "is_active": False}, headers=admin)

    assert changed.status_code == 200
    assert (changed.json()["name"], changed.json()["is_active"], changed.json()["description"]) == ("Studená kuchyně", False, "Na začátek")


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "   "}, {"name": "x" * 101}, {"name": "T", "kind": "dessert"}, {"name": "T", "surprise": 1}, {}])
async def test_a_category_needs_a_name_and_a_known_kind(client, admin, body):
    assert (await client.post(f"{BASE}/manage/categories", json=body, headers=admin)).status_code == 422


async def test_a_category_field_cannot_be_set_to_null_and_an_unknown_category_is_404(client, admin):
    category = await add_category(client, admin)

    assert (await client.patch(f"{BASE}/manage/categories/{category['id']}", json={"name": None}, headers=admin)).status_code == 422
    assert (await client.patch(f"{BASE}/manage/categories/{uuid.uuid4()}", json={"name": "X"}, headers=admin)).status_code == 404
    assert (await client.delete(f"{BASE}/manage/categories/{uuid.uuid4()}", headers=admin)).status_code == 404


async def test_deleting_a_category_deletes_its_items_and_prices_with_it(client, admin, db_session):
    doomed = await add_category(client, admin, "Doomed")
    kept = await add_category(client, admin, "Kept")
    await add_item(client, admin, doomed["id"], "A", prices=[{"label": "", "price": 10}, {"label": "big", "price": 20}])
    await add_item(client, admin, doomed["id"], "B")
    await add_item(client, admin, kept["id"], "C")

    resp = await client.delete(f"{BASE}/manage/categories/{doomed['id']}", headers=admin)

    assert resp.status_code == 204
    assert await count(db_session, MenuCategory) == 1 and await count(db_session, MenuItem) == 1
    assert await count(db_session, MenuPrice) == 1  # only C's price is left


async def test_categories_are_reordered_by_the_ids_given(client, admin):
    a, b, c = [await add_category(client, admin, name) for name in ("A", "B", "C")]

    resp = await client.post(f"{BASE}/manage/categories/order", json={"ids": [c["id"], a["id"], b["id"]]}, headers=admin)

    assert resp.status_code == 200
    assert [entry["name"] for entry in resp.json()] == ["C", "A", "B"]
    assert [entry["name"] for entry in (await client.get(f"{BASE}/manage/categories", headers=admin)).json()] == ["C", "A", "B"]


async def test_a_reorder_must_name_exactly_the_existing_ids_once_each(client, admin):
    a, b = [await add_category(client, admin, name) for name in ("A", "B")]
    url = f"{BASE}/manage/categories/order"

    missing = await client.post(url, json={"ids": [a["id"]]}, headers=admin)
    twice = await client.post(url, json={"ids": [a["id"], a["id"]]}, headers=admin)
    extra = await client.post(url, json={"ids": [a["id"], b["id"], str(uuid.uuid4())]}, headers=admin)
    unknown = await client.post(url, json={"ids": [a["id"], str(uuid.uuid4())]}, headers=admin)

    for resp in (missing, twice, extra, unknown):
        assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"ids": "ids_mismatch"}}
    assert [entry["name"] for entry in (await client.get(f"{BASE}/manage/categories", headers=admin)).json()] == ["A", "B"]


# --- Items ---------------------------------------------------------------------------------------------


async def test_an_item_is_created_with_its_prices_and_allergens(client, admin):
    category = await add_category(client, admin, "Piva", kind="drink")

    item = await add_item(
        client,
        admin,
        category["id"],
        "Plzeň 12°",
        description="  Čepovaná  ",
        allergens=[7, 1, 1],
        prices=[{"label": "0,3 l", "price": 42}, {"label": "0,5 l", "price": 57.5}],
    )

    assert (item["name"], item["description"], item["allergens"], item["is_available"], item["is_active"], item["position"]) == ("Plzeň 12°", "Čepovaná", [1, 7], True, True, 0)
    assert item["prices"] == [{"label": "0,3 l", "price": 42.0}, {"label": "0,5 l", "price": 57.5}]
    listed = (await client.get(f"{BASE}/manage/categories", headers=admin)).json()
    assert [i["name"] for i in listed[0]["items"]] == ["Plzeň 12°"] and listed[0]["items"][0]["prices"] == item["prices"]


async def test_items_are_placed_after_the_others_of_their_category(client, admin):
    first, second = await add_category(client, admin, "A"), await add_category(client, admin, "B")

    one = await add_item(client, admin, first["id"], "one")
    two = await add_item(client, admin, first["id"], "two")
    other = await add_item(client, admin, second["id"], "other")

    assert (one["position"], two["position"], other["position"]) == (0, 1, 0)


async def test_an_item_may_have_no_price_for_a_dish_priced_on_request(client, admin):
    category = await add_category(client, admin)

    item = await add_item(client, admin, category["id"], "Denní specialita", prices=[])

    assert item["prices"] == []


@pytest.mark.parametrize(
    "override",
    [
        {"name": ""},
        {"name": "x" * 151},
        {"description": "x" * 501},
        {"allergens": [0]},
        {"allergens": [15]},
        {"allergens": [1, 2, "x"]},
        {"prices": [{"label": "", "price": -1}]},
        {"prices": [{"label": "", "price": 1.005}]},
        {"prices": [{"label": "", "price": 100000000}]},
        {"prices": [{"label": "x" * 51, "price": 1}]},
        {"prices": [{"label": "", "price": 1}] * 7},
        {"prices": [{"price": 1, "surprise": 1}]},
        {"surprise": 1},
    ],
)
async def test_an_item_that_makes_no_sense_is_refused(client, admin, db_session, override):
    category = await add_category(client, admin)

    resp = await client.post(f"{BASE}/manage/items", json={"category_id": category["id"], "name": "Ok", "prices": [], **override}, headers=admin)

    assert resp.status_code == 422
    assert await count(db_session, MenuItem) == 0


async def test_an_item_needs_an_existing_category(client, admin):
    resp = await client.post(f"{BASE}/manage/items", json={"category_id": str(uuid.uuid4()), "name": "Lost"}, headers=admin)

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"category_id": "unknown"}}


async def test_an_item_is_changed_field_by_field_and_its_prices_are_replaced_as_a_whole(client, admin):
    category = await add_category(client, admin)
    item = await add_item(client, admin, category["id"], "Svíčková", description="Stará", allergens=[1, 3], prices=[{"label": "150 g", "price": 189}, {"label": "200 g", "price": 219}])
    url = f"{BASE}/manage/items/{item['id']}"

    renamed = await client.patch(url, json={"name": "Svíčková na smetaně", "is_available": False}, headers=admin)
    repriced = await client.patch(url, json={"prices": [{"label": "", "price": 199}]}, headers=admin)
    cleared = await client.patch(url, json={"prices": []}, headers=admin)

    assert renamed.status_code == 200
    assert (renamed.json()["name"], renamed.json()["is_available"], renamed.json()["description"], renamed.json()["allergens"]) == ("Svíčková na smetaně", False, "Stará", [1, 3])
    assert len(renamed.json()["prices"]) == 2  # untouched
    assert repriced.json()["prices"] == [{"label": "", "price": 199.0}]
    assert cleared.json()["prices"] == []


async def test_an_item_can_be_hidden_without_deleting_it(client, admin):
    category = await add_category(client, admin)
    item = await add_item(client, admin, category["id"])

    hidden = await client.patch(f"{BASE}/manage/items/{item['id']}", json={"is_active": False}, headers=admin)

    assert hidden.json()["is_active"] is False
    assert (await client.get(f"{BASE}/manage/categories", headers=admin)).json()[0]["items"][0]["is_active"] is False  # the administrators still see it


async def test_a_change_that_makes_no_sense_or_names_nothing_is_refused(client, admin):
    category = await add_category(client, admin)
    item = await add_item(client, admin, category["id"])
    url = f"{BASE}/manage/items/{item['id']}"

    for body in ({"name": None}, {"prices": None}, {"allergens": [99]}, {"category_id": str(uuid.uuid4())}, {"surprise": 1}):
        assert (await client.patch(url, json=body, headers=admin)).status_code == 422, body
    assert (await client.patch(f"{BASE}/manage/items/{uuid.uuid4()}", json={"name": "X"}, headers=admin)).status_code == 404
    assert (await client.delete(f"{BASE}/manage/items/{uuid.uuid4()}", headers=admin)).status_code == 404


async def test_an_item_moves_to_the_end_of_another_category(client, admin):
    source, target = await add_category(client, admin, "From"), await add_category(client, admin, "To")
    await add_item(client, admin, target["id"], "already there")
    moving = await add_item(client, admin, source["id"], "moving")

    resp = await client.patch(f"{BASE}/manage/items/{moving['id']}", json={"category_id": target["id"]}, headers=admin)

    assert resp.status_code == 200 and (resp.json()["category_id"], resp.json()["position"]) == (target["id"], 1)
    listed = {c["name"]: [i["name"] for i in c["items"]] for c in (await client.get(f"{BASE}/manage/categories", headers=admin)).json()}
    assert listed == {"From": [], "To": ["already there", "moving"]}


async def test_an_item_is_deleted_with_its_prices(client, admin, db_session):
    category = await add_category(client, admin)
    item = await add_item(client, admin, category["id"], prices=[{"label": "a", "price": 1}, {"label": "b", "price": 2}])
    other = await add_item(client, admin, category["id"], "Other")

    resp = await client.delete(f"{BASE}/manage/items/{item['id']}", headers=admin)

    assert resp.status_code == 204
    assert await count(db_session, MenuItem) == 1 and await count(db_session, MenuPrice) == 1
    assert (await client.get(f"{BASE}/manage/categories", headers=admin)).json()[0]["items"][0]["id"] == other["id"]


async def test_the_items_of_a_category_are_reordered(client, admin):
    category = await add_category(client, admin)
    other = await add_category(client, admin, "Other")
    a, b, c = [await add_item(client, admin, category["id"], name) for name in ("A", "B", "C")]
    foreign = await add_item(client, admin, other["id"], "Foreign")
    url = f"{BASE}/manage/categories/{category['id']}/items/order"

    ok = await client.post(url, json={"ids": [c["id"], a["id"], b["id"]]}, headers=admin)
    wrong_set = await client.post(url, json={"ids": [a["id"], b["id"]]}, headers=admin)
    foreign_item = await client.post(url, json={"ids": [a["id"], b["id"], foreign["id"]]}, headers=admin)
    unknown_category = await client.post(f"{BASE}/manage/categories/{uuid.uuid4()}/items/order", json={"ids": []}, headers=admin)

    assert ok.status_code == 200
    assert [i["name"] for i in next(entry for entry in ok.json() if entry["id"] == category["id"])["items"]] == ["C", "A", "B"]
    assert wrong_set.status_code == 422 and foreign_item.status_code == 422
    assert unknown_category.status_code == 404


# --- The lunch menu --------------------------------------------------------------------------------------


def range_params(first: int = 0, last: int = 6) -> dict:
    return {"date_from": day(first).isoformat(), "date_to": day(last).isoformat()}


async def test_a_lunch_menu_is_stored_for_a_date_with_its_dishes_in_the_order_given(client, admin):
    body = daily_body(
        dish("Gulášová polévka", "soup", amount="0,33 l", allergens=[9, 1], price=None),
        dish("Svíčková na smetaně", amount="150 g", description="houskový knedlík", allergens=[1, 3, 7, 9], price=169),
        dish("Palačinky", "dessert", price=59.5),
    )

    resp = await client.put(f"{BASE}/manage/daily/{day(1).isoformat()}", json=body, headers=admin)

    assert resp.status_code == 200, resp.text
    stored = resp.json()
    assert (stored["day"], stored["is_published"]) == (day(1).isoformat(), True)
    assert [(i["kind"], i["name"], i["amount"], i["price"]) for i in stored["items"]] == [
        ("soup", "Gulášová polévka", "0,33 l", None),
        ("main", "Svíčková na smetaně", "150 g", 169.0),
        ("dessert", "Palačinky", "", 59.5),
    ]
    assert stored["items"][0]["allergens"] == [1, 9] and stored["items"][1]["description"] == "houskový knedlík"
    assert stored["updated_at"]


async def test_putting_a_day_again_replaces_its_dishes_and_publication(client, admin, db_session):
    url = f"{BASE}/manage/daily/{day(1).isoformat()}"
    await client.put(url, json=daily_body(dish("Old one"), dish("Old two")), headers=admin)

    resp = await client.put(url, json=daily_body(dish("New"), published=False), headers=admin)

    assert [i["name"] for i in resp.json()["items"]] == ["New"] and resp.json()["is_published"] is False
    assert await count(db_session, DailyMenuItem) == 1


async def test_a_day_may_be_saved_empty_as_a_draft(client, admin):
    resp = await client.put(f"{BASE}/manage/daily/{day(2).isoformat()}", json={}, headers=admin)

    assert resp.status_code == 200 and resp.json()["items"] == [] and resp.json()["is_published"] is False


@pytest.mark.parametrize(
    "item",
    [
        {"kind": "starter", "name": "x"},
        {"kind": "main", "name": ""},
        {"kind": "main", "name": "x" * 151},
        {"kind": "main", "name": "x", "description": "x" * 501},
        {"kind": "main", "name": "x", "amount": "x" * 51},
        {"kind": "main", "name": "x", "allergens": [15]},
        {"kind": "main", "name": "x", "price": -5},
        {"kind": "main", "name": "x", "price": 1.001},
        {"kind": "main", "name": "x", "surprise": 1},
    ],
)
async def test_a_dish_that_makes_no_sense_is_refused_and_the_stored_menu_stays(client, admin, item):
    url = f"{BASE}/manage/daily/{day(1).isoformat()}"
    await client.put(url, json=daily_body(dish("Stays")), headers=admin)

    resp = await client.put(url, json=daily_body(dish("Fine"), item), headers=admin)

    assert resp.status_code == 422
    stored = (await client.get(f"{BASE}/manage/daily", params=range_params(), headers=admin)).json()
    assert [i["name"] for i in stored[0]["items"]] == ["Stays"]


async def test_a_lunch_menu_holds_at_most_thirty_dishes(client, admin):
    url = f"{BASE}/manage/daily/{day(1).isoformat()}"

    assert (await client.put(url, json=daily_body(*[dish(f"d{n}") for n in range(30)]), headers=admin)).status_code == 200
    assert (await client.put(url, json=daily_body(*[dish(f"d{n}") for n in range(31)]), headers=admin)).status_code == 422


async def test_the_list_of_days_gives_the_stored_menus_of_a_range_drafts_included(client, admin):
    await client.put(f"{BASE}/manage/daily/{day(3).isoformat()}", json=daily_body(dish("Later")), headers=admin)
    await client.put(f"{BASE}/manage/daily/{day(1).isoformat()}", json=daily_body(dish("Draft"), published=False), headers=admin)
    await client.put(f"{BASE}/manage/daily/{day(30).isoformat()}", json=daily_body(dish("Far")), headers=admin)

    resp = await client.get(f"{BASE}/manage/daily", params=range_params(0, 6), headers=admin)

    assert resp.status_code == 200
    assert [(entry["day"], entry["is_published"], entry["items"][0]["name"]) for entry in resp.json()] == [
        (day(1).isoformat(), False, "Draft"),
        (day(3).isoformat(), True, "Later"),
    ]


async def test_the_range_of_the_list_is_at_most_62_days_and_not_backwards(client, admin):
    assert (await client.get(f"{BASE}/manage/daily", params=range_params(0, 61), headers=admin)).status_code == 200
    too_wide = await client.get(f"{BASE}/manage/daily", params=range_params(0, 62), headers=admin)
    backwards = await client.get(f"{BASE}/manage/daily", params={"date_from": day(5).isoformat(), "date_to": day(1).isoformat()}, headers=admin)

    assert too_wide.status_code == 422 and too_wide.json()["detail"] == {"errors": {"date_to": "bad_range"}}
    assert backwards.status_code == 422
    assert (await client.get(f"{BASE}/manage/daily", headers=admin)).status_code == 422


async def test_a_lunch_menu_is_deleted_with_its_dishes(client, admin, db_session):
    url = f"{BASE}/manage/daily/{day(1).isoformat()}"
    await client.put(url, json=daily_body(dish("A"), dish("B")), headers=admin)

    resp = await client.delete(url, headers=admin)

    assert resp.status_code == 204 and await count(db_session, DailyMenuItem) == 0
    assert (await client.delete(url, headers=admin)).status_code == 404
    assert (await client.put("%s/manage/daily/not-a-day" % BASE, json={}, headers=admin)).status_code == 422


# --- The notes ---------------------------------------------------------------------------------------------


async def test_the_notes_start_empty_and_are_set_as_a_whole(client, admin):
    first = await client.get(f"{BASE}/manage/settings", headers=admin)

    assert first.status_code == 200 and first.json() == {"daily_note": "", "offer_note": ""}

    saved = await client.put(f"{BASE}/manage/settings", json={"daily_note": "  Po-Pá 11-14 h  ", "offer_note": "Alergeny sdělíme."}, headers=admin)

    assert saved.json() == {"daily_note": "Po-Pá 11-14 h", "offer_note": "Alergeny sdělíme."}
    assert (await client.get(f"{BASE}/manage/settings", headers=admin)).json() == saved.json()
    assert (await client.put(f"{BASE}/manage/settings", json={"daily_note": ""}, headers=admin)).json() == {"daily_note": "", "offer_note": ""}


async def test_a_note_is_at_most_a_thousand_characters_and_unknown_keys_are_refused(client, admin):
    assert (await client.put(f"{BASE}/manage/settings", json={"daily_note": "x" * 1000}, headers=admin)).status_code == 200
    assert (await client.put(f"{BASE}/manage/settings", json={"daily_note": "x" * 1001}, headers=admin)).status_code == 422
    assert (await client.put(f"{BASE}/manage/settings", json={"surprise": "x"}, headers=admin)).status_code == 422
