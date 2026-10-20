# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the event_calendar module's endpoints.

An event is a term belonging to an article (the articles module): these tests
seed articles and events directly and check what the calendar, the wall
(dashboard), the per-article list and search show - visibility always follows
the article.

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` (whether the module is mounted on the real app
depends on the branch's backend/modules.json - see
test_modules_notifications_router.py). ASGITransport keeps the JWT
dependency chain and db_session on one event loop. Each test starts from
empty article and event tables (inside its own rolled-back transaction), so
assertions on whole listings don't depend on what the database holds.

Rows get explicit created_at values where order matters: inside one
transaction Postgres' now() is the same for every row."""

import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.articles.models import Article, ArticleType
from app.modules.articles.search import build_search_text, normalize_text
from app.modules.event_calendar import manifest
from app.modules.event_calendar.config import EventCalendarConfig, get_config
from app.modules.event_calendar.models import Event
from app.modules.event_calendar.router import router as event_router
from app.modules.registry import check_module_dependencies

BASE = "/api/modules/event_calendar"
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
COLORS = {
    "border_light": "#112233",
    "background_light": "#ddeeff",
    "border_dark": "#445566",
    "background_dark": "#101820",
}

_event_app = FastAPI()
_event_app.include_router(event_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, tmp_path, rsa_keypair, monkeypatch):
    # Events first: they refer to articles.
    await db_session.execute(delete(Event))
    await db_session.execute(delete(Article))
    await db_session.execute(delete(ArticleType))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _event_app.dependency_overrides[get_db] = lambda: db_session
    _event_app.dependency_overrides[get_settings] = lambda: Settings(uploads_dir=str(tmp_path))
    _event_app.dependency_overrides[get_config] = lambda: EventCalendarConfig(page_size=10)
    yield
    _event_app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_event_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def editor_headers(db_session, make_access_token):
    """An administrator of this application (local User.is_admin) - with a
    plain auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def user_headers(make_access_token):
    """Not an administrator here - even though the auth service calls them
    "admin": role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


async def _article(db_session, slug: str, **fields) -> Article:
    fields.setdefault("status", "published")
    title = fields.setdefault("title", slug)
    article = Article(
        slug=slug,
        search_text=build_search_text(title, fields.get("perex", ""), fields.get("content", "")),
        **fields,
    )
    db_session.add(article)
    await db_session.commit()
    db_session.expunge_all()
    return article


async def _event(db_session, article: Article, start: date, **fields) -> Event:
    title = fields.pop("title", f"{article.slug} term")
    description = fields.get("short_description", "")
    event = Event(
        article_id=article.id,
        title=title,
        start_date=start,
        search_text=normalize_text(f"{title} {description}"),
        **fields,
    )
    db_session.add(event)
    await db_session.commit()
    db_session.expunge_all()
    return event


async def _seed_type(db_session, name: str = "Report") -> ArticleType:
    article_type = ArticleType(name=name, **COLORS)
    db_session.add(article_type)
    await db_session.commit()
    db_session.expunge_all()
    return article_type


def _titles(items):
    return [item["title"] for item in items]


def _slugs(items):
    return [item["slug"] for item in items]


def _created(day: int) -> datetime:
    return datetime(2026, 1, day, 12, 0, tzinfo=timezone.utc)


# --- Module contract ------------------------------------------------------------


def test_manifest_requires_articles():
    assert manifest.key == "event_calendar"
    assert manifest.router is event_router
    assert manifest.requires == ("articles",)


def test_enabling_the_calendar_without_articles_is_warned_about():
    assert check_module_dependencies(["event_calendar"]) == [
        "module 'event_calendar' is enabled but requires 'articles', which is not enabled"
    ]
    assert check_module_dependencies(["event_calendar", "articles"]) == []


# --- Upcoming list --------------------------------------------------------------


async def test_upcoming_lists_unfinished_events_of_listed_articles_soonest_first(client, db_session):
    live = await _article(db_session, "live")
    await _event(db_session, live, TODAY + timedelta(days=5), title="later")
    await _event(db_session, live, TODAY, title="today")
    await _event(db_session, live, YESTERDAY, title="yesterday")
    await _event(db_session, live, YESTERDAY - timedelta(days=1), end_date=TODAY, title="running")
    await _event(db_session, live, YESTERDAY - timedelta(days=3), end_date=YESTERDAY, title="just over")
    for slug, fields in {
        "draft": {"status": "draft"},
        "archived": {"status": "archived"},
        "embargoed": {"display_from": TOMORROW},
        "expired": {"display_to": YESTERDAY},
    }.items():
        hidden = await _article(db_session, slug, **fields)
        await _event(db_session, hidden, TOMORROW, title=f"{slug} event")

    resp = await client.get(BASE)

    assert resp.status_code == 200
    assert _titles(resp.json()["items"]) == ["running", "today", "later"]
    assert resp.json()["has_more"] is False
    assert "content" not in resp.json()["items"][0]["article"]


async def test_upcoming_orders_same_day_by_time_untimed_first(client, db_session):
    article = await _article(db_session, "a")
    await _event(db_session, article, TOMORROW, title="evening", start_time=time(18, 0))
    await _event(db_session, article, TOMORROW, title="morning", start_time=time(8, 0), end_time=time(9, 30))
    await _event(db_session, article, TOMORROW, title="all day")

    items = (await client.get(BASE)).json()["items"]

    assert _titles(items) == ["all day", "morning", "evening"]
    assert items[1]["start_time"] == "08:00:00" and items[1]["end_time"] == "09:30:00"


async def test_upcoming_pages_by_page_size(client, db_session):
    article = await _article(db_session, "a")
    for i in range(12):
        await _event(db_session, article, TODAY + timedelta(days=i), title=f"e{i:02d}")

    first = (await client.get(BASE)).json()
    second = (await client.get(BASE, params={"offset": 10})).json()

    assert _titles(first["items"]) == [f"e{i:02d}" for i in range(10)]
    assert first["has_more"] is True
    assert _titles(second["items"]) == ["e10", "e11"]
    assert second["has_more"] is False


async def test_events_carry_their_article_and_its_type_colours(client, db_session):
    report = await _seed_type(db_session)
    article = await _article(db_session, "typed", type_id=report.id, pinned=True, image_url="/x.png")
    await _event(db_session, article, TOMORROW, short_description="Hover text")

    event = (await client.get(BASE)).json()["items"][0]

    assert event["short_description"] == "Hover text"
    assert event["article"]["slug"] == "typed"
    assert event["article"]["pinned"] is True
    assert event["article"]["image_url"] == "/x.png"
    assert event["article"]["type"] == {"id": str(report.id), "name": "Report", **COLORS}


# --- Archive and month ----------------------------------------------------------


async def test_archive_groups_findable_events_by_the_month_they_start_in(client, db_session):
    live = await _article(db_session, "live")
    archived = await _article(db_session, "archived", status="archived")
    draft = await _article(db_session, "draft", status="draft")
    await _event(db_session, live, date(2025, 3, 1))
    await _event(db_session, live, date(2025, 3, 20))
    await _event(db_session, archived, date(2025, 11, 2))
    await _event(db_session, live, date(2026, 1, 5), end_date=date(2026, 2, 3))
    await _event(db_session, draft, date(2024, 6, 1))

    resp = await client.get(f"{BASE}/archive")

    assert resp.json() == [
        {"year": 2026, "months": [{"month": 1, "count": 1}]},
        {"year": 2025, "months": [{"month": 3, "count": 2}, {"month": 11, "count": 1}]},
    ]


async def test_month_returns_every_event_touching_it_findable_ones_only(client, db_session):
    live = await _article(db_session, "live")
    archived = await _article(db_session, "archived", status="archived")
    draft = await _article(db_session, "draft", status="draft")
    expired = await _article(db_session, "expired", display_to=YESTERDAY)
    for day in range(1, 13):
        await _event(db_session, live, date(2026, 5, day), title=f"d{day:02d}")
    await _event(db_session, live, date(2026, 4, 28), end_date=date(2026, 5, 2), title="from april")
    await _event(db_session, live, date(2026, 5, 30), end_date=date(2026, 6, 2), title="into june")
    await _event(db_session, live, date(2026, 6, 1), title="june")
    await _event(db_session, live, date(2026, 4, 1), end_date=date(2026, 4, 30), title="april")
    await _event(db_session, archived, date(2026, 5, 13), title="archived")
    await _event(db_session, draft, date(2026, 5, 14), title="draft")
    await _event(db_session, expired, date(2026, 5, 15), title="expired")

    resp = await client.get(f"{BASE}/month", params={"year": 2026, "month": 5})

    titles = _titles(resp.json())
    assert titles[0] == "from april"
    assert [t for t in titles if t.startswith("d")] == [f"d{day:02d}" for day in range(1, 13)]
    assert "into june" in titles and "archived" in titles
    assert not {"june", "april", "draft", "expired"} & set(titles)


async def test_month_rejects_invalid_month(client):
    assert (await client.get(f"{BASE}/month", params={"year": 2026, "month": 13})).status_code == 422
    assert (await client.get(f"{BASE}/month", params={"year": 0, "month": 1})).status_code == 422


# --- Dates of one article -------------------------------------------------------


async def test_events_of_an_article_in_date_order_past_and_future(client, db_session):
    article = await _article(db_session, "a")
    other = await _article(db_session, "b")
    await _event(db_session, article, TODAY + timedelta(days=9), title="later")
    await _event(db_session, article, TODAY - timedelta(days=9), title="earlier")
    await _event(db_session, other, TOMORROW, title="not mine")

    resp = await client.get(f"{BASE}/by-article/{article.id}")

    assert resp.status_code == 200
    assert _titles(resp.json()) == ["earlier", "later"]


async def test_events_of_an_archived_article_are_still_listed(client, db_session):
    article = await _article(db_session, "a", status="archived")
    await _event(db_session, article, TOMORROW, title="kept")

    assert _titles((await client.get(f"{BASE}/by-article/{article.id}")).json()) == ["kept"]


@pytest.mark.parametrize("fields", [{"status": "draft"}, {"display_from": TOMORROW}, {"display_to": YESTERDAY}])
async def test_events_of_a_hidden_or_unknown_article_are_404(client, db_session, fields):
    article = await _article(db_session, "a", **fields)
    await _event(db_session, article, TOMORROW)

    assert (await client.get(f"{BASE}/by-article/{article.id}")).status_code == 404
    assert (await client.get(f"{BASE}/by-article/{uuid.uuid4()}")).status_code == 404


# --- Dashboard (the wall) --------------------------------------------------------


async def test_dashboard_upcoming_is_the_article_with_the_nearest_unfinished_event(client, db_session):
    near = await _article(db_session, "near", pinned=True, created_at=_created(1))
    far = await _article(db_session, "far", created_at=_created(2))
    await _event(db_session, far, TODAY + timedelta(days=9))
    await _event(db_session, near, TODAY + timedelta(days=3))
    await _event(db_session, near, TODAY + timedelta(days=1))

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert body["upcoming"]["slug"] == "near"
    assert body["upcoming"]["date"] == str(TOMORROW)
    assert body["upcoming"]["date_kind"] == "event"
    assert body["pinned"] == []  # the upcoming one is never repeated
    assert body["recent_past"] == []  # another upcoming article is neither pinned nor past


async def test_dashboard_an_ongoing_multi_day_event_still_counts_as_upcoming(client, db_session):
    article = await _article(db_session, "running")
    await _event(db_session, article, TODAY - timedelta(days=2), end_date=TOMORROW)

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert body["upcoming"]["slug"] == "running"
    assert body["upcoming"]["date"] == str(TODAY - timedelta(days=2))


async def test_dashboard_an_article_is_upcoming_while_any_date_is_ahead_and_past_after(client, db_session):
    mixed = await _article(db_session, "mixed")
    await _event(db_session, mixed, TODAY - timedelta(days=30))
    await _event(db_session, mixed, TODAY + timedelta(days=4))
    over = await _article(db_session, "over")
    await _event(db_session, over, TODAY - timedelta(days=20))
    await _event(db_session, over, TODAY - timedelta(days=8))

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert body["upcoming"]["slug"] == "mixed"
    assert body["upcoming"]["date"] == str(TODAY + timedelta(days=4))
    assert _slugs(body["recent_past"]) == ["over"]
    assert body["recent_past"][0]["date"] == str(TODAY - timedelta(days=8))  # its latest date
    assert body["recent_past"][0]["date_kind"] == "event"


async def test_dashboard_pinned_articles_newest_date_first_whether_or_not_they_have_dates(client, db_session):
    await _article(db_session, "pinned-dateless-old", pinned=True, created_at=_created(1))
    upcoming = await _article(db_session, "upcoming", created_at=_created(2))
    await _event(db_session, upcoming, TODAY + timedelta(days=1))
    pinned_old = await _article(db_session, "pinned-old", pinned=True, created_at=_created(3))
    await _event(db_session, pinned_old, TODAY - timedelta(days=30))
    await _article(db_session, "pinned-dateless", pinned=True, created_at=_created(10))

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert body["upcoming"]["slug"] == "upcoming"
    # Newest date first: the event 30 days ago (autumn) is newer than the two January creation days.
    assert _slugs(body["pinned"]) == ["pinned-old", "pinned-dateless", "pinned-dateless-old"]
    by_slug = {a["slug"]: a for a in body["pinned"]}
    assert by_slug["pinned-old"]["date"] == str(TODAY - timedelta(days=30))
    assert by_slug["pinned-dateless"]["date"] == "2026-01-10"
    assert by_slug["pinned-dateless"]["date_kind"] == "created"


async def test_dashboard_recent_past_is_five_unpinned_articles_newest_date_first(client, db_session):
    for i in range(6):
        article = await _article(db_session, f"past{i}")
        await _event(db_session, article, TODAY - timedelta(days=i + 1))
    dateless = await _article(db_session, "dateless", created_at=_created(5))
    pinned = await _article(db_session, "pinned", pinned=True, created_at=_created(6))
    await _event(db_session, pinned, TODAY - timedelta(days=2))

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert body["upcoming"] is None
    assert _slugs(body["recent_past"]) == [f"past{i}" for i in range(5)]
    assert dateless.slug not in _slugs(body["recent_past"])  # created in January, older than all five
    assert _slugs(body["pinned"]) == ["pinned"]


async def test_dashboard_an_article_without_dates_is_past_by_its_creation_day(client, db_session):
    await _article(db_session, "dateless", created_at=_created(5))

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert _slugs(body["recent_past"]) == ["dateless"]
    assert body["recent_past"][0]["date"] == "2026-01-05"
    assert body["recent_past"][0]["date_kind"] == "created"
    assert body["recent_past"][0]["perex"] == ""
    assert "content" not in body["recent_past"][0]


@pytest.mark.parametrize(
    "fields", [{"status": "draft"}, {"status": "archived"}, {"display_from": TOMORROW}, {"display_to": YESTERDAY}]
)
async def test_dashboard_never_shows_articles_that_are_not_listed(client, db_session, fields):
    hidden = await _article(db_session, "hidden", pinned=True, **fields)
    await _event(db_session, hidden, TOMORROW)
    past_hidden = await _article(db_session, "past-hidden", **fields)
    await _event(db_session, past_hidden, YESTERDAY)

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert body == {"upcoming": None, "pinned": [], "recent_past": []}


async def test_dashboard_empty(client):
    assert (await client.get(f"{BASE}/dashboard")).json() == {"upcoming": None, "pinned": [], "recent_past": []}


# --- Search ---------------------------------------------------------------------


async def test_search_finds_articles_through_event_text_ignoring_case_and_diacritics(client, db_session):
    concert = await _article(db_session, "concert")
    await _event(db_session, concert, date(2026, 9, 5), title="Podzimní koncert")
    reading = await _article(db_session, "reading")
    await _event(db_session, reading, date(2026, 10, 1), short_description="Čtení pro děti")

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "PODZIMNI koncert"})).json()) == ["concert"]
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "deti"})).json()) == ["reading"]
    assert (await client.get(f"{BASE}/search", params={"q": "nic takového"})).json() == []


async def test_search_finds_articles_by_their_own_text(client, db_session):
    await _article(db_session, "story", title="Kráva na louce", perex="O žluťoučkém koni", content="<p>Příliš děkuji</p>")

    for query in ("krava", "zlutouckem", "prilis dekuji"):
        assert _slugs((await client.get(f"{BASE}/search", params={"q": query})).json()) == ["story"], query


async def test_search_matches_the_start_date_in_both_notations(client, db_session):
    concert = await _article(db_session, "concert")
    await _event(db_session, concert, date(2026, 9, 5), title="x")
    reading = await _article(db_session, "reading")
    await _event(db_session, reading, date(2026, 10, 1), title="y")

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "05.09.2026"})).json()) == ["concert"]
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "2026-10"})).json()) == ["reading"]


async def test_search_returns_an_article_once_however_many_dates_match(client, db_session):
    article = await _article(db_session, "weekly", title="Weekly")
    for week in range(3):
        await _event(db_session, article, TODAY + timedelta(days=7 * week), title="Pondělní čtení")

    resp = await client.get(f"{BASE}/search", params={"q": "pondelni"})

    assert _slugs(resp.json()) == ["weekly"]


async def test_search_dates_each_result_like_the_wall_does(client, db_session):
    article = await _article(db_session, "a", title="Bazar")
    await _event(db_session, article, TODAY + timedelta(days=3))
    await _article(db_session, "dateless", title="Bazar bez termínu", created_at=_created(7))

    by_slug = {a["slug"]: a for a in (await client.get(f"{BASE}/search", params={"q": "bazar"})).json()}

    assert by_slug["a"]["date"] == str(TODAY + timedelta(days=3)) and by_slug["a"]["date_kind"] == "event"
    assert by_slug["dateless"]["date"] == "2026-01-07" and by_slug["dateless"]["date_kind"] == "created"


async def test_search_finds_archived_but_not_drafts_or_out_of_window(client, db_session):
    for slug, fields in {
        "live": {},
        "archived": {"status": "archived"},
        "draft": {"status": "draft"},
        "embargoed": {"display_from": TOMORROW},
        "expired": {"display_to": YESTERDAY},
    }.items():
        article = await _article(db_session, slug, created_at=_created(1) if slug == "live" else _created(2), **fields)
        await _event(db_session, article, TOMORROW, title="Společné setkání")

    resp = await client.get(f"{BASE}/search", params={"q": "setkani"})

    assert sorted(_slugs(resp.json())) == ["archived", "live"]


async def test_search_treats_like_wildcards_literally(client, db_session):
    percent = await _article(db_session, "percent")
    await _event(db_session, percent, TOMORROW, title="Sleva 100% na vše")
    plain = await _article(db_session, "plain")
    await _event(db_session, plain, TOMORROW, title="Sleva 1000 na vše")
    underscore = await _article(db_session, "underscore")
    await _event(db_session, underscore, TOMORROW, title="a_b")
    letters = await _article(db_session, "letters")
    await _event(db_session, letters, TOMORROW, title="axb")

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "100%"})).json()) == ["percent"]
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "a_b"})).json()) == ["underscore"]
    # A lone % is a literal percent sign, not "match everything": only the one that contains it.
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "%"})).json()) == ["percent"]


async def test_search_with_blank_query(client):
    assert (await client.get(f"{BASE}/search", params={"q": ""})).status_code == 422
    assert (await client.get(f"{BASE}/search", params={"q": "   "})).json() == []


# --- Administrator-only gate -----------------------------------------------------


def _admin_routes():
    """Every (method, path) under /manage except /manage/me (that one answers
    anybody signed in), read from the OpenAPI schema - router.routes only
    holds the included /manage router as one object."""
    paths = _event_app.openapi()["paths"]
    return [
        (method.upper(), path.removeprefix(BASE))
        for path, operations in paths.items()
        if path.removeprefix(BASE).startswith("/manage") and path.removeprefix(BASE) != "/manage/me"
        for method in operations
    ]


async def _call(client, method: str, path: str, headers: dict):
    return await client.request(method, f"{BASE}{path.replace('{event_id}', str(uuid.uuid4()))}", headers=headers)


def test_there_are_admin_routes_to_check():
    assert len(_admin_routes()) >= 5


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_anonymous_requests_are_rejected_on_every_admin_route(client, method, path):
    assert (await _call(client, method, path, headers={})).status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_non_admins_are_rejected_on_every_admin_route(client, user_headers, method, path):
    resp = await _call(client, method, path, headers=user_headers)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


async def test_editor_status(client, editor_headers, user_headers):
    assert (await client.get(f"{BASE}/manage/me", headers=editor_headers)).json() == {"is_editor": True}
    assert (await client.get(f"{BASE}/manage/me", headers=user_headers)).json() == {"is_editor": False}
    assert (await client.get(f"{BASE}/manage/me")).status_code in (401, 403)


async def test_admin_flag_not_role_decides(client, db_session, make_access_token):
    sub = uuid.uuid4()
    user = User(auth_sub=sub, is_admin=False)
    db_session.add(user)
    await db_session.commit()
    headers = {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='admin')}"}

    assert (await client.get(f"{BASE}/manage", headers=headers)).status_code == 403

    user.is_admin = True
    await db_session.commit()
    assert (await client.get(f"{BASE}/manage", headers=headers)).status_code == 200


# --- Administrators: events -------------------------------------------------------


async def test_create_event_and_read_it_back_with_its_article(client, db_session, editor_headers):
    article = await _article(db_session, "a", status="draft")

    resp = await client.post(
        f"{BASE}/manage",
        json={
            "article_id": str(article.id),
            "title": "Jarní bazar",
            "short_description": "Knihy za pár korun",
            "start_date": "2026-03-14",
            "end_date": "2026-03-15",
            "start_time": "10:00",
            "end_time": "16:30",
        },
        headers=editor_headers,
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["article_id"] == str(article.id) and body["article"]["slug"] == "a"
    assert body["start_time"] == "10:00:00" and body["end_time"] == "16:30:00"
    assert (await client.get(f"{BASE}/manage/{body['id']}", headers=editor_headers)).json()["title"] == "Jarní bazar"


async def test_create_event_needs_only_article_title_and_start_date(client, db_session, editor_headers):
    article = await _article(db_session, "a")

    resp = await client.post(
        f"{BASE}/manage",
        json={"article_id": str(article.id), "title": "T", "start_date": "2026-03-14"},
        headers=editor_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["short_description"] == ""
    assert resp.json()["end_date"] is None and resp.json()["start_time"] is None


async def test_a_created_event_is_found_through_search(client, db_session, editor_headers):
    article = await _article(db_session, "a")
    await client.post(
        f"{BASE}/manage",
        json={"article_id": str(article.id), "title": "Žluťoučký kůň", "start_date": str(TOMORROW)},
        headers=editor_headers,
    )

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "zlutoucky kun"})).json()) == ["a"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": ""},
        {"title": "t" * 201},
        {"short_description": "d" * 129},
        {"start_date": "not a date"},
        {"end_date": "2026-03-13"},
        {"end_time": "10:00"},
        {"start_time": "10:00", "end_time": "09:59"},
        {"article_id": "00000000-0000-0000-0000-000000000000"},
        {"end_date": "2026-03-14", "start_time": "10:00", "end_time": "09:00"},
    ],
)
async def test_create_event_rejects_invalid_input(client, db_session, editor_headers, overrides):
    article = await _article(db_session, "a")
    body = {"article_id": str(article.id), "title": "T", "start_date": "2026-03-14", **overrides}

    assert (await client.post(f"{BASE}/manage", json=body, headers=editor_headers)).status_code == 422


async def test_a_multi_day_event_may_end_earlier_in_the_day_than_it_starts(client, db_session, editor_headers):
    """Friday 18:00 to Sunday 12:00 is fine - the times only have to be in order within one day."""
    article = await _article(db_session, "a")

    resp = await client.post(
        f"{BASE}/manage",
        json={
            "article_id": str(article.id),
            "title": "Weekend",
            "start_date": "2026-03-13",
            "end_date": "2026-03-15",
            "start_time": "18:00",
            "end_time": "12:00",
        },
        headers=editor_headers,
    )

    assert resp.status_code == 201


async def test_a_short_description_of_exactly_128_characters_is_fine(client, db_session, editor_headers):
    article = await _article(db_session, "a")

    resp = await client.post(
        f"{BASE}/manage",
        json={"article_id": str(article.id), "title": "T", "start_date": "2026-03-14", "short_description": "d" * 128},
        headers=editor_headers,
    )

    assert resp.status_code == 201


async def test_manage_list_shows_every_event_and_filters_by_article(client, db_session, editor_headers):
    draft = await _article(db_session, "draft", status="draft")
    live = await _article(db_session, "live")
    await _event(db_session, draft, date(2026, 5, 1), title="in a draft")
    await _event(db_session, live, date(2026, 5, 3), title="live late")
    await _event(db_session, live, date(2026, 4, 1), title="live early")

    everything = (await client.get(f"{BASE}/manage", headers=editor_headers)).json()
    of_live = (await client.get(f"{BASE}/manage", params={"article_id": str(live.id)}, headers=editor_headers)).json()

    assert _titles(everything) == ["live late", "in a draft", "live early"]
    assert _titles(of_live) == ["live late", "live early"]


async def test_update_event_changes_only_sent_fields_and_can_clear_optionals(client, db_session, editor_headers):
    article = await _article(db_session, "a")
    event = await _event(
        db_session,
        article,
        date(2026, 5, 1),
        title="Old",
        short_description="keep",
        end_date=date(2026, 5, 3),
        start_time=time(10, 0),
        end_time=time(12, 0),
    )

    resp = await client.patch(
        f"{BASE}/manage/{event.id}",
        json={"title": "New", "end_date": None, "end_time": None},
        headers=editor_headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "New" and body["short_description"] == "keep"
    assert body["end_date"] is None and body["end_time"] is None and body["start_time"] == "10:00:00"


async def test_update_event_can_move_it_to_another_article(client, db_session, editor_headers):
    first = await _article(db_session, "first")
    second = await _article(db_session, "second")
    event = await _event(db_session, first, TOMORROW)

    resp = await client.patch(f"{BASE}/manage/{event.id}", json={"article_id": str(second.id)}, headers=editor_headers)

    assert resp.status_code == 200 and resp.json()["article"]["slug"] == "second"


async def test_update_event_refreshes_what_search_finds(client, db_session, editor_headers):
    article = await _article(db_session, "a")
    event = await _event(db_session, article, TOMORROW, title="Stará", short_description="")

    await client.patch(f"{BASE}/manage/{event.id}", json={"title": "Nová událost"}, headers=editor_headers)

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "nova udalost"})).json()) == ["a"]
    assert (await client.get(f"{BASE}/search", params={"q": "stara"})).json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"title": None},
        {"article_id": None},
        {"start_date": None},
        {"short_description": None},
        {"title": ""},
        {"short_description": "d" * 129},
        {"article_id": "00000000-0000-0000-0000-000000000000"},
    ],
)
async def test_update_event_rejects_invalid_input(client, db_session, editor_headers, body):
    article = await _article(db_session, "a")
    event = await _event(db_session, article, TOMORROW)

    assert (await client.patch(f"{BASE}/manage/{event.id}", json=body, headers=editor_headers)).status_code == 422


async def test_update_event_checks_the_term_against_the_stored_values(client, db_session, editor_headers):
    article = await _article(db_session, "a")
    event = await _event(
        db_session, article, date(2026, 5, 1), end_date=date(2026, 5, 1), start_time=time(10, 0), end_time=time(12, 0)
    )

    later_start = await client.patch(f"{BASE}/manage/{event.id}", json={"start_date": "2026-05-02"}, headers=editor_headers)
    earlier_end_time = await client.patch(f"{BASE}/manage/{event.id}", json={"end_time": "09:00"}, headers=editor_headers)
    drop_start_time = await client.patch(f"{BASE}/manage/{event.id}", json={"start_time": None}, headers=editor_headers)

    assert later_start.status_code == earlier_end_time.status_code == drop_start_time.status_code == 422


async def test_update_event_allows_a_term_that_is_only_consistent_as_a_whole(client, db_session, editor_headers):
    article = await _article(db_session, "a")
    event = await _event(db_session, article, date(2026, 5, 1), start_time=time(10, 0), end_time=time(12, 0))

    resp = await client.patch(
        f"{BASE}/manage/{event.id}",
        json={"start_date": "2026-06-01", "end_date": "2026-06-03", "end_time": "09:00"},
        headers=editor_headers,
    )

    assert resp.status_code == 200, resp.text


async def test_unknown_event_is_404_for_get_patch_and_delete(client, editor_headers):
    unknown = uuid.uuid4()

    assert (await client.get(f"{BASE}/manage/{unknown}", headers=editor_headers)).status_code == 404
    assert (await client.patch(f"{BASE}/manage/{unknown}", json={"title": "x"}, headers=editor_headers)).status_code == 404
    assert (await client.delete(f"{BASE}/manage/{unknown}", headers=editor_headers)).status_code == 404


async def test_delete_event_removes_the_date_but_not_the_article(client, db_session, editor_headers):
    article = await _article(db_session, "a")
    event = await _event(db_session, article, TOMORROW)

    resp = await client.delete(f"{BASE}/manage/{event.id}", headers=editor_headers)

    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/manage/{event.id}", headers=editor_headers)).status_code == 404
    assert (await client.get(f"{BASE}/by-article/{article.id}")).json() == []


async def test_delete_event_something_refers_to_is_409(client, db_session, editor_headers):
    """A later module (a registration, say) may point at an event with ON DELETE
    RESTRICT; the calendar answers 409 instead of a server error."""
    article = await _article(db_session, "a")
    event = await _event(db_session, article, TOMORROW)
    # A real table (a temporary one may not reference a permanent one); the DDL
    # goes away with the test's rolled-back transaction. Committed here so the
    # router's own rollback of the failed delete does not undo it.
    await db_session.execute(
        text(
            "CREATE TABLE tmp_event_ref ("
            "id uuid PRIMARY KEY, event_id uuid NOT NULL REFERENCES module_events (id) ON DELETE RESTRICT)"
        )
    )
    await db_session.execute(
        text("INSERT INTO tmp_event_ref (id, event_id) VALUES (:id, :event_id)"),
        {"id": uuid.uuid4(), "event_id": event.id},
    )
    await db_session.commit()

    resp = await client.delete(f"{BASE}/manage/{event.id}", headers=editor_headers)

    assert resp.status_code == 409
    assert (await client.get(f"{BASE}/manage/{event.id}", headers=editor_headers)).status_code == 200


# --- Database guarantees ----------------------------------------------------------


async def test_an_article_with_events_cannot_be_deleted(db_session):
    article = await _article(db_session, "a")
    await _event(db_session, article, TOMORROW)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(delete(Article).where(Article.id == article.id))


@pytest.mark.parametrize(
    "fields",
    [
        {"end_date": YESTERDAY},
        {"end_time": time(9, 0)},  # no start_time
    ],
)
async def test_the_database_itself_refuses_an_inconsistent_term(db_session, fields):
    article = await _article(db_session, "a")

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(Event(article_id=article.id, title="x", start_date=TODAY, **fields))
            await db_session.flush()
