# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the event_calendar module's endpoints.

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` (whether the module is mounted on the real app
depends on the branch's backend/modules.json - see
test_modules_notifications_router.py). ASGITransport keeps the JWT
dependency chain and db_session on one event loop. Each test starts from an
empty module_events table (inside its own rolled-back transaction), so
assertions on whole listings don't depend on what the database holds."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.config import Settings, get_settings
from app.database import get_db
from app.modules.event_calendar.config import EventCalendarConfig, get_config
from app.modules.event_calendar.models import Event
from app.modules.event_calendar.permissions import set_editor_check
from app.modules.event_calendar.router import router as event_router

BASE = "/api/modules/event_calendar"
TODAY = date.today()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

_event_app = FastAPI()
_event_app.include_router(event_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, tmp_path, rsa_keypair, monkeypatch):
    await db_session.execute(delete(Event))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    settings = Settings(uploads_dir=str(tmp_path), app_base_url="http://api.test")
    _event_app.dependency_overrides[get_db] = lambda: db_session
    _event_app.dependency_overrides[get_settings] = lambda: settings
    _event_app.dependency_overrides[get_config] = lambda: EventCalendarConfig(editor_roles=["admin"], page_size=10)
    monkeypatch.setattr("app.modules.event_calendar.permissions.get_config", lambda: EventCalendarConfig(editor_roles=["admin"]))
    yield
    _event_app.dependency_overrides.clear()
    set_editor_check(None)


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_event_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
def editor_headers(make_access_token):
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


@pytest.fixture()
def user_headers(make_access_token):
    return {"Authorization": f"Bearer {make_access_token(role_name='user')}"}


async def _seed(db_session, slug: str, event_date: date, **fields) -> Event:
    event = Event(
        title=fields.pop("title", slug),
        slug=slug,
        event_date=event_date,
        status=fields.pop("status", "published"),
        **fields,
    )
    db_session.add(event)
    await db_session.commit()
    return event


def _slugs(items):
    return [item["slug"] for item in items]


# --- Public listing -----------------------------------------------------------


async def test_upcoming_lists_only_visible_future_events_soonest_first(client, db_session):
    await _seed(db_session, "later", TODAY + timedelta(days=5))
    await _seed(db_session, "today", TODAY)
    await _seed(db_session, "past", TODAY - timedelta(days=1))
    await _seed(db_session, "draft", TODAY + timedelta(days=1), status="draft")
    await _seed(db_session, "deleted", TODAY + timedelta(days=1), status="deleted")
    await _seed(db_session, "embargoed", TODAY + timedelta(days=1), display_from=TODAY + timedelta(days=1))
    await _seed(db_session, "expired", TODAY + timedelta(days=1), display_to=TODAY - timedelta(days=1))
    await _seed(db_session, "window", TODAY + timedelta(days=2), display_from=TODAY, display_to=TODAY)

    resp = await client.get(BASE)

    assert resp.status_code == 200
    assert _slugs(resp.json()["items"]) == ["today", "window", "later"]
    assert resp.json()["has_more"] is False
    assert "full_text" not in resp.json()["items"][0]


async def test_upcoming_pages_by_ten(client, db_session):
    for i in range(12):
        await _seed(db_session, f"e{i:02d}", TODAY + timedelta(days=i))

    first = (await client.get(BASE)).json()
    second = (await client.get(BASE, params={"offset": 10})).json()

    assert _slugs(first["items"]) == [f"e{i:02d}" for i in range(10)]
    assert first["has_more"] is True
    assert _slugs(second["items"]) == ["e10", "e11"]
    assert second["has_more"] is False


async def test_archive_groups_visible_events_by_year_and_month(client, db_session):
    await _seed(db_session, "a", date(2025, 3, 1))
    await _seed(db_session, "b", date(2025, 3, 20))
    await _seed(db_session, "c", date(2025, 11, 2))
    await _seed(db_session, "d", date(2026, 1, 5))
    await _seed(db_session, "hidden", date(2024, 6, 1), status="draft")

    resp = await client.get(f"{BASE}/archive")

    assert resp.json() == [
        {"year": 2026, "months": [{"month": 1, "count": 1}]},
        {"year": 2025, "months": [{"month": 3, "count": 2}, {"month": 11, "count": 1}]},
    ]


async def test_month_returns_every_visible_event_unpaginated(client, db_session):
    for day in range(1, 13):
        await _seed(db_session, f"d{day:02d}", date(2026, 5, day), pinned=day == 3)
    await _seed(db_session, "other-month", date(2026, 6, 1))
    await _seed(db_session, "draft-in-month", date(2026, 5, 20), status="draft")

    resp = await client.get(f"{BASE}/month", params={"year": 2026, "month": 5})

    assert _slugs(resp.json()) == [f"d{day:02d}" for day in range(1, 13)]
    assert [item["pinned"] for item in resp.json()][2] is True


async def test_month_rejects_invalid_month(client):
    resp = await client.get(f"{BASE}/month", params={"year": 2026, "month": 13})
    assert resp.status_code == 422


async def test_dashboard(client, db_session):
    await _seed(db_session, "soonest", TODAY + timedelta(days=1), pinned=True)
    await _seed(db_session, "pinned-past", TODAY - timedelta(days=30), pinned=True)
    await _seed(db_session, "later", TODAY + timedelta(days=9))
    for i in range(6):
        await _seed(db_session, f"past{i}", TODAY - timedelta(days=i + 1))

    body = (await client.get(f"{BASE}/dashboard")).json()

    assert body["upcoming"]["slug"] == "soonest"
    assert _slugs(body["pinned"]) == ["pinned-past"]
    assert _slugs(body["recent_past"]) == [f"past{i}" for i in range(5)]


async def test_search_matches_title_description_and_dates(client, db_session):
    await _seed(db_session, "concert", date(2026, 9, 5), title="Podzimní koncert")
    await _seed(db_session, "reading", date(2026, 10, 1), short_description="Čtení pro děti")
    await _seed(db_session, "draft", date(2026, 9, 5), title="Koncert koncept", status="draft")

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "koncert"})).json()) == ["concert"]
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "děti"})).json()) == ["reading"]
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "05.09.2026"})).json()) == ["concert"]
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "2026-10"})).json()) == ["reading"]


async def test_detail_published_only_but_ignores_display_window(client, db_session):
    await _seed(db_session, "expired", TODAY, display_to=TODAY - timedelta(days=1), full_text="<p>Hi</p>")
    await _seed(db_session, "draft", TODAY, status="draft")

    ok = await client.get(f"{BASE}/expired")
    draft = await client.get(f"{BASE}/draft")

    assert ok.status_code == 200
    assert ok.json()["full_text"] == "<p>Hi</p>"
    assert "status" not in ok.json()
    assert draft.status_code == 404


# --- Editor permissions -------------------------------------------------------


async def test_editor_status(client, editor_headers, user_headers):
    assert (await client.get(f"{BASE}/manage/me", headers=editor_headers)).json() == {"is_editor": True}
    assert (await client.get(f"{BASE}/manage/me", headers=user_headers)).json() == {"is_editor": False}
    assert (await client.get(f"{BASE}/manage/me")).status_code in (401, 403)


async def test_manage_requires_editor(client, user_headers):
    assert (await client.get(f"{BASE}/manage", headers=user_headers)).status_code == 403
    assert (await client.get(f"{BASE}/manage")).status_code in (401, 403)
    resp = await client.post(
        f"{BASE}/manage", json={"title": "x", "slug": "x", "event_date": str(TODAY)}, headers=user_headers
    )
    assert resp.status_code == 403


async def test_custom_editor_check_replaces_role_check(client, editor_headers, user_headers):
    async def nobody(user, claims):
        return claims.get("login") == "special"

    set_editor_check(nobody)

    assert (await client.get(f"{BASE}/manage", headers=editor_headers)).status_code == 403


# --- Editor CRUD --------------------------------------------------------------


async def test_create_sanitizes_and_lists_all_statuses(client, db_session, editor_headers):
    resp = await client.post(
        f"{BASE}/manage",
        json={
            "title": "Koncert",
            "slug": "koncert",
            "event_date": str(TODAY),
            "full_text": '<h1>Nadpis</h1><p><span style="color: red">x</span></p><script>alert(1)</script>',
            "image_url": "http://api.test/api/modules/event_calendar/uploads/x.png",
        },
        headers=editor_headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert "<h1>Nadpis</h1>" in body["full_text"]
    assert "color" in body["full_text"]
    assert "<script" not in body["full_text"]

    await _seed(db_session, "gone", TODAY, status="deleted")
    listed = (await client.get(f"{BASE}/manage", headers=editor_headers)).json()
    assert sorted(_slugs(listed)) == ["gone", "koncert"]


@pytest.mark.parametrize(
    ("override", "status"),
    [
        ({"slug": "Bad Slug"}, 422),
        ({"slug": "manage"}, 422),
        ({"image_url": "javascript:alert(1)"}, 422),
        ({"display_from": str(TODAY + timedelta(days=2)), "display_to": str(TODAY)}, 422),
        ({"title": ""}, 422),
    ],
)
async def test_create_validation(client, editor_headers, override, status):
    payload = {"title": "x", "slug": "valid-slug", "event_date": str(TODAY), **override}
    resp = await client.post(f"{BASE}/manage", json=payload, headers=editor_headers)
    assert resp.status_code == status


async def test_create_duplicate_slug_409(client, db_session, editor_headers):
    await _seed(db_session, "taken", TODAY)
    resp = await client.post(
        f"{BASE}/manage", json={"title": "x", "slug": "taken", "event_date": str(TODAY)}, headers=editor_headers
    )
    assert resp.status_code == 409


async def test_update_partial_sanitize_and_soft_delete(client, db_session, editor_headers):
    event = await _seed(db_session, "upd", TODAY, display_from=TODAY)

    resp = await client.patch(
        f"{BASE}/manage/{event.id}",
        json={"full_text": "<p onclick='x()'>t</p>", "display_from": None, "pinned": True},
        headers=editor_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_text"] == "<p>t</p>"
    assert resp.json()["display_from"] is None
    assert resp.json()["pinned"] is True
    assert resp.json()["title"] == "upd"

    deleted = await client.patch(f"{BASE}/manage/{event.id}", json={"status": "deleted"}, headers=editor_headers)
    assert deleted.json()["status"] == "deleted"
    assert (await client.get(f"{BASE}/upd")).status_code == 404


async def test_update_rejects_null_required_field_and_bad_window(client, db_session, editor_headers):
    event = await _seed(db_session, "upd2", TODAY, display_to=TODAY)

    assert (await client.patch(f"{BASE}/manage/{event.id}", json={"title": None}, headers=editor_headers)).status_code == 422
    resp = await client.patch(
        f"{BASE}/manage/{event.id}", json={"display_from": str(TODAY + timedelta(days=1))}, headers=editor_headers
    )
    assert resp.status_code == 422


async def test_update_and_get_unknown_404(client, editor_headers):
    missing = uuid.uuid4()
    assert (await client.get(f"{BASE}/manage/{missing}", headers=editor_headers)).status_code == 404
    assert (await client.patch(f"{BASE}/manage/{missing}", json={}, headers=editor_headers)).status_code == 404


# --- Uploads ------------------------------------------------------------------


async def test_upload_and_serve_image(client, editor_headers, tmp_path):
    resp = await client.post(
        f"{BASE}/manage/uploads", files={"file": ("../evil.png", PNG, "image/png")}, headers=editor_headers
    )

    assert resp.status_code == 200
    url = resp.json()["url"]
    assert url.startswith("http://api.test/api/modules/event_calendar/uploads/")
    filename = url.rsplit("/", 1)[1]
    assert (tmp_path / "event_calendar" / filename).read_bytes() == PNG

    served = await client.get(f"{BASE}/uploads/{filename}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == PNG


@pytest.mark.parametrize(
    ("content", "content_type", "status"),
    [
        (PNG, "text/html", 415),
        (b"<html>not an image</html>", "image/png", 415),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024), "image/png", 413),
    ],
    # Explicit ids: the default one would embed the 5 MB payload in
    # PYTEST_CURRENT_TEST, which overflows Windows' environment size limit.
    ids=["unsupported-type", "content-mismatch", "too-large"],
)
async def test_upload_rejections(client, editor_headers, content, content_type, status):
    resp = await client.post(
        f"{BASE}/manage/uploads", files={"file": ("x", content, content_type)}, headers=editor_headers
    )
    assert resp.status_code == status


async def test_upload_requires_editor(client, user_headers):
    resp = await client.post(f"{BASE}/manage/uploads", files={"file": ("x.png", PNG, "image/png")}, headers=user_headers)
    assert resp.status_code == 403


@pytest.mark.parametrize("filename", ["..%2F..%2Fsecret.png", "abc.png", "0" * 32 + ".exe", "0" * 32 + ".png"])
async def test_serve_rejects_bad_or_missing_filenames(client, filename):
    assert (await client.get(f"{BASE}/uploads/{filename}")).status_code == 404
