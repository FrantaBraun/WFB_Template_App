# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the five projects the portfolio migration seeds.

conftest.py does not build the schema - db_session just opens a transaction
on whatever database DATABASE_URL names, so the suite needs one that
`alembic upgrade head` has been run on, and the seed rows exist there. A test
that merely read them would depend on nobody having edited the portfolio in
that database since (the shared development one is edited by its owner), so
these tests REPLAY the migration's own insert (`_insert_seed_items`) into an
emptied table inside the rolled-back transaction and check what comes out:
the literal in the migration is valid for the module, fits the real table,
and reads back through the public endpoints unchanged. Nothing is left behind.
"""

import importlib.util

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.config import BASE_DIR
from app.database import get_db
from app.modules.portfolio.models import PortfolioItem
from app.modules.portfolio.router import router as portfolio_router
from app.modules.portfolio.schemas import ItemCreate

BASE = "/api/modules/portfolio"
SEED_SLUGS = ["withfbraun", "auth", "template-app", "api-hub", "my-repository"]


def _load_migration():
    files = list((BASE_DIR / "alembic" / "versions").glob("*_add_portfolio_items_table.py"))
    assert len(files) == 1, files
    spec = importlib.util.spec_from_file_location("portfolio_seed_migration", files[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load_migration()
SEED = migration.SEED_ITEMS

_app = FastAPI()
_app.include_router(portfolio_router, prefix=BASE)


@pytest.fixture()
async def seeded(db_session):
    """The table emptied and the migration's seed inserted, in this test's own transaction."""
    await db_session.execute(delete(PortfolioItem))

    def replay(sync_session):
        with Operations.context(MigrationContext.configure(sync_session.connection())):
            migration._insert_seed_items()

    await db_session.run_sync(replay)
    _app.dependency_overrides[get_db] = lambda: db_session
    yield db_session
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client(seeded):
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


# --- The literal itself (needs no database) ------------------------------------


def test_the_migration_seeds_exactly_the_five_projects_in_order():
    assert [item["slug"] for item in SEED] == SEED_SLUGS
    assert [item["sort_order"] for item in SEED] == [1, 2, 3, 4, 5]


def test_the_migration_is_part_of_the_alembic_chain_and_can_be_undone():
    script = ScriptDirectory(str(BASE_DIR / "alembic"))
    revision = script.get_revision(migration.revision)

    assert revision is not None
    assert revision.down_revision == migration.down_revision
    assert script.get_revision(migration.down_revision) is not None
    assert callable(migration.downgrade)


@pytest.mark.parametrize("item", SEED, ids=SEED_SLUGS)
def test_every_seed_item_passes_the_modules_own_validation_unchanged(item):
    """So an administrator opening and saving a seeded item changes nothing."""
    assert ItemCreate.model_validate(item).model_dump() == item


def test_the_seed_keeps_the_texts_in_both_languages_and_the_one_unfinished_project():
    by_slug = {item["slug"]: item for item in SEED}

    assert all(item["title_cs"] and item["summary_cs"] and item["title_en"] and item["summary_en"] for item in SEED)
    assert all(item["published"] for item in SEED)
    assert by_slug["my-repository"]["status"] == "in_preparation"
    assert by_slug["my-repository"]["url"] is None
    assert all(item["status"] == "live" and item["url"] for item in SEED if item["slug"] != "my-repository")
    assert "–" in by_slug["withfbraun"]["summary_cs"]  # the en dash and the diacritics are not mangled
    assert "příběhy" in by_slug["withfbraun"]["summary_cs"]
    assert "\n\n" in by_slug["withfbraun"]["description_cs"]


# --- Replayed into the real table ----------------------------------------------


async def test_the_seed_inserts_into_the_real_table(seeded):
    count = await seeded.scalar(select(func.count()).select_from(PortfolioItem))
    slugs = (await seeded.scalars(select(PortfolioItem.slug).order_by(PortfolioItem.sort_order))).all()

    assert count == 5
    assert list(slugs) == SEED_SLUGS


async def test_the_public_list_shows_the_seed_in_order(client):
    resp = await client.get(f"{BASE}/items")

    assert resp.status_code == 200
    assert [item["slug"] for item in resp.json()] == SEED_SLUGS


@pytest.mark.parametrize("language", ["cs", "en"])
@pytest.mark.parametrize("seed", SEED, ids=SEED_SLUGS)
async def test_every_seed_item_reads_back_unchanged_in_both_languages(client, seed, language):
    resp = await client.get(f"{BASE}/items/{seed['slug']}", params={"language": language})

    assert resp.status_code == 200
    assert resp.json() == {
        "slug": seed["slug"],
        "title": seed[f"title_{language}"],
        "summary": seed[f"summary_{language}"],
        "description": seed[f"description_{language}"],
        "url": seed["url"],
        "status": seed["status"],
        "tags": seed["tags"],
    }


async def test_the_seeded_tags_keep_their_order_and_an_empty_list_stays_empty(client):
    items = {item["slug"]: item for item in (await client.get(f"{BASE}/items")).json()}

    assert items["template-app"]["tags"] == ["FastAPI", "React", "TypeScript", "PostgreSQL", "Tailwind CSS"]
    assert items["my-repository"]["tags"] == []
