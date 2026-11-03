# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/teams/{team_id}/webhooks: who may see (members, masked) and
change (owners) a team's webhooks, that a URL is checked when it is saved, that
the signing secret is shown once and the URL never in full, the PATCH rules,
the limit, and the test message.

DNS and the receiver are replaced (safe_http._getaddrinfo, respx): nothing
leaves the machine."""

import httpx
import pytest
import respx
from sqlalchemy import func, select

import app.security.jwt as jwt_module
import app.services.safe_http as safe_http
from app.config import Settings
from app.models.team import Team, TeamMembership
from app.models.webhook import TeamWebhook
from app.api.teams.webhooks import MAX_WEBHOOKS_PER_TEAM
from tests.version_support import make_user, request, token_for

PUBLIC = "93.184.216.34"
SLACK_URL = "https://hooks.slack.com/services/T0123ABCD/B0456EFGH/xyzSECRETabcd"
GENERIC_URL = "https://hooks.example.com/ingest/TOKENvalue1234"


@pytest.fixture(autouse=True)
def _environment(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)

    async def resolve(host: str, port: int) -> list[str]:
        return [PUBLIC]

    monkeypatch.setattr(safe_http, "_getaddrinfo", resolve)


def _settings(**overrides) -> Settings:
    """The address check is ON here whatever the test environment says."""
    values = {
        "webhook_timeout_seconds": 2.0,
        "frontend_url": "https://app.example.com",
        "outbound_allow_private_addresses": False,
    }
    values.update(overrides)
    return Settings(**values)


async def _team(db_session, make_access_token):
    """A team with an owner, a plain member and an outsider (with tokens)."""
    owner = await make_user(db_session, email="owner@example.com")
    member = await make_user(db_session, email="member@example.com")
    outsider = await make_user(db_session, email="outsider@example.com")
    team = Team(name="Platform")
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMembership(team_id=team.id, user_id=owner.id, role="owner"))
    db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    await db_session.flush()
    tokens = {name: token_for(make_access_token, user) for name, user in (("owner", owner), ("member", member), ("outsider", outsider))}
    return team, owner, tokens


def _path(team, webhook=None, suffix: str = "") -> str:
    return f"/api/teams/{team.id}/webhooks" + (f"/{webhook.id}" if webhook is not None else "") + suffix


async def _create(db_session, team, token, **body):
    body.setdefault("kind", "generic")
    body.setdefault("url", GENERIC_URL)
    return await request(db_session, "POST", _path(team), token=token, settings=_settings(), json=body)


# --- creating -----------------------------------------------------------------------


async def test_an_owner_creates_a_generic_webhook_and_sees_the_secret_once(db_session, make_access_token):
    team, _, tokens = await _team(db_session, make_access_token)

    created = await _create(db_session, team, tokens["owner"], name="  Our endpoint  ", only_breaking=True)

    assert created.status_code == 201
    body = created.json()
    assert body["kind"] == "generic" and body["name"] == "Our endpoint" and body["only_breaking"] is True
    assert body["enabled"] is True and body["last_status"] is None and body["consecutive_failures"] == 0
    assert len(body["secret"]) == 64
    assert "TOKENvalue1234" not in created.text  # the URL comes back masked, even to the one who typed it
    assert body["url_masked"] == "https://hooks.example.com/ingest/…1234"

    listed = await request(db_session, "GET", _path(team), token=tokens["owner"])
    assert body["secret"] not in listed.text and "TOKENvalue1234" not in listed.text
    assert "secret" not in listed.json()[0]


async def test_a_slack_webhook_has_no_secret(db_session, make_access_token):
    team, _, tokens = await _team(db_session, make_access_token)

    created = await _create(db_session, team, tokens["owner"], kind="slack", url=SLACK_URL)

    assert created.status_code == 201
    assert created.json()["secret"] is None
    assert "SECRET" not in created.text and "T0123ABCD" not in created.text


@pytest.mark.parametrize(
    ("kind", "url"),
    [
        ("slack", "https://example.com/services/T0/B0/x"),  # not Slack's host
        ("slack", "https://hooks.slack.com.evil.com/services/T0/B0/x"),
        ("generic", "http://hooks.example.com/ingest"),  # not encrypted
        ("generic", "ftp://hooks.example.com/ingest"),
        ("generic", "https://user:pass@hooks.example.com/ingest"),
        ("generic", "https://127.0.0.1/ingest"),
        ("generic", "https://169.254.169.254/latest/meta-data"),
        ("generic", "https://[::1]/ingest"),
        ("generic", "not a url"),
        ("generic", "   "),
    ],
)
async def test_an_address_that_may_not_be_called_is_refused_when_saving(db_session, make_access_token, kind, url):
    team, _, tokens = await _team(db_session, make_access_token)

    resp = await _create(db_session, team, tokens["owner"], kind=kind, url=url)

    assert resp.status_code == 422
    assert await db_session.scalar(select(func.count()).select_from(TeamWebhook)) == 0


async def test_a_host_that_resolves_privately_or_not_at_all_is_refused(db_session, make_access_token, monkeypatch):
    team, _, tokens = await _team(db_session, make_access_token)

    async def private(host: str, port: int) -> list[str]:
        return ["10.0.0.5"]

    async def nowhere(host: str, port: int) -> list[str]:
        raise OSError("not found")

    monkeypatch.setattr(safe_http, "_getaddrinfo", private)
    internal = await _create(db_session, team, tokens["owner"])
    monkeypatch.setattr(safe_http, "_getaddrinfo", nowhere)
    missing = await _create(db_session, team, tokens["owner"])

    assert (internal.status_code, missing.status_code) == (422, 422)
    assert "not a public one" in internal.json()["detail"] and "cannot be resolved" in missing.json()["detail"]


async def test_private_addresses_are_accepted_only_where_the_deployment_allows_them(db_session, make_access_token):
    team, _, tokens = await _team(db_session, make_access_token)
    body = {"kind": "generic", "url": "http://localhost:9000/hook"}

    refused = await request(db_session, "POST", _path(team), token=tokens["owner"], settings=_settings(), json=body)
    allowed = await request(
        db_session, "POST", _path(team), token=tokens["owner"], settings=_settings(outbound_allow_private_addresses=True), json=body
    )

    assert (refused.status_code, allowed.status_code) == (422, 201)


@pytest.mark.parametrize("body", [{"kind": "email", "url": GENERIC_URL}, {"kind": "generic"}, {"url": GENERIC_URL}, {"kind": "generic", "url": GENERIC_URL, "name": "x" * 101}])
async def test_a_malformed_body_is_422(db_session, make_access_token, body):
    team, _, tokens = await _team(db_session, make_access_token)

    resp = await request(db_session, "POST", _path(team), token=tokens["owner"], settings=_settings(), json=body)

    assert resp.status_code == 422


async def test_a_team_has_at_most_so_many_webhooks(db_session, make_access_token):
    team, owner, tokens = await _team(db_session, make_access_token)
    for index in range(MAX_WEBHOOKS_PER_TEAM):
        db_session.add(TeamWebhook(team_id=team.id, kind="generic", url=f"https://h.example.com/{index}", secret="s", created_by_user_id=owner.id))
    await db_session.flush()

    resp = await _create(db_session, team, tokens["owner"])

    assert resp.status_code == 409


# --- who may -------------------------------------------------------------------------


async def test_members_see_the_webhooks_but_only_owners_change_them(db_session, make_access_token):
    team, owner, tokens = await _team(db_session, make_access_token)
    webhook = TeamWebhook(team_id=team.id, kind="generic", url=GENERIC_URL, secret="s", created_by_user_id=owner.id)
    db_session.add(webhook)
    await db_session.flush()
    member = tokens["member"]

    listed = await request(db_session, "GET", _path(team), token=member)
    created = await _create(db_session, team, member)
    patched = await request(db_session, "PATCH", _path(team, webhook), token=member, json={"enabled": False})
    deleted = await request(db_session, "DELETE", _path(team, webhook), token=member)
    tested = await request(db_session, "POST", _path(team, webhook, "/test"), token=member, settings=_settings())

    assert listed.status_code == 200 and len(listed.json()) == 1
    assert [r.status_code for r in (created, patched, deleted, tested)] == [403, 403, 403, 403]
    await db_session.refresh(webhook)
    assert webhook.enabled is True


async def test_an_outsider_cannot_tell_the_team_exists(db_session, make_access_token):
    team, owner, tokens = await _team(db_session, make_access_token)
    webhook = TeamWebhook(team_id=team.id, kind="generic", url=GENERIC_URL, secret="s", created_by_user_id=owner.id)
    db_session.add(webhook)
    await db_session.flush()
    outsider = tokens["outsider"]

    results = [
        await request(db_session, "GET", _path(team), token=outsider),
        await _create(db_session, team, outsider),
        await request(db_session, "PATCH", _path(team, webhook), token=outsider, json={"enabled": False}),
        await request(db_session, "DELETE", _path(team, webhook), token=outsider),
        await request(db_session, "POST", _path(team, webhook, "/test"), token=outsider, settings=_settings()),
    ]

    assert [r.status_code for r in results] == [404] * 5


async def test_every_route_needs_a_signed_in_user(db_session, make_access_token):
    team, owner, _ = await _team(db_session, make_access_token)
    webhook = TeamWebhook(team_id=team.id, kind="generic", url=GENERIC_URL, secret="s", created_by_user_id=owner.id)
    db_session.add(webhook)
    await db_session.flush()

    results = [
        await request(db_session, "GET", _path(team)),
        await request(db_session, "POST", _path(team), json={"kind": "generic", "url": GENERIC_URL}),
        await request(db_session, "PATCH", _path(team, webhook), json={}),
        await request(db_session, "DELETE", _path(team, webhook)),
        await request(db_session, "POST", _path(team, webhook, "/test")),
    ]

    assert all(r.status_code in (401, 403) for r in results)


async def test_another_teams_webhook_is_not_reachable_through_this_team(db_session, make_access_token):
    team, owner, tokens = await _team(db_session, make_access_token)
    other = Team(name="Other")
    db_session.add(other)
    await db_session.flush()
    foreign = TeamWebhook(team_id=other.id, kind="generic", url=GENERIC_URL, secret="s", created_by_user_id=owner.id)
    db_session.add(foreign)
    await db_session.flush()

    results = [
        await request(db_session, "PATCH", _path(team, foreign), token=tokens["owner"], json={"enabled": False}),
        await request(db_session, "DELETE", _path(team, foreign), token=tokens["owner"]),
        await request(db_session, "POST", _path(team, foreign, "/test"), token=tokens["owner"], settings=_settings()),
    ]

    assert [r.status_code for r in results] == [404, 404, 404]
    await db_session.refresh(foreign)
    assert foreign.enabled is True


# --- changing and removing ----------------------------------------------------------


async def test_patch_changes_the_name_the_flags_and_nothing_else(db_session, make_access_token):
    team, _, tokens = await _team(db_session, make_access_token)
    created = (await _create(db_session, team, tokens["owner"], name="Old")).json()
    path = f"{_path(team)}/{created['id']}"

    patched = await request(
        db_session, "PATCH", path, token=tokens["owner"], json={"name": "  New  ", "enabled": False, "only_breaking": True, "url": "https://evil.example.com/"}
    )
    only_name = await request(db_session, "PATCH", path, token=tokens["owner"], json={"name": "   "})

    assert patched.status_code == 200
    assert (patched.json()["name"], patched.json()["enabled"], patched.json()["only_breaking"]) == ("New", False, True)
    assert patched.json()["url_masked"] == created["url_masked"]  # the address cannot be changed
    assert only_name.json()["name"] is None and only_name.json()["enabled"] is False  # an omitted field is left alone


@pytest.mark.parametrize("field", ["enabled", "only_breaking"])
async def test_a_flag_cannot_be_set_to_null(db_session, make_access_token, field):
    team, _, tokens = await _team(db_session, make_access_token)
    created = (await _create(db_session, team, tokens["owner"])).json()

    resp = await request(db_session, "PATCH", f"{_path(team)}/{created['id']}", token=tokens["owner"], json={field: None})

    assert resp.status_code == 422


async def test_delete_removes_the_webhook(db_session, make_access_token):
    team, _, tokens = await _team(db_session, make_access_token)
    created = (await _create(db_session, team, tokens["owner"])).json()

    deleted = await request(db_session, "DELETE", f"{_path(team)}/{created['id']}", token=tokens["owner"])
    listed = await request(db_session, "GET", _path(team), token=tokens["owner"])
    again = await request(db_session, "DELETE", f"{_path(team)}/{created['id']}", token=tokens["owner"])

    assert deleted.status_code == 204 and listed.json() == [] and again.status_code == 404


# --- the test message ---------------------------------------------------------------


@respx.mock
async def test_the_test_message_is_sent_signed_and_recorded(db_session, make_access_token):
    team, _, tokens = await _team(db_session, make_access_token)
    created = (await _create(db_session, team, tokens["owner"])).json()
    route = respx.post(f"https://{PUBLIC}/ingest/TOKENvalue1234").mock(return_value=httpx.Response(200))

    resp = await request(db_session, "POST", f"{_path(team)}/{created['id']}/test", token=tokens["owner"], settings=_settings())

    assert resp.status_code == 200 and resp.json() == {"ok": True, "status_code": 200, "error": None}
    request_sent = route.calls.last.request
    assert request_sent.headers["x-apihub-event"] == "ping" and request_sent.headers["x-apihub-signature"].startswith("sha256=")
    listed = (await request(db_session, "GET", _path(team), token=tokens["owner"])).json()[0]
    assert (listed["last_status"], listed["last_error"], listed["consecutive_failures"]) == ("ok", None, 0)
    assert listed["last_attempt_at"] is not None


@respx.mock
async def test_a_test_message_the_receiver_refuses_is_a_200_that_says_so(db_session, make_access_token):
    team, _, tokens = await _team(db_session, make_access_token)
    created = (await _create(db_session, team, tokens["owner"], kind="slack", url=SLACK_URL)).json()
    respx.post(f"https://{PUBLIC}/services/T0123ABCD/B0456EFGH/xyzSECRETabcd").mock(return_value=httpx.Response(404, text="no_service"))

    resp = await request(db_session, "POST", f"{_path(team)}/{created['id']}/test", token=tokens["owner"], settings=_settings())

    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "status_code": 404, "error": "The receiver answered 404"}
    listed = (await request(db_session, "GET", _path(team), token=tokens["owner"])).json()[0]
    assert (listed["last_status"], listed["consecutive_failures"]) == ("error", 1)
    assert "no_service" not in resp.text  # the receiver's own words are never passed on


async def test_the_test_message_is_not_sent_to_an_address_that_has_become_private(db_session, make_access_token, monkeypatch):
    team, _, tokens = await _team(db_session, make_access_token)
    created = (await _create(db_session, team, tokens["owner"])).json()

    async def private(host: str, port: int) -> list[str]:
        return ["192.168.1.10"]

    monkeypatch.setattr(safe_http, "_getaddrinfo", private)
    resp = await request(db_session, "POST", f"{_path(team)}/{created['id']}/test", token=tokens["owner"], settings=_settings())

    assert resp.json() == {"ok": False, "status_code": None, "error": "The address is not allowed"}
