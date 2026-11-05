# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.auth_client.AuthClient: each upstream method
against a mocked auth.withfbraun.com (via respx), plus the mandatory
X-Api-Key requirement enforced across every single method."""

import json

import httpx
import pytest
import respx
from httpx import Response

from app.config import Settings
from app.services.auth_client import AuthClient


@respx.mock
async def test_register_success(auth_test_settings):
    respx.post("https://auth.test/api/auth/register").mock(
        return_value=Response(201, json={"user": {"id": "u1"}, "verify_token": "tok"})
    )
    client = AuthClient(auth_test_settings)
    result = await client.register(
        email="a@example.com", login="alogin", password="password123", first_name="A", last_name="B"
    )
    assert result["user"]["id"] == "u1"
    await client.aclose()


@respx.mock
async def test_register_sends_api_key_header(auth_test_settings):
    route = respx.post("https://auth.test/api/auth/register").mock(
        return_value=Response(201, json={"user": {}, "verify_token": "tok"})
    )
    client = AuthClient(auth_test_settings)
    await client.register(
        email="a@example.com", login="alogin", password="password123", first_name="A", last_name="B"
    )
    assert route.calls.last.request.headers["X-Api-Key"] == "test-api-key"
    await client.aclose()


@respx.mock
async def test_login_success_returns_response(auth_test_settings):
    respx.post("https://auth.test/api/auth/login").mock(
        return_value=Response(
            200, json={"access_token": "a", "refresh_token": "r", "token_type": "bearer"}
        )
    )
    client = AuthClient(auth_test_settings)
    resp = await client.login(identifier="user", password="pw")
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "a"
    await client.aclose()


@respx.mock
async def test_login_consent_required_does_not_raise(auth_test_settings):
    respx.post("https://auth.test/api/auth/login").mock(
        return_value=Response(
            403, json={"detail": {"consent_required": True, "application_group_id": "g1"}}
        )
    )
    client = AuthClient(auth_test_settings)
    resp = await client.login(identifier="user", password="pw")
    assert resp.status_code == 403
    assert resp.json()["detail"]["consent_required"] is True
    await client.aclose()


@respx.mock
async def test_refresh_raises_on_401(auth_test_settings):
    respx.post("https://auth.test/api/auth/refresh").mock(return_value=Response(401, json={}))
    client = AuthClient(auth_test_settings)
    with pytest.raises(httpx.HTTPStatusError):
        await client.refresh(refresh_token="bad")
    await client.aclose()


@respx.mock
async def test_logout_success(auth_test_settings):
    respx.post("https://auth.test/api/auth/logout").mock(return_value=Response(204))
    client = AuthClient(auth_test_settings)
    await client.logout(access_token="a", refresh_token="r")
    await client.aclose()


@respx.mock
async def test_get_me(auth_test_settings):
    """/me now returns a consent wrapper, not the flat profile directly."""
    respx.get("https://auth.test/api/auth/me").mock(
        return_value=Response(
            200,
            json={
                "consent_required": False,
                "application_group_id": "g1",
                "user": {"id": "u1", "login": "alogin"},
            },
        )
    )
    client = AuthClient(auth_test_settings)
    me = await client.get_me(access_token="a")
    assert me["consent_required"] is False
    assert me["user"]["login"] == "alogin"
    await client.aclose()


@respx.mock
async def test_get_me_consent_required(auth_test_settings):
    respx.get("https://auth.test/api/auth/me").mock(
        return_value=Response(
            200,
            json={"consent_required": True, "application_group_id": "g1", "user": None},
        )
    )
    client = AuthClient(auth_test_settings)
    me = await client.get_me(access_token="a")
    assert me["consent_required"] is True
    assert me["user"] is None
    await client.aclose()


@respx.mock
async def test_get_public_key(auth_test_settings):
    respx.get("https://auth.test/api/auth/public-key").mock(
        return_value=Response(200, json={"public_key": "PEMDATA", "algorithm": "RS256"})
    )
    client = AuthClient(auth_test_settings)
    key = await client.get_public_key()
    assert key == "PEMDATA"
    await client.aclose()


@respx.mock
async def test_get_group_info(auth_test_settings):
    respx.get("https://auth.test/api/auth/group-info").mock(
        return_value=Response(
            200,
            json={"id": "g1", "name": "My App", "description": "...", "scopes": ["email"]},
        )
    )
    client = AuthClient(auth_test_settings)
    info = await client.get_group_info()
    assert info["name"] == "My App"
    await client.aclose()


@respx.mock
async def test_update_me(auth_test_settings):
    respx.patch("https://auth.test/api/auth/me").mock(
        return_value=Response(200, json={"id": "u1", "first_name": "New"})
    )
    client = AuthClient(auth_test_settings)
    result = await client.update_me(access_token="a", payload={"first_name": "New"})
    assert result["first_name"] == "New"
    await client.aclose()


@respx.mock
async def test_get_group_attributes(auth_test_settings):
    respx.get("https://auth.test/api/auth/me/group-attributes/g1").mock(
        return_value=Response(
            200,
            json={"application_group_id": "g1", "user_data": {"company_name": "Acme"}, "updated_at": None},
        )
    )
    client = AuthClient(auth_test_settings)
    result = await client.get_group_attributes(access_token="a", group_id="g1")
    assert result["user_data"]["company_name"] == "Acme"
    await client.aclose()


@respx.mock
async def test_update_group_attributes_sends_full_user_data(auth_test_settings):
    route = respx.patch("https://auth.test/api/auth/me/group-attributes/g1").mock(
        return_value=Response(
            200,
            json={"application_group_id": "g1", "user_data": {"company_name": "Acme"}, "updated_at": None},
        )
    )
    client = AuthClient(auth_test_settings)
    result = await client.update_group_attributes(
        access_token="a", group_id="g1", user_data={"company_name": "Acme"}
    )
    assert result["user_data"]["company_name"] == "Acme"
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body == {"user_data": {"company_name": "Acme"}}
    await client.aclose()


@respx.mock
async def test_login_mfa_required_does_not_raise(auth_test_settings):
    """Password right, second factor needed: login() hands the 403 back
    untouched so the router can forward the mfa_token and methods."""
    respx.post("https://auth.test/api/auth/login").mock(
        return_value=Response(
            403,
            json={"detail": {"mfa_required": True, "mfa_token": "mt", "methods": ["totp", "backup_code"]}},
        )
    )
    client = AuthClient(auth_test_settings)
    resp = await client.login(identifier="user", password="pw")
    assert resp.status_code == 403
    assert resp.json()["detail"]["mfa_token"] == "mt"
    await client.aclose()


@respx.mock
async def test_login_mfa_sends_token_method_and_code(auth_test_settings):
    route = respx.post("https://auth.test/api/auth/login/mfa").mock(
        return_value=Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 900})
    )
    client = AuthClient(auth_test_settings)
    result = await client.login_mfa(mfa_token="mt", code="123456")
    assert result["access_token"] == "a"
    assert json.loads(route.calls.last.request.content) == {
        "mfa_token": "mt",
        "method": "totp",
        "code": "123456",
    }
    assert route.calls.last.request.headers["X-Api-Key"] == "test-api-key"
    await client.aclose()


@respx.mock
async def test_login_mfa_backup_code_method(auth_test_settings):
    route = respx.post("https://auth.test/api/auth/login/mfa").mock(
        return_value=Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 900})
    )
    client = AuthClient(auth_test_settings)
    await client.login_mfa(mfa_token="mt", code="K7QF2-M9XPA", method="backup_code")
    assert json.loads(route.calls.last.request.content)["method"] == "backup_code"
    await client.aclose()


@respx.mock
async def test_login_mfa_raises_on_wrong_code(auth_test_settings):
    respx.post("https://auth.test/api/auth/login/mfa").mock(
        return_value=Response(401, json={"detail": "Invalid verification code"})
    )
    client = AuthClient(auth_test_settings)
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await client.login_mfa(mfa_token="mt", code="000000")
    assert excinfo.value.response.status_code == 401
    await client.aclose()


@respx.mock
async def test_google_exchange_sends_code_with_api_key(auth_test_settings):
    route = respx.post("https://auth.test/api/auth/google/exchange").mock(
        return_value=Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 900})
    )
    client = AuthClient(auth_test_settings)
    result = await client.google_exchange(code="Qm3x")
    assert result["refresh_token"] == "r"
    assert json.loads(route.calls.last.request.content) == {"code": "Qm3x"}
    # Without the key the service could not apply the group's minimum sign-in level.
    assert route.calls.last.request.headers["X-Api-Key"] == "test-api-key"
    await client.aclose()


@respx.mock
async def test_google_exchange_mfa_required_raises_with_challenge(auth_test_settings):
    respx.post("https://auth.test/api/auth/google/exchange").mock(
        return_value=Response(
            403,
            json={"detail": {"mfa_required": True, "mfa_token": "mt", "methods": ["totp"]}},
        )
    )
    client = AuthClient(auth_test_settings)
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await client.google_exchange(code="Qm3x")
    assert excinfo.value.response.json()["detail"]["mfa_token"] == "mt"
    await client.aclose()


@pytest.fixture()
def no_key_client():
    return AuthClient(Settings(auth_url="https://auth.test", auth_api_key=""))


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.register(email="a@example.com", login="a", password="password123", first_name="A", last_name="B"),
        lambda c: c.login(identifier="user", password="pw"),
        lambda c: c.login_mfa(mfa_token="mt", code="123456"),
        lambda c: c.google_exchange(code="Qm3x"),
        lambda c: c.refresh(refresh_token="rt"),
        lambda c: c.logout(access_token="a", refresh_token="r"),
        lambda c: c.get_me(access_token="a"),
        lambda c: c.update_me(access_token="a", payload={}),
        lambda c: c.get_public_key(),
        lambda c: c.get_group_info(),
        lambda c: c.get_consent_info(group_id="g1", access_token="a"),
        lambda c: c.grant_consent(group_id="g1", access_token="a"),
        lambda c: c.reject_consent(group_id="g1", access_token="a"),
        lambda c: c.get_group_attributes(group_id="g1", access_token="a"),
        lambda c: c.update_group_attributes(group_id="g1", access_token="a", user_data={}),
        lambda c: c.request_password_reset(email="a@example.com"),
        lambda c: c.confirm_password_reset(token="t", new_password="password123"),
        lambda c: c.change_password(access_token="a", current_password="old", new_password="password123"),
    ],
)
async def test_every_method_requires_api_key(no_key_client, call):
    """X-Api-Key is now mandatory on every call, not just register/login."""
    with pytest.raises(RuntimeError):
        await call(no_key_client)
    await no_key_client.aclose()
