# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the portfolio module's public endpoints (published items only,
language resolution, ordering) and its administrator endpoints (gate, CRUD,
slugs). Validation of the individual fields is in
test_modules_portfolio_validation.py, moving items in
test_modules_portfolio_move.py, the seed data in test_modules_portfolio_seed.py.

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` (whether the module is mounted on the real app
depends on the branch's backend/modules.json). ASGITransport keeps the JWT
dependency chain and db_session on one event loop.

The table is NOT empty in a migrated database: the migration seeds five
projects. Every test therefore starts by deleting all rows - inside its own
transaction, which db_session rolls back - so the seeded rows are back for
the next test (and for the application) and nothing a test creates survives."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.modules.portfolio import manifest
from app.modules.portfolio.models import PortfolioItem
from app.modules.portfolio.router import admin_router
from app.modules.portfolio.router import router as portfolio_router

BASE = "/api/modules/portfolio"

_app = FastAPI()
_app.include_router(portfolio_router, prefix=BASE)

PUBLIC_ITEM_KEYS = {"slug", "title", "summary", "url", "status", "tags"}
ADMIN_ITEM_KEYS = {
    "id", "slug", "title_cs", "title_en", "summary_cs", "summary_en", "description_cs", "description_en",
    "url", "status", "tags", "published", "sort_order", "created_at", "updated_at",
}


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


async def _create(client, admin, **fields) -> dict:
    body = {"title_cs": "Projekt", "summary_cs": "Krátký popis projektu.", **fields}
    resp = await client.post(f"{BASE}/manage/items", json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _public_slugs(client, **params) -> list[str]:
    resp = await client.get(f"{BASE}/items", params=params)
    assert resp.status_code == 200, resp.text
    return [item["slug"] for item in resp.json()]


def test_manifest_key_matches_its_folder():
    assert manifest.key == "portfolio"
    assert manifest.router is portfolio_router


# --- Administrator-only gate ---------------------------------------------------


def _admin_routes():
    return [(method, route.path) for route in admin_router.routes for method in sorted(route.methods)]


def test_every_route_is_a_known_public_read_or_one_the_gate_tests_below_cover():
    """A route added to the module without the admin gate would have to be
    in this list of public ones - otherwise it fails here, not ships open."""
    mounted = {
        (method.upper(), path.removeprefix(BASE))
        for path, operations in _app.openapi()["paths"].items()
        for method in operations
    }
    public = {("GET", "/items"), ("GET", "/items/{slug}")}

    assert public <= mounted
    assert mounted - public == set(_admin_routes())


def test_the_admin_router_itself_carries_require_admin():
    assert any(dep.dependency is require_admin for dep in admin_router.dependencies)
    assert all(
        any(dep.dependency is require_admin for dep in route.dependencies) for route in admin_router.routes
    )


def test_admin_routes_are_all_there():
    assert set(_admin_routes()) == {
        ("GET", "/manage/items"),
        ("POST", "/manage/items"),
        ("GET", "/manage/items/{item_id}"),
        ("PATCH", "/manage/items/{item_id}"),
        ("DELETE", "/manage/items/{item_id}"),
        ("POST", "/manage/items/{item_id}/move"),
    }


async def _call(client, method: str, path: str, headers: dict):
    return await client.request(method, f"{BASE}{path.replace('{item_id}', str(uuid.uuid4()))}", headers=headers)


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_anonymous_requests_are_rejected_on_every_admin_route(client, method, path):
    resp = await _call(client, method, path, headers={})

    assert resp.status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _admin_routes())
async def test_non_admins_are_rejected_on_every_admin_route(client, non_admin, method, path):
    resp = await _call(client, method, path, headers=non_admin)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


async def test_a_non_admin_cannot_change_anything(client, admin, non_admin):
    item = await _create(client, admin)

    created = await client.post(
        f"{BASE}/manage/items", json={"title_cs": "X", "summary_cs": "Y"}, headers=non_admin
    )
    patched = await client.patch(f"{BASE}/manage/items/{item['id']}", json={"title_cs": "Hacked"}, headers=non_admin)
    deleted = await client.delete(f"{BASE}/manage/items/{item['id']}", headers=non_admin)

    assert (created.status_code, patched.status_code, deleted.status_code) == (403, 403, 403)
    unchanged = await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)
    assert unchanged.json() == item
    assert await _public_slugs(client) == [item["slug"]]


# --- Public: list --------------------------------------------------------------


async def test_public_endpoints_need_no_sign_in(client, admin):
    item = await _create(client, admin)

    listing = await client.get(f"{BASE}/items")
    detail = await client.get(f"{BASE}/items/{item['slug']}")

    assert listing.status_code == 200
    assert detail.status_code == 200


async def test_public_list_is_empty_without_items(client):
    resp = await client.get(f"{BASE}/items")

    assert resp.status_code == 200
    assert resp.json() == []


async def test_public_list_shows_only_published_items(client, admin):
    shown = await _create(client, admin, slug="shown")
    await _create(client, admin, slug="hidden", published=False)

    assert await _public_slugs(client) == [shown["slug"]]


async def test_public_list_is_ordered_by_sort_order(client, admin):
    for slug, order in (("c-third", 30), ("a-first", 10), ("b-second", 20)):
        await _create(client, admin, slug=slug, sort_order=order)

    assert await _public_slugs(client) == ["a-first", "b-second", "c-third"]


async def test_public_list_breaks_ties_by_id(client, admin):
    items = [await _create(client, admin, slug=f"tie-{n}", sort_order=7) for n in range(4)]
    by_id = sorted(items, key=lambda i: uuid.UUID(i["id"]))

    assert await _public_slugs(client) == [i["slug"] for i in by_id]


async def test_public_list_items_carry_exactly_the_public_fields(client, admin):
    await _create(
        client,
        admin,
        slug="full",
        title_en="Project",
        summary_en="Short description.",
        description_cs="Dlouhý popis.",
        description_en="Long description.",
        url="https://example.com/x",
        status="in_preparation",
        tags=["React", "FastAPI"],
        published=True,
        sort_order=3,
    )

    (item,) = (await client.get(f"{BASE}/items")).json()

    assert set(item) == PUBLIC_ITEM_KEYS
    assert item == {
        "slug": "full",
        "title": "Projekt",
        "summary": "Krátký popis projektu.",
        "url": "https://example.com/x",
        "status": "in_preparation",
        "tags": ["React", "FastAPI"],
    }


async def test_public_list_limit(client, admin):
    for n in range(1, 5):
        await _create(client, admin, slug=f"item-{n}", sort_order=n)

    assert await _public_slugs(client, limit=2) == ["item-1", "item-2"]
    assert await _public_slugs(client, limit=1) == ["item-1"]
    assert len(await _public_slugs(client, limit=50)) == 4
    assert len(await _public_slugs(client)) == 4


async def test_limit_counts_published_items_only(client, admin):
    await _create(client, admin, slug="hidden-first", sort_order=1, published=False)
    await _create(client, admin, slug="visible", sort_order=2)

    assert await _public_slugs(client, limit=1) == ["visible"]


@pytest.mark.parametrize("limit", ["0", "51", "-1", "abc", "1.5"])
async def test_public_list_rejects_an_invalid_limit(client, limit):
    resp = await client.get(f"{BASE}/items", params={"limit": limit})

    assert resp.status_code == 422


# --- Public: language ----------------------------------------------------------


@pytest.fixture()
async def bilingual(client, admin):
    return await _create(
        client,
        admin,
        slug="dvojjazycny",
        title_cs="Český název",
        title_en="English title",
        summary_cs="Český popis.",
        summary_en="English summary.",
        description_cs="Český text.\n\nDruhý odstavec.",
        description_en="English text.\n\nSecond paragraph.",
    )


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (None, "cs"),
        ("", "cs"),
        ("cs", "cs"),
        ("CS", "cs"),
        ("cs-CZ", "cs"),
        ("en", "en"),
        ("EN", "en"),
        ("en-GB", "en"),
        ("en_US", "en"),
        (" en ", "en"),
        ("de", "cs"),
        ("de-AT", "cs"),
        ("xx_YY", "cs"),
        ("not a language", "cs"),
    ],
)
async def test_language_resolution_on_list_and_detail(client, bilingual, language, expected):
    params = {} if language is None else {"language": language}
    title = {"cs": "Český název", "en": "English title"}[expected]
    summary = {"cs": "Český popis.", "en": "English summary."}[expected]
    description = {"cs": "Český text.\n\nDruhý odstavec.", "en": "English text.\n\nSecond paragraph."}[expected]

    (listed,) = (await client.get(f"{BASE}/items", params=params)).json()
    detail = (await client.get(f"{BASE}/items/dvojjazycny", params=params)).json()

    assert (listed["title"], listed["summary"]) == (title, summary)
    assert (detail["title"], detail["summary"], detail["description"]) == (title, summary, description)


async def test_language_longer_than_35_characters_is_rejected(client, bilingual):
    assert (await client.get(f"{BASE}/items", params={"language": "e" * 35})).status_code == 200
    assert (await client.get(f"{BASE}/items", params={"language": "e" * 36})).status_code == 422
    assert (await client.get(f"{BASE}/items/dvojjazycny", params={"language": "e" * 36})).status_code == 422


async def test_empty_english_texts_fall_back_to_czech(client, admin):
    await _create(client, admin, slug="jen-cesky", description_cs="Jen česky.")

    (listed,) = (await client.get(f"{BASE}/items", params={"language": "en"})).json()
    detail = (await client.get(f"{BASE}/items/jen-cesky", params={"language": "en"})).json()

    assert listed["title"] == "Projekt"
    assert listed["summary"] == "Krátký popis projektu."
    assert detail["description"] == "Jen česky."


async def test_each_field_falls_back_on_its_own(client, admin):
    await _create(client, admin, slug="napul", title_en="Only a title", description_en="Only a text.")

    detail = (await client.get(f"{BASE}/items/napul", params={"language": "en"})).json()

    assert detail["title"] == "Only a title"
    assert detail["summary"] == "Krátký popis projektu."
    assert detail["description"] == "Only a text."


async def test_empty_czech_texts_fall_back_to_english(client, admin, db_session):
    """The API refuses an empty Czech title, so this can only come from the
    database - but then Czech visitors should still see something."""
    await _create(client, admin, slug="bez-cestiny", title_en="English title", summary_en="English summary.")
    await db_session.execute(update(PortfolioItem).where(PortfolioItem.slug == "bez-cestiny").values(title_cs=""))

    detail = (await client.get(f"{BASE}/items/bez-cestiny", params={"language": "cs"})).json()

    assert detail["title"] == "English title"
    assert detail["summary"] == "Krátký popis projektu."


async def test_whitespace_only_english_text_counts_as_empty(client, admin, db_session):
    await _create(client, admin, slug="mezery")
    await db_session.execute(update(PortfolioItem).where(PortfolioItem.slug == "mezery").values(title_en="   "))

    detail = (await client.get(f"{BASE}/items/mezery", params={"language": "en"})).json()

    assert detail["title"] == "Projekt"


# --- Public: detail ------------------------------------------------------------


async def test_detail_has_the_public_fields_and_the_description(client, admin):
    await _create(
        client,
        admin,
        slug="detail",
        description_cs="První odstavec.\n\nDruhý odstavec,\nnový řádek.",
        url="https://example.com",
        status="live",
        tags=["A"],
    )

    resp = await client.get(f"{BASE}/items/detail")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == PUBLIC_ITEM_KEYS | {"description"}
    assert body["description"] == "První odstavec.\n\nDruhý odstavec,\nnový řádek."
    assert body["url"] == "https://example.com"
    assert body["tags"] == ["A"]


async def test_unknown_and_unpublished_slugs_answer_the_same_404(client, admin):
    await _create(client, admin, slug="skryta", published=False)

    unpublished = await client.get(f"{BASE}/items/skryta")
    unknown = await client.get(f"{BASE}/items/neexistuje")

    assert unpublished.status_code == unknown.status_code == 404
    assert unpublished.json() == unknown.json()
    assert unpublished.headers["content-type"] == unknown.headers["content-type"]


@pytest.mark.parametrize("slug", ["UPPER", "with space", "x" * 300, "%00", "manage"])
async def test_odd_slugs_are_a_404_not_an_error(client, slug):
    resp = await client.get(f"{BASE}/items/{slug}")

    assert resp.status_code == 404


async def test_unpublishing_and_republishing_toggles_the_public_page(client, admin):
    item = await _create(client, admin, slug="prepinac")
    assert (await client.get(f"{BASE}/items/prepinac")).status_code == 200

    await client.patch(f"{BASE}/manage/items/{item['id']}", json={"published": False}, headers=admin)
    assert (await client.get(f"{BASE}/items/prepinac")).status_code == 404
    assert await _public_slugs(client) == []

    await client.patch(f"{BASE}/manage/items/{item['id']}", json={"published": True}, headers=admin)
    assert (await client.get(f"{BASE}/items/prepinac")).status_code == 200
    assert await _public_slugs(client) == ["prepinac"]


async def test_public_responses_never_leak_admin_fields(client, admin):
    await _create(client, admin, slug="tajne", published=True, sort_order=99)

    text = (await client.get(f"{BASE}/items")).text + (await client.get(f"{BASE}/items/tajne")).text

    for leaked in ("sort_order", "published", "created_at", "updated_at", "title_cs", "title_en", '"id"'):
        assert leaked not in text


# --- Administrators: read ------------------------------------------------------


async def test_admin_list_has_every_item_with_every_field_of_both_languages(client, admin):
    await _create(client, admin, slug="viditelna", title_en="Visible", sort_order=1)
    await _create(client, admin, slug="skryta", published=False, sort_order=2)

    resp = await client.get(f"{BASE}/manage/items", headers=admin)

    assert resp.status_code == 200
    items = resp.json()
    assert [i["slug"] for i in items] == ["viditelna", "skryta"]
    assert all(set(i) == ADMIN_ITEM_KEYS for i in items)
    assert items[0]["title_en"] == "Visible"
    assert items[1]["published"] is False


async def test_admin_get_returns_the_item(client, admin):
    item = await _create(client, admin, slug="jedna")

    resp = await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)

    assert resp.status_code == 200
    assert resp.json() == item


async def test_admin_get_unknown_item_is_404(client, admin):
    resp = await client.get(f"{BASE}/manage/items/{uuid.uuid4()}", headers=admin)

    assert resp.status_code == 404


async def test_admin_get_with_a_malformed_id_is_422(client, admin):
    resp = await client.get(f"{BASE}/manage/items/not-a-uuid", headers=admin)

    assert resp.status_code == 422


# --- Administrators: create ----------------------------------------------------


async def test_create_with_only_the_required_fields_uses_the_defaults(client, admin):
    item = await _create(client, admin, title_cs="Web", summary_cs="Můj web.")

    assert set(item) == ADMIN_ITEM_KEYS
    assert item["title_en"] == item["summary_en"] == ""
    assert item["description_cs"] == item["description_en"] == ""
    assert item["url"] is None
    assert item["status"] == "live"
    assert item["tags"] == []
    assert item["published"] is True
    assert item["slug"] == "web"
    assert item["sort_order"] == 1


async def test_create_stores_everything_that_was_sent(client, admin):
    sent = {
        "slug": "muj-projekt",
        "title_cs": "Můj projekt",
        "title_en": "My project",
        "summary_cs": "Stručně.",
        "summary_en": "Briefly.",
        "description_cs": "Popis.\n\nDalší odstavec.",
        "description_en": "Description.\n\nAnother paragraph.",
        "url": "https://example.com/projekt?a=1#b",
        "status": "in_preparation",
        "tags": ["Python", "Postgres"],
        "published": False,
        "sort_order": 42,
    }

    item = await _create(client, admin, **sent)

    assert {k: item[k] for k in sent} == sent
    fetched = (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).json()
    assert fetched == item


async def test_create_without_sort_order_appends_at_the_end(client, admin):
    orders = [(await _create(client, admin))["sort_order"] for _ in range(3)]
    assert orders == [1, 2, 3]

    await _create(client, admin, sort_order=20)
    assert (await _create(client, admin))["sort_order"] == 21


async def test_create_with_an_explicit_sort_order_may_tie(client, admin):
    first = await _create(client, admin, sort_order=5)
    second = await _create(client, admin, sort_order=5)

    assert first["sort_order"] == second["sort_order"] == 5


# --- Administrators: slugs -----------------------------------------------------


async def test_generated_slug_comes_from_the_english_title(client, admin):
    item = await _create(client, admin, title_cs="Moje aplikace", title_en="My Application")

    assert item["slug"] == "my-application"


async def test_generated_slug_falls_back_to_the_czech_title(client, admin):
    item = await _create(client, admin, title_cs="Moje aplikace", title_en="")

    assert item["slug"] == "moje-aplikace"


async def test_generated_slug_transliterates_diacritics(client, admin):
    item = await _create(client, admin, title_cs="Příliš žluťoučký kůň: úpěl ďábelské ódy!", title_en="")

    assert item["slug"] == "prilis-zlutoucky-kun-upel-dabelske-ody"


async def test_a_blank_slug_is_the_same_as_none(client, admin):
    item = await _create(client, admin, slug="  ", title_cs="Z názvu")

    assert item["slug"] == "z-nazvu"


async def test_generated_slugs_get_a_number_on_collision(client, admin):
    slugs = [(await _create(client, admin, title_cs="Web", title_en="")) ["slug"] for _ in range(4)]

    assert slugs == ["web", "web-2", "web-3", "web-4"]


async def test_generated_slug_skips_a_taken_number(client, admin):
    await _create(client, admin, slug="web")
    await _create(client, admin, slug="web-2")

    assert (await _create(client, admin, title_cs="Web"))["slug"] == "web-3"


async def test_generated_slug_collides_with_an_unpublished_item_too(client, admin):
    await _create(client, admin, slug="web", published=False)

    assert (await _create(client, admin, title_cs="Web"))["slug"] == "web-2"


async def test_a_long_title_gives_a_slug_within_the_limit_even_with_a_suffix(client, admin):
    title = "Dlouhý název " * 9  # 117 characters
    first = await _create(client, admin, title_cs=title.strip(), title_en="")
    second = await _create(client, admin, title_cs=title.strip(), title_en="")

    assert len(first["slug"]) <= 80
    assert len(second["slug"]) <= 80
    assert second["slug"].endswith("-2")
    assert first["slug"] != second["slug"]
    for slug in (first["slug"], second["slug"]):
        assert "--" not in slug
        assert not slug.startswith("-")
        assert slug.replace("-", "").isalnum()


async def test_a_title_without_letters_gets_a_placeholder_slug(client, admin):
    first = await _create(client, admin, title_cs="★★★", title_en="")
    second = await _create(client, admin, title_cs="???", title_en="")

    assert (first["slug"], second["slug"]) == ("item", "item-2")


async def test_english_title_without_letters_falls_back_to_czech_for_the_slug(client, admin):
    item = await _create(client, admin, title_cs="Hra", title_en="★")

    assert item["slug"] == "hra"


async def test_the_reserved_slug_is_never_generated(client, admin):
    item = await _create(client, admin, title_cs="Manage", title_en="")

    assert item["slug"] == "manage-2"


async def test_an_explicit_slug_that_is_taken_is_a_409(client, admin):
    await _create(client, admin, slug="obsazeny")

    resp = await client.post(
        f"{BASE}/manage/items", json={"slug": "obsazeny", "title_cs": "Jiný", "summary_cs": "Jiný."}, headers=admin
    )

    assert resp.status_code == 409
    assert len((await client.get(f"{BASE}/manage/items", headers=admin)).json()) == 1


@pytest.mark.parametrize(
    "slug",
    ["Velke", "s mezerou", "pod_tržítko", "a", "x" * 81, "-zacatek", "konec-", "dvojita--pomlcka", "čeština", "manage", "a/b"],
)
async def test_an_invalid_explicit_slug_is_a_422(client, admin, slug):
    resp = await client.post(
        f"{BASE}/manage/items", json={"slug": slug, "title_cs": "T", "summary_cs": "S"}, headers=admin
    )

    assert resp.status_code == 422


@pytest.mark.parametrize("slug", ["ab", "a1", "a-b-c", "x" * 80, "2026", "web-2"])
async def test_valid_explicit_slugs_are_accepted(client, admin, slug):
    assert (await _create(client, admin, slug=slug))["slug"] == slug


# --- Administrators: update ----------------------------------------------------


async def test_patch_changes_only_the_fields_sent(client, admin):
    item = await _create(
        client, admin, slug="puvodni", title_en="Original", tags=["A", "B"], url="https://example.com", sort_order=4
    )

    resp = await client.patch(
        f"{BASE}/manage/items/{item['id']}", json={"title_cs": "Nový název", "published": False}, headers=admin
    )

    assert resp.status_code == 200
    updated = resp.json()
    assert updated["title_cs"] == "Nový název"
    assert updated["published"] is False
    for field in ("id", "slug", "title_en", "summary_cs", "tags", "url", "sort_order", "status", "created_at"):
        assert updated[field] == item[field], field
    assert (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).json() == updated


async def test_patch_with_an_empty_body_changes_nothing(client, admin):
    item = await _create(client, admin)

    resp = await client.patch(f"{BASE}/manage/items/{item['id']}", json={}, headers=admin)

    assert resp.status_code == 200
    assert resp.json() == item


async def test_patch_can_replace_tags_and_status(client, admin):
    item = await _create(client, admin, tags=["A"], status="live")

    updated = (
        await client.patch(
            f"{BASE}/manage/items/{item['id']}", json={"tags": [], "status": "in_preparation"}, headers=admin
        )
    ).json()

    assert updated["tags"] == []
    assert updated["status"] == "in_preparation"


async def test_patch_can_clear_the_url_with_null_or_an_empty_string(client, admin):
    item = await _create(client, admin, url="https://example.com")

    first = await client.patch(f"{BASE}/manage/items/{item['id']}", json={"url": None}, headers=admin)
    assert first.json()["url"] is None

    await client.patch(f"{BASE}/manage/items/{item['id']}", json={"url": "https://example.org"}, headers=admin)
    second = await client.patch(f"{BASE}/manage/items/{item['id']}", json={"url": ""}, headers=admin)
    assert second.json()["url"] is None


async def test_patch_can_change_the_slug_and_the_public_address_follows(client, admin):
    item = await _create(client, admin, slug="stare")

    resp = await client.patch(f"{BASE}/manage/items/{item['id']}", json={"slug": "nove"}, headers=admin)

    assert resp.status_code == 200
    assert resp.json()["slug"] == "nove"
    assert (await client.get(f"{BASE}/items/stare")).status_code == 404
    assert (await client.get(f"{BASE}/items/nove")).status_code == 200


async def test_patch_to_the_items_own_slug_is_fine(client, admin):
    item = await _create(client, admin, slug="moje")

    resp = await client.patch(
        f"{BASE}/manage/items/{item['id']}", json={"slug": "moje", "title_cs": "Změna"}, headers=admin
    )

    assert resp.status_code == 200
    assert resp.json()["title_cs"] == "Změna"


async def test_patch_to_a_taken_slug_is_a_409_and_changes_nothing(client, admin):
    await _create(client, admin, slug="prvni")
    second = await _create(client, admin, slug="druhy")

    resp = await client.patch(
        f"{BASE}/manage/items/{second['id']}", json={"slug": "prvni", "title_cs": "Nový"}, headers=admin
    )

    assert resp.status_code == 409
    assert (await client.get(f"{BASE}/manage/items/{second['id']}", headers=admin)).json() == second


@pytest.mark.parametrize("slug", ["Velke", "a", "x" * 81, "s mezerou", "manage", "-a"])
async def test_patch_to_an_invalid_slug_is_a_422_and_changes_nothing(client, admin, slug):
    item = await _create(client, admin, slug="platny")

    resp = await client.patch(f"{BASE}/manage/items/{item['id']}", json={"slug": slug}, headers=admin)

    assert resp.status_code == 422
    assert (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).json() == item


async def test_patch_unknown_item_is_404(client, admin):
    resp = await client.patch(f"{BASE}/manage/items/{uuid.uuid4()}", json={"title_cs": "X"}, headers=admin)

    assert resp.status_code == 404


async def test_patch_can_set_an_explicit_sort_order(client, admin):
    first = await _create(client, admin, slug="a-first")
    second = await _create(client, admin, slug="b-second")

    await client.patch(f"{BASE}/manage/items/{second['id']}", json={"sort_order": 0}, headers=admin)

    assert await _public_slugs(client) == ["b-second", "a-first"]
    assert first["sort_order"] == 1


# --- Administrators: delete ----------------------------------------------------


async def test_delete_removes_the_item_everywhere(client, admin):
    item = await _create(client, admin, slug="smazat")
    keep = await _create(client, admin, slug="nechat")

    resp = await client.delete(f"{BASE}/manage/items/{item['id']}", headers=admin)

    assert resp.status_code == 204
    assert resp.content == b""
    assert (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).status_code == 404
    assert (await client.get(f"{BASE}/items/smazat")).status_code == 404
    assert [i["slug"] for i in (await client.get(f"{BASE}/manage/items", headers=admin)).json()] == [keep["slug"]]


async def test_a_deleted_items_slug_can_be_used_again(client, admin):
    item = await _create(client, admin, slug="znovu")
    await client.delete(f"{BASE}/manage/items/{item['id']}", headers=admin)

    assert (await _create(client, admin, slug="znovu"))["slug"] == "znovu"


async def test_delete_unknown_item_is_404(client, admin):
    resp = await client.delete(f"{BASE}/manage/items/{uuid.uuid4()}", headers=admin)

    assert resp.status_code == 404
