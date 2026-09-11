# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/api-docs/* and /api/public/api-docs: the visibility matrix
on the single-document GET and its /versions list (member/non-member/
anonymous x private/public), create-by-URL and create-by-upload, recheck
against an unchanged vs. a changed fixture spec, the raw spec download, the
member-only mutation endpoints' 404-for-non-member guard, the PATCH
recheck_period/source_url validation rule, and the public listing's
is_public=true-only/no-auth/no-team-scoping behavior.

Uses the same ASGITransport + dependency_overrides[get_db] + db_session +
make_access_token() pattern as test_teams_router.py - these routes need both
a real JWT and the DB in the same request. respx mocks fetch_spec_from_url's
outbound HTTP call (never the real network); it coexists with the
ASGITransport-driven request to the app itself since that one is dispatched
in-process and never touches respx's patched transport (see
test_modules_kontaktni_formular_router.py for the same combination, there
via the sync TestClient instead). Version rows are seeded by calling
process_new_spec directly - it derives checksum/storage_path itself, so
hand-building an ApiDocumentVersion row would either duplicate that logic or
fake it."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from sqlalchemy import select

import app.security.jwt as jwt_module
from app.config import Settings, get_settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.team import Team, TeamMembership
from app.models.user import User
from app.services.api_document_versions import process_new_spec


@pytest.fixture(autouse=True)
def _signed_in(rsa_keypair, monkeypatch):
    """Every signed-in request in this file needs a verified JWT - seed the
    cached public key once per test instead of repeating this everywhere."""
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


@pytest.fixture()
def api_docs_settings(tmp_path) -> Settings:
    """uploads_dir pointed at a throwaway tmp_path so tests never touch the
    real backend/uploads directory."""
    return Settings(uploads_dir=str(tmp_path), spec_fetch_timeout_seconds=5.0)


async def _request(db_session, method: str, path: str, *, token: str | None = None, settings=None, **kwargs):
    from app.database import get_db
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    if settings is not None:
        fastapi_app.dependency_overrides[get_settings] = lambda: settings
    headers = kwargs.pop("headers", {}) or {}
    if token is not None:
        headers = {**headers, "Authorization": f"Bearer {token}"}
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, path, headers=headers, **kwargs)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        if settings is not None:
            fastapi_app.dependency_overrides.pop(get_settings, None)


def _spec_bytes(version: str, title: str = "Example API") -> bytes:
    return json.dumps({"openapi": "3.0.0", "info": {"title": title, "version": version}}).encode()


async def _make_user(db_session, email: str | None = "user@example.com") -> User:
    user = User(auth_sub=uuid.uuid4(), email=email)
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_team_with_owner(db_session, owner: User, name: str = "Test Team") -> Team:
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMembership(team_id=team.id, user_id=owner.id, role="owner"))
    await db_session.flush()
    return team


async def _make_document(db_session, team: Team, user: User, **overrides) -> ApiDocument:
    fields = dict(team_id=team.id, title="Some API", created_by_user_id=user.id)
    fields.update(overrides)
    doc = ApiDocument(**fields)
    db_session.add(doc)
    await db_session.flush()
    return doc


async def _seed_version(db_session, doc: ApiDocument, uploads_dir: str, version: str = "1.0.0", source: str = "initial") -> ApiDocumentVersion:
    result = await process_new_spec(
        doc, _spec_bytes(version), source=source, db=db_session, uploads_dir=uploads_dir, max_size_bytes=10_000_000
    )
    assert result is not None
    return result


# --- GET /{id} visibility matrix ---------------------------------------------------


async def test_get_document_member_sees_private_doc(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=False)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(doc.id)
    assert body["can_edit"] is True


async def test_get_document_non_member_private_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=False)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}", token=outsider_token)

    assert resp.status_code == 404


async def test_get_document_anonymous_private_returns_404(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=False)

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}")

    assert resp.status_code == 404


async def test_get_document_anonymous_sees_public_doc_cannot_edit(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=True)

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}")

    assert resp.status_code == 200
    assert resp.json()["can_edit"] is False


async def test_get_document_non_member_sees_public_doc_cannot_edit(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=True)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}", token=outsider_token)

    assert resp.status_code == 200
    assert resp.json()["can_edit"] is False


async def test_get_document_member_sees_public_doc_can_edit(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}", token=token)

    assert resp.status_code == 200
    assert resp.json()["can_edit"] is True


async def test_get_document_unknown_id_returns_404(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/api-docs/{uuid.uuid4()}", token=token)

    assert resp.status_code == 404


# --- GET /{id}/versions visibility + ordering --------------------------------------


async def test_list_versions_member_sees_private_doc(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=False)
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir, version="1.0.0")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}/versions", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["version"] == "1.0.0"
    assert body[0]["archived_at"] is None


async def test_list_versions_non_member_private_returns_404(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=False)
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}/versions", token=outsider_token)

    assert resp.status_code == 404


async def test_list_versions_anonymous_private_returns_404(db_session, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=False)
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir)

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}/versions")

    assert resp.status_code == 404


async def test_list_versions_anonymous_sees_public_doc(db_session, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=True)
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir)

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}/versions")

    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_versions_newest_first_and_archived_flag(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner)
    first = await _seed_version(db_session, doc, api_docs_settings.uploads_dir, version="1.0.0")
    second = await _seed_version(
        db_session, doc, api_docs_settings.uploads_dir, version="2.0.0", source="manual_recheck"
    )
    # Postgres's now() is fixed at transaction start, not per-statement, and
    # this whole test runs inside one transaction (db_session's savepoint
    # wrapper - see conftest.py), so both rows would otherwise land on the
    # exact same fetched_at. Force a real, unambiguous ordering the same way
    # two separate real requests naturally would.
    first.fetched_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    second.fetched_at = datetime.now(timezone.utc)
    await db_session.flush()
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/api-docs/{doc.id}/versions", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["version"] == "2.0.0"
    assert body[0]["archived_at"] is None
    assert body[0]["source"] == "manual_recheck"
    assert body[1]["version"] == "1.0.0"
    assert body[1]["archived_at"] is not None


# --- GET /{id}/versions/{version_id}/spec -------------------------------------------


async def test_get_version_spec_returns_raw_bytes(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner)
    version = await _seed_version(db_session, doc, api_docs_settings.uploads_dir, version="1.0.0")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "GET", f"/api/api-docs/{doc.id}/versions/{version.id}/spec", token=token, settings=api_docs_settings
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.content == _spec_bytes("1.0.0")


async def test_get_version_spec_non_member_private_returns_404(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, is_public=False)
    version = await _seed_version(db_session, doc, api_docs_settings.uploads_dir)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "GET",
        f"/api/api-docs/{doc.id}/versions/{version.id}/spec",
        token=outsider_token,
        settings=api_docs_settings,
    )

    assert resp.status_code == 404


async def test_get_version_spec_mismatched_document_returns_404(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc_a = await _make_document(db_session, team, owner, title="Doc A")
    doc_b = await _make_document(db_session, team, owner, title="Doc B")
    version_a = await _seed_version(db_session, doc_a, api_docs_settings.uploads_dir)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "GET",
        f"/api/api-docs/{doc_b.id}/versions/{version_a.id}/spec",
        token=token,
        settings=api_docs_settings,
    )

    assert resp.status_code == 404


# --- POST /api/api-docs (create by URL) ---------------------------------------------


@respx.mock
async def test_create_by_url_success(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))
    respx.get("https://example.com/openapi.json").mock(
        return_value=httpx.Response(200, content=_spec_bytes("1.0.0"))
    )

    resp = await _request(
        db_session,
        "POST",
        "/api/api-docs",
        token=token,
        settings=api_docs_settings,
        json={
            "team_id": str(team.id),
            "title": "Example API",
            "source_url": "https://example.com/openapi.json",
            "recheck_period": "manual",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Example API"
    assert body["team_id"] == str(team.id)
    assert body["source_url"] == "https://example.com/openapi.json"
    assert body["can_edit"] is True
    assert body["last_check_error"] is None
    assert body["current_version"]["version"] == "1.0.0"
    assert body["current_version"]["format"] == "json"
    assert body["current_version"]["source"] == "initial"


async def test_create_by_url_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        "/api/api-docs",
        token=outsider_token,
        json={"team_id": str(team.id), "title": "X", "source_url": "https://example.com/spec.json"},
    )

    assert resp.status_code == 404


async def test_create_missing_source_url_returns_422_and_creates_no_document(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", "/api/api-docs", token=token, json={"team_id": str(team.id), "title": "X"}
    )

    assert resp.status_code == 422
    docs = (await db_session.execute(select(ApiDocument).where(ApiDocument.team_id == team.id))).scalars().all()
    assert docs == []


@respx.mock
async def test_create_by_url_fetch_failure_returns_422_and_keeps_document(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))
    respx.get("https://example.com/openapi.json").mock(return_value=httpx.Response(500))

    resp = await _request(
        db_session,
        "POST",
        "/api/api-docs",
        token=token,
        settings=api_docs_settings,
        json={"team_id": str(team.id), "title": "Example API", "source_url": "https://example.com/openapi.json"},
    )

    assert resp.status_code == 422
    docs = (await db_session.execute(select(ApiDocument).where(ApiDocument.team_id == team.id))).scalars().all()
    assert len(docs) == 1
    assert docs[0].last_check_error is not None


@respx.mock
async def test_create_by_url_invalid_spec_returns_422_and_keeps_document(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))
    respx.get("https://example.com/openapi.json").mock(return_value=httpx.Response(200, content=b"\xff\xff\xff\xff"))

    resp = await _request(
        db_session,
        "POST",
        "/api/api-docs",
        token=token,
        settings=api_docs_settings,
        json={"team_id": str(team.id), "title": "Example API", "source_url": "https://example.com/openapi.json"},
    )

    assert resp.status_code == 422
    docs = (await db_session.execute(select(ApiDocument).where(ApiDocument.team_id == team.id))).scalars().all()
    assert len(docs) == 1
    assert docs[0].last_check_error is not None


# --- POST /api/api-docs/upload (create by file) -------------------------------------


async def test_create_by_upload_success(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        "/api/api-docs/upload",
        token=token,
        settings=api_docs_settings,
        data={"team_id": str(team.id), "title": "Uploaded API"},
        files={"file": ("openapi.json", _spec_bytes("1.0.0"), "application/json")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Uploaded API"
    assert body["source_url"] is None
    assert body["recheck_period"] == "manual"
    assert body["current_version"]["version"] == "1.0.0"
    assert body["current_version"]["source"] == "initial"


async def test_create_by_upload_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        "/api/api-docs/upload",
        token=outsider_token,
        data={"team_id": str(team.id), "title": "X"},
        files={"file": ("openapi.json", _spec_bytes("1.0.0"), "application/json")},
    )

    assert resp.status_code == 404


async def test_create_by_upload_invalid_spec_returns_422_and_keeps_document(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        "/api/api-docs/upload",
        token=token,
        settings=api_docs_settings,
        data={"team_id": str(team.id), "title": "X"},
        files={"file": ("broken.json", b"\xff\xff\xff\xff", "application/json")},
    )

    assert resp.status_code == 422
    docs = (await db_session.execute(select(ApiDocument).where(ApiDocument.team_id == team.id))).scalars().all()
    assert len(docs) == 1


# --- POST /{id}/recheck --------------------------------------------------------------


@respx.mock
async def test_recheck_unchanged_version_is_noop(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, source_url="https://example.com/openapi.json")
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir, version="1.0.0")
    token = make_access_token(sub=str(owner.auth_sub))
    respx.get("https://example.com/openapi.json").mock(
        return_value=httpx.Response(200, content=_spec_bytes("1.0.0"))
    )

    resp = await _request(
        db_session, "POST", f"/api/api-docs/{doc.id}/recheck", token=token, settings=api_docs_settings
    )

    assert resp.status_code == 200
    assert resp.json()["current_version"]["version"] == "1.0.0"
    all_versions = (
        (await db_session.execute(select(ApiDocumentVersion).where(ApiDocumentVersion.documentation_id == doc.id)))
        .scalars()
        .all()
    )
    assert len(all_versions) == 1


@respx.mock
async def test_recheck_changed_version_archives_old_creates_new(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, source_url="https://example.com/openapi.json")
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir, version="1.0.0")
    token = make_access_token(sub=str(owner.auth_sub))
    respx.get("https://example.com/openapi.json").mock(
        return_value=httpx.Response(200, content=_spec_bytes("2.0.0"))
    )

    resp = await _request(
        db_session, "POST", f"/api/api-docs/{doc.id}/recheck", token=token, settings=api_docs_settings
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version"]["version"] == "2.0.0"
    assert body["current_version"]["source"] == "manual_recheck"

    all_versions = (
        (await db_session.execute(select(ApiDocumentVersion).where(ApiDocumentVersion.documentation_id == doc.id)))
        .scalars()
        .all()
    )
    assert len(all_versions) == 2
    archived = [v for v in all_versions if v.archived_at is not None]
    assert len(archived) == 1
    assert archived[0].version == "1.0.0"


async def test_recheck_no_source_url_returns_400(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, source_url=None)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "POST", f"/api/api-docs/{doc.id}/recheck", token=token)

    assert resp.status_code == 400


async def test_recheck_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, source_url="https://example.com/openapi.json")
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "POST", f"/api/api-docs/{doc.id}/recheck", token=outsider_token)

    assert resp.status_code == 404


# --- POST /{id}/upload-version --------------------------------------------------------


async def test_upload_version_creates_new_version_regardless_of_original_source(
    db_session, make_access_token, api_docs_settings
):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, source_url=None, recheck_period="manual")
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir, version="1.0.0")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/upload-version",
        token=token,
        settings=api_docs_settings,
        files={"file": ("openapi.json", _spec_bytes("2.0.0"), "application/json")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version"]["version"] == "2.0.0"
    assert body["current_version"]["source"] == "manual_upload"


async def test_upload_version_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/upload-version",
        token=outsider_token,
        files={"file": ("openapi.json", _spec_bytes("1.0.0"), "application/json")},
    )

    assert resp.status_code == 404


# --- PATCH /{id} ------------------------------------------------------------------


async def test_patch_updates_fields(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, title="Old title", is_public=False)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/api-docs/{doc.id}",
        token=token,
        json={"title": "New title", "notes": "Some notes", "is_public": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "New title"
    assert body["notes"] == "Some notes"
    assert body["is_public"] is True
    await db_session.refresh(doc)
    assert doc.title == "New title"


async def test_patch_recheck_period_without_source_url_returns_422(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, source_url=None, recheck_period="manual")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "PATCH", f"/api/api-docs/{doc.id}", token=token, json={"recheck_period": "daily"}
    )

    assert resp.status_code == 422
    await db_session.refresh(doc)
    assert doc.recheck_period == "manual"


async def test_patch_clearing_source_url_while_non_manual_returns_422(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(
        db_session, team, owner, source_url="https://example.com/openapi.json", recheck_period="daily"
    )
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "PATCH", f"/api/api-docs/{doc.id}", token=token, json={"source_url": None})

    assert resp.status_code == 422
    await db_session.refresh(doc)
    assert doc.source_url == "https://example.com/openapi.json"


async def test_patch_can_set_recheck_period_and_source_url_together(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, source_url=None, recheck_period="manual")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/api-docs/{doc.id}",
        token=token,
        json={"recheck_period": "daily", "source_url": "https://example.com/openapi.json"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["recheck_period"] == "daily"
    assert body["source_url"] == "https://example.com/openapi.json"


async def test_patch_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "PATCH", f"/api/api-docs/{doc.id}", token=outsider_token, json={"title": "Hack"}
    )

    assert resp.status_code == 404


# --- GET /api/api-docs (member list) ------------------------------------------------


async def test_list_documents_scoped_to_callers_teams(db_session, make_access_token):
    owner_a = await _make_user(db_session, email="a@example.com")
    owner_b = await _make_user(db_session, email="b@example.com")
    team_a = await _make_team_with_owner(db_session, owner_a, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner_b, name="Team B")
    await _make_document(db_session, team_a, owner_a, title="Doc A")
    await _make_document(db_session, team_b, owner_b, title="Doc B")
    token_a = make_access_token(sub=str(owner_a.auth_sub))

    resp = await _request(db_session, "GET", "/api/api-docs", token=token_a)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Doc A"


async def test_list_documents_team_id_filter(db_session, make_access_token):
    owner = await _make_user(db_session)
    team_a = await _make_team_with_owner(db_session, owner, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner, name="Team B")
    await _make_document(db_session, team_a, owner, title="Doc A")
    await _make_document(db_session, team_b, owner, title="Doc B")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/api-docs?team_id={team_b.id}", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Doc B"


async def test_list_documents_includes_current_version_string(db_session, make_access_token, api_docs_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    doc = await _make_document(db_session, team, owner, title="Doc A")
    await _seed_version(db_session, doc, api_docs_settings.uploads_dir, version="3.1.4")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", "/api/api-docs", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["current_version"] == "3.1.4"


def test_list_documents_requires_auth(client):
    resp = client.get("/api/api-docs")
    assert resp.status_code in (401, 403)


# --- GET /api/public/api-docs -------------------------------------------------------


async def test_public_listing_only_includes_public_docs_no_team_scoping(db_session, api_docs_settings):
    owner = await _make_user(db_session)
    team_a = await _make_team_with_owner(db_session, owner, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner, name="Team B")
    public_doc = await _make_document(db_session, team_a, owner, title="Public Doc", is_public=True)
    await _seed_version(db_session, public_doc, api_docs_settings.uploads_dir, version="1.0.0")
    await _make_document(db_session, team_b, owner, title="Private Doc", is_public=False)

    resp = await _request(db_session, "GET", "/api/public/api-docs")  # no token at all

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Public Doc"
    assert body[0]["team_id"] == str(team_a.id)
    assert body[0]["current_version"] == "1.0.0"
