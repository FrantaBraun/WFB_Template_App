# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/auth/*: register/login/refresh/logout/me/group-info/consent,
proxied to a mocked auth.withfbraun.com and asserting the BFF's own
consent_required -> 403 conversion and bearer-auth requirements."""

import json
import uuid

import respx
from httpx import ASGITransport, AsyncClient, Response

from app.config import get_settings

AUTH_URL = get_settings().auth_url


@respx.mock
def test_register_proxies_upstream(client):
    respx.post(f"{AUTH_URL}/api/auth/register").mock(
        return_value=Response(201, json={"user": {"id": "u1"}, "verify_token": "tok"})
    )

    resp = client.post(
        "/api/auth/register",
        json={
            "email": "a@example.com",
            "login": "alogin",
            "password": "password123",
            "first_name": "A",
            "last_name": "B",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["user"]["id"] == "u1"


@respx.mock
def test_login_success(client):
    respx.post(f"{AUTH_URL}/api/auth/login").mock(
        return_value=Response(
            200,
            json={
                "access_token": "a",
                "refresh_token": "r",
                "token_type": "bearer",
                "expires_in": 900,
            },
        )
    )

    resp = client.post("/api/auth/login", json={"identifier": "user", "password": "pw"})

    assert resp.status_code == 200
    assert resp.json()["access_token"] == "a"


@respx.mock
def test_login_consent_required_passthrough(client):
    respx.post(f"{AUTH_URL}/api/auth/login").mock(
        return_value=Response(
            403, json={"detail": {"consent_required": True, "application_group_id": "g1"}}
        )
    )

    resp = client.post("/api/auth/login", json={"identifier": "user", "password": "pw"})

    assert resp.status_code == 403
    assert resp.json()["detail"]["consent_required"] is True
    assert resp.json()["detail"]["application_group_id"] == "g1"


@respx.mock
def test_refresh_success(client):
    respx.post(f"{AUTH_URL}/api/auth/refresh").mock(
        return_value=Response(
            200,
            json={
                "access_token": "a2",
                "refresh_token": "r2",
                "token_type": "bearer",
                "expires_in": 900,
            },
        )
    )

    resp = client.post("/api/auth/refresh", json={"refresh_token": "old"})

    assert resp.status_code == 200
    assert resp.json()["access_token"] == "a2"


@respx.mock
def test_refresh_expired_propagates_401(client):
    respx.post(f"{AUTH_URL}/api/auth/refresh").mock(
        return_value=Response(401, json={"detail": "session expired"})
    )

    resp = client.post("/api/auth/refresh", json={"refresh_token": "bad"})

    assert resp.status_code == 401


@respx.mock
def test_logout_success(client):
    respx.post(f"{AUTH_URL}/api/auth/logout").mock(return_value=Response(204))

    resp = client.post(
        "/api/auth/logout",
        json={"refresh_token": "r"},
        headers={"Authorization": "Bearer sometoken"},
    )

    assert resp.status_code == 204


def test_logout_requires_bearer(client):
    resp = client.post("/api/auth/logout", json={"refresh_token": "r"})
    assert resp.status_code in (401, 403)


def test_me_requires_bearer(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


async def _me_request(db_session, make_access_token, sub: str | None = None):
    # TestClient drives the app from a separate thread with its own event
    # loop, which conflicts with db_session's connection (bound to this
    # test's loop). An in-process ASGI transport keeps everything on one loop.
    from app.database import get_db
    from app.main import app as fastapi_app

    sub = sub or str(uuid.uuid4())
    token = make_access_token(sub=sub)

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    try:
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)


@respx.mock
async def test_me_creates_local_user_and_returns_upstream_profile(
    db_session, make_access_token, rsa_keypair, monkeypatch
):
    """Verified directly against the real service: once consent is granted,
    /me returns the flat profile with no wrapper at all - not
    {consent_required: false, ..., user: {...}} as originally assumed. In this
    legacy no-wrapper shape there's no application_group_id to surface, so it
    degrades to None rather than raising."""
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    sub = str(uuid.uuid4())

    respx.get(f"{AUTH_URL}/api/auth/me").mock(
        return_value=Response(200, json={"id": sub, "login": "alogin", "email": "a@example.com"})
    )

    resp = await _me_request(db_session, make_access_token, sub=sub)

    assert resp.status_code == 200
    assert resp.json()["login"] == "alogin"
    assert resp.json()["application_group_id"] is None


@respx.mock
async def test_me_wrapper_shape_with_user_populated_also_handled(
    db_session, make_access_token, rsa_keypair, monkeypatch
):
    """Defensive: if the upstream ever does wrap a granted response as
    {consent_required: false, user: {...}}, unwrap it rather than return the
    wrapper itself - and still surface application_group_id alongside it."""
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    sub = str(uuid.uuid4())

    respx.get(f"{AUTH_URL}/api/auth/me").mock(
        return_value=Response(
            200,
            json={
                "consent_required": False,
                "application_group_id": "g1",
                "user": {"id": sub, "login": "alogin", "email": "a@example.com"},
            },
        )
    )

    resp = await _me_request(db_session, make_access_token, sub=sub)

    assert resp.status_code == 200
    assert resp.json()["login"] == "alogin"
    assert resp.json()["application_group_id"] == "g1"


@respx.mock
async def test_me_consent_required_returns_403(db_session, make_access_token, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)

    respx.get(f"{AUTH_URL}/api/auth/me").mock(
        return_value=Response(
            200,
            json={"consent_required": True, "application_group_id": "g1", "user": None},
        )
    )

    resp = await _me_request(db_session, make_access_token)

    assert resp.status_code == 403
    assert resp.json()["detail"]["consent_required"] is True
    assert resp.json()["detail"]["application_group_id"] == "g1"


@respx.mock
def test_update_me_success(client):
    respx.patch(f"{AUTH_URL}/api/auth/me").mock(
        return_value=Response(200, json={"id": "u1", "first_name": "New"})
    )

    resp = client.patch(
        "/api/auth/me",
        json={"first_name": "New"},
        headers={"Authorization": "Bearer sometoken"},
    )

    assert resp.status_code == 200
    assert resp.json()["first_name"] == "New"


@respx.mock
def test_update_me_propagates_upstream_error(client):
    respx.patch(f"{AUTH_URL}/api/auth/me").mock(
        return_value=Response(422, json={"detail": "invalid country_code"})
    )

    resp = client.patch(
        "/api/auth/me",
        json={"country_code": "XX"},
        headers={"Authorization": "Bearer sometoken"},
    )

    assert resp.status_code == 422


@respx.mock
def test_get_group_attributes_success(client):
    respx.get(f"{AUTH_URL}/api/auth/me/group-attributes/g1").mock(
        return_value=Response(
            200,
            json={"application_group_id": "g1", "user_data": {"company_name": "Acme"}, "updated_at": None},
        )
    )

    resp = client.get(
        "/api/auth/me/group-attributes/g1", headers={"Authorization": "Bearer sometoken"}
    )

    assert resp.status_code == 200
    assert resp.json()["user_data"]["company_name"] == "Acme"


@respx.mock
def test_update_group_attributes_success(client):
    respx.patch(f"{AUTH_URL}/api/auth/me/group-attributes/g1").mock(
        return_value=Response(
            200,
            json={"application_group_id": "g1", "user_data": {"company_name": "Acme"}, "updated_at": None},
        )
    )

    resp = client.patch(
        "/api/auth/me/group-attributes/g1",
        json={"user_data": {"company_name": "Acme"}},
        headers={"Authorization": "Bearer sometoken"},
    )

    assert resp.status_code == 200
    assert resp.json()["user_data"]["company_name"] == "Acme"


def test_update_me_requires_bearer(client):
    resp = client.patch("/api/auth/me", json={"first_name": "New"})
    assert resp.status_code in (401, 403)


def test_group_attributes_require_bearer(client):
    resp = client.get("/api/auth/me/group-attributes/g1")
    assert resp.status_code in (401, 403)


@respx.mock
def test_group_info_proxies_upstream(client):
    respx.get(f"{AUTH_URL}/api/auth/group-info").mock(
        return_value=Response(
            200,
            json={"id": "g1", "name": "My App", "description": "...", "scopes": ["email"]},
        )
    )

    resp = client.get("/api/auth/group-info")

    assert resp.status_code == 200
    assert resp.json()["name"] == "My App"


@respx.mock
def test_grant_consent_success(client):
    respx.post(f"{AUTH_URL}/api/auth/consent/g1/grant").mock(return_value=Response(204))

    resp = client.post("/api/auth/consent/g1/grant", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 204


@respx.mock
def test_reject_consent_success(client):
    respx.post(f"{AUTH_URL}/api/auth/consent/g1/reject").mock(return_value=Response(204))

    resp = client.post("/api/auth/consent/g1/reject", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 204


def test_grant_consent_requires_bearer(client):
    resp = client.post("/api/auth/consent/g1/grant")
    assert resp.status_code in (401, 403)


@respx.mock
def test_password_reset_request_sends_link_to_this_app(client):
    route = respx.post(f"{AUTH_URL}/api/auth/password-reset/request").mock(return_value=Response(204))

    resp = client.post("/api/auth/password-reset/request", json={"email": "a@example.com"})

    assert resp.status_code == 204
    sent = json.loads(route.calls.last.request.content)
    assert sent["email"] == "a@example.com"
    assert sent["reset_url"].endswith("/reset-password")


@respx.mock
def test_password_reset_request_forwards_upstream_error(client):
    respx.post(f"{AUTH_URL}/api/auth/password-reset/request").mock(
        return_value=Response(429, json={"detail": "Too many requests"})
    )

    resp = client.post("/api/auth/password-reset/request", json={"email": "a@example.com"})

    assert resp.status_code == 429
    assert resp.json()["detail"] == "Too many requests"


def test_password_reset_request_rejects_invalid_email(client):
    resp = client.post("/api/auth/password-reset/request", json={"email": "not-an-email"})
    assert resp.status_code == 422


@respx.mock
def test_password_reset_confirm_success(client):
    route = respx.post(f"{AUTH_URL}/api/auth/password-reset/confirm").mock(return_value=Response(204))

    resp = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "tok", "new_password": "newpassword1"},
    )

    assert resp.status_code == 204
    assert json.loads(route.calls.last.request.content) == {"token": "tok", "new_password": "newpassword1"}


@respx.mock
def test_password_reset_confirm_expired_token(client):
    respx.post(f"{AUTH_URL}/api/auth/password-reset/confirm").mock(
        return_value=Response(400, json={"detail": "Invalid or expired token"})
    )

    resp = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "old", "new_password": "newpassword1"},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid or expired token"


def test_password_reset_confirm_rejects_short_password(client):
    resp = client.post("/api/auth/password-reset/confirm", json={"token": "tok", "new_password": "short"})
    assert resp.status_code == 422


@respx.mock
def test_change_password_success(client):
    route = respx.post(f"{AUTH_URL}/api/auth/me/change-password").mock(return_value=Response(204))

    resp = client.post(
        "/api/auth/me/change-password",
        json={"current_password": "oldpassword", "new_password": "newpassword1"},
        headers={"Authorization": "Bearer token"},
    )

    assert resp.status_code == 204
    assert route.calls.last.request.headers["Authorization"] == "Bearer token"
    assert json.loads(route.calls.last.request.content) == {
        "current_password": "oldpassword",
        "new_password": "newpassword1",
    }


@respx.mock
def test_change_password_wrong_current_password(client):
    respx.post(f"{AUTH_URL}/api/auth/me/change-password").mock(
        return_value=Response(400, json={"detail": "Current password is incorrect"})
    )

    resp = client.post(
        "/api/auth/me/change-password",
        json={"current_password": "wrong", "new_password": "newpassword1"},
        headers={"Authorization": "Bearer token"},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Current password is incorrect"


def test_change_password_requires_bearer(client):
    resp = client.post(
        "/api/auth/me/change-password",
        json={"current_password": "oldpassword", "new_password": "newpassword1"},
    )
    assert resp.status_code in (401, 403)
