# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The public side of the pub menu module: the standing menu and the lunch menu by
week, and what never reaches a visitor (inactive categories and items, drafts,
anything only an administrator is meant to see). The menus are filled in over HTTP
as an administrator, the way the pub does it.

Mounts just this module's router on a throwaway app (see menu_support.py), with
"today" fixed (Wednesday 10 March 2027) and the database a rolled-back session."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.user import User
from app.modules.pub_menu.config import get_config, load_config
from tests.menu_support import (
    BASE,
    MONDAY,
    TODAY,
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
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


async def put_day(client, admin, on: date, *items: dict, published: bool = True) -> None:
    resp = await client.put(f"{BASE}/manage/daily/{on.isoformat()}", json=daily_body(*items, published=published), headers=admin)
    assert resp.status_code == 200, resp.text


# --- The standing menu --------------------------------------------------------------------------------


async def test_an_empty_pub_shows_an_empty_menu_without_needing_anyone_to_set_it_up(client):
    resp = await client.get(f"{BASE}/offer")

    assert resp.status_code == 200
    assert resp.json() == {"currency": "CZK", "note": "", "categories": []}


async def test_the_menu_shows_categories_and_items_in_the_order_the_pub_set_with_their_prices(client, admin):
    drinks = await add_category(client, admin, "Výčepní piva", kind="drink", description="Čepujeme")
    food = await add_category(client, admin, "Hlavní jídla")
    await add_item(client, admin, drinks["id"], "Plzeň 12°", allergens=[1], prices=[{"label": "0,3 l", "price": 42}, {"label": "0,5 l", "price": 57.5}])
    await add_item(client, admin, drinks["id"], "Kozel 10°", prices=[{"label": "0,5 l", "price": 49}])
    await add_item(client, admin, food["id"], "Svíčková", description="knedlík", allergens=[9, 3, 1], prices=[{"label": "150 g", "price": 189}])

    resp = await client.get(f"{BASE}/offer")

    assert resp.status_code == 200
    body = resp.json()
    assert [(c["name"], c["kind"], c["description"]) for c in body["categories"]] == [("Výčepní piva", "drink", "Čepujeme"), ("Hlavní jídla", "food", "")]
    beers = body["categories"][0]["items"]
    assert [i["name"] for i in beers] == ["Plzeň 12°", "Kozel 10°"]
    assert beers[0]["prices"] == [{"label": "0,3 l", "price": 42.0}, {"label": "0,5 l", "price": 57.5}]
    assert beers[0]["allergens"] == [1] and beers[0]["is_available"] is True
    dish_ = body["categories"][1]["items"][0]
    assert (dish_["name"], dish_["description"], dish_["allergens"]) == ("Svíčková", "knedlík", [1, 3, 9])


async def test_inactive_categories_and_items_are_not_shown_but_unavailable_ones_are_marked(client, admin):
    shown = await add_category(client, admin, "Shown")
    hidden = await add_category(client, admin, "Hidden", is_active=False)
    await add_item(client, admin, shown["id"], "Visible")
    await add_item(client, admin, shown["id"], "Sold out", is_available=False)
    await add_item(client, admin, shown["id"], "Off the menu", is_active=False)
    await add_item(client, admin, hidden["id"], "In a hidden category")

    categories = (await client.get(f"{BASE}/offer")).json()["categories"]

    assert [c["name"] for c in categories] == ["Shown"]
    assert [(i["name"], i["is_available"]) for i in categories[0]["items"]] == [("Visible", True), ("Sold out", False)]


async def test_a_category_with_no_active_items_is_still_shown_empty(client, admin):
    await add_category(client, admin, "Zatím prázdná")

    assert [(c["name"], c["items"]) for c in (await client.get(f"{BASE}/offer")).json()["categories"]] == [("Zatím prázdná", [])]


async def test_the_offer_note_is_shown_with_the_menu(client, admin):
    await client.put(f"{BASE}/manage/settings", json={"offer_note": "Informace o alergenech Vám rádi sdělíme."}, headers=admin)

    assert (await client.get(f"{BASE}/offer")).json()["note"] == "Informace o alergenech Vám rádi sdělíme."


async def test_the_public_menu_carries_nothing_for_administrators(client, admin):
    category = await add_category(client, admin)
    await add_item(client, admin, category["id"])

    body = (await client.get(f"{BASE}/offer")).json()

    assert set(body["categories"][0]) == {"id", "name", "description", "kind", "items"}
    assert set(body["categories"][0]["items"][0]) == {"id", "name", "description", "allergens", "is_available", "prices"}


async def test_the_menu_can_be_read_without_signing_in_and_does_not_need_an_administrator(client):
    assert (await client.get(f"{BASE}/offer")).status_code == 200
    assert (await client.get(f"{BASE}/daily")).status_code == 200


# --- The lunch menu by week -------------------------------------------------------------------------------


async def test_the_week_of_today_is_served_by_default_from_monday_to_sunday(client):
    resp = await client.get(f"{BASE}/daily")

    assert resp.status_code == 200
    body = resp.json()
    assert (body["week_start"], body["week_end"], body["currency"]) == (MONDAY.isoformat(), (MONDAY + timedelta(days=6)).isoformat(), "CZK")
    assert [entry["day"] for entry in body["days"]] == [(MONDAY + timedelta(days=n)).isoformat() for n in range(7)]
    assert all(entry["items"] == [] for entry in body["days"])  # nothing published yet, still every day is listed


async def test_a_published_lunch_menu_is_shown_on_its_day_with_its_dishes_in_order(client, admin):
    await put_day(
        client,
        admin,
        day(0),
        dish("Gulášová polévka", "soup", amount="0,33 l", allergens=[1, 9]),
        dish("Svíčková", amount="150 g", description="knedlík", allergens=[3, 1], price=169),
        dish("Palačinky", "dessert", price=59.5),
    )

    body = (await client.get(f"{BASE}/daily")).json()

    today = next(entry for entry in body["days"] if entry["day"] == TODAY.isoformat())
    assert [(i["kind"], i["name"], i["amount"], i["price"]) for i in today["items"]] == [
        ("soup", "Gulášová polévka", "0,33 l", None),
        ("main", "Svíčková", "150 g", 169.0),
        ("dessert", "Palačinky", "", 59.5),
    ]
    assert today["items"][1]["allergens"] == [1, 3] and today["items"][1]["description"] == "knedlík"
    assert set(today["items"][0]) == {"id", "kind", "name", "description", "amount", "allergens", "price"}
    assert sum(len(entry["items"]) for entry in body["days"]) == 3


async def test_a_draft_is_never_shown_to_visitors(client, admin):
    await put_day(client, admin, day(1), dish("Secret"), published=False)
    await put_day(client, admin, day(2), dish("Public"))

    body = (await client.get(f"{BASE}/daily")).json()

    names = [i["name"] for entry in body["days"] for i in entry["items"]]
    assert names == ["Public"]


async def test_publishing_a_draft_shows_it_and_withdrawing_it_hides_it_again(client, admin):
    await put_day(client, admin, day(1), dish("Soon"), published=False)
    assert [i for entry in (await client.get(f"{BASE}/daily")).json()["days"] for i in entry["items"]] == []

    await put_day(client, admin, day(1), dish("Soon"), published=True)
    assert [i["name"] for entry in (await client.get(f"{BASE}/daily")).json()["days"] for i in entry["items"]] == ["Soon"]

    await put_day(client, admin, day(1), dish("Soon"), published=False)
    assert [i for entry in (await client.get(f"{BASE}/daily")).json()["days"] for i in entry["items"]] == []


async def test_another_week_is_asked_for_by_any_date_in_it(client, admin):
    await put_day(client, admin, day(7), dish("Next week"))  # the Wednesday after

    asked_by_its_wednesday = (await client.get(f"{BASE}/daily", params={"date": day(7).isoformat()})).json()
    asked_by_the_sunday = (await client.get(f"{BASE}/daily", params={"date": (MONDAY + timedelta(days=13)).isoformat()})).json()
    this_week = (await client.get(f"{BASE}/daily")).json()

    assert asked_by_its_wednesday["week_start"] == asked_by_the_sunday["week_start"] == (MONDAY + timedelta(days=7)).isoformat()
    assert [i["name"] for entry in asked_by_its_wednesday["days"] for i in entry["items"]] == ["Next week"]
    assert [i["name"] for entry in asked_by_the_sunday["days"] for i in entry["items"]] == ["Next week"]
    assert [i for entry in this_week["days"] for i in entry["items"]] == []


async def test_the_sunday_belongs_to_the_week_that_ends_with_it(client, admin):
    sunday = MONDAY + timedelta(days=6)
    await put_day(client, admin, sunday, dish("Sunday roast"))
    following_monday = MONDAY + timedelta(days=7)

    this_week = (await client.get(f"{BASE}/daily", params={"date": sunday.isoformat()})).json()
    next_week = (await client.get(f"{BASE}/daily", params={"date": following_monday.isoformat()})).json()

    assert this_week["week_start"] == MONDAY.isoformat() and this_week["days"][6]["items"][0]["name"] == "Sunday roast"
    assert next_week["week_start"] == following_monday.isoformat() and next_week["days"][0]["items"] == []


async def test_the_visitor_may_browse_a_configured_number_of_weeks_back_and_ahead(client):
    config = load_config()
    body = (await client.get(f"{BASE}/daily")).json()

    assert body["min_week_start"] == (MONDAY - timedelta(weeks=config.weeks_back)).isoformat()
    assert body["max_week_start"] == (MONDAY + timedelta(weeks=config.weeks_ahead)).isoformat()
    last = MONDAY + timedelta(weeks=config.weeks_ahead)
    first = MONDAY - timedelta(weeks=config.weeks_back)
    assert (await client.get(f"{BASE}/daily", params={"date": last.isoformat()})).status_code == 200
    assert (await client.get(f"{BASE}/daily", params={"date": first.isoformat()})).status_code == 200
    for outside in (last + timedelta(days=7), first - timedelta(days=1)):
        resp = await client.get(f"{BASE}/daily", params={"date": outside.isoformat()})
        assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"date": "out_of_range"}}


async def test_the_window_follows_a_changed_configuration_and_today(client, db_session):
    config = load_config()
    config.weeks_back = 0
    config.weeks_ahead = 0
    _app.dependency_overrides[get_config] = lambda: config

    assert (await client.get(f"{BASE}/daily")).status_code == 200
    assert (await client.get(f"{BASE}/daily", params={"date": day(7).isoformat()})).status_code == 422
    assert (await client.get(f"{BASE}/daily", params={"date": day(-7).isoformat()})).status_code == 422
    install_overrides(_app, db_session, today=day(7))  # a week later "today" is in the next week
    _app.dependency_overrides[get_config] = lambda: config
    assert (await client.get(f"{BASE}/daily", params={"date": day(7).isoformat()})).status_code == 200


async def test_a_malformed_date_is_refused(client):
    assert (await client.get(f"{BASE}/daily", params={"date": "tomorrow"})).status_code == 422


async def test_the_lunch_note_is_shown_with_the_week(client, admin):
    await client.put(f"{BASE}/manage/settings", json={"daily_note": "Podáváme Po-Pá 11-14 h."}, headers=admin)

    assert (await client.get(f"{BASE}/daily")).json()["note"] == "Podáváme Po-Pá 11-14 h."


async def test_a_deleted_lunch_menu_disappears_from_the_week(client, admin):
    await put_day(client, admin, day(1), dish("Gone"))
    await client.delete(f"{BASE}/manage/daily/{day(1).isoformat()}", headers=admin)

    assert [i for entry in (await client.get(f"{BASE}/daily")).json()["days"] for i in entry["items"]] == []
