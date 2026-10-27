# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The tickets module is for administrators only: this walks every route of
the module as an anonymous visitor, as a signed-in user who is not an
administrator here (even one the auth service calls "admin") and as an
administrator, and fails when a route is added outside /manage without being
listed as public."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.modules.tickets.router import router as tickets_router
from tests.tickets_support import tickets_settings

BASE = "/api/modules/tickets"

_app = FastAPI()
_app.include_router(tickets_router, prefix=BASE)

# The only routes that work without signing in (see the router's docstring).
PUBLIC_ROUTES = {("GET", "/files/{filename}")}

_SAMPLES = {
    "number": "100001",
    "entry_id": str(uuid.uuid4()),
    "attachment_id": str(uuid.uuid4()),
    "filename": "x.png",
}


def _all_routes():
    """Every (method, path) of the module, read from the OpenAPI schema - the
    router is mounted as one object on newer FastAPI."""
    paths = _app.openapi()["paths"]
    return [(method.upper(), path.removeprefix(BASE)) for path, operations in paths.items() for method in operations]


def _manage_routes():
    return [route for route in _all_routes() if route[1].startswith("/manage")]


def _fill(path: str) -> str:
    for name, value in _SAMPLES.items():
        path = path.replace("{" + name + "}", value)
    return f"{BASE}{path}"


@pytest.fixture(autouse=True)
async def _overrides(db_session, tmp_path, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_settings] = lambda: tickets_settings(tmp_path)
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    """Not an administrator here - even though the auth service calls them
    "admin": role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


async def _call(client, method, path, headers):
    if method in ("POST", "PATCH"):
        # A body that is valid for none of them: what matters here is who gets in.
        return await client.request(method, _fill(path), json={}, headers=headers)
    return await client.request(method, _fill(path), headers=headers)


ADMIN_ROUTES = {
    ("GET", "/manage"),
    ("POST", "/manage"),
    ("GET", "/manage/mailbox"),
    ("POST", "/manage/mailbox/poll"),
    ("GET", "/manage/attachments/{attachment_id}/file"),
    ("GET", "/manage/{number}"),
    ("PATCH", "/manage/{number}"),
    ("DELETE", "/manage/{number}"),
    ("POST", "/manage/{number}/entries"),
    ("PATCH", "/manage/{number}/entries/{entry_id}"),
    ("DELETE", "/manage/{number}/entries/{entry_id}"),
    ("POST", "/manage/{number}/images"),
    ("POST", "/manage/{number}/attachments"),
    ("DELETE", "/manage/{number}/attachments/{attachment_id}"),
}


def test_every_route_is_either_the_known_public_one_or_under_manage():
    assert {route for route in _all_routes() if not route[1].startswith("/manage")} == PUBLIC_ROUTES


def test_the_admin_routes_are_exactly_the_ones_this_file_checks():
    # A new route must be added to ADMIN_ROUTES, so it is walked below.
    assert set(_manage_routes()) == ADMIN_ROUTES


@pytest.mark.parametrize("method, path", sorted(ADMIN_ROUTES))
async def test_anonymous_requests_are_rejected_on_every_admin_route(client, method, path):
    resp = await _call(client, method, path, {})

    assert resp.status_code in (401, 403)


@pytest.mark.parametrize("method, path", sorted(ADMIN_ROUTES))
async def test_a_signed_in_user_who_is_not_an_administrator_gets_403_on_every_admin_route(client, non_admin, method, path):
    resp = await _call(client, method, path, non_admin)

    assert resp.status_code == 403


@pytest.mark.parametrize("method, path", sorted(ADMIN_ROUTES))
async def test_an_administrator_gets_past_the_gate_on_every_admin_route(client, admin, method, path):
    resp = await _call(client, method, path, admin)

    # Past the gate: whatever the route then says about the made-up ticket or
    # the empty body (404 / 422 / 409 ...), it is not a refusal of the user.
    assert resp.status_code not in (401, 403)


async def test_the_public_picture_route_needs_no_token(client):
    resp = await client.get(f"{BASE}/files/{'a' * 32}.png")

    assert resp.status_code == 404  # not 401: nothing named like that exists
