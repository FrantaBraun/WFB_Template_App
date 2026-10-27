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
would 404 on core and on every branch that leaves this module off.
Mounting just this module's router on a throwaway FastAPI app tests the
same route handler and the same URL shape, without depending on that.
No DB access here either (the module has no models), so no ASGITransport/
db_session is needed. The reply-template config is overridden too, so these
tests never depend on the texts a branch commits in
backend/modules/kontaktni_formular.json."""

from email.header import decode_header, make_header

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_mail import FastMail
from httpx import Response

import app.security.jwt as jwt_module
from app.config import Settings, get_settings
from app.modules.kontaktni_formular.config import ContactFormConfig, get_contact_form_config
from app.modules.kontaktni_formular.hooks import ContactHookResult, get_contact_form_hooks
from app.modules.kontaktni_formular.router import router as contact_router
from app.services.email import _connection_config

AUTH_URL = get_settings().auth_url

_contact_app = FastAPI()
_contact_app.include_router(contact_router, prefix="/api/modules/kontaktni_formular")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_contact_app)


CS_SUBJECT = "Děkujeme za zprávu: {subject}"
EN_SUBJECT = "Thanks for your message: {subject}"


def _contact_config(**overrides) -> ContactFormConfig:
    data = {
        "send_reply": True,
        "default_language": "cs",
        "reply_templates": {
            "cs": {"subject": CS_SUBJECT, "body": "Dobrý den, {sender_name}.\n\nVaše zpráva:\n{message}"},
            "en": {"subject": EN_SUBJECT, "body": "Hello {sender_name} <{reply_to}>.\n\nYour message:\n{message}"},
        },
    }
    return ContactFormConfig.model_validate({**data, **overrides})


@pytest.fixture(autouse=True)
def override_contact_config():
    # No hooks either: which modules take part in a submission is per-branch
    # config (backend/modules.json); the hook tests below set their own.
    _contact_app.dependency_overrides[get_contact_form_config] = lambda: _contact_config()
    _contact_app.dependency_overrides[get_contact_form_hooks] = lambda: []
    yield
    _contact_app.dependency_overrides.pop(get_contact_form_config, None)
    _contact_app.dependency_overrides.pop(get_contact_form_hooks, None)


def _subject(message) -> str:
    return str(make_header(decode_header(message["Subject"])))


def _text(message) -> str:
    part = next(p for p in message.walk() if p.get_content_type() == "text/plain")
    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")


def _split_outbox(outbox, owner_address="prijem@example.com"):
    """-> (owner notification, confirmation reply) from a recorded outbox."""
    owner = [m for m in outbox if owner_address in str(m["To"])]
    replies = [m for m in outbox if owner_address not in str(m["To"])]
    assert len(owner) == 1
    return owner[0], replies


def _submit_anonymous(client, **extra):
    return client.post(
        "/api/modules/kontaktni_formular/submit",
        json={"subject": "Dotaz", "message": "Ahoj, mam otazku.", "reply_to": "host@example.com", **extra},
    )


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
        resp = _submit_anonymous(client)

    assert resp.status_code == 204
    assert len(outbox) == 2
    owner, [reply] = _split_outbox(outbox)
    assert _subject(owner) == "Dotaz"
    assert "Ahoj, mam otazku." in _text(owner)
    assert "host@example.com" in str(reply["To"])


def test_reply_without_language_uses_default_language(client, override_settings):
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client)

    owner, [reply] = _split_outbox(outbox)
    assert _subject(reply) == "Děkujeme za zprávu: Dotaz"
    assert _text(reply) == "Dobrý den, host@example.com.\n\nVaše zpráva:\nAhoj, mam otazku."
    assert "Language: -" in _text(owner)


def test_reply_uses_request_language(client, override_settings):
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client, language="en")

    owner, [reply] = _split_outbox(outbox)
    assert _subject(reply) == "Thanks for your message: Dotaz"
    assert _text(reply) == "Hello host@example.com <host@example.com>.\n\nYour message:\nAhoj, mam otazku."
    assert "Language: en" in _text(owner)


def test_reply_matches_language_by_primary_subtag(client, override_settings):
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client, language="en-US")

    _, [reply] = _split_outbox(outbox)
    assert _subject(reply) == "Thanks for your message: Dotaz"


def test_reply_falls_back_to_default_for_unconfigured_language(client, override_settings):
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client, language="de")

    owner, [reply] = _split_outbox(outbox)
    assert _subject(reply) == "Děkujeme za zprávu: Dotaz"
    assert "Language: de" in _text(owner)


def test_reply_default_language_is_configurable(client, override_settings):
    _contact_app.dependency_overrides[get_contact_form_config] = lambda: _contact_config(default_language="en")
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client, language="de")

    _, [reply] = _split_outbox(outbox)
    assert _subject(reply) == "Thanks for your message: Dotaz"


def test_send_reply_disabled_sends_only_owner_email(client, override_settings):
    _contact_app.dependency_overrides[get_contact_form_config] = lambda: _contact_config(send_reply=False)
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        resp = _submit_anonymous(client, language="en")

    assert resp.status_code == 204
    _, replies = _split_outbox(outbox)
    assert replies == []


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
    owner, [reply] = _split_outbox(outbox)
    assert "Jana Novakova <jana@example.com>" in _text(owner)
    assert "jana@example.com" in str(reply["To"])
    assert _text(reply).startswith("Dobrý den, Jana Novakova.")


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


# --- GET /info: what the page shows around the form -------------------------


def _info_settings(**overrides) -> Settings:
    # the contact details are pinned empty so a developer's own backend/.env
    # (Settings reads it) can't leak into the "nothing configured" cases
    values = {"contact_mail": "prijem@example.com", "contact_address": "", "contact_github_url": "", "contact_linkedin_url": ""}
    return Settings(**{**values, **overrides})


@pytest.fixture()
def use_info_settings():
    """Overrides Settings for one test; cleaned up unconditionally."""

    def _use(**overrides) -> None:
        _contact_app.dependency_overrides[get_settings] = lambda: _info_settings(**overrides)

    yield _use
    _contact_app.dependency_overrides.pop(get_settings, None)


def _use_config(**overrides) -> None:
    _contact_app.dependency_overrides[get_contact_form_config] = lambda: _contact_config(**overrides)


def test_info_is_empty_by_default(client, use_info_settings):
    use_info_settings()

    resp = client.get("/api/modules/kontaktni_formular/info")

    assert resp.status_code == 200
    assert resp.json() == {
        "title": "",
        "intro": "",
        "aside": "",
        "details": {"email": None, "address": None, "github_url": None, "linkedin_url": None},
    }


def test_info_shows_the_configured_details(client, use_info_settings):
    use_info_settings(
        contact_address="  Hlavni 1\n110 00 Praha  ",
        contact_github_url="https://github.com/example",
        contact_linkedin_url="https://www.linkedin.com/in/example",
    )

    details = client.get("/api/modules/kontaktni_formular/info").json()["details"]

    assert details == {
        "email": None,
        "address": "Hlavni 1\n110 00 Praha",
        "github_url": "https://github.com/example",
        "linkedin_url": "https://www.linkedin.com/in/example",
    }


def test_info_shows_the_delivery_address_only_when_show_email_is_on(client, use_info_settings):
    use_info_settings()
    assert client.get("/api/modules/kontaktni_formular/info").json()["details"]["email"] is None

    _use_config(show_email=True)
    assert client.get("/api/modules/kontaktni_formular/info").json()["details"]["email"] == "prijem@example.com"


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "ftp://example.com/x", "github.com/example", "https://", "//example.com", "data:text/html,x"],
)
def test_info_leaves_out_links_that_are_not_http_urls(client, use_info_settings, url, caplog):
    use_info_settings(contact_github_url=url, contact_linkedin_url=url)

    with caplog.at_level("WARNING"):
        details = client.get("/api/modules/kontaktni_formular/info").json()["details"]

    assert details["github_url"] is None
    assert details["linkedin_url"] is None
    assert "CONTACT_GITHUB_URL is not an http(s) URL" in caplog.text


def test_info_returns_the_texts_for_the_requested_language(client, use_info_settings):
    use_info_settings()
    _use_config(
        page={
            "cs": {"title": "Kontakt", "intro": "Napiste mi.", "aside": "Po-Pa"},
            "en": {"title": "Contact", "intro": "Write to me.", "aside": "Mon-Fri"},
        }
    )

    en = client.get("/api/modules/kontaktni_formular/info", params={"language": "en-GB"}).json()
    default = client.get("/api/modules/kontaktni_formular/info").json()
    unknown = client.get("/api/modules/kontaktni_formular/info", params={"language": "de"}).json()

    assert (en["title"], en["intro"], en["aside"]) == ("Contact", "Write to me.", "Mon-Fri")
    assert default["title"] == unknown["title"] == "Kontakt"


def test_info_exposes_nothing_beyond_the_page_fields(client, use_info_settings):
    use_info_settings(auth_api_key="secret-api-key", stripe_secret_key="sk_live_x", mail_password="hunter2")

    resp = client.get("/api/modules/kontaktni_formular/info")

    assert set(resp.json()) == {"title", "intro", "aside", "details"}
    assert set(resp.json()["details"]) == {"email", "address", "github_url", "linkedin_url"}
    for secret in ("secret-api-key", "sk_live_x", "hunter2"):
        assert secret not in resp.text


def test_info_rejects_an_overlong_language(client, use_info_settings):
    use_info_settings()

    assert client.get("/api/modules/kontaktni_formular/info", params={"language": "x" * 36}).status_code == 422


# --- Hooks of other modules (see hooks.py) -----------------------------------


@pytest.fixture()
def use_hooks():
    def _use(*hooks):
        _contact_app.dependency_overrides[get_contact_form_hooks] = lambda: list(hooks)

    return _use


def test_a_hook_receives_the_submission_before_any_mail_is_sent(client, override_settings, use_hooks):
    seen = []

    async def hook(db, submission):
        seen.append(submission)

    use_hooks(hook)
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        resp = _submit_anonymous(client, language="en")

    assert resp.status_code == 204
    assert len(outbox) == 2
    [submission] = seen
    assert (submission.subject, submission.message) == ("Dotaz", "Ahoj, mam otazku.")
    assert (submission.reply_to, submission.sender_name, submission.language) == (
        "host@example.com",
        "host@example.com",
        "en",
    )
    assert submission.signed_in is False


def test_a_hook_result_tags_both_subjects_and_redirects_the_reply(client, override_settings, use_hooks):
    async def hook(db, submission):
        return ContactHookResult(subject_tag="[Ticket#100253]", reply_to="tickets@example.com")

    use_hooks(hook)
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client)

    owner, [reply] = _split_outbox(outbox)
    assert _subject(owner) == "[Ticket#100253] - Dotaz"
    assert _subject(reply) == "[Ticket#100253] - Děkujeme za zprávu: Dotaz"
    assert "tickets@example.com" in str(reply["Reply-To"])
    assert owner["Reply-To"] is None


def test_without_a_hook_result_the_mails_are_untouched(client, override_settings, use_hooks):
    async def hook(db, submission):
        return None

    use_hooks(hook)
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client)

    owner, [reply] = _split_outbox(outbox)
    assert _subject(owner) == "Dotaz"
    assert _subject(reply) == "Děkujeme za zprávu: Dotaz"
    assert reply["Reply-To"] is None


def test_a_failing_hook_does_not_stop_the_message(client, override_settings, use_hooks, caplog):
    async def broken(db, submission):
        raise RuntimeError("boom")

    async def working(db, submission):
        return ContactHookResult(subject_tag="[Ticket#7]")

    use_hooks(broken, working)
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        resp = _submit_anonymous(client)

    assert resp.status_code == 204
    owner, [reply] = _split_outbox(outbox)
    assert _subject(owner) == "[Ticket#7] - Dotaz"
    assert "A contact form hook failed" in caplog.text


def test_the_first_hook_tag_wins(client, override_settings, use_hooks):
    async def first(db, submission):
        return ContactHookResult(subject_tag="[A]")

    async def second(db, submission):
        return ContactHookResult(subject_tag="[B]", reply_to="b@example.com")

    use_hooks(first, second)
    mail = FastMail(_connection_config(override_settings))
    with mail.record_messages() as outbox:
        _submit_anonymous(client)

    owner, [reply] = _split_outbox(outbox)
    assert _subject(owner) == "[A] - Dotaz"
    assert "b@example.com" in str(reply["Reply-To"])
