# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the kontaktni_formular module's one endpoint: POST
/api/modules/kontaktni_formular/submit.

Deliberately does NOT use conftest.py's `client` fixture (TestClient over
the real app.main app): whether that route exists at all depends on
backend/modules.json's `enabled` array at the moment app.api.router was
first imported, which is per-branch config this test file shouldn't have
to assume one way or the other - core ships it as `[]` by design (see
CLAUDE.md's Feature modules section), so asserting through the real app
would 404 on core and on every branch that leaves this module off. Mounting just this module's router on a throwaway FastAPI app tests the
same route handler and the same URL shape, without depending on that.
No DB access here either (the module has no models), so no ASGITransport/
db_session is needed."""

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_mail import FastMail
from httpx import Response

import app.security.jwt as jwt_module
from app.config import Settings, get_settings
from app.modules.kontaktni_formular.router import router as contact_router
from app.services.email import _connection_config

AUTH_URL = get_settings().auth_url

_contact_app = FastAPI()
_contact_app.include_router(contact_router, prefix="/api/modules/kontaktni_formular")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_contact_app)


@pytest.fixture()
def contact_settings() -> Settings:
    """mail_suppress_send=True so no real SMTP connection opens - same
    approach as conftest.py's mail_test_settings, plus contact_mail set."""
    return Settings(
        contact_mail="prijem@example.com",
        mail_username="test-user",
        mail_password="test-pass",
        mail_from="noreply@example.com",
        mail_server="smtp.example.com",
        mail_port=587,
        mail_starttls=True,
        mail_ssl_tls=False,
        mail_suppress_send=True,
    )


@pytest.fixture()
def override_settings(contact_settings):
    """This route depends on Settings via FastAPI's DI specifically so tests
    can override it this way (see router.py's own comment on why) - clean
    up unconditionally so a failed test can't leak the override into an
    unrelated one."""
    _contact_app.dependency_overrides[get_settings] = lambda: contact_settings
    yield contact_settings
    _contact_app.dependency_overrides.pop(get_settings, None)


@pytest.fixture()
def signed_in(rsa_keypair, monkeypatch):
    """Seeds the module-level public-key cache directly (see test_jwt.py's
    own tests) so get_current_user_claims verifies make_access_token's
    tokens without a real call to the auth service's public-key endpoint."""
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


def test_anonymous_without_reply_to_is_rejected(client, override_settings):
    resp = client.post(
        "/api/modules/kontaktni_formular/submit",
        json={"subject": "Dotaz", "message": "Ahoj, mam otazku."},
    )
    assert resp.status_code == 422


def test_anonymous_with_reply_to_sends_both_emails(client, override_settings):
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        resp = client.post(
            "/api/modules/kontaktni_formular/submit",
            json={"subject": "Dotaz", "message": "Ahoj, mam otazku.", "reply_to": "host@example.com"},
        )

    assert resp.status_code == 204
    assert len(outbox) == 2
    assert all(m["Subject"] == "Dotaz" for m in outbox)
    recipients = {str(m["To"]) for m in outbox}
    assert any("prijem@example.com" in r for r in recipients)
    assert any("host@example.com" in r for r in recipients)


@respx.mock
def test_signed_in_sender_uses_profile_name(client, override_settings, signed_in, make_access_token):
    token = make_access_token(email="jana@example.com")
    respx.get(f"{AUTH_URL}/api/auth/me").mock(
        return_value=Response(
            200,
            json={
                "consent_required": False,
                "application_group_id": "g1",
                "user": {"first_name": "Jana", "last_name": "Novakova", "email": "jana@example.com"},
            },
        )
    )

    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        resp = client.post(
            "/api/modules/kontaktni_formular/submit",
            json={"subject": "Dotaz", "message": "Ahoj."},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 204
    assert len(outbox) == 2
    recipients = {str(m["To"]) for m in outbox}
    assert any("jana@example.com" in r for r in recipients)
    assert any("prijem@example.com" in r for r in recipients)


@respx.mock
def test_signed_in_sender_falls_back_when_profile_call_fails(client, override_settings, signed_in, make_access_token):
    token = make_access_token(email="petr@example.com", login="petrn")
    respx.get(f"{AUTH_URL}/api/auth/me").mock(return_value=Response(500))

    resp = client.post(
        "/api/modules/kontaktni_formular/submit",
        json={"subject": "Dotaz", "message": "Ahoj."},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 204


@respx.mock
def test_signed_in_sender_falls_back_when_consent_required(client, override_settings, signed_in, make_access_token):
    token = make_access_token(email="ivo@example.com")
    respx.get(f"{AUTH_URL}/api/auth/me").mock(
        return_value=Response(200, json={"consent_required": True, "application_group_id": "g1"})
    )

    resp = client.post(
        "/api/modules/kontaktni_formular/submit",
        json={"subject": "Dotaz", "message": "Ahoj."},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 204


def test_missing_contact_mail_fails_loudly(client):
    unconfigured = Settings(contact_mail="", mail_suppress_send=True)
    _contact_app.dependency_overrides[get_settings] = lambda: unconfigured
    try:
        with pytest.raises(RuntimeError):
            client.post(
                "/api/modules/kontaktni_formular/submit",
                json={"subject": "Dotaz", "message": "Ahoj.", "reply_to": "host@example.com"},
            )
    finally:
        _contact_app.dependency_overrides.pop(get_settings, None)
