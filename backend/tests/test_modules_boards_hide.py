# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""An author hiding their own post and showing it again.

A hidden post is off the boards but otherwise untouched: what was paid for it
and its resonances stay, and its value keeps falling with age - hiding freezes
nothing. Same setup as the other boards router tests: the module's router on a
throwaway app, ASGITransport, tables emptied inside each test's rolled-back
transaction."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.database import get_db
from app.models.user import User
from app.modules.boards.config import BoardsConfig, ModerationConfig, get_config
from app.modules.boards.models import Category, Post, Resonance
from app.modules.boards.router import router as boards_router
from app.modules.notifications.models import Notification

BASE = "/api/modules/boards"
MANAGE = f"{BASE}/manage"

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
    async def _make(**fields) -> Person:
        sub = uuid.uuid4()
        user = User(auth_sub=sub, **fields)
        db_session.add(user)
        await db_session.commit()
        return Person(user, make_access_token(sub=str(sub)))

    return _make


@pytest.fixture()
async def alice(make_person) -> Person:
    """The author."""
    return await make_person()


@pytest.fixture()
async def bob(make_person) -> Person:
    return await make_person()


@pytest.fixture()
async def admin(make_person) -> Person:
    return await make_person(is_admin=True)


async def _category(db_session, person, slug="general", **fields) -> Category:
    category = Category(title=slug.title(), slug=slug, description="d", created_by_id=person.user.id, **fields)
    db_session.add(category)
    await db_session.commit()
    return category


async def _post(db_session, person, category, title="p", days_old=0, **fields) -> Post:
    post = Post(
        category_id=category.id,
        author_id=person.user.id,
        title=title,
        body=f"Body of {title}",
        created_at=datetime.now(timezone.utc) - timedelta(days=days_old, minutes=1),
        **fields,
    )
    db_session.add(post)
    await db_session.commit()
    return post


def _hide(client, person, post):
    return client.post(f"{BASE}/me/posts/{post.id}/hide", headers=person.headers)


def _show(client, person, post):
    return client.post(f"{BASE}/me/posts/{post.id}/show", headers=person.headers)


async def _board(client, slug="general"):
    return [p["title"] for p in (await client.get(f"{BASE}/categories/{slug}/posts")).json()["items"]]


async def _mine(client, person):
    return {p["title"]: p for p in (await client.get(f"{BASE}/me/posts", headers=person.headers)).json()["items"]}


# --- Hiding -------------------------------------------------------------------


async def test_hiding_and_showing_need_a_login(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    for action in ("hide", "show"):
        assert (await client.post(f"{BASE}/me/posts/{post.id}/{action}")).status_code == 401


async def test_a_hidden_post_leaves_the_boards_and_the_counts(client, alice, bob, db_session):
    category = await _category(db_session, alice)
    shown = await _post(db_session, alice, category, "shown")
    hidden = await _post(db_session, alice, category, "hidden")

    resp = await _hide(client, alice, hidden)

    assert resp.status_code == 200
    assert (resp.json()["title"], resp.json()["status"]) == ("hidden", "hidden")
    assert await _board(client) == ["shown"]
    assert (await client.get(f"{BASE}/categories/general")).json()["post_count"] == 1
    assert (await client.get(f"{BASE}/categories")).json()["items"][0]["post_count"] == 1
    # Nobody can resonate with what nobody can see - the author included.
    assert (await client.post(f"{BASE}/posts/{hidden.id}/resonance", headers=bob.headers)).status_code == 404
    assert (await client.post(f"{BASE}/posts/{hidden.id}/resonance", headers=alice.headers)).status_code == 404
    assert shown.status == "published"


async def test_the_author_still_finds_a_hidden_post_among_their_own(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), "mine", paid_cents=500)
    await _hide(client, alice, post)

    mine = (await _mine(client, alice))["mine"]

    assert (mine["status"], mine["moderation_reason"], mine["paid_cents"]) == ("hidden", None, 500)


async def test_hiding_changes_nothing_but_the_state(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), paid_cents=2500, resonance_count=3, days_old=4)
    created = post.created_at
    await _hide(client, alice, post)
    await _show(client, alice, post)

    await db_session.refresh(post)

    assert (post.status, post.paid_cents, post.resonance_count, post.created_at) == ("published", 2500, 3, created)
    assert (post.moderation_reason, post.moderated_at, post.moderated_by_id) == (None, None, None)


async def test_a_hidden_posts_value_keeps_falling_with_age(client, alice, db_session):
    """Same payment and resonances, ten days apart: ten points apart - while hidden too."""
    category = await _category(db_session, alice)
    newer = await _post(db_session, alice, category, "newer", paid_cents=2500, resonance_count=3, days_old=10)
    older = await _post(db_session, alice, category, "older", paid_cents=2500, resonance_count=3, days_old=20)
    before = await _mine(client, alice)
    await _hide(client, alice, newer)
    await _hide(client, alice, older)

    after = await _mine(client, alice)

    assert before["newer"]["value"] == 250 + 3 - 10
    assert (after["newer"]["value"], after["older"]["value"]) == (before["newer"]["value"], before["older"]["value"])
    assert after["newer"]["value"] - after["older"]["value"] == 10


async def test_showing_a_post_does_not_make_it_young_again(client, alice, db_session):
    """An old unpaid post sits below a fresh one; hiding and showing it does not lift it to the top."""
    category = await _category(db_session, alice)
    fresh = await _post(db_session, alice, category, "fresh")
    old = await _post(db_session, alice, category, "old", days_old=60)
    assert await _board(client) == ["fresh", "old"]

    await _hide(client, alice, old)
    await _show(client, alice, old)

    assert await _board(client) == ["fresh", "old"]
    assert fresh.status == "published"


async def test_a_shown_post_takes_the_place_its_value_gives_it(client, alice, db_session):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category, "middle", resonance_count=10)
    await _post(db_session, alice, category, "top", resonance_count=50)
    mine = await _post(db_session, alice, category, "mine", resonance_count=30)
    await _hide(client, alice, mine)
    assert await _board(client) == ["top", "middle"]

    resp = await _show(client, alice, mine)

    assert resp.json()["status"] == "published"
    assert await _board(client) == ["top", "mine", "middle"]
    assert (await client.get(f"{BASE}/categories/general")).json()["post_count"] == 3


async def test_hiding_and_showing_twice_change_nothing_more(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))

    shown_again = await _show(client, alice, post)  # already published
    hidden = await _hide(client, alice, post)
    hidden_again = await _hide(client, alice, post)

    assert [r.status_code for r in (shown_again, hidden, hidden_again)] == [200, 200, 200]
    assert (shown_again.json()["status"], hidden_again.json()["status"]) == ("published", "hidden")


# --- Whose post, whose account ------------------------------------------------


async def test_nobody_else_can_hide_or_show_a_post(client, alice, bob, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))

    theirs = await _hide(client, bob, post)
    missing = await client.post(f"{BASE}/me/posts/{uuid.uuid4()}/hide", headers=bob.headers)

    # Exactly like a post that does not exist: whose post it is is not for probing.
    assert (theirs.status_code, theirs.json()) == (missing.status_code, missing.json()) == (404, {"detail": "Post not found"})
    await db_session.refresh(post)
    assert post.status == "published"
    await _hide(client, alice, post)
    assert (await _show(client, bob, post)).status_code == 404
    await db_session.refresh(post)
    assert post.status == "hidden"


async def test_a_blocked_account_cannot_hide_or_show(client, make_person, db_session):
    blocked = await make_person(is_blocked=True)
    post = await _post(db_session, blocked, await _category(db_session, blocked))

    for action in (_hide, _show):
        resp = await action(client, blocked, post)
        assert (resp.status_code, resp.json()["detail"]["code"]) == (403, "account_blocked")


@pytest.mark.parametrize("status", ["blocked", "removed"])
async def test_a_post_taken_down_by_the_rules_can_be_neither_hidden_nor_shown(client, alice, db_session, status):
    post = await _post(db_session, alice, await _category(db_session, alice), status=status)

    for action in (_hide, _show):
        assert (await action(client, alice, post)).status_code == 409
    await db_session.refresh(post)
    assert post.status == status  # only an administrator can restore it


# --- Moderation does not stop at a hidden post --------------------------------


async def test_a_hidden_post_can_still_be_blocked_by_an_administrator(client, alice, admin, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice), "bad")
    await _hide(client, alice, post)

    resp = await client.post(f"{MANAGE}/posts/{post.id}/block", json={"reason": "Personal attacks."}, headers=admin.headers)

    assert resp.status_code == 200
    assert resp.json()["post"]["status"] == "blocked"
    notes = await db_session.scalars(select(Notification).where(Notification.user_id == alice.user.id))
    assert [n.message_key for n in notes] == ["boards:notification.postBlocked"]
    # The author cannot undo that by showing it.
    assert (await _show(client, alice, post)).status_code == 409
    await db_session.refresh(post)
    assert post.status == "blocked"


async def test_an_administrator_does_not_restore_what_the_author_hid(client, alice, admin, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    await _hide(client, alice, post)

    resp = await client.post(f"{MANAGE}/posts/{post.id}/restore", headers=admin.headers)

    assert resp.status_code == 409
    await db_session.refresh(post)
    assert post.status == "hidden"


async def test_hidden_posts_go_down_with_a_blocked_account(client, alice, admin, db_session):
    """Hiding is no way to keep a post past the block - and showing it afterwards would put it back."""
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=20, moderation=ModerationConfig(strike_limit=1))
    category = await _category(db_session, alice)
    bad = await _post(db_session, alice, category, "bad")
    hidden = await _post(db_session, alice, category, "hidden")
    shown = await _post(db_session, alice, category, "shown")
    await _hide(client, alice, hidden)

    resp = await client.post(f"{MANAGE}/posts/{bad.id}/block", json={"reason": "x"}, headers=admin.headers)

    assert resp.json()["account_blocked"] is True
    for post in (hidden, shown):
        await db_session.refresh(post)
    assert (hidden.status, shown.status) == ("removed", "removed")


async def test_administrators_find_hidden_posts_and_see_their_state(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category, "shown")
    hidden = await _post(db_session, alice, category, "hidden")
    await _hide(client, alice, hidden)

    only_hidden = await client.get(f"{MANAGE}/posts", params={"status": "hidden"}, headers=admin.headers)
    everything = await client.get(f"{MANAGE}/posts", params={"status": "all"}, headers=admin.headers)
    default = await client.get(f"{MANAGE}/posts", headers=admin.headers)

    assert [(p["title"], p["status"]) for p in only_hidden.json()["items"]] == [("hidden", "hidden")]
    assert {p["title"] for p in everything.json()["items"]} == {"shown", "hidden"}
    assert [p["title"] for p in default.json()["items"]] == ["shown"]  # the default is what is published


async def test_hiding_does_not_hide_a_post_from_the_authors_payment_overview(client, alice, db_session):
    from app.modules.boards.payments import POST_BOOST
    from app.modules.stripe_payment_gate.models import StripePayment

    post = await _post(db_session, alice, await _category(db_session, alice), "mine", paid_cents=500)
    db_session.add(
        StripePayment(
            id=uuid.uuid4(),
            user_id=alice.user.id,
            purpose=POST_BOOST,
            reference=str(post.id),
            amount=500,
            currency="usd",
            description="Boost",
            status="paid",
            paid_at=datetime.now(timezone.utc),
            extra={"points": 50},
        )
    )
    await db_session.commit()
    await _hide(client, alice, post)

    item = (await client.get(f"{BASE}/me/payments", headers=alice.headers)).json()["items"][0]

    assert (item["post_title"], item["post_status"]) == ("mine", "hidden")


async def test_nothing_is_created_or_lost_by_hiding(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    await _hide(client, alice, post)
    await _show(client, alice, post)

    assert await db_session.scalar(select(func.count()).select_from(Post)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 0
