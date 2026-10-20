# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the articles module's endpoints.

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` (whether the module is mounted on the real app
depends on the branch's backend/modules.json - see
test_modules_notifications_router.py). ASGITransport keeps the JWT
dependency chain and db_session on one event loop. Each test starts from
empty article tables (inside its own rolled-back transaction), so
assertions on whole listings don't depend on what the database holds.

Rows are seeded with explicit created_at values where order matters:
inside one transaction Postgres' now() is the same for every row."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.articles import manifest
from app.modules.articles.models import Article, ArticleType
from app.modules.articles.router import router as articles_router
from app.modules.event_calendar.models import Event

BASE = "/api/modules/articles"
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
COLORS = {
    "border_light": "#112233",
    "background_light": "#ddeeff",
    "border_dark": "#445566",
    "background_dark": "#101820",
}

_articles_app = FastAPI()
_articles_app.include_router(articles_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, tmp_path, rsa_keypair, monkeypatch):
    # Events refer to articles (ON DELETE RESTRICT): on a database that holds
    # some - a developer's - they have to go first, inside this test's
    # rolled-back transaction, or the articles could not be cleared.
    await db_session.execute(delete(Event))
    await db_session.execute(delete(Article))
    await db_session.execute(delete(ArticleType))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    settings = Settings(uploads_dir=str(tmp_path), app_base_url="http://api.test")
    _articles_app.dependency_overrides[get_db] = lambda: db_session
    _articles_app.dependency_overrides[get_settings] = lambda: settings
    yield
    _articles_app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_articles_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    """An administrator of this application (local User.is_admin) - with a
    plain auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    """Not an administrator here - even though the auth service calls them
    "admin": role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


async def _seed(db_session, slug: str, **fields) -> Article:
    fields.setdefault("status", "published")
    fields.setdefault("title", slug)
    article = Article(slug=slug, **fields)
    db_session.add(article)
    await db_session.commit()
    # Detach, so the endpoint under test loads the row (and its type) fresh.
    db_session.expunge_all()
    return article


async def _seed_type(db_session, name: str = "Report", **fields) -> ArticleType:
    article_type = ArticleType(name=name, **{**COLORS, **fields})
    db_session.add(article_type)
    await db_session.commit()
    db_session.expunge_all()
    return article_type


def _slugs(items):
    return [item["slug"] for item in items]


def _at(day: int) -> datetime:
    return datetime(2026, 1, day, 12, 0, tzinfo=timezone.utc)


def test_manifest_key_matches_its_folder():
    assert manifest.key == "articles"
    assert manifest.router is articles_router


# --- Administrator-only gate ---------------------------------------------------


def _admin_routes():
    """Every (method, path) under /manage, read from the OpenAPI schema -
    router.routes only holds the included /manage router as one object."""
    paths = _articles_app.openapi()["paths"]
    return [
        (method.upper(), path.removeprefix(BASE))
        for path, operations in paths.items()
        if path.removeprefix(BASE).startswith("/manage")
        for method in operations
    ]


async def _call(client, method: str, path: str, headers: dict):
    concrete = path.replace("{article_id}", str(uuid.uuid4())).replace("{type_id}", str(uuid.uuid4()))
    return await client.request(method, f"{BASE}{concrete}", headers=headers)


def test_there_are_admin_routes_to_check():
    assert len(_admin_routes()) >= 9


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_anonymous_requests_are_rejected_on_every_admin_route(client, method, path):
    resp = await _call(client, method, path, headers={})

    assert resp.status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_non_admins_are_rejected_on_every_admin_route(client, non_admin, method, path):
    resp = await _call(client, method, path, headers=non_admin)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


# --- Public listing -----------------------------------------------------------


async def test_list_shows_only_listed_articles_newest_first(client, db_session):
    await _seed(db_session, "old", created_at=_at(1))
    await _seed(db_session, "new", created_at=_at(3))
    await _seed(db_session, "mid-window", created_at=_at(2), display_from=YESTERDAY, display_to=TOMORROW)
    await _seed(db_session, "draft", status="draft")
    await _seed(db_session, "archived", status="archived")
    await _seed(db_session, "embargoed", display_from=TOMORROW)
    await _seed(db_session, "expired", display_to=YESTERDAY)

    resp = await client.get(BASE)

    assert resp.status_code == 200
    assert _slugs(resp.json()["items"]) == ["new", "mid-window", "old"]
    assert resp.json()["has_more"] is False
    assert "content" not in resp.json()["items"][0]


async def test_list_can_include_archived_but_never_drafts_or_embargoed(client, db_session):
    await _seed(db_session, "live", created_at=_at(3))
    await _seed(db_session, "archived", status="archived", created_at=_at(2))
    await _seed(db_session, "draft", status="draft")
    await _seed(db_session, "embargoed", display_from=TOMORROW)

    resp = await client.get(BASE, params={"include_archived": "true"})

    assert _slugs(resp.json()["items"]) == ["live", "archived"]


async def test_list_pages_with_has_more(client, db_session):
    for day in range(1, 6):
        await _seed(db_session, f"a{day}", created_at=_at(day))

    first = (await client.get(BASE, params={"limit": 3})).json()
    second = (await client.get(BASE, params={"limit": 3, "offset": 3})).json()

    assert _slugs(first["items"]) == ["a5", "a4", "a3"]
    assert first["has_more"] is True
    assert _slugs(second["items"]) == ["a2", "a1"]
    assert second["has_more"] is False


async def test_list_filters_by_type_created_range_and_text(client, db_session):
    report = await _seed_type(db_session, "Report")
    await _seed(db_session, "typed", type_id=report.id, created_at=_at(10), title="Jarní bazar", search_text="jarni bazar")
    await _seed(db_session, "untyped", created_at=_at(20), title="Podzim", search_text="podzim")

    by_type = (await client.get(BASE, params={"type_id": str(report.id)})).json()
    from_day = (await client.get(BASE, params={"created_from": "2026-01-15"})).json()
    to_day = (await client.get(BASE, params={"created_to": "2026-01-15"})).json()
    by_text = (await client.get(BASE, params={"q": "BAZAR"})).json()

    assert _slugs(by_type["items"]) == ["typed"]
    assert _slugs(from_day["items"]) == ["untyped"]
    assert _slugs(to_day["items"]) == ["typed"]
    assert _slugs(by_text["items"]) == ["typed"]


async def test_list_items_carry_their_type_and_its_colours(client, db_session):
    report = await _seed_type(db_session, "Report")
    await _seed(db_session, "typed", type_id=report.id)

    item = (await client.get(BASE)).json()["items"][0]

    assert item["type"] == {"id": str(report.id), "name": "Report", **COLORS}


async def test_list_rejects_an_out_of_range_limit(client):
    assert (await client.get(BASE, params={"limit": 0})).status_code == 422
    assert (await client.get(BASE, params={"limit": 51})).status_code == 422


# --- Search -------------------------------------------------------------------


async def test_search_ignores_case_and_diacritics_in_title_perex_and_content(client, db_session):
    from app.modules.articles.search import build_search_text

    title, perex, content = "Kráva na louce", "Příběh o ŽLUŤOUČKÉM koni", "<p>Příliš děkuji</p>"
    # search_text is built the way the write path builds it.
    await _seed(
        db_session,
        "krava",
        title=title,
        perex=perex,
        content=content,
        search_text=build_search_text(title, perex, content),
        status="published",
    )

    for query in ("KRAVA", "kráva", "zlutouckem koni", "ZLUŤOUČKÉM", "prilis dekuji", "louce"):
        resp = await client.get(f"{BASE}/search", params={"q": query})
        assert _slugs(resp.json()) == ["krava"], query


async def test_search_requires_every_word_and_returns_nothing_for_unknown_text(client, db_session):
    from app.modules.articles.search import build_search_text

    await _seed(db_session, "one", search_text=build_search_text("Jarní bazar", "", "<p>knihy a hračky</p>"))

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "bazar knihy"})).json()) == ["one"]
    assert (await client.get(f"{BASE}/search", params={"q": "bazar auta"})).json() == []
    assert (await client.get(f"{BASE}/search", params={"q": "nic"})).json() == []


async def test_search_does_not_join_neighbouring_paragraphs(client, db_session):
    from app.modules.articles.search import build_search_text

    await _seed(db_session, "paras", search_text=build_search_text("T", "", "<p>alpha</p><p>beta</p>"))

    assert (await client.get(f"{BASE}/search", params={"q": "alphabeta"})).json() == []
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "alpha beta"})).json()) == ["paras"]


async def test_search_finds_archived_but_not_drafts_or_out_of_window(client, db_session):
    await _seed(db_session, "live", search_text="termin", created_at=_at(4))
    await _seed(db_session, "archived", status="archived", search_text="termin", created_at=_at(3))
    await _seed(db_session, "draft", status="draft", search_text="termin")
    await _seed(db_session, "embargoed", display_from=TOMORROW, search_text="termin")
    await _seed(db_session, "expired", display_to=YESTERDAY, search_text="termin")

    resp = await client.get(f"{BASE}/search", params={"q": "termín"})

    assert _slugs(resp.json()) == ["live", "archived"]


async def test_search_treats_like_wildcards_literally(client, db_session):
    await _seed(db_session, "percent", search_text="sleva 100% hotovo")
    await _seed(db_session, "plain", search_text="sleva 1000 hotovo")
    await _seed(db_session, "underscore", search_text="a_b")
    await _seed(db_session, "letters", search_text="axb")

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "100%"})).json()) == ["percent"]
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "a_b"})).json()) == ["underscore"]


async def test_search_with_blank_query(client):
    assert (await client.get(f"{BASE}/search", params={"q": ""})).status_code == 422
    assert (await client.get(f"{BASE}/search", params={"q": "   "})).json() == []


# --- Types (public) -----------------------------------------------------------


async def test_types_are_public_and_sorted_by_name(client, db_session):
    await _seed_type(db_session, "Zpráva")
    await _seed_type(db_session, "Akce")

    resp = await client.get(f"{BASE}/types")

    assert resp.status_code == 200
    assert [t["name"] for t in resp.json()] == ["Akce", "Zpráva"]
    assert resp.json()[0]["border_dark"] == COLORS["border_dark"]


# --- Detail -------------------------------------------------------------------


async def test_detail_returns_published_and_archived_articles(client, db_session):
    await _seed(db_session, "live", content="<p>Hello</p>", perex="Short")
    await _seed(db_session, "old", status="archived")

    live = await client.get(f"{BASE}/live")
    old = await client.get(f"{BASE}/old")

    assert live.status_code == 200
    assert live.json()["content"] == "<p>Hello</p>"
    assert live.json()["perex"] == "Short"
    assert old.status_code == 200


async def test_detail_of_a_draft_or_unknown_slug_is_404(client, db_session):
    await _seed(db_session, "secret", status="draft")

    assert (await client.get(f"{BASE}/secret")).status_code == 404
    assert (await client.get(f"{BASE}/missing")).status_code == 404


async def test_detail_of_a_published_article_works_outside_its_window(client, db_session):
    """The window governs what is listed, not whether a link someone already has works."""
    await _seed(db_session, "expired", display_to=YESTERDAY)
    await _seed(db_session, "embargoed", display_from=TOMORROW)

    assert (await client.get(f"{BASE}/expired")).status_code == 200
    assert (await client.get(f"{BASE}/embargoed")).status_code == 200


async def test_fixed_paths_are_not_swallowed_by_the_slug_route(client):
    assert (await client.get(f"{BASE}/types")).status_code == 200
    assert (await client.get(f"{BASE}/search", params={"q": "x"})).status_code == 200


# --- Administrators: articles ---------------------------------------------------


async def test_create_article_applies_defaults_and_is_readable_back(client, admin):
    resp = await client.post(f"{BASE}/manage", json={"title": "Jarní bazar", "slug": "jarni-bazar"}, headers=admin)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["pinned"] is False
    assert body["perex"] == "" and body["content"] == ""
    assert body["type"] is None and body["type_id"] is None
    assert (await client.get(f"{BASE}/manage/{body['id']}", headers=admin)).json()["slug"] == "jarni-bazar"


async def test_create_article_sanitizes_content_and_keeps_allowed_embeds(client, admin):
    content = (
        '<p style="text-align:center">ok</p><script>alert(1)</script>'
        '<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"></iframe>'
        '<iframe src="https://evil.example/x"></iframe>'
        "<table><tbody><tr><td>c</td></tr></tbody></table>"
    )

    resp = await client.post(
        f"{BASE}/manage", json={"title": "T", "slug": "t", "content": content, "status": "published"}, headers=admin
    )

    saved = resp.json()["content"]
    assert "<script" not in saved and "evil.example" not in saved
    assert "youtube-nocookie.com/embed/dQw4w9WgXcQ" in saved
    assert "<table>" in saved and "text-align:center" in saved


async def test_created_article_is_found_by_its_content_through_search(client, admin):
    await client.post(
        f"{BASE}/manage",
        json={"title": "T", "slug": "t", "content": "<p>Žluťoučký kůň</p>", "status": "published"},
        headers=admin,
    )

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "zlutoucky kun"})).json()) == ["t"]


@pytest.mark.parametrize(
    "body",
    [
        {"title": "", "slug": "x"},
        {"title": "T", "slug": "Has Space"},
        {"title": "T", "slug": "double--hyphen"},
        {"title": "T", "slug": "manage"},
        {"title": "T", "slug": "types"},
        {"title": "T", "slug": "search"},
        {"title": "T", "slug": "uploads"},
        {"title": "T", "slug": "x", "perex": "p" * 501},
        {"title": "T", "slug": "x", "status": "deleted"},
        {"title": "T", "slug": "x", "display_from": "2026-02-02", "display_to": "2026-02-01"},
        {"title": "T", "slug": "x", "image_url": "javascript:alert(1)"},
        {"title": "T", "slug": "x", "image_url": "//evil.example/a.png"},
    ],
)
async def test_create_article_rejects_invalid_input(client, admin, body):
    assert (await client.post(f"{BASE}/manage", json=body, headers=admin)).status_code == 422


async def test_create_article_with_a_taken_slug_is_409(client, admin):
    await client.post(f"{BASE}/manage", json={"title": "A", "slug": "same"}, headers=admin)

    resp = await client.post(f"{BASE}/manage", json={"title": "B", "slug": "same"}, headers=admin)

    assert resp.status_code == 409


async def test_create_article_with_an_unknown_type_is_422(client, admin):
    resp = await client.post(
        f"{BASE}/manage", json={"title": "A", "slug": "a", "type_id": str(uuid.uuid4())}, headers=admin
    )

    assert resp.status_code == 422


async def test_create_article_with_a_type_returns_it(client, admin, db_session):
    report = await _seed_type(db_session, "Report")

    resp = await client.post(
        f"{BASE}/manage", json={"title": "A", "slug": "a", "type_id": str(report.id)}, headers=admin
    )

    assert resp.status_code == 201
    assert resp.json()["type"]["name"] == "Report"


async def test_update_article_changes_only_sent_fields_and_can_clear_optionals(client, admin, db_session):
    report = await _seed_type(db_session, "Report")
    article = await _seed(
        db_session, "a", title="Old", perex="keep", type_id=report.id, display_from=YESTERDAY, image_url="/x.png"
    )

    resp = await client.patch(
        f"{BASE}/manage/{article.id}",
        json={"title": "New", "display_from": None, "type_id": None, "image_url": None, "pinned": True},
        headers=admin,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "New" and body["perex"] == "keep" and body["slug"] == "a"
    assert body["display_from"] is None and body["type"] is None and body["image_url"] is None
    assert body["pinned"] is True


async def test_update_article_resanitizes_content_and_refreshes_search(client, admin, db_session):
    article = await _seed(db_session, "a", title="Title", search_text="title")

    await client.patch(
        f"{BASE}/manage/{article.id}",
        json={"content": "<p>Nová věc</p><script>x()</script>"},
        headers=admin,
    )

    assert _slugs((await client.get(f"{BASE}/search", params={"q": "nova vec"})).json()) == ["a"]
    assert "<script" not in (await client.get(f"{BASE}/manage/{article.id}", headers=admin)).json()["content"]


async def test_update_article_status_takes_it_off_the_listing_but_not_out_of_search(client, admin, db_session):
    # search_text is rebuilt from the text on every save, so give it a text to find.
    article = await _seed(db_session, "a", title="Bazar")

    await client.patch(f"{BASE}/manage/{article.id}", json={"status": "archived"}, headers=admin)

    assert (await client.get(BASE)).json()["items"] == []
    assert _slugs((await client.get(f"{BASE}/search", params={"q": "bazar"})).json()) == ["a"]


@pytest.mark.parametrize(
    "body",
    [
        {"title": None},
        {"slug": None},
        {"status": None},
        {"pinned": None},
        {"slug": "manage"},
        {"status": "deleted"},
        {"type_id": "00000000-0000-0000-0000-000000000000"},
        {"display_from": "2026-02-02", "display_to": "2026-02-01"},
    ],
)
async def test_update_article_rejects_invalid_input(client, admin, db_session, body):
    article = await _seed(db_session, "a")

    assert (await client.patch(f"{BASE}/manage/{article.id}", json=body, headers=admin)).status_code == 422


async def test_update_article_checks_the_window_against_the_stored_dates(client, admin, db_session):
    article = await _seed(db_session, "a", display_to=date(2026, 3, 1))

    resp = await client.patch(f"{BASE}/manage/{article.id}", json={"display_from": "2026-04-01"}, headers=admin)

    assert resp.status_code == 422


async def test_update_article_to_a_taken_slug_is_409(client, admin, db_session):
    await _seed(db_session, "taken")
    other = await _seed(db_session, "other")

    resp = await client.patch(f"{BASE}/manage/{other.id}", json={"slug": "taken"}, headers=admin)

    assert resp.status_code == 409


async def test_unknown_article_is_404_for_get_and_patch(client, admin):
    unknown = uuid.uuid4()

    assert (await client.get(f"{BASE}/manage/{unknown}", headers=admin)).status_code == 404
    assert (await client.patch(f"{BASE}/manage/{unknown}", json={"title": "x"}, headers=admin)).status_code == 404


async def test_manage_list_includes_drafts_and_filters_by_status_and_text(client, admin, db_session):
    await _seed(db_session, "draft", status="draft", search_text="alpha", created_at=_at(1))
    await _seed(db_session, "live", status="published", search_text="beta", created_at=_at(2))
    await _seed(db_session, "old", status="archived", search_text="alpha beta", created_at=_at(3))

    everything = (await client.get(f"{BASE}/manage", headers=admin)).json()
    drafts = (await client.get(f"{BASE}/manage", params={"status": "draft"}, headers=admin)).json()
    alpha = (await client.get(f"{BASE}/manage", params={"q": "alpha"}, headers=admin)).json()

    assert _slugs(everything["items"]) == ["old", "live", "draft"]
    assert _slugs(drafts["items"]) == ["draft"]
    assert _slugs(alpha["items"]) == ["old", "draft"]
    assert {"display_from", "display_to", "updated_at"} <= set(everything["items"][0])


# --- Administrators: types ------------------------------------------------------


async def test_create_and_update_a_type(client, admin):
    created = await client.post(f"{BASE}/manage/types", json={"name": "Report", **COLORS}, headers=admin)

    assert created.status_code == 201, created.text
    type_id = created.json()["id"]
    updated = await client.patch(
        f"{BASE}/manage/types/{type_id}", json={"name": "Zpráva", "border_light": "#ABCDEF"}, headers=admin
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Zpráva"
    assert updated.json()["border_light"] == "#ABCDEF"
    assert updated.json()["background_light"] == COLORS["background_light"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"border_light": "red"},
        {"background_light": "#12345"},
        {"border_dark": "#12345g"},
        {"background_dark": "rgb(0,0,0)"},
    ],
)
async def test_create_type_rejects_invalid_input(client, admin, overrides):
    resp = await client.post(f"{BASE}/manage/types", json={"name": "T", **COLORS, **overrides}, headers=admin)

    assert resp.status_code == 422


async def test_type_names_are_unique(client, admin, db_session):
    existing = await _seed_type(db_session, "Report")
    other = await _seed_type(db_session, "Other")

    created = await client.post(f"{BASE}/manage/types", json={"name": "Report", **COLORS}, headers=admin)
    renamed = await client.patch(f"{BASE}/manage/types/{other.id}", json={"name": "Report"}, headers=admin)

    assert created.status_code == 409 and renamed.status_code == 409
    assert existing.name == "Report"


async def test_update_type_rejects_null_and_unknown(client, admin, db_session):
    report = await _seed_type(db_session, "Report")

    assert (await client.patch(f"{BASE}/manage/types/{report.id}", json={"name": None}, headers=admin)).status_code == 422
    assert (await client.patch(f"{BASE}/manage/types/{uuid.uuid4()}", json={"name": "x"}, headers=admin)).status_code == 404


async def test_manage_types_lists_how_many_articles_use_each(client, admin, db_session):
    used = await _seed_type(db_session, "Used")
    await _seed_type(db_session, "Unused")
    await _seed(db_session, "a", type_id=used.id)
    await _seed(db_session, "b", type_id=used.id)

    resp = await client.get(f"{BASE}/manage/types", headers=admin)

    assert {t["name"]: t["article_count"] for t in resp.json()} == {"Used": 2, "Unused": 0}


async def test_delete_an_unused_type(client, admin, db_session):
    report = await _seed_type(db_session, "Report")

    resp = await client.delete(f"{BASE}/manage/types/{report.id}", headers=admin)

    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/types")).json() == []


async def test_delete_a_type_in_use_is_refused_without_a_replacement(client, admin, db_session):
    report = await _seed_type(db_session, "Report")
    await _seed(db_session, "a", type_id=report.id)

    resp = await client.delete(f"{BASE}/manage/types/{report.id}", headers=admin)

    assert resp.status_code == 409
    assert [t["name"] for t in (await client.get(f"{BASE}/types")).json()] == ["Report"]


async def test_delete_a_type_in_use_moves_its_articles_to_the_replacement(client, admin, db_session):
    old = await _seed_type(db_session, "Old")
    new = await _seed_type(db_session, "New")
    article = await _seed(db_session, "a", type_id=old.id)

    resp = await client.delete(f"{BASE}/manage/types/{old.id}", params={"replace_with": str(new.id)}, headers=admin)

    assert resp.status_code == 204
    moved = (await client.get(f"{BASE}/manage/{article.id}", headers=admin)).json()
    assert moved["type_id"] == str(new.id) and moved["type"]["name"] == "New"
    assert [t["name"] for t in (await client.get(f"{BASE}/types")).json()] == ["New"]


async def test_delete_type_rejects_itself_or_an_unknown_replacement(client, admin, db_session):
    report = await _seed_type(db_session, "Report")
    await _seed(db_session, "a", type_id=report.id)

    same = await client.delete(f"{BASE}/manage/types/{report.id}", params={"replace_with": str(report.id)}, headers=admin)
    unknown = await client.delete(f"{BASE}/manage/types/{report.id}", params={"replace_with": str(uuid.uuid4())}, headers=admin)

    assert same.status_code == 422 and unknown.status_code == 422
    assert (await db_session.scalar(select(ArticleType).where(ArticleType.id == report.id))) is not None


async def test_delete_unknown_type_is_404(client, admin):
    assert (await client.delete(f"{BASE}/manage/types/{uuid.uuid4()}", headers=admin)).status_code == 404


# --- Uploads --------------------------------------------------------------------


async def test_upload_stores_the_image_and_serves_it_back(client, admin, tmp_path):
    resp = await client.post(f"{BASE}/manage/uploads", files={"file": ("a.png", PNG, "image/png")}, headers=admin)

    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert url.startswith("http://api.test/api/modules/articles/uploads/") and url.endswith(".png")
    filename = url.rsplit("/", 1)[1]
    assert (tmp_path / "articles" / filename).read_bytes() == PNG
    served = await client.get(f"{BASE}/uploads/{filename}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert "immutable" in served.headers["cache-control"]
    assert served.content == PNG


async def test_upload_rejects_wrong_type_wrong_content_and_oversize(client, admin):
    wrong_type = await client.post(f"{BASE}/manage/uploads", files={"file": ("a.txt", b"hi", "text/plain")}, headers=admin)
    fake_png = await client.post(f"{BASE}/manage/uploads", files={"file": ("a.png", b"not a png", "image/png")}, headers=admin)
    too_big = await client.post(
        f"{BASE}/manage/uploads", files={"file": ("a.png", PNG + b"\x00" * (5 * 1024 * 1024), "image/png")}, headers=admin
    )

    assert wrong_type.status_code == 415
    assert fake_png.status_code == 415
    assert too_big.status_code == 413


async def test_upload_is_for_administrators_only(client, non_admin):
    resp = await client.post(f"{BASE}/manage/uploads", files={"file": ("a.png", PNG, "image/png")}, headers=non_admin)

    assert resp.status_code == 403


@pytest.mark.parametrize("filename", ["x.png", "../etc/passwd", "a" * 32 + ".exe", "a" * 32 + ".png.txt", "G" * 32 + ".png", "a" * 32 + ".png"])
async def test_serving_only_accepts_names_the_module_generated(client, filename):
    assert (await client.get(f"{BASE}/uploads/{filename}")).status_code == 404
