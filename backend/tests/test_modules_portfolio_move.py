# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for POST /manage/items/{id}/move: swapping an item with its
neighbour in the order the public list uses, the no-ops at both ends, and
the renumbering that keeps a swap meaningful when two items share a
sort_order.

Same setup as test_modules_portfolio_router.py: a throwaway FastAPI app with
just this module's router, ASGITransport, and a rolled-back db_session whose
table is emptied inside the transaction first (the migration seeds rows)."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import get_db
from app.models.user import User
from app.modules.portfolio.models import PortfolioItem
from app.modules.portfolio.router import router as portfolio_router

BASE = "/api/modules/portfolio"

_app = FastAPI()
_app.include_router(portfolio_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await db_session.execute(delete(PortfolioItem))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
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


async def _create(client, admin, slug: str, **fields) -> dict:
    resp = await client.post(
        f"{BASE}/manage/items",
        json={"slug": slug, "title_cs": slug.upper(), "summary_cs": "Popis.", **fields},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _move(client, admin, item: dict, direction: str):
    return await client.post(f"{BASE}/manage/items/{item['id']}/move", json={"direction": direction}, headers=admin)


async def _order(client, admin) -> list[str]:
    return [i["slug"] for i in (await client.get(f"{BASE}/manage/items", headers=admin)).json()]


async def _orders(client, admin) -> list[tuple[str, int]]:
    return [(i["slug"], i["sort_order"]) for i in (await client.get(f"{BASE}/manage/items", headers=admin)).json()]


async def _public_order(client) -> list[str]:
    return [i["slug"] for i in (await client.get(f"{BASE}/items")).json()]


@pytest.fixture()
async def abc(client, admin):
    """Three items in the order a, b, c with sort_order 1, 2, 3."""
    for slug in ("p-a", "p-b", "p-c"):
        await _create(client, admin, slug)
    return (await client.get(f"{BASE}/manage/items", headers=admin)).json()


async def test_move_up_swaps_with_the_previous_item(client, admin, abc):
    a, b, c = abc

    resp = await _move(client, admin, b, "up")

    assert resp.status_code == 200
    assert await _orders(client, admin) == [("p-b", 1), ("p-a", 2), ("p-c", 3)]


async def test_move_down_swaps_with_the_next_item(client, admin, abc):
    a, b, c = abc

    resp = await _move(client, admin, b, "down")

    assert resp.status_code == 200
    assert await _orders(client, admin) == [("p-a", 1), ("p-c", 2), ("p-b", 3)]


async def test_the_answer_is_the_whole_list_in_its_new_order(client, admin, abc):
    a, b, c = abc

    resp = await _move(client, admin, c, "up")

    assert [i["slug"] for i in resp.json()] == ["p-a", "p-c", "p-b"]
    assert resp.json() == (await client.get(f"{BASE}/manage/items", headers=admin)).json()
    assert {"id", "slug", "title_cs", "sort_order", "published"} <= set(resp.json()[0])


async def test_moving_twice_in_a_row_walks_an_item_to_the_top(client, admin, abc):
    a, b, c = abc

    await _move(client, admin, c, "up")
    await _move(client, admin, c, "up")

    assert await _order(client, admin) == ["p-c", "p-a", "p-b"]


async def test_up_then_down_is_back_where_it_started(client, admin, abc):
    a, b, c = abc

    await _move(client, admin, b, "up")
    await _move(client, admin, b, "down")

    assert await _orders(client, admin) == [("p-a", 1), ("p-b", 2), ("p-c", 3)]


async def test_the_first_item_up_is_a_harmless_no_op(client, admin, abc):
    a, b, c = abc

    resp = await _move(client, admin, a, "up")

    assert resp.status_code == 200
    assert [i["slug"] for i in resp.json()] == ["p-a", "p-b", "p-c"]
    assert await _orders(client, admin) == [("p-a", 1), ("p-b", 2), ("p-c", 3)]


async def test_the_last_item_down_is_a_harmless_no_op(client, admin, abc):
    a, b, c = abc

    resp = await _move(client, admin, c, "down")

    assert resp.status_code == 200
    assert await _orders(client, admin) == [("p-a", 1), ("p-b", 2), ("p-c", 3)]


async def test_a_single_item_stays_put(client, admin):
    only = await _create(client, admin, "jediny")

    assert (await _move(client, admin, only, "up")).status_code == 200
    assert (await _move(client, admin, only, "down")).status_code == 200
    assert await _orders(client, admin) == [("jediny", 1)]


async def test_a_no_op_does_not_touch_the_other_items(client, admin):
    """Even when sort_orders tie: nothing is renumbered unless something moves."""
    first = await _create(client, admin, "first", sort_order=5)
    await _create(client, admin, "second", sort_order=5)
    by_id = sorted((await client.get(f"{BASE}/manage/items", headers=admin)).json(), key=lambda i: uuid.UUID(i["id"]))
    top = by_id[0]

    await _move(client, admin, top, "up")

    assert [o for _, o in await _orders(client, admin)] == [5, 5]
    assert first["sort_order"] == 5


async def test_the_public_list_follows_a_move(client, admin, abc):
    a, b, c = abc

    await _move(client, admin, c, "up")

    assert await _public_order(client) == ["p-a", "p-c", "p-b"]


async def test_only_the_two_swapped_items_change_when_the_orders_are_distinct(client, admin):
    for slug, order in (("p-a", 10), ("p-b", 20), ("p-c", 30), ("p-d", 40)):
        await _create(client, admin, slug, sort_order=order)
    items = {i["slug"]: i for i in (await client.get(f"{BASE}/manage/items", headers=admin)).json()}

    await _move(client, admin, items["p-c"], "up")

    assert await _orders(client, admin) == [("p-a", 10), ("p-c", 20), ("p-b", 30), ("p-d", 40)]


async def test_gaps_in_the_sort_orders_do_not_matter(client, admin):
    for slug, order in (("p-a", 0), ("p-b", 500), ("p-c", 1000)):
        await _create(client, admin, slug, sort_order=order)
    items = {i["slug"]: i for i in (await client.get(f"{BASE}/manage/items", headers=admin)).json()}

    await _move(client, admin, items["p-c"], "up")

    assert await _orders(client, admin) == [("p-a", 0), ("p-c", 500), ("p-b", 1000)]


async def test_an_unpublished_item_is_a_neighbour_too(client, admin):
    """The editor's list shows it, so the swap must be visible there."""
    await _create(client, admin, "p-a")
    await _create(client, admin, "p-b", published=False)
    await _create(client, admin, "p-c")
    items = {i["slug"]: i for i in (await client.get(f"{BASE}/manage/items", headers=admin)).json()}

    await _move(client, admin, items["p-c"], "up")

    assert await _order(client, admin) == ["p-a", "p-c", "p-b"]
    assert await _public_order(client) == ["p-a", "p-c"]


async def test_an_unpublished_item_can_itself_be_moved(client, admin):
    await _create(client, admin, "p-a")
    await _create(client, admin, "p-b", published=False)
    items = {i["slug"]: i for i in (await client.get(f"{BASE}/manage/items", headers=admin)).json()}

    resp = await _move(client, admin, items["p-b"], "up")

    assert resp.status_code == 200
    assert await _order(client, admin) == ["p-b", "p-a"]


# --- Items that share a sort_order --------------------------------------------


async def test_items_with_the_same_sort_order_are_renumbered_so_a_move_takes_effect(client, admin):
    for slug in ("p-x", "p-y", "p-z"):
        await _create(client, admin, slug, sort_order=5)
    shown = (await client.get(f"{BASE}/manage/items", headers=admin)).json()
    first, second, third = shown  # display order: sort_order, then id

    resp = await _move(client, admin, third, "up")

    assert resp.status_code == 200
    expected = [first["slug"], third["slug"], second["slug"]]
    assert await _orders(client, admin) == [(expected[0], 1), (expected[1], 2), (expected[2], 3)]
    assert await _public_order(client) == expected


async def test_moving_down_among_equal_sort_orders(client, admin):
    for slug in ("p-x", "p-y", "p-z"):
        await _create(client, admin, slug, sort_order=0)
    first, second, third = (await client.get(f"{BASE}/manage/items", headers=admin)).json()

    await _move(client, admin, first, "down")

    assert await _order(client, admin) == [second["slug"], first["slug"], third["slug"]]
    assert sorted(o for _, o in await _orders(client, admin)) == [1, 2, 3]


async def test_a_partial_tie_is_normalised_and_the_display_order_is_kept(client, admin):
    await _create(client, admin, "p-a", sort_order=1)
    await _create(client, admin, "p-b", sort_order=2)
    await _create(client, admin, "p-c", sort_order=2)
    await _create(client, admin, "p-d", sort_order=3)
    before = (await client.get(f"{BASE}/manage/items", headers=admin)).json()
    assert [i["slug"] for i in before][0] == "p-a" and [i["slug"] for i in before][3] == "p-d"

    # move the last item up: it must jump over exactly one neighbour
    resp = await _move(client, admin, before[3], "up")

    after = [i["slug"] for i in resp.json()]
    assert after == [before[0]["slug"], before[1]["slug"], before[3]["slug"], before[2]["slug"]]
    assert [i["sort_order"] for i in resp.json()] == [1, 2, 3, 4]


async def test_appending_after_a_tie_still_goes_last(client, admin):
    await _create(client, admin, "p-a", sort_order=5)
    await _create(client, admin, "p-b", sort_order=5)

    last = await _create(client, admin, "p-c")

    assert last["sort_order"] == 6
    assert (await _order(client, admin))[-1] == "p-c"


# --- Errors --------------------------------------------------------------------


async def test_moving_an_unknown_item_is_404(client, admin, abc):
    resp = await client.post(f"{BASE}/manage/items/{uuid.uuid4()}/move", json={"direction": "up"}, headers=admin)

    assert resp.status_code == 404
    assert await _orders(client, admin) == [("p-a", 1), ("p-b", 2), ("p-c", 3)]


@pytest.mark.parametrize("body", [{"direction": "left"}, {"direction": ""}, {"direction": "UP"}, {}, {"direction": None}])
async def test_an_invalid_direction_is_422_and_changes_nothing(client, admin, abc, body):
    a, b, c = abc

    resp = await client.post(f"{BASE}/manage/items/{b['id']}/move", json=body, headers=admin)

    assert resp.status_code == 422
    assert await _orders(client, admin) == [("p-a", 1), ("p-b", 2), ("p-c", 3)]


async def test_a_malformed_id_is_422(client, admin):
    resp = await client.post(f"{BASE}/manage/items/nope/move", json={"direction": "up"}, headers=admin)

    assert resp.status_code == 422
