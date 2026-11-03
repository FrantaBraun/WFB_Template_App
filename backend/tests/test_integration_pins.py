# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for pinning the version of a document an integration was built
against: setting, replacing and removing the pin, who may and for what,
what the integration's document list says about a pin (how far behind, and
what changed since - which several versions on can differ from what the
newest version brought), that the comparison is remembered and that a
failure of it is not, and what happens when the document leaves the
integration or is deleted."""

from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

import app.security.jwt as jwt_module
import app.services.version_comparison as comparison_module
from app.models.api_document import ApiDocument
from app.models.integration import IntegrationDocument, IntegrationDocumentPin
from app.services.version_comparison import compare_versions
from tests.version_support import (
    docs_settings,
    make_collection,
    make_document,
    make_integration,
    make_team,
    make_user,
    pets_spec,
    record_history,
    request,
    token_for,
)


@pytest.fixture(autouse=True)
def _isolated(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    comparison_module._CACHE.clear()
    yield
    comparison_module._CACHE.clear()


def _no_pets(version: str) -> dict:
    return pets_spec(version, paths={})  # every operation gone: one breaking change from pets_spec


async def _scenario(db_session, tmp_path, *, public: bool = True):
    """An integration of a team using a three-version document: 1.0.0 (with
    GET /pets), 2.0.0 and 3.0.0 (both without)."""
    integrator = await make_user(db_session, email="integrator@example.com")
    doc = await make_document(db_session, is_public=public)
    team = await make_team(db_session, "Integrators", members=(integrator,))
    integration = await make_integration(db_session, team, integrator, "Billing sync", documents=(doc,))
    v1, v2, v3 = await record_history(db_session, doc, [pets_spec("1.0.0"), _no_pets("2.0.0"), _no_pets("3.0.0")], tmp_path)
    return integrator, doc, integration, (v1, v2, v3)


def _pin_path(integration, doc) -> str:
    return f"/api/integrations/{integration.id}/documents/{doc.id}/pin"


async def _documents(db_session, make_access_token, user, integration, tmp_path):
    resp = await request(
        db_session,
        "GET",
        f"/api/integrations/{integration.id}/documents",
        token=token_for(make_access_token, user),
        settings=docs_settings(tmp_path),
    )
    assert resp.status_code == 200, resp.text
    return {row["id"]: row for row in resp.json()}


async def _pin(db_session, make_access_token, user, integration, doc, version, tmp_path=None):
    return await request(
        db_session,
        "PUT",
        _pin_path(integration, doc),
        token=token_for(make_access_token, user),
        json={"version_id": str(version.id)},
    )


# --- pinning ------------------------------------------------------------------------


async def test_nothing_is_pinned_until_someone_pins(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)

    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert row["pin"] is None
    assert row["current_version_id"] == str(v3.id)


async def test_a_pinned_older_version_says_how_far_behind_and_what_changed_since(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)

    pinned = await _pin(db_session, make_access_token, integrator, integration, doc, v1)
    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert pinned.status_code == 204
    assert row["pin"]["version"] == "1.0.0" and row["pin"]["version_id"] == str(v1.id)
    assert (row["pin"]["is_current"], row["pin"]["versions_behind"]) == (False, 2)
    # 1.0.0 -> 3.0.0: GET /pets is gone. The newest version alone (2.0.0 -> 3.0.0) brought nothing:
    assert row["pin"]["summary"] == {"breaking": 1, "warning": 0, "info": 0}
    assert row["latest_change"]["summary"] == {"breaking": 0, "warning": 0, "info": 0}


async def test_pinning_the_current_version_means_up_to_date(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)

    await _pin(db_session, make_access_token, integrator, integration, doc, v3)
    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert (row["pin"]["is_current"], row["pin"]["versions_behind"], row["pin"]["summary"]) == (True, 0, None)


async def test_only_newer_versions_count_as_behind(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)

    await _pin(db_session, make_access_token, integrator, integration, doc, v2)
    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert (row["pin"]["versions_behind"], row["pin"]["summary"]) == (1, {"breaking": 0, "warning": 0, "info": 0})


async def test_pinning_again_replaces_the_pin(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)

    await _pin(db_session, make_access_token, integrator, integration, doc, v1)
    again = await _pin(db_session, make_access_token, integrator, integration, doc, v2)
    count = await db_session.scalar(
        select(func.count()).select_from(IntegrationDocumentPin).where(IntegrationDocumentPin.integration_id == integration.id)
    )
    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert again.status_code == 204 and count == 1
    assert row["pin"]["version"] == "2.0.0"


async def test_unpinning_removes_it_and_is_idempotent(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    await _pin(db_session, make_access_token, integrator, integration, doc, v1)
    token = token_for(make_access_token, integrator)

    first = await request(db_session, "DELETE", _pin_path(integration, doc), token=token)
    second = await request(db_session, "DELETE", _pin_path(integration, doc), token=token)
    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert (first.status_code, second.status_code) == (204, 204)
    assert row["pin"] is None


async def test_a_document_reached_through_a_collection_can_be_pinned_too(db_session, make_access_token, tmp_path):
    integrator = await make_user(db_session, email="integrator@example.com")
    doc = await make_document(db_session, is_public=True)
    team = await make_team(db_session, "Integrators", members=(integrator,))
    collection = await make_collection(db_session, team, integrator, documents=(doc,))
    integration = await make_integration(db_session, team, integrator, "Via collection", collections=(collection,))
    v1, v2 = await record_history(db_session, doc, [pets_spec("1.0.0"), _no_pets("2.0.0")], tmp_path)

    pinned = await _pin(db_session, make_access_token, integrator, integration, doc, v1)
    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert pinned.status_code == 204
    assert row["pin"]["summary"] == {"breaking": 1, "warning": 0, "info": 0}


# --- who may, and for what ----------------------------------------------------------


async def test_only_team_members_may_pin_or_unpin(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    outsider = await make_user(db_session, email="outsider@example.com")

    put = await _pin(db_session, make_access_token, outsider, integration, doc, v1)
    delete = await request(db_session, "DELETE", _pin_path(integration, doc), token=token_for(make_access_token, outsider))
    anonymous = await request(db_session, "PUT", _pin_path(integration, doc), json={"version_id": str(v1.id)})
    count = await db_session.scalar(select(func.count()).select_from(IntegrationDocumentPin))

    assert (put.status_code, delete.status_code) == (404, 404)
    assert anonymous.status_code in (401, 403)
    assert count == 0


async def test_a_document_that_is_not_part_of_the_integration_cannot_be_pinned(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    other = await make_document(db_session, is_public=True)
    [other_v1] = await record_history(db_session, other, [pets_spec("1.0.0")], tmp_path)

    resp = await _pin(db_session, make_access_token, integrator, integration, other, other_v1)

    assert resp.status_code == 404


async def test_a_version_of_another_document_or_an_unknown_one_is_404(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    other = await make_document(db_session, is_public=True)
    [foreign] = await record_history(db_session, other, [pets_spec("9.0.0")], tmp_path)
    token = token_for(make_access_token, integrator)

    foreign_version = await _pin(db_session, make_access_token, integrator, integration, doc, foreign)
    unknown = await request(
        db_session, "PUT", _pin_path(integration, doc), token=token, json={"version_id": "00000000-0000-0000-0000-000000000001"}
    )

    assert (foreign_version.status_code, unknown.status_code) == (404, 404)


async def test_a_document_made_private_since_cannot_be_pinned_by_another_team(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path, public=False)

    resp = await _pin(db_session, make_access_token, integrator, integration, doc, v1)

    assert resp.status_code == 404


async def test_a_member_of_both_teams_can_pin_a_private_document(db_session, make_access_token, tmp_path):
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,), is_public=False)
    team = await make_team(db_session, "Integrators", members=(member,))
    integration = await make_integration(db_session, team, member, "Internal", documents=(doc,))
    [v1] = await record_history(db_session, doc, [pets_spec("1.0.0")], tmp_path)

    resp = await _pin(db_session, make_access_token, member, integration, doc, v1)

    assert resp.status_code == 204


# --- lifecycle ----------------------------------------------------------------------


async def test_a_pin_is_hidden_while_its_document_is_out_of_the_integration_and_returns_with_it(
    db_session, make_access_token, tmp_path
):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    await _pin(db_session, make_access_token, integrator, integration, doc, v1)

    await db_session.execute(delete(IntegrationDocument).where(IntegrationDocument.integration_id == integration.id))
    gone = await _documents(db_session, make_access_token, integrator, integration, tmp_path)
    db_session.add(IntegrationDocument(integration_id=integration.id, documentation_id=doc.id, added_by_user_id=integrator.id))
    await db_session.flush()
    back = await _documents(db_session, make_access_token, integrator, integration, tmp_path)

    assert gone == {}
    assert back[str(doc.id)]["pin"]["version"] == "1.0.0"


async def test_deleting_the_document_or_the_integration_takes_the_pins_with_it(db_session, make_access_token, tmp_path):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    other_doc = await make_document(db_session, is_public=True)
    [other_v1] = await record_history(db_session, other_doc, [pets_spec("1.0.0")], tmp_path)
    db_session.add(IntegrationDocument(integration_id=integration.id, documentation_id=other_doc.id, added_by_user_id=integrator.id))
    await db_session.flush()
    await _pin(db_session, make_access_token, integrator, integration, doc, v1)
    await _pin(db_session, make_access_token, integrator, integration, other_doc, other_v1)

    await db_session.delete(await db_session.get(ApiDocument, other_doc.id))
    await db_session.flush()
    after_document = await db_session.scalar(select(func.count()).select_from(IntegrationDocumentPin))
    await db_session.delete(integration)
    await db_session.flush()
    after_integration = await db_session.scalar(select(func.count()).select_from(IntegrationDocumentPin))

    assert (after_document, after_integration) == (1, 0)


# --- the comparison -----------------------------------------------------------------


async def test_a_pinned_version_whose_file_is_gone_has_no_summary_but_the_list_still_works(
    db_session, make_access_token, tmp_path
):
    integrator, doc, integration, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    await _pin(db_session, make_access_token, integrator, integration, doc, v1)
    (Path(tmp_path) / v1.storage_path).unlink()

    row = (await _documents(db_session, make_access_token, integrator, integration, tmp_path))[str(doc.id)]

    assert row["pin"]["summary"] is None
    assert (row["pin"]["version"], row["pin"]["versions_behind"]) == ("1.0.0", 2)


async def test_the_comparison_of_a_pair_of_versions_is_made_once(db_session, tmp_path, monkeypatch):
    _, _, _, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    calls: list[int] = []
    real = comparison_module.diff_specs

    def counting(old, new):
        calls.append(1)
        return real(old, new)

    monkeypatch.setattr(comparison_module, "diff_specs", counting)

    first = await compare_versions(str(tmp_path), v1, v3)
    second = await compare_versions(str(tmp_path), v1, v3)
    other_pair = await compare_versions(str(tmp_path), v2, v3)

    assert first == second == {"breaking": 1, "warning": 0, "info": 0}
    assert other_pair == {"breaking": 0, "warning": 0, "info": 0}
    assert len(calls) == 2  # (v1, v3) once and (v2, v3) once


async def test_a_failed_comparison_is_not_remembered(db_session, tmp_path):
    _, _, _, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    saved = (Path(tmp_path) / v1.storage_path).read_bytes()
    (Path(tmp_path) / v1.storage_path).unlink()

    failed = await compare_versions(str(tmp_path), v1, v3)
    (Path(tmp_path) / v1.storage_path).write_bytes(saved)  # the file comes back
    recovered = await compare_versions(str(tmp_path), v1, v3)

    assert failed is None
    assert recovered == {"breaking": 1, "warning": 0, "info": 0}


async def test_the_cache_is_bounded(db_session, tmp_path, monkeypatch):
    _, _, _, (v1, v2, v3) = await _scenario(db_session, tmp_path)
    monkeypatch.setattr(comparison_module, "_CACHE_SIZE", 1)

    await compare_versions(str(tmp_path), v1, v3)
    await compare_versions(str(tmp_path), v2, v3)

    assert list(comparison_module._CACHE) == [(v2.id, v3.id)]  # the oldest was dropped
