# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for what a version brought over the one it replaced: the summary
recorded on a version by process_new_spec (and that a comparison that fails
never fails the check), the "breaking changes" line of the e-mail, and
GET /api/api-docs/{id}/versions/{version_id}/changes - which version it
compares with, who may ask, and what it says when a file is gone.

socket.getfqdn is stubbed because building an e-mail calls it for the
Message-ID and costs about a second per message on the development machine."""

import logging
import socket
from pathlib import Path

import pytest
from fastapi_mail import FastMail
from sqlalchemy import select

import app.security.jwt as jwt_module
import app.services.api_document_versions as versions_module
from app.models.api_document import ApiDocumentVersion
from app.services.email import _connection_config
from app.services.notifications import notify_new_version
from tests.version_support import (
    docs_settings,
    make_document,
    make_user,
    pets_spec,
    record,
    record_history,
    request,
    token_for,
)


@pytest.fixture(autouse=True)
def _quiet_environment(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    monkeypatch.setattr(socket, "getfqdn", lambda *args, **kwargs: "localhost")


def _removing_pets(version: str) -> dict:
    """pets_spec's only operation gone, another one added: 1 breaking, 1 info."""
    return pets_spec(version, paths={"/owners": {"get": {"responses": {"200": {"description": "ok"}}}}})


# --- the summary recorded on a version ----------------------------------------------


async def test_a_new_version_records_how_it_differs_from_the_one_it_replaced(db_session, tmp_path):
    doc = await make_document(db_session)
    first = await record(db_session, doc, pets_spec("1.0.0"), tmp_path)

    second = await record(db_session, doc, _removing_pets("2.0.0"), tmp_path)

    assert first.change_summary is None  # nothing before it
    assert second.change_summary == {"breaking": 1, "warning": 0, "info": 1}


async def test_a_content_change_records_a_summary_too(db_session, tmp_path):
    doc = await make_document(db_session)
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    changed = pets_spec("1.0.0")
    changed["paths"]["/pets"]["get"]["deprecated"] = True

    second = await record(db_session, doc, changed, tmp_path)

    assert second.content_changed is True
    assert second.change_summary == {"breaking": 0, "warning": 1, "info": 0}


async def test_a_change_in_text_only_has_an_all_zero_summary(db_session, tmp_path):
    doc = await make_document(db_session)
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)

    second = await record(db_session, doc, pets_spec("1.0.0", description="new words"), tmp_path)

    assert second.change_summary == {"breaking": 0, "warning": 0, "info": 0}


async def test_a_failing_comparison_never_fails_the_check(db_session, tmp_path, monkeypatch, caplog):
    doc = await make_document(db_session)
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("cannot diff")

    monkeypatch.setattr(versions_module, "diff_parsed", boom)
    with caplog.at_level(logging.ERROR):
        second = await record(db_session, doc, pets_spec("2.0.0"), tmp_path)

    assert second.version == "2.0.0" and second.change_summary is None
    assert doc.last_check_error is None
    assert "Cannot compare version" in caplog.text


async def test_a_missing_old_file_means_no_summary_but_a_recorded_version(db_session, tmp_path):
    doc = await make_document(db_session)
    first = await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    (Path(tmp_path) / first.storage_path).unlink()

    second = await record(db_session, doc, pets_spec("2.0.0"), tmp_path)

    assert second.version == "2.0.0" and second.change_summary is None


# --- the e-mail ---------------------------------------------------------------------


async def _mail_for(db_session, doc, version, settings):
    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        await notify_new_version(doc, version, db_session, settings=settings)
    sent = [m for m in outbox if "member@example.com" in str(m["To"])]
    assert len(sent) == 1
    return str(sent[0]["Subject"]), sent[0].get_payload()[0].get_payload(decode=True).decode()


async def test_the_e_mail_names_breaking_changes_and_links_to_them(db_session, tmp_path, mail_test_settings):
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,), title="Pets API")
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    second = await record(db_session, doc, _removing_pets("2.0.0"), tmp_path)

    subject, body = await _mail_for(db_session, doc, second, mail_test_settings)

    assert subject == "New version of Pets API: 2.0.0 - 1 breaking change"
    assert "Breaking changes: 1. Potentially breaking: 0." in body
    assert f"/api-docs/{doc.id}/versions/{second.id}/changes" in body


async def test_the_e_mail_of_a_content_change_names_them_too(db_session, tmp_path, mail_test_settings):
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,), title="Pets API")
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    changed = pets_spec("1.0.0", paths={})  # same version, everything removed
    second = await record(db_session, doc, changed, tmp_path)

    subject, body = await _mail_for(db_session, doc, second, mail_test_settings)

    assert subject == "Pets API changed without a new version number (1.0.0) - 1 breaking change"
    assert "Breaking changes: 1." in body


async def test_the_e_mail_says_nothing_about_changes_when_there_are_none(db_session, tmp_path, mail_test_settings):
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,), title="Pets API")
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    second = await record(db_session, doc, pets_spec("2.0.0"), tmp_path)  # same paths

    subject, body = await _mail_for(db_session, doc, second, mail_test_settings)

    assert subject == "New version of Pets API: 2.0.0"
    assert "Breaking changes" not in body and "What changed" not in body


# --- GET .../versions/{id}/changes --------------------------------------------------


async def _three_versions(db_session, tmp_path, **doc_fields):
    owner = await make_user(db_session, email="owner@example.com")
    doc = await make_document(db_session, members=(owner,), **doc_fields)
    v1, v2, v3 = await record_history(
        db_session, doc, [pets_spec("1.0.0"), _removing_pets("2.0.0"), _removing_pets("3.0.0")], tmp_path
    )
    return owner, doc, v1, v2, v3


async def test_changes_default_to_the_version_just_before(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path)

    resp = await request(
        db_session,
        "GET",
        f"/api/api-docs/{doc.id}/versions/{v2.id}/changes",
        token=token_for(make_access_token, owner),
        settings=docs_settings(tmp_path),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert (body["base"]["id"], body["target"]["id"]) == (str(v1.id), str(v2.id))
    assert (body["base"]["version"], body["target"]["version"]) == ("1.0.0", "2.0.0")
    assert body["summary"] == {"breaking": 1, "warning": 0, "info": 1}
    assert body["truncated"] is False
    first = body["changes"][0]  # most severe first
    assert (first["kind"], first["severity"], first["method"], first["path"]) == ("operation_removed", "breaking", "GET", "/pets")
    assert set(first) == {"kind", "severity", "method", "path", "scope", "status", "media_type", "location", "detail"}
    assert body["changes"][1]["kind"] == "operation_added"


async def test_two_versions_that_differ_only_in_number_have_no_changes(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path)

    resp = await request(
        db_session,
        "GET",
        f"/api/api-docs/{doc.id}/versions/{v3.id}/changes",
        token=token_for(make_access_token, owner),
        settings=docs_settings(tmp_path),
    )

    assert resp.status_code == 200
    assert resp.json()["changes"] == [] and resp.json()["summary"] == {"breaking": 0, "warning": 0, "info": 0}


async def test_against_picks_any_other_version_of_the_document(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path)

    resp = await request(
        db_session,
        "GET",
        f"/api/api-docs/{doc.id}/versions/{v3.id}/changes?against={v1.id}",
        token=token_for(make_access_token, owner),
        settings=docs_settings(tmp_path),
    )

    body = resp.json()
    assert (body["base"]["version"], body["target"]["version"]) == ("1.0.0", "3.0.0")
    assert body["summary"] == {"breaking": 1, "warning": 0, "info": 1}


async def test_the_oldest_version_has_nothing_before_it_unless_against_is_given(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path)
    token = token_for(make_access_token, owner)
    settings = docs_settings(tmp_path)

    alone = await request(db_session, "GET", f"/api/api-docs/{doc.id}/versions/{v1.id}/changes", token=token, settings=settings)
    given = await request(
        db_session, "GET", f"/api/api-docs/{doc.id}/versions/{v1.id}/changes?against={v2.id}", token=token, settings=settings
    )

    assert alone.status_code == 404
    assert given.status_code == 200 and given.json()["base"]["id"] == str(v2.id)


async def test_a_version_or_against_that_is_not_this_documents_is_404(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path)
    other = await make_document(db_session, members=(owner,))
    foreign = await record(db_session, other, pets_spec("9.0.0"), tmp_path)
    token = token_for(make_access_token, owner)
    settings = docs_settings(tmp_path)
    unknown = "00000000-0000-0000-0000-000000000001"

    foreign_target = await request(db_session, "GET", f"/api/api-docs/{doc.id}/versions/{foreign.id}/changes", token=token, settings=settings)
    foreign_against = await request(db_session, "GET", f"/api/api-docs/{doc.id}/versions/{v2.id}/changes?against={foreign.id}", token=token, settings=settings)
    unknown_target = await request(db_session, "GET", f"/api/api-docs/{doc.id}/versions/{unknown}/changes", token=token, settings=settings)

    assert (foreign_target.status_code, foreign_against.status_code, unknown_target.status_code) == (404, 404, 404)


async def test_visibility_is_the_same_as_the_version_list(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path, is_public=False)
    outsider = await make_user(db_session, email="outsider@example.com")
    path = f"/api/api-docs/{doc.id}/versions/{v2.id}/changes"
    settings = docs_settings(tmp_path)

    anonymous = await request(db_session, "GET", path, settings=settings)
    outsider_resp = await request(db_session, "GET", path, token=token_for(make_access_token, outsider), settings=settings)
    member_resp = await request(db_session, "GET", path, token=token_for(make_access_token, owner), settings=settings)
    doc.is_public = True
    await db_session.flush()
    public_anonymous = await request(db_session, "GET", path, settings=settings)

    assert (anonymous.status_code, outsider_resp.status_code, member_resp.status_code) == (404, 404, 200)
    assert public_anonymous.status_code == 200


async def test_a_stored_file_that_is_gone_is_404_and_one_that_no_longer_parses_is_422(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path)
    token = token_for(make_access_token, owner)
    settings = docs_settings(tmp_path)
    path = f"/api/api-docs/{doc.id}/versions/{v2.id}/changes"

    (Path(tmp_path) / v1.storage_path).write_bytes(b"{ not a spec")
    garbled = await request(db_session, "GET", path, token=token, settings=settings)
    (Path(tmp_path) / v1.storage_path).unlink()
    gone = await request(db_session, "GET", path, token=token, settings=settings)

    assert garbled.status_code == 422
    assert gone.status_code == 404


async def test_the_summary_is_on_the_version_list_and_the_current_version(db_session, make_access_token, tmp_path):
    owner, doc, v1, v2, v3 = await _three_versions(db_session, tmp_path)
    token = token_for(make_access_token, owner)

    listing = await request(db_session, "GET", f"/api/api-docs/{doc.id}/versions", token=token)
    detail = await request(db_session, "GET", f"/api/api-docs/{doc.id}", token=token)

    summaries = {row["version"]: row["change_summary"] for row in listing.json()}
    assert summaries == {
        "1.0.0": None,
        "2.0.0": {"breaking": 1, "warning": 0, "info": 1},
        "3.0.0": {"breaking": 0, "warning": 0, "info": 0},
    }
    assert detail.json()["current_version"]["change_summary"] == {"breaking": 0, "warning": 0, "info": 0}


async def test_the_bell_carries_the_number_of_breaking_changes(db_session, make_access_token, tmp_path):
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,))
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    await record(db_session, doc, _removing_pets("2.0.0"), tmp_path)

    resp = await request(db_session, "GET", "/api/notifications", token=token_for(make_access_token, member))

    by_version = {item["version"]: item["breaking_changes"] for item in resp.json()["items"]}
    assert by_version == {"1.0.0": 0, "2.0.0": 1}


async def test_the_summary_survives_in_the_database(db_session, tmp_path):
    doc = await make_document(db_session)
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    second = await record(db_session, doc, _removing_pets("2.0.0"), tmp_path)

    row = (await db_session.execute(select(ApiDocumentVersion).where(ApiDocumentVersion.id == second.id))).scalar_one()

    assert row.change_summary == {"breaking": 1, "warning": 0, "info": 1}
