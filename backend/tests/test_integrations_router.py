# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/integrations/*: strict team-only permission on every
endpoint (there is no public/anonymous-readable path for Integration at
all, unlike ApiDocument/Collection - see app/api/integrations/router.py's
module docstring), create/list/patch, collection add/remove (incl. the
cross-team-public-succeeds / cross-team-private-404 / idempotent-double-add
cases), document add/remove (same shape, plus proving a direct-link removal
never affects collection-derived reachability), and the merged /documents
endpoint's core de-duplication behavior.

Every endpoint requires a real, verified token (get_current_user, never
get_current_user_optional): a request with NO token at all is rejected by
FastAPI's HTTPBearer dependency itself (401/403) before any route body
runs, while a request with a valid token for a genuine non-member reaches
the application-level membership check and gets 404 - including when the
integration has a fully public member collection or document, since
visibility of the integration itself never inherits from its members' own
visibility. Both cases are covered below, precisely distinguished rather
than conflated.

Uses the same ASGITransport + dependency_overrides[get_db] + db_session +
make_access_token() pattern as test_collections_router.py."""

import uuid

import httpx
import pytest
from sqlalchemy import select

import app.security.jwt as jwt_module
from app.models.api_document import ApiDocument
from app.models.collection import Collection, CollectionDocument
from app.models.integration import Integration, IntegrationCollection, IntegrationDocument
from app.models.team import Team, TeamMembership
from app.models.user import User


@pytest.fixture(autouse=True)
def _signed_in(rsa_keypair, monkeypatch):
    """Every signed-in request in this file needs a verified JWT - seed the
    cached public key once per test instead of repeating this everywhere."""
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


async def _request(db_session, method: str, path: str, *, token: str | None = None, **kwargs):
    from app.database import get_db
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    headers = kwargs.pop("headers", {}) or {}
    if token is not None:
        headers = {**headers, "Authorization": f"Bearer {token}"}
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, path, headers=headers, **kwargs)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)


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


async def _make_collection(db_session, team: Team, user: User, **overrides) -> Collection:
    fields = dict(team_id=team.id, name="Some Collection", created_by_user_id=user.id)
    fields.update(overrides)
    collection = Collection(**fields)
    db_session.add(collection)
    await db_session.flush()
    return collection


async def _make_integration(db_session, team: Team, user: User, **overrides) -> Integration:
    fields = dict(team_id=team.id, name="Some Integration", created_by_user_id=user.id)
    fields.update(overrides)
    integration = Integration(**fields)
    db_session.add(integration)
    await db_session.flush()
    return integration


async def _add_document_to_collection(db_session, collection: Collection, doc: ApiDocument, user: User) -> None:
    db_session.add(CollectionDocument(collection_id=collection.id, documentation_id=doc.id, added_by_user_id=user.id))
    await db_session.flush()


async def _add_collection_to_integration(
    db_session, integration: Integration, collection: Collection, user: User
) -> None:
    db_session.add(
        IntegrationCollection(integration_id=integration.id, collection_id=collection.id, added_by_user_id=user.id)
    )
    await db_session.flush()


async def _add_document_to_integration(db_session, integration: Integration, doc: ApiDocument, user: User) -> None:
    db_session.add(
        IntegrationDocument(integration_id=integration.id, documentation_id=doc.id, added_by_user_id=user.id)
    )
    await db_session.flush()


# --- POST /api/integrations (create) --------------------------------------------------


async def test_create_integration_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        "/api/integrations",
        token=token,
        json={"team_id": str(team.id), "name": "My Integration", "description": "Some notes"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Integration"
    assert body["description"] == "Some notes"
    assert body["team_id"] == str(team.id)
    assert body["collection_count"] == 0
    assert body["direct_document_count"] == 0
    assert "can_edit" not in body
    assert "is_public" not in body


async def test_create_integration_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "POST", "/api/integrations", token=outsider_token, json={"team_id": str(team.id), "name": "X"}
    )

    assert resp.status_code == 404
    rows = (await db_session.execute(select(Integration).where(Integration.team_id == team.id))).scalars().all()
    assert rows == []


def test_create_integration_requires_auth(client):
    resp = client.post("/api/integrations", json={"team_id": str(uuid.uuid4()), "name": "X"})
    assert resp.status_code in (401, 403)


# --- GET /api/integrations (member list) -----------------------------------------------


async def test_list_integrations_scoped_to_callers_teams(db_session, make_access_token):
    owner_a = await _make_user(db_session, email="a@example.com")
    owner_b = await _make_user(db_session, email="b@example.com")
    team_a = await _make_team_with_owner(db_session, owner_a, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner_b, name="Team B")
    await _make_integration(db_session, team_a, owner_a, name="Integration A")
    await _make_integration(db_session, team_b, owner_b, name="Integration B")
    token_a = make_access_token(sub=str(owner_a.auth_sub))

    resp = await _request(db_session, "GET", "/api/integrations", token=token_a)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Integration A"


async def test_list_integrations_team_id_filter(db_session, make_access_token):
    owner = await _make_user(db_session)
    team_a = await _make_team_with_owner(db_session, owner, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner, name="Team B")
    await _make_integration(db_session, team_a, owner, name="Integration A")
    await _make_integration(db_session, team_b, owner, name="Integration B")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations?team_id={team_b.id}", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Integration B"


async def test_list_integrations_includes_collection_and_document_counts(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection_1 = await _make_collection(db_session, team, owner, name="Collection 1")
    collection_2 = await _make_collection(db_session, team, owner, name="Collection 2")
    doc = await _make_document(db_session, team, owner)
    await _add_collection_to_integration(db_session, integration, collection_1, owner)
    await _add_collection_to_integration(db_session, integration, collection_2, owner)
    await _add_document_to_integration(db_session, integration, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", "/api/integrations", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["collection_count"] == 2
    assert body[0]["document_count"] == 1


async def test_list_integrations_orders_by_name(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    await _make_integration(db_session, team, owner, name="Zeta")
    await _make_integration(db_session, team, owner, name="Alpha")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", "/api/integrations", token=token)

    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()]
    assert names == ["Alpha", "Zeta"]


def test_list_integrations_requires_auth(client):
    resp = client.get("/api/integrations")
    assert resp.status_code in (401, 403)


# --- GET /api/integrations/{id} ------------------------------------------------------


async def test_get_integration_member_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner, description="Some description")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(integration.id)
    assert body["description"] == "Some description"
    assert body["collection_count"] == 0
    assert body["direct_document_count"] == 0


async def test_get_integration_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}", token=outsider_token)

    assert resp.status_code == 404


async def test_get_integration_anonymous_returns_401_or_403(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}")  # no token at all

    assert resp.status_code in (401, 403)


async def test_get_integration_unknown_id_returns_404(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/integrations/{uuid.uuid4()}", token=token)

    assert resp.status_code == 404


async def test_get_integration_public_member_collection_does_not_leak_visibility(db_session, make_access_token):
    """The integration's own visibility never inherits from a member
    Collection's is_public flag - a non-member still gets 404 on the
    integration itself even though they could see the public collection
    directly via /api/collections/{id}."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    public_collection = await _make_collection(db_session, team, owner, is_public=True)
    await _add_collection_to_integration(db_session, integration, public_collection, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}", token=outsider_token)

    assert resp.status_code == 404


async def test_get_integration_public_member_document_does_not_leak_visibility(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    public_doc = await _make_document(db_session, team, owner, is_public=True)
    await _add_document_to_integration(db_session, integration, public_doc, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}", token=outsider_token)

    assert resp.status_code == 404


# --- PATCH /api/integrations/{id} ----------------------------------------------------


async def test_patch_integration_updates_fields(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner, name="Old name")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/integrations/{integration.id}",
        token=token,
        json={"name": "New name", "description": "New notes"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New name"
    assert body["description"] == "New notes"
    await db_session.refresh(integration)
    assert integration.name == "New name"


async def test_patch_integration_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "PATCH", f"/api/integrations/{integration.id}", token=outsider_token, json={"name": "Hack"}
    )

    assert resp.status_code == 404


# --- GET /api/integrations/{id}/collections --------------------------------------------


async def test_list_integration_collections_member_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection_b = await _make_collection(db_session, team, owner, name="B Collection")
    collection_a = await _make_collection(db_session, team, owner, name="A Collection")
    await _add_collection_to_integration(db_session, integration, collection_b, owner)
    await _add_collection_to_integration(db_session, integration, collection_a, owner)
    doc = await _make_document(db_session, team, owner)
    await _add_document_to_collection(db_session, collection_a, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/collections", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert [c["name"] for c in body] == ["A Collection", "B Collection"]
    assert body[0]["document_count"] == 1
    assert body[1]["document_count"] == 0


async def test_list_integration_collections_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/collections", token=outsider_token)

    assert resp.status_code == 404


# --- POST/DELETE /{id}/collections/{collection_id} -------------------------------------


async def test_add_collection_same_team_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/collections/{collection.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(IntegrationCollection).where(IntegrationCollection.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].collection_id == collection.id


async def test_add_collection_other_team_public_succeeds(db_session, make_access_token):
    """Cross-team aggregation is allowed when the target is public - the
    plan's locked-in assumption, mirrored from collections/router.py's own
    add-document endpoint."""
    owner = await _make_user(db_session)
    integration_team = await _make_team_with_owner(db_session, owner, name="Integration Team")
    other_team = await _make_team_with_owner(db_session, owner, name="Other Team")
    integration = await _make_integration(db_session, integration_team, owner)
    other_public_collection = await _make_collection(db_session, other_team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        f"/api/integrations/{integration.id}/collections/{other_public_collection.id}",
        token=token,
    )

    assert resp.status_code == 204


async def test_add_collection_other_team_private_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    integration_team = await _make_team_with_owner(db_session, owner, name="Integration Team")
    other_team = await _make_team_with_owner(db_session, owner, name="Other Team")
    integration = await _make_integration(db_session, integration_team, owner)
    other_private_collection = await _make_collection(db_session, other_team, owner, is_public=False)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        f"/api/integrations/{integration.id}/collections/{other_private_collection.id}",
        token=token,
    )

    assert resp.status_code == 404
    rows = (
        (
            await db_session.execute(
                select(IntegrationCollection).where(IntegrationCollection.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_add_collection_idempotent_double_add(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    first = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/collections/{collection.id}", token=token
    )
    second = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/collections/{collection.id}", token=token
    )

    assert first.status_code == 204
    assert second.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(IntegrationCollection).where(IntegrationCollection.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_add_collection_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        f"/api/integrations/{integration.id}/collections/{collection.id}",
        token=outsider_token,
    )

    assert resp.status_code == 404


async def test_add_collection_unknown_collection_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/collections/{uuid.uuid4()}", token=token
    )

    assert resp.status_code == 404


async def test_remove_collection_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    await _add_collection_to_integration(db_session, integration, collection, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/collections/{collection.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(IntegrationCollection).where(IntegrationCollection.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_remove_collection_idempotent_when_absent(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/collections/{collection.id}", token=token
    )

    assert resp.status_code == 204


async def test_remove_collection_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    await _add_collection_to_integration(db_session, integration, collection, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "DELETE",
        f"/api/integrations/{integration.id}/collections/{collection.id}",
        token=outsider_token,
    )

    assert resp.status_code == 404
    rows = (
        (
            await db_session.execute(
                select(IntegrationCollection).where(IntegrationCollection.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


# --- POST/DELETE /{id}/documents/{documentation_id} -------------------------------------


async def test_add_document_same_team_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "POST", f"/api/integrations/{integration.id}/documents/{doc.id}", token=token)

    assert resp.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(IntegrationDocument).where(IntegrationDocument.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].documentation_id == doc.id


async def test_add_document_other_team_public_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    integration_team = await _make_team_with_owner(db_session, owner, name="Integration Team")
    other_team = await _make_team_with_owner(db_session, owner, name="Other Team")
    integration = await _make_integration(db_session, integration_team, owner)
    other_public_doc = await _make_document(db_session, other_team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/documents/{other_public_doc.id}", token=token
    )

    assert resp.status_code == 204


async def test_add_document_other_team_private_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    integration_team = await _make_team_with_owner(db_session, owner, name="Integration Team")
    other_team = await _make_team_with_owner(db_session, owner, name="Other Team")
    integration = await _make_integration(db_session, integration_team, owner)
    other_private_doc = await _make_document(db_session, other_team, owner, is_public=False)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/documents/{other_private_doc.id}", token=token
    )

    assert resp.status_code == 404
    rows = (
        (
            await db_session.execute(
                select(IntegrationDocument).where(IntegrationDocument.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_add_document_idempotent_double_add(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    first = await _request(db_session, "POST", f"/api/integrations/{integration.id}/documents/{doc.id}", token=token)
    second = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/documents/{doc.id}", token=token
    )

    assert first.status_code == 204
    assert second.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(IntegrationDocument).where(IntegrationDocument.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_add_document_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/documents/{doc.id}", token=outsider_token
    )

    assert resp.status_code == 404


async def test_add_document_unknown_document_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/documents/{uuid.uuid4()}", token=token
    )

    assert resp.status_code == 404


async def test_remove_document_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    await _add_document_to_integration(db_session, integration, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/documents/{doc.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(IntegrationDocument).where(IntegrationDocument.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_remove_document_idempotent_when_absent(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/documents/{doc.id}", token=token
    )

    assert resp.status_code == 204


async def test_remove_document_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    await _add_document_to_integration(db_session, integration, doc, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/documents/{doc.id}", token=outsider_token
    )

    assert resp.status_code == 404
    rows = (
        (
            await db_session.execute(
                select(IntegrationDocument).where(IntegrationDocument.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_remove_document_direct_link_does_not_affect_collection_reachability(db_session, make_access_token):
    """Removing a direct IntegrationDocument link only affects direct
    membership - a document still reachable via a member Collection stays
    reachable through the merged /documents endpoint afterward."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner, title="Shared Doc")
    await _add_collection_to_integration(db_session, integration, collection, owner)
    await _add_document_to_collection(db_session, collection, doc, owner)
    await _add_document_to_integration(db_session, integration, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    remove_resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/documents/{doc.id}", token=token
    )
    assert remove_resp.status_code == 204

    merged_resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)
    assert merged_resp.status_code == 200
    body = merged_resp.json()
    assert len(body) == 1
    assert body[0]["id"] == str(doc.id)
    assert [s["type"] for s in body[0]["sources"]] == ["collection"]


# --- GET /api/integrations/{id}/documents (merged, de-duplicated) ----------------------


async def test_list_integration_documents_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=outsider_token)

    assert resp.status_code == 404


async def test_list_integration_documents_empty_when_no_members(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_integration_documents_direct_only_source(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(db_session, team, owner, title="Direct Doc")
    await _add_document_to_integration(db_session, integration, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Direct Doc"
    assert body[0]["sources"] == [{"type": "direct", "collection_id": None, "collection_name": None}]


async def test_list_integration_documents_collection_only_source(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner, name="Collection X")
    doc = await _make_document(db_session, team, owner, title="Collection Doc")
    await _add_collection_to_integration(db_session, integration, collection, owner)
    await _add_document_to_collection(db_session, collection, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["sources"] == [
        {"type": "collection", "collection_id": str(collection.id), "collection_name": "Collection X"}
    ]


async def test_list_integration_documents_dedup_direct_and_collection(db_session, make_access_token):
    """The Definition of Done scenario: a standalone document that is BOTH a
    direct IntegrationDocument member AND independently a member of a
    Collection that's also linked to the same Integration must appear
    exactly once, with a sources list containing one "direct" and one
    "collection" entry - never zero times, never twice."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner, name="Collection A")
    doc = await _make_document(db_session, team, owner, title="Shared Doc")
    await _add_collection_to_integration(db_session, integration, collection, owner)
    await _add_document_to_collection(db_session, collection, doc, owner)
    await _add_document_to_integration(db_session, integration, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == str(doc.id)
    sources = body[0]["sources"]
    assert len(sources) == 2
    types = {s["type"] for s in sources}
    assert types == {"direct", "collection"}
    collection_source = next(s for s in sources if s["type"] == "collection")
    assert collection_source["collection_id"] == str(collection.id)
    assert collection_source["collection_name"] == "Collection A"
    direct_source = next(s for s in sources if s["type"] == "direct")
    assert direct_source["collection_id"] is None
    assert direct_source["collection_name"] is None


async def test_list_integration_documents_dedup_across_two_collections(db_session, make_access_token):
    """The same document reachable via two different member Collections (no
    direct link at all) also gets exactly one entry, with two "collection"
    sources."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection_1 = await _make_collection(db_session, team, owner, name="Collection 1")
    collection_2 = await _make_collection(db_session, team, owner, name="Collection 2")
    doc = await _make_document(db_session, team, owner, title="Doubly Linked Doc")
    await _add_collection_to_integration(db_session, integration, collection_1, owner)
    await _add_collection_to_integration(db_session, integration, collection_2, owner)
    await _add_document_to_collection(db_session, collection_1, doc, owner)
    await _add_document_to_collection(db_session, collection_2, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert len(body[0]["sources"]) == 2
    assert {s["type"] for s in body[0]["sources"]} == {"collection"}


async def test_list_integration_documents_ordered_by_title(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc_b = await _make_document(db_session, team, owner, title="B Doc")
    doc_a = await _make_document(db_session, team, owner, title="A Doc")
    await _add_document_to_integration(db_session, integration, doc_b, owner)
    await _add_document_to_integration(db_session, integration, doc_a, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)

    assert resp.status_code == 200
    titles = [d["title"] for d in resp.json()]
    assert titles == ["A Doc", "B Doc"]


async def test_list_integration_documents_includes_summary_fields(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    doc = await _make_document(
        db_session, team, owner, title="Full Doc", is_public=True, recheck_period="daily"
    )
    await _add_document_to_integration(db_session, integration, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token)

    assert resp.status_code == 200
    body = resp.json()[0]
    assert body["id"] == str(doc.id)
    assert body["title"] == "Full Doc"
    assert body["team_id"] == str(team.id)
    assert body["is_public"] is True
    assert body["recheck_period"] == "daily"
    assert body["last_checked_at"] is None
    assert body["last_check_error"] is None
    assert body["current_version"] is None
