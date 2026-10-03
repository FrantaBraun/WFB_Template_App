# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""An administrator blocking and restoring a whole category.

Same setup as test_modules_boards_moderation_router.py: the module's router on
a throwaway app, ASGITransport, and boards tables emptied inside each test's
rolled-back transaction."""

import uuid

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
    """Creates the categories."""
    return await make_person()


@pytest.fixture()
async def bob(make_person) -> Person:
    """Writes the posts."""
    return await make_person()


@pytest.fixture()
async def admin(make_person) -> Person:
    return await make_person(is_admin=True)


async def _category(db_session, person, slug="general", title=None, **fields) -> Category:
    category = Category(
        title=title or slug.title(), slug=slug, description="About " + slug, created_by_id=person.user.id, **fields
    )
    db_session.add(category)
    await db_session.commit()
    return category


async def _post(db_session, person, category, title="p", **fields) -> Post:
    post = Post(category_id=category.id, author_id=person.user.id, title=title, body=f"Body of {title}", **fields)
    db_session.add(post)
    await db_session.commit()
    return post


async def _block(client, admin, slug="general", reason="Breaks the rules: the whole board is about insulting people."):
    return await client.post(f"{MANAGE}/categories/{slug}/block", json={"reason": reason}, headers=admin.headers)


async def _notifications(db_session, person) -> list[Notification]:
    return list(await db_session.scalars(select(Notification).where(Notification.user_id == person.user.id)))


# --- Only administrators ------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/categories", None),
        ("post", "/categories/general/block", {"reason": "x"}),
        ("post", "/categories/general/restore", None),
    ],
)
async def test_category_moderation_is_for_administrators_only(client, alice, method, path, body):
    kwargs = {} if body is None else {"json": body}

    anonymous = await getattr(client, method)(MANAGE + path, **kwargs)
    ordinary = await getattr(client, method)(MANAGE + path, headers=alice.headers, **kwargs)

    assert (anonymous.status_code, ordinary.status_code) == (401, 403)


async def test_a_refused_attempt_changes_nothing(client, alice, db_session):
    category = await _category(db_session, alice)
    await client.post(f"{MANAGE}/categories/general/block", json={"reason": "x"}, headers=alice.headers)
    await db_session.refresh(category)
    assert category.status == "published"


# --- Blocking -----------------------------------------------------------------


async def test_blocking_a_category_records_why_and_tells_its_creator(client, alice, admin, db_session):
    category = await _category(db_session, alice, title="Insults")

    resp = await _block(client, admin, reason="The whole board is about insulting people.")

    assert resp.status_code == 200
    body = resp.json()
    assert (body["status"], body["slug"]) == ("blocked", "general")
    assert body["moderation_reason"] == "The whole board is about insulting people."
    assert body["moderated_at"] is not None
    assert body["created_by_id"] == str(alice.user.id)

    await db_session.refresh(category)
    assert (category.status, category.moderated_by_id) == ("blocked", admin.user.id)

    notification = (await _notifications(db_session, alice))[0]
    assert notification.message_key == "boards:notification.categoryBlocked"
    assert notification.message_params == {"title": "Insults", "reason": "The whole board is about insulting people."}
    assert notification.reference_id == category.id


async def test_blocking_needs_a_reason(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    for reason in ("", "   ", "x" * 1001):
        resp = await client.post(f"{MANAGE}/categories/general/block", json={"reason": reason}, headers=admin.headers)
        assert resp.status_code == 422
    await db_session.refresh(category)
    assert category.status == "published"
    assert await _notifications(db_session, alice) == []


async def test_a_category_is_blocked_only_once_and_only_if_it_exists(client, alice, admin, db_session):
    await _category(db_session, alice)
    assert (await _block(client, admin)).status_code == 200

    again = await _block(client, admin)
    missing = await _block(client, admin, slug="nowhere")

    assert (again.status_code, missing.status_code) == (409, 404)
    assert len(await _notifications(db_session, alice)) == 1  # the creator is not told twice


# --- What a blocked category looks like to everybody else ---------------------


async def test_a_blocked_category_is_gone_for_visitors(client, alice, bob, admin, db_session):
    category = await _category(db_session, alice)
    other = await _category(db_session, alice, slug="other")
    post = await _post(db_session, bob, category)
    await _block(client, admin)

    listed = await client.get(f"{BASE}/categories")
    one = await client.get(f"{BASE}/categories/general")
    posts = await client.get(f"{BASE}/categories/general/posts")

    assert [c["slug"] for c in listed.json()["items"]] == [other.slug]
    assert (one.status_code, posts.status_code) == (404, 404)
    assert post.status == "published"  # hidden by its category, not by its own state


async def test_nothing_can_be_posted_checked_or_resonated_in_a_blocked_category(client, alice, bob, admin, db_session):
    category = await _category(db_session, alice)
    post = await _post(db_session, bob, category)
    await _block(client, admin)
    draft = {"title": "A title", "body": "A text"}

    created = await client.post(f"{BASE}/categories/general/posts", json=draft, headers=bob.headers)
    checked = await client.post(f"{BASE}/categories/general/posts/check", json=draft, headers=bob.headers)
    resonated = await client.post(f"{BASE}/posts/{post.id}/resonance", headers=alice.headers)

    assert (created.status_code, checked.status_code, resonated.status_code) == (404, 404, 404)
    assert await db_session.scalar(select(func.count()).select_from(Resonance)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Post)) == 1


async def test_a_blocked_category_keeps_everything_in_it_and_is_no_strike_for_anybody(client, alice, bob, admin, db_session):
    """Hiding the board is not a verdict on its posts: they keep their state,
    what was paid for them and their resonances, and nobody's account is
    blocked - not the posts' authors', not the creator's, even at a limit of 1."""
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(
        page_size=20, moderation=ModerationConfig(strike_limit=1)
    )
    category = await _category(db_session, alice)
    post = await _post(db_session, bob, category, paid_cents=2500, resonance_count=4)
    await _block(client, admin)

    await db_session.refresh(post)
    await db_session.refresh(alice.user)
    await db_session.refresh(bob.user)

    assert (post.status, post.paid_cents, post.resonance_count) == ("published", 2500, 4)
    assert (alice.user.is_blocked, bob.user.is_blocked) == (False, False)
    assert await _notifications(db_session, bob) == []  # the posts' authors are not written to


async def test_the_address_of_a_blocked_category_stays_taken(client, alice, bob, admin, db_session):
    await _category(db_session, alice, title="General")
    await _block(client, admin)

    created = await client.post(
        f"{BASE}/categories", json={"title": "General", "description": "A new start"}, headers=bob.headers
    )

    assert created.json()["slug"] == "general-2"


async def test_a_post_in_a_blocked_category_is_marked_for_its_author_and_for_administrators(
    client, alice, bob, admin, db_session
):
    category = await _category(db_session, alice)
    await _post(db_session, bob, category, "mine")
    await _block(client, admin)

    mine = (await client.get(f"{BASE}/me/posts", headers=bob.headers)).json()["items"][0]
    seen_by_admin = (await client.get(f"{MANAGE}/posts", headers=admin.headers)).json()["items"][0]

    assert (mine["status"], mine["category_blocked"]) == ("published", True)
    assert seen_by_admin["category_blocked"] is True


async def test_a_post_in_an_ordinary_category_is_not_marked(client, alice, bob, admin, db_session):
    await _post(db_session, bob, await _category(db_session, alice), "mine")

    mine = (await client.get(f"{BASE}/me/posts", headers=bob.headers)).json()["items"][0]
    seen_by_admin = (await client.get(f"{MANAGE}/posts", headers=admin.headers)).json()["items"][0]

    assert (mine["category_blocked"], seen_by_admin["category_blocked"]) == (False, False)


async def test_administrators_still_reach_a_blocked_categorys_rules(client, alice, admin, db_session):
    await _category(db_session, alice, machine_rules={"keywords": [{"term": "life", "weight": 1}], "notes": ""})
    await _block(client, admin)

    read = await client.get(f"{MANAGE}/categories/general/rules", headers=admin.headers)
    rebuilt = await client.post(f"{MANAGE}/categories/general/rules/rebuild", headers=admin.headers)

    assert read.status_code == 200
    assert read.json()["rules"]["keywords"] == [{"term": "life", "weight": 1.0}]
    assert rebuilt.status_code == 200


# --- Restoring ----------------------------------------------------------------


async def test_restoring_brings_the_category_back_exactly_as_it_was(client, alice, bob, admin, db_session):
    category = await _category(db_session, alice, title="Insults")
    post = await _post(db_session, bob, category, paid_cents=2500, resonance_count=2)
    before = (await client.get(f"{BASE}/categories/general/posts")).json()["items"]
    await _block(client, admin)

    resp = await client.post(f"{MANAGE}/categories/general/restore", headers=admin.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert (body["status"], body["moderation_reason"], body["moderated_at"], body["post_count"]) == ("published", None, None, 1)
    await db_session.refresh(category)
    assert (category.status, category.moderated_by_id) == ("published", None)
    assert (await client.get(f"{BASE}/categories/general")).status_code == 200
    assert (await client.get(f"{BASE}/categories")).json()["items"][0]["slug"] == "general"
    after = (await client.get(f"{BASE}/categories/general/posts")).json()["items"]
    assert [(p["id"], p["resonance_count"]) for p in after] == [(p["id"], p["resonance_count"]) for p in before]
    await db_session.refresh(post)
    assert (post.paid_cents, post.resonance_count) == (2500, 2)


async def test_restoring_tells_the_creator_and_links_to_the_category(client, alice, admin, db_session):
    await _category(db_session, alice, title="Insults")
    await _block(client, admin)
    await client.post(f"{MANAGE}/categories/general/restore", headers=admin.headers)

    blocked, restored = sorted(await _notifications(db_session, alice), key=lambda n: n.message_key)

    assert restored.message_key == "boards:notification.categoryRestored"
    assert restored.message_params == {"title": "Insults"}
    assert restored.link_url == "/categories/general"
    assert blocked.message_key == "boards:notification.categoryBlocked"


async def test_only_a_blocked_category_can_be_restored(client, alice, admin, db_session):
    await _category(db_session, alice)

    unblocked = await client.post(f"{MANAGE}/categories/general/restore", headers=admin.headers)
    missing = await client.post(f"{MANAGE}/categories/nowhere/restore", headers=admin.headers)

    assert (unblocked.status_code, missing.status_code) == (409, 404)
    assert await _notifications(db_session, alice) == []


async def test_a_category_can_be_blocked_again_after_a_restore(client, alice, admin, db_session):
    await _category(db_session, alice)
    await _block(client, admin, reason="First reason.")
    await client.post(f"{MANAGE}/categories/general/restore", headers=admin.headers)

    resp = await _block(client, admin, reason="Second reason.")

    assert (resp.status_code, resp.json()["moderation_reason"]) == (200, "Second reason.")


# --- The administrators' list -------------------------------------------------


async def test_the_administrators_list_shows_blocked_categories_the_public_one_hides(client, alice, bob, admin, db_session):
    category = await _category(db_session, alice)
    await _category(db_session, alice, slug="other")
    await _post(db_session, bob, category, "one")
    await _post(db_session, bob, category, "gone", status="blocked")
    await _block(client, admin)

    everything = await client.get(f"{MANAGE}/categories", headers=admin.headers)
    only_blocked = await client.get(f"{MANAGE}/categories", params={"status": "blocked"}, headers=admin.headers)
    only_published = await client.get(f"{MANAGE}/categories", params={"status": "published"}, headers=admin.headers)

    assert {c["slug"] for c in everything.json()["items"]} == {"general", "other"}
    assert [c["slug"] for c in only_blocked.json()["items"]] == ["general"]
    assert [c["slug"] for c in only_published.json()["items"]] == ["other"]
    blocked = only_blocked.json()["items"][0]
    assert blocked["post_count"] == 1  # published posts only
    assert blocked["moderation_reason"]
    assert blocked["created_by_id"] == str(alice.user.id)


async def test_the_administrators_list_searches_titles_and_addresses_literally(client, alice, admin, db_session):
    await _category(db_session, alice, slug="philosophy", title="Everyday philosophy")
    await _category(db_session, alice, slug="tech-100", title="Technology")

    by_title = await client.get(f"{MANAGE}/categories", params={"q": "PHILO"}, headers=admin.headers)
    by_slug = await client.get(f"{MANAGE}/categories", params={"q": "tech-1"}, headers=admin.headers)
    percent = await client.get(f"{MANAGE}/categories", params={"q": "%"}, headers=admin.headers)

    assert [c["slug"] for c in by_title.json()["items"]] == ["philosophy"]
    assert [c["slug"] for c in by_slug.json()["items"]] == ["tech-100"]
    assert percent.json()["items"] == []


async def test_the_administrators_list_pages(client, alice, admin, db_session):
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=2)
    for number in range(3):
        await _category(db_session, alice, slug=f"c{number}")

    first = (await client.get(f"{MANAGE}/categories", headers=admin.headers)).json()
    second = (await client.get(f"{MANAGE}/categories", params={"offset": 2}, headers=admin.headers)).json()

    assert (len(first["items"]), first["has_more"]) == (2, True)
    assert (len(second["items"]), second["has_more"]) == (1, False)
    assert {c["slug"] for c in first["items"] + second["items"]} == {"c0", "c1", "c2"}
