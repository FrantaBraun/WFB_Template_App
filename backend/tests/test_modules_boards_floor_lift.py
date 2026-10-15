# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The zero floor of a post's value applies to the process, not only to the
number shown: a post that has sunk to 0 does not keep a hidden debt for the next
resonance to pay off - one resonance on an old post makes it 1, at once.

Resonances go through the module's real endpoint; the payment side is in
test_modules_boards_payments.py. Same setup as the other boards router tests."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import get_db
from app.models.user import User
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.boards.models import Category, Post, Resonance
from app.modules.boards.router import router as boards_router
from app.modules.boards.service import post_value

BASE = "/api/modules/boards"

_app = FastAPI()
_app.include_router(boards_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=20)
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


class Person:
    def __init__(self, user: User, token: str):
        self.user = user
        self.headers = {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_person(db_session, make_access_token):
    async def _make() -> Person:
        sub = uuid.uuid4()
        user = User(auth_sub=sub)
        db_session.add(user)
        await db_session.commit()
        return Person(user, make_access_token(sub=str(sub)))

    return _make


@pytest.fixture()
async def alice(make_person) -> Person:
    return await make_person()


@pytest.fixture()
async def bob(make_person) -> Person:
    return await make_person()


@pytest.fixture()
async def carol(make_person) -> Person:
    return await make_person()


async def _category(db_session, person, slug="general") -> Category:
    category = Category(title=slug.title(), slug=slug, description="d", created_by_id=person.user.id)
    db_session.add(category)
    await db_session.commit()
    return category


async def _post(db_session, person, category, title="p", days_old=0, **fields) -> Post:
    post = Post(
        category_id=category.id,
        author_id=person.user.id,
        title=title,
        body=f"Body of {title}",
        created_at=datetime.now(timezone.utc) - timedelta(days=days_old, hours=1 if days_old else 0),
        **fields,
    )
    db_session.add(post)
    await db_session.commit()
    return post


async def _resonate(client, person, post):
    resp = await client.post(f"{BASE}/posts/{post.id}/resonance", headers=person.headers)
    assert resp.status_code == 200
    return resp.json()


async def _board(client, slug="general"):
    return [(p["title"], p["value"]) for p in (await client.get(f"{BASE}/categories/{slug}/posts")).json()["items"]]


# --- A resonance shows in full ------------------------------------------------


async def test_one_resonance_on_an_old_post_shows_as_one_at_once(client, alice, bob, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=60)

    answer = await _resonate(client, bob, post)

    assert answer["value"] == 1
    assert await _board(client) == [("p", 1)]


async def test_a_resonance_on_an_old_post_that_already_had_some_shows_in_full(client, alice, bob, db_session):
    """Thirty days old with 5 resonances is 25 below zero - the 6th shows as 1, not as 'still 0'."""
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=30, resonance_count=5)

    answer = await _resonate(client, bob, post)

    assert answer["value"] == 1
    assert answer["resonance_count"] == 6


async def test_a_resonance_on_an_old_post_that_was_paid_for_shows_in_full(client, alice, bob, db_session):
    """$1 is 10 points, sixty days is 60: the post is 50 below zero, and the resonance is still worth 1."""
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=60, paid_cents=100)

    answer = await _resonate(client, bob, post)

    assert answer["value"] == 1
    await db_session.refresh(post)
    assert post.floor_lift == 50


async def test_every_further_resonance_adds_one(client, alice, bob, carol, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=60)

    values = [(await _resonate(client, person, post))["value"] for person in (bob, carol)]

    assert values == [1, 2]


async def test_a_post_that_is_above_zero_is_not_lifted_and_just_gains_a_point(client, alice, bob, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=10, resonance_count=50)

    answer = await _resonate(client, bob, post)

    assert answer["value"] == 41  # 50 - 10 + 1
    await db_session.refresh(post)
    assert post.floor_lift == 0


async def test_a_new_post_needs_no_lift(client, alice, bob, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))

    assert (await _resonate(client, bob, post))["value"] == 1
    await db_session.refresh(post)
    assert post.floor_lift == 0


async def test_the_lift_is_exactly_what_the_post_was_below_zero(client, alice, bob, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=30, resonance_count=5)

    await _resonate(client, bob, post)

    await db_session.refresh(post)
    assert post.floor_lift == 25  # 5 resonances - 30 days = -25


async def test_a_post_sunk_by_a_lift_already_given_is_lifted_again_only_by_what_it_sank_since(client, alice, bob, carol, db_session):
    """Revived at 60 days (lift 60), then left alone: the lift stays, and only the age since counts."""
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=60)
    await _resonate(client, bob, post)
    await db_session.refresh(post)
    assert (post.floor_lift, post.resonance_count) == (60, 1)

    # Ten days on, with nothing new, the post has lost 10 points and shows 0 - it is 9 below zero.
    later = datetime.now(timezone.utc) + timedelta(days=10)
    assert post_value(0, post.resonance_count, post.created_at, later, BoardsConfig(), post.floor_lift) == 0

    # The next resonance then lifts exactly that shortfall (9) and shows as 1 again.
    post.created_at = post.created_at - timedelta(days=10)  # the clock moved on, as far as the row can tell
    await db_session.commit()
    answer = await _resonate(client, carol, post)
    assert answer["value"] == 1
    await db_session.refresh(post)
    assert post.floor_lift == 69


# --- The board ----------------------------------------------------------------


async def test_a_revived_post_ranks_above_one_that_is_still_dead(client, alice, bob, db_session):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category, "dead", days_old=60)
    revived = await _post(db_session, alice, category, "revived", days_old=60)

    await _resonate(client, bob, revived)

    assert await _board(client) == [("revived", 1), ("dead", 0)]


async def test_the_board_stays_in_order_of_value_with_lifted_posts_among_the_others(client, alice, bob, carol, db_session):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category, "strong", days_old=2, resonance_count=40)
    old = await _post(db_session, alice, category, "old-revived", days_old=90)
    await _post(db_session, alice, category, "fresh")
    await _resonate(client, bob, old)
    await _resonate(client, carol, old)

    board = await _board(client)

    assert board == [("strong", 38), ("old-revived", 2), ("fresh", 0)]
    assert [value for _, value in board] == sorted((value for _, value in board), reverse=True)


async def test_the_lift_is_the_same_wherever_the_value_is_shown(client, alice, bob, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), days_old=40)
    await _resonate(client, bob, post)

    mine = (await client.get(f"{BASE}/me/posts", headers=alice.headers)).json()["items"]

    assert [p["value"] for p in mine] == [1]
