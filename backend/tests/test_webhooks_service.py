# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.webhooks and for a new version reaching the teams'
webhooks: the messages (Slack and signed JSON), masking a URL, how a delivery
that goes wrong is reported, and who is called - the owning team, the teams
whose integration uses a public document (each told only its own integrations),
never an unrelated team, a disabled webhook, or a private document's other
teams - and that nothing a webhook does can fail the check that produced the
version.

Nothing leaves the machine: DNS is what the tests say (every host resolves to
a public address) and the calls go through respx to that address, i.e. through
the real, address-pinning path of app.services.safe_http."""

import hashlib
import hmac
import json
import logging
import socket

import httpx
import pytest
import respx

import app.services.notifications as notifications_module
import app.services.safe_http as safe_http
from app.config import Settings
from app.models.team import Team
from app.models.webhook import TeamWebhook
from app.services.webhooks import (
    DeliveryResult,
    build_ping_event,
    build_version_event,
    mask_url,
    record,
    send,
    sign,
    slack_message,
)
from tests.version_support import (
    make_document,
    make_integration,
    make_team,
    make_user,
    pets_spec,
    record as record_version,
)

PUBLIC = "93.184.216.34"
SECRET = "s3cret"


@pytest.fixture(autouse=True)
def _network(monkeypatch):
    """Every host name resolves to one public address; getfqdn is stubbed (a
    DNS lookup per e-mail otherwise)."""

    async def resolve(host: str, port: int) -> list[str]:
        return [PUBLIC]

    monkeypatch.setattr(safe_http, "_getaddrinfo", resolve)
    monkeypatch.setattr(socket, "getfqdn", lambda *args, **kwargs: "localhost")
    # A new version's webhooks are delivered with the application's own settings
    # (notify_new_version is not handed any): make those the strict ones.
    monkeypatch.setattr(notifications_module, "get_settings", _settings)


# --- URL masking --------------------------------------------------------------------


def test_a_slack_url_is_masked_so_it_cannot_be_used_but_can_be_recognised():
    url = "https://hooks.slack.com/services/T0123ABCD/B0456EFGH/xyzSECRETabcd"

    masked = mask_url(url)

    assert masked == "https://hooks.slack.com/services/…abcd"
    assert "T0123ABCD" not in masked and "SECRET" not in masked


def test_masking_drops_the_query_and_copes_with_short_urls():
    assert mask_url("https://example.com/hook?token=SECRET") == "https://example.com/…hook"
    assert mask_url("https://example.com") == "https://example.com/"
    assert mask_url("https://example.com/") == "https://example.com/"
    assert "SECRET" not in mask_url("https://example.com/a/b/c?token=SECRET")


# --- the messages -------------------------------------------------------------------


class _Doc:
    id = "11111111-1111-1111-1111-111111111111"
    title = "Pets API"


class _Version:
    id = "22222222-2222-2222-2222-222222222222"
    version = "2.0.0"
    content_changed = False
    source = "auto_recheck"
    fetched_at = None
    change_summary = {"breaking": 2, "warning": 1, "info": 0}


def _event(**version_fields) -> dict:
    version = type("V", (_Version,), version_fields)
    return build_version_event(_Doc, version, "https://app.example.com/", ["Billing sync"])


def test_the_event_describes_the_document_the_version_and_what_changed():
    event = _event()

    assert event["event"] == "document.version_created"
    assert event["document"] == {"id": _Doc.id, "title": "Pets API", "url": f"https://app.example.com/api-docs/{_Doc.id}"}
    assert event["version"]["version"] == "2.0.0" and event["version"]["content_changed"] is False
    assert event["changes"] == {"breaking": 2, "warning": 1, "info": 0}
    assert event["changes_url"] == f"https://app.example.com/api-docs/{_Doc.id}/versions/{_Version.id}/changes"
    assert event["integrations"] == ["Billing sync"]
    assert event["delivery_id"] and event["created_at"]


def test_a_version_without_a_summary_has_no_changes_and_a_summary_of_nothing_no_link():
    assert _event(change_summary=None)["changes"] is None
    assert _event(change_summary=None)["changes_url"] is None
    nothing = _event(change_summary={"breaking": 0, "warning": 0, "info": 0})
    assert nothing["changes"] == {"breaking": 0, "warning": 0, "info": 0} and nothing["changes_url"] is None


def test_the_slack_message_has_a_headline_the_breaking_count_the_integrations_and_links():
    text = slack_message(_event())["text"]

    assert "*Pets API* has a new version: *2.0.0*" in text
    assert ":warning: 2 breaking changes" in text
    assert "Affects: Billing sync" in text
    assert "<https://app.example.com/api-docs/" in text and "|What changed>" in text


def test_the_slack_message_words_one_breaking_change_and_a_content_change():
    one = slack_message(_event(change_summary={"breaking": 1, "warning": 0, "info": 0}))["text"]
    changed = slack_message(_event(content_changed=True, change_summary=None))["text"]

    assert "1 breaking change" in one and "1 breaking changes" not in one
    assert "changed without a new version number (*2.0.0*)" in changed
    assert "breaking" not in changed and "What changed" not in changed


def test_what_a_user_typed_cannot_become_slack_markup():
    version = type("V", (_Version,), {"version": "<!channel>", "change_summary": None})
    doc = type("D", (_Doc,), {"title": "A & <@U123|admin> B"})

    text = slack_message(build_version_event(doc, version, "https://app.example.com", ["<https://evil|x>"]))["text"]

    assert "<!channel>" not in text and "<@U123" not in text and "<https://evil" not in text
    assert "&amp;" in text and "&lt;!channel&gt;" in text


def test_the_ping_is_a_message_in_both_formats():
    ping = build_ping_event()

    assert ping["event"] == "ping" and ping["delivery_id"]
    assert "works" in slack_message(ping)["text"]


def test_the_signature_is_an_hmac_of_the_timestamp_and_the_body():
    body = b'{"a":1}'
    expected = hmac.new(b"key", b"1700000000." + body, hashlib.sha256).hexdigest()

    assert sign("key", "1700000000", body) == expected
    assert sign("other", "1700000000", body) != expected
    assert sign("key", "1700000001", body) != expected  # the timestamp is part of what is signed


# --- one delivery -------------------------------------------------------------------


def _webhook(kind: str = "generic", url: str = "https://hooks.example.com/ingest") -> TeamWebhook:
    return TeamWebhook(kind=kind, url=url, secret=SECRET if kind == "generic" else None)


def _settings(**overrides) -> Settings:
    """The address check is ON here whatever the test environment says (conftest
    switches it off for everything else), since this is what is under test."""
    values = {
        "webhook_timeout_seconds": 2.0,
        "frontend_url": "https://app.example.com",
        "outbound_allow_private_addresses": False,
    }
    values.update(overrides)
    return Settings(**values)


@respx.mock
async def test_a_generic_delivery_is_signed_and_carries_the_event():
    route = respx.post(f"https://{PUBLIC}/ingest").mock(return_value=httpx.Response(204))
    event = _event()

    result = await send(_webhook(), event, _settings())

    assert result == DeliveryResult(ok=True, status_code=204)
    request = route.calls.last.request
    assert json.loads(request.content) == event
    assert request.headers["host"] == "hooks.example.com"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["x-apihub-event"] == "document.version_created"
    assert request.headers["x-apihub-delivery"] == event["delivery_id"]
    timestamp = request.headers["x-apihub-timestamp"]
    expected = hmac.new(SECRET.encode(), timestamp.encode() + b"." + request.content, hashlib.sha256).hexdigest()
    assert request.headers["x-apihub-signature"] == f"sha256={expected}"


@respx.mock
async def test_a_slack_delivery_is_just_the_message_and_signs_nothing():
    route = respx.post(f"https://{PUBLIC}/services/T0/B0/x").mock(return_value=httpx.Response(200, text="ok"))

    result = await send(_webhook("slack", "https://hooks.slack.com/services/T0/B0/x"), _event(), _settings())

    assert result.ok is True
    request = route.calls.last.request
    assert set(json.loads(request.content)) == {"text"}
    assert not [name for name in request.headers if name.lower().startswith("x-apihub")]


@pytest.mark.parametrize(
    ("answer", "ok", "error"),
    [
        (httpx.Response(200), True, None),
        (httpx.Response(299), True, None),
        (httpx.Response(404), False, "The receiver answered 404"),
        (httpx.Response(500), False, "The receiver answered 500"),
        (httpx.Response(302, headers={"Location": "http://169.254.169.254/"}), False, "The receiver answered 302"),
    ],
)
@respx.mock
async def test_the_answer_decides_whether_a_delivery_worked(answer, ok, error):
    respx.post(f"https://{PUBLIC}/ingest").mock(return_value=answer)

    result = await send(_webhook(), _event(), _settings())

    assert (result.ok, result.error) == (ok, error)


@pytest.mark.parametrize(
    ("failure", "error"),
    [(httpx.ReadTimeout("slow"), "Timed out"), (httpx.ConnectError("refused"), "Could not connect"), (RuntimeError("boom"), "Unexpected error")],
)
@respx.mock
async def test_a_failure_becomes_a_short_fixed_error_and_never_raises(failure, error):
    respx.post(f"https://{PUBLIC}/ingest").mock(side_effect=failure)

    result = await send(_webhook(), _event(), _settings())

    assert (result.ok, result.error, result.status_code) == (False, error, None)


@respx.mock
async def test_an_address_that_must_not_be_called_is_not_called(monkeypatch):
    async def private(host: str, port: int) -> list[str]:
        return ["169.254.169.254"]

    monkeypatch.setattr(safe_http, "_getaddrinfo", private)
    route = respx.route().mock(return_value=httpx.Response(200))

    result = await send(_webhook(), _event(), _settings())

    assert (result.ok, result.error) == (False, "The address is not allowed")
    assert not route.called


def test_recording_a_delivery_counts_consecutive_failures():
    hook = _webhook()
    hook.consecutive_failures = 0

    record(hook, DeliveryResult(ok=False, error="Timed out"))
    record(hook, DeliveryResult(ok=False, error="Timed out"))
    assert (hook.last_status, hook.last_error, hook.consecutive_failures) == ("error", "Timed out", 2)

    record(hook, DeliveryResult(ok=True, status_code=200))
    assert (hook.last_status, hook.last_error, hook.consecutive_failures) == ("ok", None, 0)
    assert hook.last_attempt_at is not None


# --- a new version reaching the teams' webhooks -------------------------------------


async def _hook(db_session, team, creator, path: str = "ingest", **fields) -> TeamWebhook:
    values = dict(
        team_id=team.id,
        kind="generic",
        url=f"https://hooks.example.com/{path}",
        secret=SECRET,
        created_by_user_id=creator.id,
    )
    values.update(fields)
    hook = TeamWebhook(**values)
    db_session.add(hook)
    await db_session.flush()
    return hook


def _breaking(version: str) -> dict:
    return pets_spec(version, paths={})  # every operation gone: one breaking change


async def _owning_team(db_session):
    """A public document, the team that owns it, and an unrelated team."""
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,), is_public=True, title="Pets API")
    stranger_team = await make_team(db_session, "Unrelated")
    return doc, await db_session.get(Team, doc.team_id), stranger_team


@respx.mock
async def test_a_new_version_is_posted_to_the_owning_teams_webhook(db_session, tmp_path):
    doc, doc_team, _ = await _owning_team(db_session)
    hook = await _hook(db_session, doc_team, await make_user(db_session))
    route = respx.post(f"https://{PUBLIC}/ingest").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)
    second = await record_version(db_session, doc, _breaking("2.0.0"), tmp_path)

    assert route.call_count == 2  # one per version
    payload = json.loads(route.calls.last.request.content)
    assert payload["version"]["id"] == str(second.id) and payload["version"]["version"] == "2.0.0"
    assert payload["changes"] == {"breaking": 1, "warning": 0, "info": 0}
    assert payload["integrations"] == []
    assert (hook.last_status, hook.last_error, hook.consecutive_failures) == ("ok", None, 0)
    assert hook.last_attempt_at is not None


@respx.mock
async def test_a_slack_webhook_gets_the_chat_message(db_session, tmp_path):
    doc, doc_team, _ = await _owning_team(db_session)
    await _hook(db_session, doc_team, await make_user(db_session), kind="slack", secret=None, url="https://hooks.slack.com/services/T0/B0/x")
    route = respx.post(f"https://{PUBLIC}/services/T0/B0/x").mock(return_value=httpx.Response(200, text="ok"))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert "*Pets API* has a new version: *1.0.0*" in json.loads(route.calls.last.request.content)["text"]


@respx.mock
async def test_only_breaking_stays_quiet_for_a_version_without_breaking_changes(db_session, tmp_path):
    doc, doc_team, _ = await _owning_team(db_session)
    await _hook(db_session, doc_team, await make_user(db_session), only_breaking=True)
    route = respx.post(f"https://{PUBLIC}/ingest").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)
    await record_version(db_session, doc, pets_spec("2.0.0"), tmp_path)  # same paths: nothing breaking
    assert route.call_count == 0

    await record_version(db_session, doc, _breaking("3.0.0"), tmp_path)
    assert route.call_count == 1


@respx.mock
async def test_a_disabled_webhook_is_not_called(db_session, tmp_path):
    doc, doc_team, _ = await _owning_team(db_session)
    await _hook(db_session, doc_team, await make_user(db_session), enabled=False)
    route = respx.post(f"https://{PUBLIC}/ingest").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert not route.called


@respx.mock
async def test_an_unrelated_teams_webhook_is_not_called(db_session, tmp_path):
    doc, doc_team, stranger_team = await _owning_team(db_session)
    creator = await make_user(db_session)
    await _hook(db_session, doc_team, creator, path="own")
    await _hook(db_session, stranger_team, creator, path="stranger")
    own = respx.post(f"https://{PUBLIC}/own").mock(return_value=httpx.Response(200))
    stranger = respx.post(f"https://{PUBLIC}/stranger").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert own.called and not stranger.called


@respx.mock
async def test_the_team_of_an_integration_is_called_with_its_own_integrations_only(db_session, tmp_path):
    doc, doc_team, _ = await _owning_team(db_session)
    integrator = await make_user(db_session, email="integrator@example.com")
    team_a = await make_team(db_session, "Integrators A", members=(integrator,))
    team_b = await make_team(db_session, "Integrators B", members=(integrator,))
    await make_integration(db_session, team_a, integrator, "Billing sync", documents=(doc,))
    await make_integration(db_session, team_b, integrator, "Secret project", documents=(doc,))
    await _hook(db_session, doc_team, integrator, path="owner")
    await _hook(db_session, team_a, integrator, path="a")
    await _hook(db_session, team_b, integrator, path="b")
    owner = respx.post(f"https://{PUBLIC}/owner").mock(return_value=httpx.Response(200))
    a = respx.post(f"https://{PUBLIC}/a").mock(return_value=httpx.Response(200))
    b = respx.post(f"https://{PUBLIC}/b").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert json.loads(a.calls.last.request.content)["integrations"] == ["Billing sync"]
    assert json.loads(b.calls.last.request.content)["integrations"] == ["Secret project"]
    owner_body = owner.calls.last.request.content.decode()
    assert "Billing sync" not in owner_body and "Secret project" not in owner_body
    assert "Secret project" not in a.calls.last.request.content.decode()


@respx.mock
async def test_a_private_documents_versions_do_not_reach_another_teams_webhook(db_session, tmp_path):
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,), is_public=False)
    integrator = await make_user(db_session)
    team = await make_team(db_session, "Integrators", members=(integrator,))
    await make_integration(db_session, team, integrator, "Stale reference", documents=(doc,))
    await _hook(db_session, team, integrator, path="integrators")
    route = respx.post(f"https://{PUBLIC}/integrators").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert not route.called


@respx.mock
async def test_a_receiver_that_fails_is_recorded_and_the_check_still_succeeds(db_session, tmp_path):
    doc, doc_team, _ = await _owning_team(db_session)
    hook = await _hook(db_session, doc_team, await make_user(db_session))
    respx.post(f"https://{PUBLIC}/ingest").mock(return_value=httpx.Response(500))

    first = await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)
    assert first.version == "1.0.0"
    assert (hook.last_status, hook.last_error, hook.consecutive_failures) == ("error", "The receiver answered 500", 1)

    await record_version(db_session, doc, pets_spec("2.0.0"), tmp_path)
    assert hook.consecutive_failures == 2

    respx.post(f"https://{PUBLIC}/ingest").mock(return_value=httpx.Response(200))
    await record_version(db_session, doc, pets_spec("3.0.0"), tmp_path)
    assert (hook.last_status, hook.last_error, hook.consecutive_failures) == ("ok", None, 0)


@respx.mock
async def test_one_webhook_failing_does_not_stop_another(db_session, tmp_path):
    doc, doc_team, _ = await _owning_team(db_session)
    creator = await make_user(db_session)
    broken = await _hook(db_session, doc_team, creator, path="broken")
    working = await _hook(db_session, doc_team, creator, path="working")
    respx.post(f"https://{PUBLIC}/broken").mock(side_effect=httpx.ConnectError("refused"))
    ok_route = respx.post(f"https://{PUBLIC}/working").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert ok_route.called
    assert (broken.last_status, broken.last_error) == ("error", "Could not connect")
    assert working.last_status == "ok"


@respx.mock
async def test_webhooks_are_called_even_when_nobody_has_an_address(db_session, tmp_path):
    doc = await make_document(db_session, is_public=True)  # its only member has no e-mail
    team = await db_session.get(Team, doc.team_id)
    await _hook(db_session, team, await make_user(db_session))
    route = respx.post(f"https://{PUBLIC}/ingest").mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert route.called


async def test_a_delivery_that_blows_up_cannot_fail_the_check(db_session, tmp_path, monkeypatch, caplog):
    doc, doc_team, _ = await _owning_team(db_session)

    async def boom(*args, **kwargs):
        raise RuntimeError("database gone")

    monkeypatch.setattr(notifications_module, "deliver_version_event", boom)
    with caplog.at_level(logging.ERROR):
        version = await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert version.version == "1.0.0" and doc.last_check_error is None
    assert "Failed to deliver webhooks" in caplog.text


@respx.mock
async def test_a_webhook_whose_address_now_resolves_privately_is_not_called(db_session, tmp_path, monkeypatch):
    """Checked when it was saved, but DNS may answer differently since."""
    doc, doc_team, _ = await _owning_team(db_session)
    hook = await _hook(db_session, doc_team, await make_user(db_session))

    async def private(host: str, port: int) -> list[str]:
        return ["10.0.0.5"]

    monkeypatch.setattr(safe_http, "_getaddrinfo", private)
    route = respx.route().mock(return_value=httpx.Response(200))

    await record_version(db_session, doc, pets_spec("1.0.0"), tmp_path)

    assert not route.called
    assert (hook.last_status, hook.last_error) == ("error", "The address is not allowed")
