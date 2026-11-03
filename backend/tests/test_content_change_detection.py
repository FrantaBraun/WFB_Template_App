# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for noticing that a spec changed although its info.version did not:
process_new_spec archives the old row and records a new one marked
content_changed (and leaves a spec that was only reformatted, reordered or
served as YAML alone), the per-document switch, the notification and its
e-mail, and how the API reports it (upload-version, the version list, the
bell's notifications).

socket.getfqdn is stubbed because building an e-mail calls it for the
Message-ID and costs about a second per message on the development machine."""

import json
import logging
import socket
import uuid
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from fastapi_mail import FastMail
from sqlalchemy import select

import app.security.jwt as jwt_module
from app.config import Settings, get_settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.notification import Notification
from app.models.team import Team, TeamMembership
from app.models.user import User
from app.services.api_document_versions import process_new_spec
from app.services.email import _connection_config
from app.services.notifications import notify_new_version
from app.services.spec_storage import read_spec_file


@pytest.fixture(autouse=True)
def _quiet_environment(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    monkeypatch.setattr(socket, "getfqdn", lambda *args, **kwargs: "localhost")


def _spec(version: str = "1.0.0", **info_extra) -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Example API", "version": version, **info_extra},
        "paths": {
            "/pets": {"get": {"responses": {"200": {"description": "A list of pets"}}}},
            "/owners": {"get": {"responses": {"200": {"description": "A list of owners"}}}},
        },
    }


def _json(spec: dict, **dump_kwargs) -> bytes:
    return json.dumps(spec, **dump_kwargs).encode()


async def _make_user(db_session, email: str | None = None) -> User:
    user = User(auth_sub=uuid.uuid4(), email=email)
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_document(db_session, *, members: tuple[User, ...] = (), **overrides) -> ApiDocument:
    team = Team(name="Test Team")
    db_session.add(team)
    await db_session.flush()
    creator = await _make_user(db_session)
    for member in (creator, *members):
        db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    fields = dict(team_id=team.id, title="Some API", created_by_user_id=creator.id)
    fields.update(overrides)
    doc = ApiDocument(**fields)
    db_session.add(doc)
    await db_session.flush()
    return doc


async def _process(db_session, doc, raw: bytes, tmp_path, source: str = "manual_recheck"):
    return await process_new_spec(
        doc, raw, source=source, db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )


async def _all_versions(db_session, doc) -> list[ApiDocumentVersion]:
    result = await db_session.execute(
        select(ApiDocumentVersion)
        .where(ApiDocumentVersion.documentation_id == doc.id)
        .order_by(ApiDocumentVersion.fetched_at)
    )
    return list(result.scalars().all())


# --- process_new_spec ---------------------------------------------------------------


async def test_changed_content_with_the_same_version_archives_the_old_row(db_session, tmp_path):
    doc = await _make_document(db_session)
    first = await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")
    changed = _spec()
    changed["paths"]["/pets"]["get"]["responses"]["200"]["description"] = "Now paginated"

    second = await _process(db_session, doc, _json(changed), tmp_path)

    assert second is not None
    assert second.version == "1.0.0" and second.content_changed is True
    assert second.archived_at is None and second.source == "manual_recheck"
    await db_session.refresh(first)
    assert first.archived_at is not None
    assert first.content_changed is False
    assert len(await _all_versions(db_session, doc)) == 2
    # What the spec said before is still readable, next to what it says now.
    assert json.loads(read_spec_file(str(tmp_path), first.storage_path)) == _spec()
    assert json.loads(read_spec_file(str(tmp_path), second.storage_path)) == changed


async def test_a_different_version_is_not_marked_as_a_content_change(db_session, tmp_path):
    doc = await _make_document(db_session)
    await _process(db_session, doc, _json(_spec("1.0.0")), tmp_path, source="initial")

    second = await _process(db_session, doc, _json(_spec("2.0.0", description="changed too")), tmp_path)

    assert second.version == "2.0.0" and second.content_changed is False


async def test_a_first_version_is_not_a_content_change(db_session, tmp_path):
    doc = await _make_document(db_session)

    first = await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")

    assert first.content_changed is False


async def test_checking_again_after_a_content_change_is_a_noop(db_session, tmp_path):
    """The new row is the one compared with next, so one change is one event."""
    doc = await _make_document(db_session)
    await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")
    changed = _json(_spec(description="changed"))
    await _process(db_session, doc, changed, tmp_path)

    again = await _process(db_session, doc, changed, tmp_path)

    assert again is None
    assert len(await _all_versions(db_session, doc)) == 2


async def test_reformatting_the_same_spec_is_not_a_change(db_session, tmp_path):
    doc = await _make_document(db_session)
    await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")

    pretty = await _process(db_session, doc, _json(_spec(), indent=4), tmp_path)
    sorted_keys = await _process(db_session, doc, _json(_spec(), sort_keys=True, separators=(",", ":")), tmp_path)

    assert pretty is None and sorted_keys is None
    assert len(await _all_versions(db_session, doc)) == 1


async def test_reordering_keys_is_not_a_change(db_session, tmp_path):
    doc = await _make_document(db_session)
    spec = _spec()
    await _process(db_session, doc, _json(spec), tmp_path, source="initial")
    reordered = {"paths": dict(reversed(list(spec["paths"].items()))), "info": spec["info"], "openapi": "3.0.0"}

    result = await _process(db_session, doc, _json(reordered), tmp_path)

    assert result is None


async def test_the_same_spec_as_yaml_is_not_a_change(db_session, tmp_path):
    doc = await _make_document(db_session)
    await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")

    result = await _process(db_session, doc, yaml.safe_dump(_spec()).encode(), tmp_path)

    assert result is None
    assert len(await _all_versions(db_session, doc)) == 1


async def test_the_order_of_a_list_is_part_of_the_content(db_session, tmp_path):
    doc = await _make_document(db_session)
    first = _spec()
    first["tags"] = [{"name": "pets"}, {"name": "owners"}]
    await _process(db_session, doc, _json(first), tmp_path, source="initial")
    second = _spec()
    second["tags"] = [{"name": "owners"}, {"name": "pets"}]

    result = await _process(db_session, doc, _json(second), tmp_path)

    assert result is not None and result.content_changed is True


async def test_the_switch_turns_detection_off(db_session, tmp_path):
    doc = await _make_document(db_session, detect_content_changes=False)
    await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")

    result = await _process(db_session, doc, _json(_spec(description="changed")), tmp_path)

    assert result is None
    assert len(await _all_versions(db_session, doc)) == 1
    assert doc.last_checked_at is not None and doc.last_check_error is None


async def test_a_new_document_has_detection_on(db_session):
    doc = await _make_document(db_session)

    assert doc.detect_content_changes is True


async def test_missing_stored_file_is_not_a_change_and_does_not_fail(db_session, tmp_path, caplog):
    doc = await _make_document(db_session)
    first = await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")
    (Path(tmp_path) / first.storage_path).unlink()

    with caplog.at_level(logging.WARNING):
        result = await _process(db_session, doc, _json(_spec(description="changed")), tmp_path)

    assert result is None
    assert "Cannot compare the content" in caplog.text
    assert doc.last_check_error is None


async def test_identical_bytes_do_not_need_the_stored_file(db_session, tmp_path, caplog):
    """The common case - nothing changed - is answered from the checksum."""
    doc = await _make_document(db_session)
    raw = _json(_spec())
    first = await _process(db_session, doc, raw, tmp_path, source="initial")
    (Path(tmp_path) / first.storage_path).unlink()

    with caplog.at_level(logging.WARNING):
        result = await _process(db_session, doc, raw, tmp_path)

    assert result is None
    assert "Cannot compare the content" not in caplog.text


# --- notification and e-mail --------------------------------------------------------


async def test_team_members_get_a_notification_for_a_content_change(db_session, tmp_path):
    member = await _make_user(db_session, email="member@example.com")
    doc = await _make_document(db_session, members=(member,))
    await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")

    second = await _process(db_session, doc, _json(_spec(description="changed")), tmp_path)

    notification = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == member.id, Notification.version_id == second.id)
        )
    ).scalar_one()
    assert notification.kind == "new_version" and notification.documentation_id == doc.id


async def test_the_e_mail_says_the_version_number_did_not_change(db_session, tmp_path, mail_test_settings):
    member = await _make_user(db_session, email="member@example.com")
    doc = await _make_document(db_session, members=(member,), title="Payments API")
    await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")
    second = await _process(db_session, doc, _json(_spec(description="changed")), tmp_path)

    mail = FastMail(_connection_config(mail_test_settings))
    with mail.record_messages() as outbox:
        await notify_new_version(doc, second, db_session, settings=mail_test_settings)

    sent = [m for m in outbox if "member@example.com" in str(m["To"])]
    assert len(sent) == 1
    assert str(sent[0]["Subject"]) == "Payments API changed without a new version number (1.0.0)"
    body = sent[0].get_payload()[0].get_payload(decode=True).decode()
    assert "version is still 1.0.0" in body and "version history" in body


async def test_the_e_mail_for_a_new_version_is_unchanged(db_session, tmp_path, mail_test_settings):
    member = await _make_user(db_session, email="member@example.com")
    doc = await _make_document(db_session, members=(member,), title="Payments API")
    await _process(db_session, doc, _json(_spec("1.0.0")), tmp_path, source="initial")
    second = await _process(db_session, doc, _json(_spec("2.0.0")), tmp_path)

    mail = FastMail(_connection_config(mail_test_settings))
    with mail.record_messages() as outbox:
        await notify_new_version(doc, second, db_session, settings=mail_test_settings)

    assert str(outbox[0]["Subject"]) == "New version of Payments API: 2.0.0"


# --- the API ------------------------------------------------------------------------


@pytest.fixture()
def docs_settings(tmp_path) -> Settings:
    return Settings(uploads_dir=str(tmp_path), spec_fetch_timeout_seconds=5.0)


async def _request(db_session, method: str, path: str, *, token: str, settings=None, **kwargs):
    from app.database import get_db
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    if settings is not None:
        fastapi_app.dependency_overrides[get_settings] = lambda: settings
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        if settings is not None:
            fastapi_app.dependency_overrides.pop(get_settings, None)


def _token(make_access_token, user: User) -> str:
    return make_access_token(sub=str(user.auth_sub), email=user.email, login=user.login)


async def _document_owned_by(db_session, owner: User, tmp_path, **overrides) -> ApiDocument:
    doc = await _make_document(db_session, members=(owner,), source_url=None, **overrides)
    await _process(db_session, doc, _json(_spec()), tmp_path, source="initial")
    return doc


async def test_upload_version_reports_a_content_change(db_session, make_access_token, docs_settings, tmp_path):
    owner = await _make_user(db_session, email="owner@example.com")
    doc = await _document_owned_by(db_session, owner, tmp_path)
    token = _token(make_access_token, owner)

    resp = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/upload-version",
        token=token,
        settings=docs_settings,
        files={"file": ("openapi.json", _json(_spec(description="changed")), "application/json")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["content_changed"] is True
    assert body["new_version_found"] is False  # the version string did not change
    assert body["previous_version"] == "1.0.0"
    assert body["current_version"]["version"] == "1.0.0"
    assert body["current_version"]["content_changed"] is True
    assert body["current_version"]["source"] == "manual_upload"


async def test_upload_of_the_same_content_reports_neither(db_session, make_access_token, docs_settings, tmp_path):
    owner = await _make_user(db_session, email="owner@example.com")
    doc = await _document_owned_by(db_session, owner, tmp_path)

    resp = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/upload-version",
        token=_token(make_access_token, owner),
        settings=docs_settings,
        files={"file": ("openapi.json", _json(_spec(), indent=2), "application/json")},
    )

    body = resp.json()
    assert (body["content_changed"], body["new_version_found"]) == (False, False)


async def test_a_new_version_reports_new_version_found_and_no_content_change(
    db_session, make_access_token, docs_settings, tmp_path
):
    owner = await _make_user(db_session, email="owner@example.com")
    doc = await _document_owned_by(db_session, owner, tmp_path)

    resp = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/upload-version",
        token=_token(make_access_token, owner),
        settings=docs_settings,
        files={"file": ("openapi.json", _json(_spec("2.0.0")), "application/json")},
    )

    body = resp.json()
    assert (body["new_version_found"], body["content_changed"]) == (True, False)


@respx.mock
async def test_recheck_by_url_reports_a_content_change(db_session, make_access_token, docs_settings, tmp_path):
    owner = await _make_user(db_session, email="owner@example.com")
    doc = await _document_owned_by(db_session, owner, tmp_path)
    doc.source_url = "https://example.com/openapi.json"
    await db_session.flush()
    respx.get("https://example.com/openapi.json").mock(
        return_value=httpx.Response(200, content=_json(_spec(description="changed")))
    )

    resp = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/recheck",
        token=_token(make_access_token, owner),
        settings=docs_settings,
    )

    body = resp.json()
    assert (body["content_changed"], body["new_version_found"]) == (True, False)
    assert body["current_version"]["source"] == "manual_recheck"


async def test_version_list_marks_the_row_that_replaced_same_version_content(
    db_session, make_access_token, docs_settings, tmp_path
):
    owner = await _make_user(db_session, email="owner@example.com")
    doc = await _document_owned_by(db_session, owner, tmp_path)
    await _process(db_session, doc, _json(_spec(description="changed")), tmp_path)

    resp = await _request(
        db_session, "GET", f"/api/api-docs/{doc.id}/versions", token=_token(make_access_token, owner)
    )

    rows = resp.json()
    assert len(rows) == 2
    current = next(row for row in rows if row["archived_at"] is None)
    archived = next(row for row in rows if row["archived_at"] is not None)
    assert (current["version"], current["content_changed"]) == ("1.0.0", True)
    assert (archived["version"], archived["content_changed"]) == ("1.0.0", False)


async def test_detail_has_the_switch_and_patch_changes_it(db_session, make_access_token, tmp_path):
    owner = await _make_user(db_session, email="owner@example.com")
    doc = await _document_owned_by(db_session, owner, tmp_path)
    token = _token(make_access_token, owner)

    before = await _request(db_session, "GET", f"/api/api-docs/{doc.id}", token=token)
    off = await _request(
        db_session, "PATCH", f"/api/api-docs/{doc.id}", token=token, json={"detect_content_changes": False}
    )
    title_only = await _request(db_session, "PATCH", f"/api/api-docs/{doc.id}", token=token, json={"title": "Renamed"})
    null_value = await _request(
        db_session, "PATCH", f"/api/api-docs/{doc.id}", token=token, json={"detect_content_changes": None}
    )

    assert before.json()["detect_content_changes"] is True
    assert off.json()["detect_content_changes"] is False
    assert title_only.json()["detect_content_changes"] is False  # an omitted field is left alone
    assert null_value.status_code == 422


async def test_bell_marks_a_content_change_and_the_banner_query_still_finds_it(
    db_session, make_access_token, tmp_path
):
    member = await _make_user(db_session, email="member@example.com")
    doc = await _make_document(db_session, members=(member,))
    await _process(db_session, doc, _json(_spec("1.0.0")), tmp_path, source="initial")
    await _process(db_session, doc, _json(_spec("1.0.0", description="changed")), tmp_path)
    await _process(db_session, doc, _json(_spec("2.0.0")), tmp_path)
    token = _token(make_access_token, member)

    bell = await _request(db_session, "GET", "/api/notifications", token=token)
    banner = await _request(
        db_session, "GET", f"/api/notifications?documentation_id={doc.id}&unread=true", token=token
    )

    # Every row of this test shares one transaction timestamp, so the order of
    # the list is not asserted - only what is in it.
    flags = sorted((item["version"], item["content_changed"]) for item in bell.json()["items"])
    assert flags == [("1.0.0", False), ("1.0.0", True), ("2.0.0", False)]
    assert len(banner.json()["items"]) == 3
