# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The public category search (title and description, ignoring case and
diacritics, busiest first) and the sitemap that lists the categories.

Same setup as test_modules_boards_router.py: only this module's router on a
throwaway app, every test on empty boards tables inside its own rolled-back
transaction."""

import importlib.util
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.modules.boards import search, sitemap
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.boards.models import STATUS_BLOCKED, STATUS_HIDDEN, Category, Post, Resonance
from app.modules.boards.router import router as boards_router

BASE = "/api/modules/boards"
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# The package's `router` attribute is the APIRouter, which shadows the submodule.
router_module = sys.modules["app.modules.boards.router"]

_app = FastAPI()
_app.include_router(boards_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session):
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=20)
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def author(db_session) -> User:
    user = User(auth_sub=uuid.uuid4())
    db_session.add(user)
    await db_session.commit()
    return user


async def _category(db_session, author, slug, title, description="A board.", **fields) -> Category:
    category = Category(title=title, slug=slug, description=description, created_by_id=author.id, **fields)
    db_session.add(category)
    await db_session.commit()
    return category


async def _post(db_session, author, category, title="Post", **fields) -> Post:
    post = Post(category_id=category.id, author_id=author.id, title=title, body="Body", **fields)
    db_session.add(post)
    await db_session.commit()
    return post


async def _slugs(client, **params) -> list[str]:
    resp = await client.get(f"{BASE}/categories", params=params)
    assert resp.status_code == 200
    return [item["slug"] for item in resp.json()["items"]]


# --- Normalizing ----------------------------------------------------------------


def test_normalize_text_drops_case_diacritics_and_extra_spaces():
    assert search.normalize_text("  Příliš   ŽLUŤOUČKÝ\tKůň ") == "prilis zlutoucky kun"
    assert search.build_search_text("Příroda", "Zvířata a lesy") == "priroda zvirata a lesy"


def test_the_migrations_copy_of_the_normalizer_matches_the_apps():
    path = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "bd7b5715b84c_add_category_search_text.py"
    spec = importlib.util.spec_from_file_location("category_search_text_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    for text in ("Příroda a ZVÍŘATA", "straße  Œuvre", "éclair", "  ", "100% _ \\ hotovo", "日本語 ﬁ"):
        assert migration._normalize(text) == search.normalize_text(text)


async def test_a_category_made_any_way_is_searchable(db_session, author):
    category = await _category(db_session, author, "priroda", "Příroda", "Zvířata a lesy")

    await db_session.refresh(category)

    assert category.search_text == "priroda zvirata a lesy"


# --- Searching ------------------------------------------------------------------


async def test_a_search_finds_a_word_in_the_title_or_in_the_description(client, db_session, author):
    await _category(db_session, author, "music", "Hudba", "Písně, koncerty a nástroje")
    await _category(db_session, author, "food", "Jídlo", "Recepty a hudba u stolu")
    await _category(db_session, author, "sport", "Sport", "Běh a plavání")

    assert sorted(await _slugs(client, q="hudba")) == ["food", "music"]
    assert await _slugs(client, q="koncerty") == ["music"]
    assert await _slugs(client, q="plavani") == ["sport"]


async def test_a_search_ignores_case_and_diacritics_both_ways(client, db_session, author):
    await _category(db_session, author, "with", "Příroda", "Zvířata a lesy")
    await _category(db_session, author, "without", "Priroda 2", "Zvirata a lesy")

    for query in ("priroda", "PŘÍRODA", "Příroda", "pŘiroda"):
        assert sorted(await _slugs(client, q=query)) == ["with", "without"], query
    assert sorted(await _slugs(client, q="zvířata")) == ["with", "without"]


async def test_every_word_of_the_query_has_to_match_in_the_title_and_description_together(client, db_session, author):
    await _category(db_session, author, "a", "Cestování", "Hory a moře")
    await _category(db_session, author, "b", "Hory", "Turistika")
    await _category(db_session, author, "c", "Moře", "Dovolená")

    assert await _slugs(client, q="cestování moře") == ["a"]
    assert await _slugs(client, q="  hory   moře ") == ["a"]
    assert sorted(await _slugs(client, q="hory")) == ["a", "b"]
    assert await _slugs(client, q="hory dovolená") == []


async def test_a_word_is_matched_anywhere_inside_the_text(client, db_session, author):
    await _category(db_session, author, "a", "Filosofie")

    assert await _slugs(client, q="loso") == ["a"]


async def test_percent_and_underscore_in_a_query_are_taken_literally(client, db_session, author):
    await _category(db_session, author, "pct", "100% hotovo")
    await _category(db_session, author, "snake", "snake_case")
    await _category(db_session, author, "plain", "Obyčejná")

    assert await _slugs(client, q="100%") == ["pct"]
    assert await _slugs(client, q="e_c") == ["snake"]
    assert await _slugs(client, q="%") == ["pct"]
    assert await _slugs(client, q="_") == ["snake"]
    assert await _slugs(client, q="\\") == []


@pytest.mark.parametrize("blank", ["", " ", "   \t "])
async def test_a_blank_query_is_no_search(client, db_session, author, blank):
    await _category(db_session, author, "a", "A")
    await _category(db_session, author, "b", "B")

    assert sorted(await _slugs(client, q=blank)) == ["a", "b"]


async def test_nothing_found_is_an_empty_page_not_an_error(client, db_session, author):
    await _category(db_session, author, "a", "A")

    resp = await client.get(f"{BASE}/categories", params={"q": "neexistuje"})

    assert resp.status_code == 200
    assert resp.json() == {"items": [], "has_more": False}


async def test_a_query_over_100_characters_is_refused(client):
    assert (await client.get(f"{BASE}/categories", params={"q": "x" * 100})).status_code == 200
    assert (await client.get(f"{BASE}/categories", params={"q": "x" * 101})).status_code == 422


async def test_a_blocked_category_is_not_found_by_a_search(client, db_session, author):
    await _category(db_session, author, "open", "Hudba")
    await _category(db_session, author, "closed", "Hudba 2", status=STATUS_BLOCKED)

    assert await _slugs(client, q="hudba") == ["open"]


async def test_the_search_text_is_never_part_of_the_answer(client, db_session, author):
    await _category(db_session, author, "a", "Příroda")

    resp = await client.get(f"{BASE}/categories", params={"q": "priroda"})

    assert set(resp.json()["items"][0]) == {"id", "title", "slug", "description", "post_count", "created_at"}
    assert "search_text" not in resp.text


# --- Order ------------------------------------------------------------------------


async def test_found_categories_come_busiest_first_then_by_title(client, db_session, author):
    quiet_b = await _category(db_session, author, "quiet-b", "Hudba B")
    quiet_a = await _category(db_session, author, "quiet-a", "Hudba A")
    busy = await _category(db_session, author, "busy", "Hudba busy")
    busiest = await _category(db_session, author, "busiest", "Hudba nejvíc")
    other = await _category(db_session, author, "other", "Sport", "Tady o hudbě nic není... vlastně hudba")
    for _ in range(3):
        await _post(db_session, author, busiest)
    for _ in range(2):
        await _post(db_session, author, busy)
    await _post(db_session, author, quiet_b)
    assert quiet_a is not None and other is not None

    resp = await client.get(f"{BASE}/categories", params={"q": "hudba"})

    assert [(c["slug"], c["post_count"]) for c in resp.json()["items"]] == [
        ("busiest", 3),
        ("busy", 2),
        ("quiet-b", 1),
        ("quiet-a", 0),
        ("other", 0),
    ]


async def test_only_published_posts_count_for_the_order(client, db_session, author):
    hidden_heavy = await _category(db_session, author, "hidden-heavy", "Téma A")
    one_live = await _category(db_session, author, "one-live", "Téma B")
    for _ in range(3):
        await _post(db_session, author, hidden_heavy, status=STATUS_HIDDEN)
    await _post(db_session, author, one_live)

    resp = await client.get(f"{BASE}/categories", params={"q": "téma"})

    assert [(c["slug"], c["post_count"]) for c in resp.json()["items"]] == [("one-live", 1), ("hidden-heavy", 0)]


async def test_a_search_pages_through_its_results_in_the_same_order(client, db_session, author):
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=2)
    busy = await _category(db_session, author, "m-busy", "Hudba busy")
    for slug in ("m1", "m2", "m3", "m4"):
        await _category(db_session, author, slug, f"Hudba {slug}")
    await _category(db_session, author, "x", "Sport")
    await _post(db_session, author, busy)

    first = (await client.get(f"{BASE}/categories", params={"q": "hudba"})).json()
    second = (await client.get(f"{BASE}/categories", params={"q": "hudba", "offset": 2})).json()
    third = (await client.get(f"{BASE}/categories", params={"q": "hudba", "offset": 4})).json()

    assert [c["slug"] for c in first["items"] + second["items"] + third["items"]] == [
        "m-busy",
        "m1",
        "m2",
        "m3",
        "m4",
    ]
    assert (first["has_more"], second["has_more"], third["has_more"]) == (True, True, False)


# --- The sitemap -------------------------------------------------------------------


def _locs(resp) -> list[str]:
    root = ElementTree.fromstring(resp.content)
    return [loc.text for loc in root.findall("sm:url/sm:loc", SITEMAP_NS)]


@pytest.fixture()
def frontend_at():
    """Points the sitemap at a frontend address."""

    def _set(url: str) -> None:
        _app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(update={"frontend_url": url})

    return _set


@pytest.fixture()
def modules_on(monkeypatch):
    def _set(*keys: str) -> None:
        monkeypatch.setattr(router_module, "load_enabled_module_keys", lambda: list(keys))

    return _set


async def test_the_sitemap_is_xml_with_the_public_pages_and_the_published_categories(
    client, db_session, author, frontend_at, modules_on
):
    frontend_at("https://bumpfeel.example")
    modules_on("boards", "stripe_payment_gate", "kontaktni_formular")
    await _category(db_session, author, "priroda", "Příroda")
    await _category(db_session, author, "closed", "Zavřená", status=STATUS_BLOCKED)

    resp = await client.get(f"{BASE}/sitemap.xml")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "max-age" in resp.headers["cache-control"]
    assert _locs(resp) == [
        "https://bumpfeel.example/",
        "https://bumpfeel.example/categories",
        "https://bumpfeel.example/o-nas",
        "https://bumpfeel.example/obchodni-podminky",
        "https://bumpfeel.example/ochrana-osobnich-udaju",
        "https://bumpfeel.example/cookies",
        "https://bumpfeel.example/contact",
        "https://bumpfeel.example/categories/priroda",
    ]


async def test_pages_of_a_module_that_is_off_are_not_in_the_sitemap(client, frontend_at, modules_on):
    frontend_at("https://bumpfeel.example")
    modules_on("boards")

    assert _locs(await client.get(f"{BASE}/sitemap.xml")) == [
        "https://bumpfeel.example/",
        "https://bumpfeel.example/categories",
    ]

    modules_on("boards", "kontaktni_formular")

    assert _locs(await client.get(f"{BASE}/sitemap.xml"))[-1] == "https://bumpfeel.example/contact"


async def test_the_sitemap_takes_the_address_without_a_trailing_slash(client, frontend_at, modules_on):
    frontend_at("https://bumpfeel.example/")
    modules_on("boards")

    assert _locs(await client.get(f"{BASE}/sitemap.xml"))[0] == "https://bumpfeel.example/"


async def test_a_category_is_dated_by_its_newest_published_post(client, db_session, author, frontend_at, modules_on):
    frontend_at("https://bumpfeel.example")
    modules_on("boards")
    created = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    newest = created + timedelta(days=30)
    hidden_later = created + timedelta(days=60)
    lively = await _category(db_session, author, "lively", "Živá", created_at=created)
    await _post(db_session, author, lively, created_at=created + timedelta(days=5))
    await _post(db_session, author, lively, created_at=newest)
    await _post(db_session, author, lively, created_at=hidden_later, status=STATUS_HIDDEN)
    await _category(db_session, author, "empty", "Prázdná", created_at=created)

    resp = await client.get(f"{BASE}/sitemap.xml")

    dates = {
        url.find("sm:loc", SITEMAP_NS).text.rsplit("/", 1)[1]: url.find("sm:lastmod", SITEMAP_NS)
        for url in ElementTree.fromstring(resp.content).findall("sm:url", SITEMAP_NS)
    }
    assert dates["lively"].text == "2026-01-31T12:00:00Z"
    assert dates["empty"].text == "2026-01-01T12:00:00Z"
    assert dates["categories"] is None


async def test_a_slug_cannot_break_the_sitemap(client, db_session, author, frontend_at, modules_on):
    frontend_at("https://bumpfeel.example")
    modules_on("boards")
    await _category(db_session, author, "a&b<c>\"d' e", "Odd")

    resp = await client.get(f"{BASE}/sitemap.xml")

    assert resp.status_code == 200
    assert _locs(resp)[-1] == "https://bumpfeel.example/categories/a%26b%3Cc%3E%22d%27%20e"


async def test_the_sitemap_never_lists_more_urls_than_the_protocol_allows(
    client, db_session, author, frontend_at, modules_on, monkeypatch
):
    frontend_at("https://bumpfeel.example")
    modules_on("boards")
    monkeypatch.setattr(sitemap, "URL_LIMIT", 4)
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for number in range(5):
        await _category(db_session, author, f"c{number}", f"C{number}", created_at=started + timedelta(hours=number))

    locs = _locs(await client.get(f"{BASE}/sitemap.xml"))

    assert len(locs) == 4
    assert locs[2:] == ["https://bumpfeel.example/categories/c0", "https://bumpfeel.example/categories/c1"]


def test_the_protocol_limit_is_50000_urls():
    assert sitemap.URL_LIMIT == 50_000


def test_static_paths_follow_the_enabled_modules_in_a_fixed_order():
    assert sitemap.static_paths([]) == ["/", "/categories"]
    assert sitemap.static_paths(["kontaktni_formular", "stripe_payment_gate"]) == [
        "/",
        "/categories",
        "/o-nas",
        "/obchodni-podminky",
        "/ochrana-osobnich-udaju",
        "/cookies",
        "/contact",
    ]
