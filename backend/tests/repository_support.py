# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What the repository module's API tests share: the throwaway app the router
is mounted on (whether the module is on the real app depends on the branch's
backend/modules.json, which a test must not assume - see
test_modules_notifications_router.py), two signed-in users, and helpers that
create repositories, tables, attributes and records the way a client does.

ASGITransport keeps the JWT dependency chain and db_session on one event loop;
every test runs in its own rolled-back transaction. The module's limits are the
defaults unless a test calls set_limits()."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.models.user import User
from app.modules.repository import logic
from app.modules.repository.config import RepositoryConfig, get_limits
from app.modules.repository.models import Record
from app.modules.repository.router import router as repository_router

BASE = "/api/modules/repository"

repository_app = FastAPI()
repository_app.include_router(repository_router, prefix=BASE)

LIMITS = RepositoryConfig()


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    repository_app.dependency_overrides[get_db] = lambda: db_session
    repository_app.dependency_overrides[get_limits] = lambda: LIMITS
    yield
    repository_app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=repository_app), base_url="http://test") as ac:
        yield ac


class Caller(dict):
    """The headers of a signed-in user (pass it as `headers=`), which also
    knows the database id of that user for tests that seed rows directly."""

    user_id: uuid.UUID


@pytest.fixture()
async def make_user(db_session, make_access_token):
    """A factory of signed-in users: make_user() -> Caller."""

    async def _make() -> Caller:
        sub = uuid.uuid4()
        user = User(auth_sub=sub)
        db_session.add(user)
        await db_session.commit()
        caller = Caller({"Authorization": f"Bearer {make_access_token(sub=str(sub))}"})
        caller.user_id = user.id
        return caller

    return _make


@pytest.fixture()
async def alice(make_user):
    return await make_user()


@pytest.fixture()
async def bob(make_user):
    return await make_user()


def set_limits(**changes) -> None:
    repository_app.dependency_overrides[get_limits] = lambda: RepositoryConfig(**changes)


def attribute(attribute_type="text", name="Attribute", **fields) -> dict:
    """An attribute as the client sends it, with a fresh id."""
    return {"id": str(uuid.uuid4()), "name": name, "type": attribute_type, **fields}


async def create_repository(client, headers, name="My books", **fields) -> dict:
    resp = await client.post(f"{BASE}/repositories", json={"name": name, **fields}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_table(client, headers, repository, name="Novels", **fields) -> dict:
    resp = await client.post(f"{BASE}/repositories/{repository}/tables", json={"name": name, **fields}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def put_attributes(client, headers, repository, table, attributes, **params):
    return await client.put(
        f"{BASE}/repositories/{repository}/tables/{table}/attributes",
        json={"attributes": attributes},
        headers=headers,
        params=params,
    )


async def make_table(client, headers, *attributes, repository_name="My books", table_name="Novels", **table_fields):
    """A repository with one table that has these attributes (sent as given, so
    the tests know their ids): returns (repository, table, attributes)."""
    repository = await create_repository(client, headers, name=repository_name)
    table = await create_table(client, headers, repository["slug"], name=table_name, **table_fields)
    if attributes:
        resp = await put_attributes(client, headers, repository["slug"], table["slug"], list(attributes))
        assert resp.status_code == 200, resp.text
        table = resp.json()
    return repository, table, list(attributes)


def records_url(repository: dict, table: dict, suffix: str = "") -> str:
    return f"{BASE}/repositories/{repository['slug']}/tables/{table['slug']}/records{suffix}"


async def post_record(client, headers, repository, table, name="Dune", data=None, **fields) -> dict:
    resp = await client.post(records_url(repository, table), json={"name": name, "data": data or {}, **fields}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_record(db_session, table_id, name="Dune", data=None, deleted=False, created_on=None, slug=None) -> Record:
    """A record inserted directly (for tests that need many, or odd data)."""
    record = Record(
        table_id=uuid.UUID(str(table_id)),
        name=name,
        slug=slug or logic.slugify(name) + "-" + uuid.uuid4().hex[:6],
        data=data or {},
        deleted_on=datetime.now(timezone.utc) if deleted else None,
    )
    if created_on is not None:
        record.created_on = created_on
    db_session.add(record)
    await db_session.commit()
    return record


async def query(client, headers, repository, table, **body):
    resp = await client.post(
        f"{BASE}/repositories/{repository['slug']}/tables/{table['slug']}/records-query", json=body, headers=headers
    )
    return resp
