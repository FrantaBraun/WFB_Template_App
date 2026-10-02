# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the boards module's endpoints: categories, posts, resonances.

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` (whether the module is mounted on the real app
depends on the branch's backend/modules.json - see
test_modules_notifications_router.py). ASGITransport keeps the JWT
dependency chain and db_session on one event loop. Each test starts from
empty boards tables (inside its own rolled-back transaction), so assertions
on whole listings don't depend on what the database holds."""

import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.database import get_db
from app.models.user import User
from app.modules.boards import service
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.boards.models import Category, Post, Resonance
from app.modules.boards.router import router as boards_router

BASE = "/api/modules/boards"

# The package's `router` attribute is the APIRouter (see boards/__init__.py),
# which shadows the submodule for dotted-string monkeypatch targets.
router_module = sys.modules["app.modules.boards.router"]

_boards_app = FastAPI()
_boards_app.include_router(boards_router, prefix=BASE)

CATEGORY_KEYS = {"id", "title", "slug", "description", "post_count", "created_at"}
POST_KEYS = {"id", "title", "body", "value", "resonance_count", "resonated_by_me", "mine", "paid_cents", "created_at"}


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _boards_app.dependency_overrides[get_db] = lambda: db_session
    _boards_app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=20)
    yield
    _boards_app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_boards_app), base_url="http://test") as ac:
        yield ac


class Person:
    """A signed-in user: the local row plus ready-made auth headers."""

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


async def _seed_category(db_session, person: Person, slug: str = "general", title: str | None = None) -> Category:
    category = Category(title=title or slug, slug=slug, description="About " + slug, created_by_id=person.user.id)
    db_session.add(category)
    await db_session.commit()
    return category


async def _seed_post(db_session, person: Person, category: Category, title: str, **fields) -> Post:
    post = Post(category_id=category.id, author_id=person.user.id, title=title, body=f"Body of {title}", **fields)
    db_session.add(post)
    await db_session.commit()
    return post


def _ago(days: int = 0) -> datetime:
    """`days` whole days old with an hour to spare, so the age floors to
    exactly `days` even if a test straddles midnight."""
    return datetime.now(timezone.utc) - timedelta(days=days, hours=1) if days else datetime.now(timezone.utc)


def _titles(page) -> list[str]:
    return [item["title"] for item in page["items"]]


def _no_trace_of(person: Person, resp) -> None:
    assert str(person.user.id) not in resp.text
    assert str(person.user.auth_sub) not in resp.text


# --- Creating categories ------------------------------------------------------


async def test_creating_a_category_needs_a_login(client):
    resp = await client.post(f"{BASE}/categories", json={"title": "T", "description": "D"})
    assert resp.status_code == 401


async def test_creating_a_category_generates_the_slug_and_hides_the_creator(client, alice):
    resp = await client.post(
        f"{BASE}/categories", json={"title": "Rezervace Salónu", "description": "Co sem patří"}, headers=alice.headers
    )

    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == CATEGORY_KEYS
    assert body["slug"] == "rezervace-salonu"
    assert body["title"] == "Rezervace Salónu"
    assert body["description"] == "Co sem patří"
    assert body["post_count"] == 0
    _no_trace_of(alice, resp)


async def test_the_same_title_gets_a_numbered_slug(client, alice, bob):
    slugs = []
    for person in (alice, bob, alice):
        resp = await client.post(
            f"{BASE}/categories", json={"title": "Ideas", "description": "d"}, headers=person.headers
        )
        slugs.append(resp.json()["slug"])

    assert slugs == ["ideas", "ideas-2", "ideas-3"]


async def test_a_category_cannot_take_the_slug_of_the_new_category_page(client, alice):
    resp = await client.post(f"{BASE}/categories", json={"title": "New", "description": "d"}, headers=alice.headers)
    assert resp.json()["slug"] == "new-2"


async def test_the_slug_is_retried_when_another_request_took_it_first(client, alice, db_session, monkeypatch):
    """unique_slug() can hand two simultaneous requests the same slug; the
    unique index rejects the second and the endpoint picks again."""
    await _seed_category(db_session, alice, slug="race")
    answers = iter(["race"])  # a stale answer first, then the real thing

    async def stale_then_real(db, title):
        return next(answers, None) or await service.unique_slug(db, title)

    monkeypatch.setattr(router_module, "unique_slug", stale_then_real)

    resp = await client.post(f"{BASE}/categories", json={"title": "Race", "description": "d"}, headers=alice.headers)

    assert resp.status_code == 201
    assert resp.json()["slug"] == "race-2"


async def test_giving_up_on_a_slug_after_repeated_collisions_is_a_409(client, alice, db_session, monkeypatch):
    await _seed_category(db_session, alice, slug="taken")

    async def always_taken(db, title):
        return "taken"

    monkeypatch.setattr(router_module, "unique_slug", always_taken)

    resp = await client.post(f"{BASE}/categories", json={"title": "Taken", "description": "d"}, headers=alice.headers)

    assert resp.status_code == 409
    assert (await db_session.scalar(select(func.count()).select_from(Category))) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "description": "d"},
        {"title": "   ", "description": "d"},
        {"title": "T", "description": ""},
        {"title": "T", "description": " \n "},
        {"title": "x" * 121, "description": "d"},
        {"title": "T", "description": "x" * 4097},
        {"title": "Two\nlines", "description": "d"},
        {"title": "T", "description": "nul\x00byte"},
        {"title": "T", "description": "d", "created_by_id": str(uuid.uuid4())},
        {"title": "T"},
        {"title": 5, "description": "d"},
    ],
)
async def test_an_invalid_category_is_refused(client, alice, db_session, payload):
    resp = await client.post(f"{BASE}/categories", json=payload, headers=alice.headers)

    assert resp.status_code == 422
    assert (await db_session.scalar(select(func.count()).select_from(Category))) == 0


async def test_category_text_limits_are_in_characters_not_bytes(client, alice):
    """4096 characters of description and 120 of title are fine even when
    each character is an emoji (4 bytes in UTF-8, 2 UTF-16 units in JS)."""
    resp = await client.post(
        f"{BASE}/categories", json={"title": "😀" * 120, "description": "🧠" * 4096}, headers=alice.headers
    )
    assert resp.status_code == 201
    assert resp.json()["slug"] == "category"

    too_long = await client.post(
        f"{BASE}/categories", json={"title": "ok", "description": "🧠" * 4097}, headers=alice.headers
    )
    assert too_long.status_code == 422


async def test_category_text_is_trimmed(client, alice):
    resp = await client.post(
        f"{BASE}/categories", json={"title": "  Padded  ", "description": "\n  desc \n"}, headers=alice.headers
    )
    assert resp.json()["title"] == "Padded"
    assert resp.json()["description"] == "desc"


# --- Reading categories -------------------------------------------------------


async def test_categories_are_public_busiest_first_then_by_title(client, alice, db_session):
    quiet_b = await _seed_category(db_session, alice, "b-quiet", title="B quiet")
    quiet_a = await _seed_category(db_session, alice, "a-quiet", title="A quiet")
    busy = await _seed_category(db_session, alice, "busy", title="Busy")
    await _seed_post(db_session, alice, busy, "p1")
    await _seed_post(db_session, alice, busy, "p2")
    await _seed_post(db_session, alice, quiet_b, "p3")
    assert quiet_a is not None

    resp = await client.get(f"{BASE}/categories")

    assert resp.status_code == 200
    page = resp.json()
    assert [(c["slug"], c["post_count"]) for c in page["items"]] == [("busy", 2), ("b-quiet", 1), ("a-quiet", 0)]
    assert page["has_more"] is False
    assert all(set(c) == CATEGORY_KEYS for c in page["items"])
    _no_trace_of(alice, resp)


async def test_categories_page_by_page_size(client, alice, db_session):
    _boards_app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=2)
    for slug in ("c1", "c2", "c3", "c4", "c5"):
        await _seed_category(db_session, alice, slug)

    first = (await client.get(f"{BASE}/categories")).json()
    second = (await client.get(f"{BASE}/categories", params={"offset": 2})).json()
    third = (await client.get(f"{BASE}/categories", params={"offset": 4})).json()

    assert [c["slug"] for c in first["items"] + second["items"] + third["items"]] == ["c1", "c2", "c3", "c4", "c5"]
    assert (first["has_more"], second["has_more"], third["has_more"]) == (True, True, False)


async def test_one_category_by_slug(client, alice, db_session):
    category = await _seed_category(db_session, alice, "general", title="General")
    await _seed_post(db_session, alice, category, "p1")

    resp = await client.get(f"{BASE}/categories/general")

    assert resp.status_code == 200
    assert resp.json()["title"] == "General"
    assert resp.json()["post_count"] == 1
    assert set(resp.json()) == CATEGORY_KEYS
    assert (await client.get(f"{BASE}/categories/missing")).status_code == 404


# --- Creating posts -----------------------------------------------------------


async def test_posting_needs_a_login(client, alice, db_session):
    await _seed_category(db_session, alice)
    resp = await client.post(f"{BASE}/categories/general/posts", json={"title": "T", "body": "B"})
    assert resp.status_code == 401


async def test_posting_to_a_missing_category_is_a_404(client, alice):
    resp = await client.post(f"{BASE}/categories/nope/posts", json={"title": "T", "body": "B"}, headers=alice.headers)
    assert resp.status_code == 404


async def test_a_new_post_starts_at_zero_and_shows_no_author(client, alice, db_session):
    category = await _seed_category(db_session, alice)

    resp = await client.post(
        f"{BASE}/categories/general/posts", json={"title": "Hello", "body": "First thought 💡"}, headers=alice.headers
    )

    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == POST_KEYS
    assert (body["title"], body["body"]) == ("Hello", "First thought 💡")
    assert (body["value"], body["resonance_count"], body["resonated_by_me"]) == (0, 0, False)
    _no_trace_of(alice, resp)

    stored = (await db_session.scalars(select(Post).where(Post.category_id == category.id))).one()
    assert stored.author_id == alice.user.id  # kept for moderation, never shown
    assert stored.paid_cents == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "body": "B"},
        {"title": "T", "body": ""},
        {"title": "T", "body": "   \n  "},
        {"title": "x" * 121, "body": "B"},
        {"title": "T", "body": "x" * 2049},
        {"title": "Two\nlines", "body": "B"},
        {"title": "T", "body": "nul\x00byte"},
        {"title": "T", "body": "B", "author_id": str(uuid.uuid4())},
        {"title": "T", "body": "B", "paid_cents": 100000},
        {"title": "T"},
    ],
)
async def test_an_invalid_post_is_refused(client, alice, db_session, payload):
    await _seed_category(db_session, alice)

    resp = await client.post(f"{BASE}/categories/general/posts", json=payload, headers=alice.headers)

    assert resp.status_code == 422
    assert (await db_session.scalar(select(func.count()).select_from(Post))) == 0


async def test_the_post_text_limit_is_2048_characters_counting_spaces_and_emoji(client, alice, db_session):
    await _seed_category(db_session, alice)
    url = f"{BASE}/categories/general/posts"

    exact = await client.post(url, json={"title": "T", "body": "a b " * 512}, headers=alice.headers)
    emoji = await client.post(url, json={"title": "T", "body": "💡" * 2048}, headers=alice.headers)
    over = await client.post(url, json={"title": "T", "body": "a" * 2048 + "b"}, headers=alice.headers)

    # "a b " * 512 is 2048 characters, but its trailing space is trimmed.
    assert (exact.status_code, emoji.status_code, over.status_code) == (201, 201, 422)


async def test_line_breaks_are_normalized_and_counted_once(client, alice, db_session):
    await _seed_category(db_session, alice)

    resp = await client.post(
        f"{BASE}/categories/general/posts", json={"title": "T", "body": "one\r\ntwo\rthree"}, headers=alice.headers
    )

    assert resp.json()["body"] == "one\ntwo\nthree"

    # Raw length 2102 but 1402 once CRLF counts as one line break: fits.
    fits = await client.post(
        f"{BASE}/categories/general/posts", json={"title": "T", "body": "a\r\n" * 700 + "ab"}, headers=alice.headers
    )
    # 2049 characters with the line breaks counted once: one too many.
    over = await client.post(
        f"{BASE}/categories/general/posts", json={"title": "T", "body": "a\r\n" * 1024 + "b"}, headers=alice.headers
    )
    assert (fits.status_code, over.status_code) == (201, 422)


# --- Reading and ordering posts -----------------------------------------------


async def test_posts_are_public_and_ordered_by_value(client, alice, db_session):
    """Values: paid $10 = 100; 60 resonances a day old = 59; $10 paid 60
    days ago = 40; brand new = 0; unloved for 5 days = -5."""
    category = await _seed_category(db_session, alice)
    await _seed_post(db_session, alice, category, "stale", created_at=_ago(5))
    await _seed_post(db_session, alice, category, "fresh")
    await _seed_post(db_session, alice, category, "old-paid", paid_cents=1000, created_at=_ago(60))
    await _seed_post(db_session, alice, category, "resonant", resonance_count=60, created_at=_ago(1))
    await _seed_post(db_session, alice, category, "paid", paid_cents=1000)

    resp = await client.get(f"{BASE}/categories/general/posts")

    assert resp.status_code == 200
    page = resp.json()
    assert [(p["title"], p["value"]) for p in page["items"]] == [
        ("paid", 100),
        ("resonant", 59),
        ("old-paid", 40),
        ("fresh", 0),
        ("stale", -5),
    ]
    assert page["has_more"] is False
    assert all(set(p) == POST_KEYS for p in page["items"])
    _no_trace_of(alice, resp)


async def test_an_unpaid_unresonated_post_is_worth_less_each_day(client, alice, db_session):
    category = await _seed_category(db_session, alice)
    await _seed_post(db_session, alice, category, "three-days", created_at=_ago(3))

    value = (await client.get(f"{BASE}/categories/general/posts")).json()["items"][0]["value"]

    assert value == -3


async def test_only_posts_of_that_category_are_listed(client, alice, db_session):
    one = await _seed_category(db_session, alice, "one")
    two = await _seed_category(db_session, alice, "two")
    await _seed_post(db_session, alice, one, "in-one")
    await _seed_post(db_session, alice, two, "in-two")

    assert _titles((await client.get(f"{BASE}/categories/one/posts")).json()) == ["in-one"]
    assert _titles((await client.get(f"{BASE}/categories/two/posts")).json()) == ["in-two"]
    assert (await client.get(f"{BASE}/categories/missing/posts")).status_code == 404


async def test_posts_page_by_page_size_without_gaps_or_repeats(client, alice, db_session):
    _boards_app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=3)
    category = await _seed_category(db_session, alice)
    for resonances in range(7):
        await _seed_post(db_session, alice, category, f"r{resonances}", resonance_count=resonances)

    url = f"{BASE}/categories/general/posts"
    pages = [(await client.get(url, params={"offset": offset})).json() for offset in (0, 3, 6)]

    assert [_titles(p) for p in pages] == [["r6", "r5", "r4"], ["r3", "r2", "r1"], ["r0"]]
    assert [p["has_more"] for p in pages] == [True, True, False]
    assert (await client.get(url, params={"offset": 9})).json() == {"items": [], "has_more": False}


async def test_a_negative_offset_is_refused(client, alice, db_session):
    await _seed_category(db_session, alice)
    assert (await client.get(f"{BASE}/categories/general/posts", params={"offset": -1})).status_code == 422


async def test_a_new_post_lands_among_the_others_by_its_value(client, alice, db_session):
    """Posting is just another post at value 0: above the unloved, below
    anything with points."""
    category = await _seed_category(db_session, alice)
    await _seed_post(db_session, alice, category, "liked", resonance_count=3)
    await _seed_post(db_session, alice, category, "unloved", created_at=_ago(2))

    await client.post(f"{BASE}/categories/general/posts", json={"title": "mine", "body": "b"}, headers=alice.headers)

    assert _titles((await client.get(f"{BASE}/categories/general/posts")).json()) == ["liked", "mine", "unloved"]


# --- Resonance ----------------------------------------------------------------


async def test_resonating_needs_a_login(client, alice, db_session):
    post = await _seed_post(db_session, alice, await _seed_category(db_session, alice), "p")
    assert (await client.post(f"{BASE}/posts/{post.id}/resonance")).status_code == 401


async def test_resonating_with_a_missing_post_is_a_404(client, bob):
    resp = await client.post(f"{BASE}/posts/{uuid.uuid4()}/resonance", headers=bob.headers)
    assert resp.status_code == 404


async def test_a_resonance_adds_one_point_and_shows_only_a_count(client, alice, bob, db_session):
    post = await _seed_post(db_session, alice, await _seed_category(db_session, alice), "p")

    resp = await client.post(f"{BASE}/posts/{post.id}/resonance", headers=bob.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == POST_KEYS
    assert (body["resonance_count"], body["value"], body["resonated_by_me"]) == (1, 1, True)
    _no_trace_of(bob, resp)
    _no_trace_of(alice, resp)


async def test_a_user_can_resonate_with_a_post_only_once(client, alice, bob, db_session):
    post = await _seed_post(db_session, alice, await _seed_category(db_session, alice), "p")
    url = f"{BASE}/posts/{post.id}/resonance"

    first = await client.post(url, headers=bob.headers)
    second = await client.post(url, headers=bob.headers)

    assert (first.status_code, second.status_code) == (200, 409)
    await db_session.refresh(post)
    assert post.resonance_count == 1


async def test_resonances_of_different_users_add_up_and_match_the_rows(client, alice, bob, make_person, db_session):
    carol = await make_person()
    post = await _seed_post(db_session, alice, await _seed_category(db_session, alice), "p")

    for person in (alice, bob, carol):
        assert (await client.post(f"{BASE}/posts/{post.id}/resonance", headers=person.headers)).status_code == 200

    await db_session.refresh(post)
    rows = await db_session.scalar(select(func.count()).select_from(Resonance).where(Resonance.post_id == post.id))
    assert post.resonance_count == rows == 3


async def test_resonating_moves_a_post_up_the_board(client, alice, bob, db_session):
    category = await _seed_category(db_session, alice)
    low = await _seed_post(db_session, alice, category, "low")
    await _seed_post(db_session, alice, category, "high", resonance_count=1)
    url = f"{BASE}/categories/general/posts"
    assert _titles((await client.get(url)).json()) == ["high", "low"]

    for person in (bob, alice):
        await client.post(f"{BASE}/posts/{low.id}/resonance", headers=person.headers)

    assert _titles((await client.get(url)).json()) == ["low", "high"]


async def test_the_listing_marks_only_the_viewers_own_resonances(client, alice, bob, db_session):
    category = await _seed_category(db_session, alice)
    liked = await _seed_post(db_session, alice, category, "liked")
    await _seed_post(db_session, alice, category, "other")
    await client.post(f"{BASE}/posts/{liked.id}/resonance", headers=bob.headers)
    url = f"{BASE}/categories/general/posts"

    def flags(resp):
        return {p["title"]: p["resonated_by_me"] for p in resp.json()["items"]}

    assert flags(await client.get(url, headers=bob.headers)) == {"liked": True, "other": False}
    assert flags(await client.get(url, headers=alice.headers)) == {"liked": False, "other": False}
    assert flags(await client.get(url)) == {"liked": False, "other": False}


async def test_nobody_can_tell_who_resonated(client, alice, bob, db_session):
    """Not even the author, looking at their own post's listing."""
    category = await _seed_category(db_session, alice)
    post = await _seed_post(db_session, alice, category, "p")
    await client.post(f"{BASE}/posts/{post.id}/resonance", headers=bob.headers)

    for headers in ({}, alice.headers, bob.headers):
        resp = await client.get(f"{BASE}/categories/general/posts", headers=headers)
        assert resp.json()["items"][0]["resonance_count"] == 1
        _no_trace_of(alice, resp)
        _no_trace_of(bob, resp)


# --- Public pages never depend on the token -----------------------------------


async def test_a_garbage_token_reads_the_public_listing_as_anonymous(client, alice, db_session):
    """The frontend sends its stored token everywhere; a 401 here would make
    it log a visitor out of a page that never needed a login."""
    category = await _seed_category(db_session, alice)
    await _seed_post(db_session, alice, category, "p")

    resp = await client.get(f"{BASE}/categories/general/posts", headers={"Authorization": "Bearer not-a-jwt"})

    assert resp.status_code == 200
    assert resp.json()["items"][0]["resonated_by_me"] is False


async def test_an_expired_token_reads_the_public_listing_as_anonymous(client, alice, make_access_token, db_session):
    category = await _seed_category(db_session, alice)
    await _seed_post(db_session, alice, category, "p")
    expired = make_access_token(sub=str(alice.user.auth_sub), exp=1)

    resp = await client.get(
        f"{BASE}/categories/general/posts", headers={"Authorization": f"Bearer {expired}"}
    )

    assert resp.status_code == 200


async def test_a_bad_token_is_still_refused_where_a_login_is_needed(client, alice, db_session):
    await _seed_category(db_session, alice)
    resp = await client.post(
        f"{BASE}/categories/general/posts",
        json={"title": "T", "body": "B"},
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert resp.status_code == 401
