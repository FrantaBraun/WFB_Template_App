# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/collections/* and /api/public/collections: the visibility
matrix on the single-collection GET and its /documents list (member/
non-member/anonymous x private/public), can_edit/is_subscribed correctness,
create/list/patch, add/remove document (incl. the
cross-team-add-of-a-public-document case and the idempotent-double-add
case), subscribe/unsubscribe (mirroring api_docs's own subscribe tests one
level up the domain model), and the public listing's
is_public-only/no-auth/no-team-scoping behavior.

Uses the same ASGITransport + dependency_overrides[get_db] + db_session +
make_access_token() pattern as test_api_docs_router.py - these routes need
both a real JWT and the DB in the same request."""

import uuid

import httpx
import pytest
from sqlalchemy import select

import app.security.jwt as jwt_module
from app.models.api_document import ApiDocument
from app.models.collection import Collection, CollectionDocument
from app.models.integration import Integration, IntegrationCollection
from app.models.knowledge_base import KnowledgeBasePage
from app.models.notification import Subscription
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


async def _add_document(db_session, collection: Collection, doc: ApiDocument, user: User) -> CollectionDocument:
    link = CollectionDocument(collection_id=collection.id, documentation_id=doc.id, added_by_user_id=user.id)
    db_session.add(link)
    await db_session.flush()
    return link


# --- GET /{id} visibility matrix ---------------------------------------------------


async def test_get_collection_member_sees_private_collection(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(collection.id)
    assert body["can_edit"] is True


async def test_get_collection_non_member_private_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}", token=outsider_token)

    assert resp.status_code == 404


async def test_get_collection_anonymous_private_returns_404(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}")

    assert resp.status_code == 404


async def test_get_collection_anonymous_sees_public_collection_cannot_edit(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}")

    assert resp.status_code == 200
    assert resp.json()["can_edit"] is False


async def test_get_collection_non_member_sees_public_collection_cannot_edit(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}", token=outsider_token)

    assert resp.status_code == 200
    assert resp.json()["can_edit"] is False


async def test_get_collection_member_sees_public_collection_can_edit(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}", token=token)

    assert resp.status_code == 200
    assert resp.json()["can_edit"] is True


async def test_get_collection_unknown_id_returns_404(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{uuid.uuid4()}", token=token)

    assert resp.status_code == 404


# --- GET /{id} is_subscribed ---------------------------------------------------------


async def test_get_collection_is_subscribed_null_when_anonymous(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}")

    assert resp.status_code == 200
    assert resp.json()["is_subscribed"] is None


async def test_get_collection_is_subscribed_false_when_signed_in_not_subscribed(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}", token=outsider_token)

    assert resp.status_code == 200
    assert resp.json()["is_subscribed"] is False


async def test_get_collection_is_subscribed_true_when_signed_in_subscribed(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))
    db_session.add(Subscription(user_id=owner.id, collection_id=collection.id))
    await db_session.flush()

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}", token=token)

    assert resp.status_code == 200
    assert resp.json()["is_subscribed"] is True


# --- GET /{id}/documents visibility matrix --------------------------------------------


async def test_list_collection_documents_member_sees_private(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)
    doc = await _make_document(db_session, team, owner, title="Doc A")
    await _add_document(db_session, collection, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/documents", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Doc A"


async def test_list_collection_documents_non_member_private_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/documents", token=outsider_token)

    assert resp.status_code == 404


async def test_list_collection_documents_anonymous_private_returns_404(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/documents")

    assert resp.status_code == 404


async def test_list_collection_documents_anonymous_sees_public(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    doc = await _make_document(db_session, team, owner)
    await _add_document(db_session, collection, doc, owner)

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/documents")

    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_collection_documents_non_member_sees_public(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    doc = await _make_document(db_session, team, owner)
    await _add_document(db_session, collection, doc, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/documents", token=outsider_token)

    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_collection_documents_member_sees_public(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/documents", token=token)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_collection_documents_ordered_by_title(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc_b = await _make_document(db_session, team, owner, title="B Doc")
    doc_a = await _make_document(db_session, team, owner, title="A Doc")
    await _add_document(db_session, collection, doc_b, owner)
    await _add_document(db_session, collection, doc_a, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/documents", token=token)

    assert resp.status_code == 200
    titles = [d["title"] for d in resp.json()]
    assert titles == ["A Doc", "B Doc"]


# --- POST /api/collections (create) --------------------------------------------------


async def test_create_collection_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        "/api/collections",
        token=token,
        json={"team_id": str(team.id), "name": "My Collection", "description": "Some notes"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Collection"
    assert body["description"] == "Some notes"
    assert body["team_id"] == str(team.id)
    assert body["is_public"] is False
    assert body["document_count"] == 0
    assert body["can_edit"] is True
    assert body["is_subscribed"] is False


async def test_create_collection_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        "/api/collections",
        token=outsider_token,
        json={"team_id": str(team.id), "name": "X"},
    )

    assert resp.status_code == 404
    rows = (await db_session.execute(select(Collection).where(Collection.team_id == team.id))).scalars().all()
    assert rows == []


# --- GET /api/collections (member list) -----------------------------------------------


async def test_list_collections_scoped_to_callers_teams(db_session, make_access_token):
    owner_a = await _make_user(db_session, email="a@example.com")
    owner_b = await _make_user(db_session, email="b@example.com")
    team_a = await _make_team_with_owner(db_session, owner_a, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner_b, name="Team B")
    await _make_collection(db_session, team_a, owner_a, name="Collection A")
    await _make_collection(db_session, team_b, owner_b, name="Collection B")
    token_a = make_access_token(sub=str(owner_a.auth_sub))

    resp = await _request(db_session, "GET", "/api/collections", token=token_a)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Collection A"


async def test_list_collections_team_id_filter(db_session, make_access_token):
    owner = await _make_user(db_session)
    team_a = await _make_team_with_owner(db_session, owner, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner, name="Team B")
    await _make_collection(db_session, team_a, owner, name="Collection A")
    await _make_collection(db_session, team_b, owner, name="Collection B")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections?team_id={team_b.id}", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Collection B"


async def test_list_collections_includes_document_count(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc_1 = await _make_document(db_session, team, owner, title="Doc 1")
    doc_2 = await _make_document(db_session, team, owner, title="Doc 2")
    await _add_document(db_session, collection, doc_1, owner)
    await _add_document(db_session, collection, doc_2, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", "/api/collections", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["document_count"] == 2


def test_list_collections_requires_auth(client):
    resp = client.get("/api/collections")
    assert resp.status_code in (401, 403)


# --- PATCH /{id} ------------------------------------------------------------------


async def test_patch_updates_fields(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, name="Old name", is_public=False)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/collections/{collection.id}",
        token=token,
        json={"name": "New name", "description": "New notes", "is_public": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New name"
    assert body["description"] == "New notes"
    assert body["is_public"] is True
    await db_session.refresh(collection)
    assert collection.name == "New name"


async def test_patch_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "PATCH", f"/api/collections/{collection.id}", token=outsider_token, json={"name": "Hack"}
    )

    assert resp.status_code == 404


# --- DELETE /{collection_id} -------------------------------------------------------


async def test_delete_collection_member_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/collections/{collection.id}", token=token)

    assert resp.status_code == 204
    rows = (await db_session.execute(select(Collection).where(Collection.id == collection.id))).scalars().all()
    assert rows == []


async def test_delete_collection_non_member_returns_404_and_leaves_row(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "DELETE", f"/api/collections/{collection.id}", token=outsider_token)

    assert resp.status_code == 404
    rows = (await db_session.execute(select(Collection).where(Collection.id == collection.id))).scalars().all()
    assert len(rows) == 1


async def test_delete_collection_unknown_id_returns_404(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "DELETE", f"/api/collections/{uuid.uuid4()}", token=token)

    assert resp.status_code == 404


def test_delete_collection_requires_auth(client):
    resp = client.delete(f"/api/collections/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)


async def test_delete_collection_cascades_every_related_row(db_session, make_access_token):
    """Full fan-out around one collection - a CollectionDocument (a document
    it holds), an IntegrationCollection (its own membership in an
    integration), a direct Subscription and a KnowledgeBasePage - then
    delete the collection and assert every one of those FK-CASCADE rows is
    actually gone, not just that the FK declarations look right."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    await _add_document(db_session, collection, doc, owner)

    integration = Integration(team_id=team.id, name="Some Integration", created_by_user_id=owner.id)
    db_session.add(integration)
    await db_session.flush()
    db_session.add(
        IntegrationCollection(integration_id=integration.id, collection_id=collection.id, added_by_user_id=owner.id)
    )

    db_session.add(Subscription(user_id=owner.id, collection_id=collection.id))
    db_session.add(KnowledgeBasePage(collection_id=collection.id, title="Some Page", created_by_user_id=owner.id))
    await db_session.flush()
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/collections/{collection.id}", token=token)

    assert resp.status_code == 204
    assert (await db_session.execute(select(Collection).where(Collection.id == collection.id))).scalars().all() == []
    assert (
        (await db_session.execute(select(CollectionDocument).where(CollectionDocument.collection_id == collection.id)))
        .scalars()
        .all()
        == []
    )
    assert (
        (
            await db_session.execute(
                select(IntegrationCollection).where(IntegrationCollection.collection_id == collection.id)
            )
        )
        .scalars()
        .all()
        == []
    )
    assert (
        (await db_session.execute(select(Subscription).where(Subscription.collection_id == collection.id)))
        .scalars()
        .all()
        == []
    )
    assert (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.collection_id == collection.id)))
        .scalars()
        .all()
        == []
    )

    # The collection's own deletion doesn't ripple beyond rows with a direct
    # FK to it - the document it held and the integration it belonged to
    # both survive.
    assert (await db_session.execute(select(ApiDocument).where(ApiDocument.id == doc.id))).scalar_one_or_none() is not None
    assert (
        await db_session.execute(select(Integration).where(Integration.id == integration.id))
    ).scalar_one_or_none() is not None


# --- POST/DELETE /{id}/documents/{documentation_id} -----------------------------------


async def test_add_document_same_team_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/collections/{collection.id}/documents/{doc.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (await db_session.execute(select(CollectionDocument).where(CollectionDocument.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].documentation_id == doc.id


async def test_add_document_other_team_public_doc_succeeds(db_session, make_access_token):
    """Cross-team aggregation is allowed when the target is public - the
    plan's locked-in assumption."""
    owner = await _make_user(db_session)
    collection_team = await _make_team_with_owner(db_session, owner, name="Collection Team")
    other_team = await _make_team_with_owner(db_session, owner, name="Other Team")
    collection = await _make_collection(db_session, collection_team, owner)
    other_public_doc = await _make_document(db_session, other_team, owner, title="Other public doc", is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/collections/{collection.id}/documents/{other_public_doc.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (await db_session.execute(select(CollectionDocument).where(CollectionDocument.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].documentation_id == other_public_doc.id


async def test_add_document_other_team_private_doc_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    collection_team = await _make_team_with_owner(db_session, owner, name="Collection Team")
    other_team = await _make_team_with_owner(db_session, owner, name="Other Team")
    collection = await _make_collection(db_session, collection_team, owner)
    other_private_doc = await _make_document(
        db_session, other_team, owner, title="Other private doc", is_public=False
    )
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/collections/{collection.id}/documents/{other_private_doc.id}", token=token
    )

    assert resp.status_code == 404
    rows = (
        (await db_session.execute(select(CollectionDocument).where(CollectionDocument.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert rows == []


async def test_add_document_idempotent_double_add(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    first = await _request(db_session, "POST", f"/api/collections/{collection.id}/documents/{doc.id}", token=token)
    second = await _request(db_session, "POST", f"/api/collections/{collection.id}/documents/{doc.id}", token=token)

    assert first.status_code == 204
    assert second.status_code == 204
    rows = (
        (await db_session.execute(select(CollectionDocument).where(CollectionDocument.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_add_document_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "POST", f"/api/collections/{collection.id}/documents/{doc.id}", token=outsider_token
    )

    assert resp.status_code == 404


async def test_add_document_unknown_document_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/collections/{collection.id}/documents/{uuid.uuid4()}", token=token
    )

    assert resp.status_code == 404


async def test_remove_document_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    await _add_document(db_session, collection, doc, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/collections/{collection.id}/documents/{doc.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (await db_session.execute(select(CollectionDocument).where(CollectionDocument.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert rows == []


async def test_remove_document_idempotent_when_absent(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/collections/{collection.id}/documents/{doc.id}", token=token
    )

    assert resp.status_code == 204


async def test_remove_document_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    doc = await _make_document(db_session, team, owner)
    await _add_document(db_session, collection, doc, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "DELETE", f"/api/collections/{collection.id}/documents/{doc.id}", token=outsider_token
    )

    assert resp.status_code == 404
    rows = (
        (await db_session.execute(select(CollectionDocument).where(CollectionDocument.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1


# --- GET /api/public/collections -------------------------------------------------------


async def test_public_listing_only_includes_public_collections_no_team_scoping(db_session):
    owner = await _make_user(db_session)
    team_a = await _make_team_with_owner(db_session, owner, name="Team A")
    team_b = await _make_team_with_owner(db_session, owner, name="Team B")
    public_collection = await _make_collection(db_session, team_a, owner, name="Public Collection", is_public=True)
    doc = await _make_document(db_session, team_a, owner)
    await _add_document(db_session, public_collection, doc, owner)
    await _make_collection(db_session, team_b, owner, name="Private Collection", is_public=False)

    resp = await _request(db_session, "GET", "/api/public/collections")  # no token at all

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Public Collection"
    assert body[0]["team_id"] == str(team_a.id)
    assert body[0]["document_count"] == 1


# --- POST/DELETE /{id}/subscribe -----------------------------------------------------


async def test_subscribe_non_member_public_collection_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    outsider = await _make_user(db_session, email="outsider@example.com")
    outsider_token = make_access_token(sub=str(outsider.auth_sub))

    resp = await _request(db_session, "POST", f"/api/collections/{collection.id}/subscribe", token=outsider_token)

    assert resp.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(Subscription).where(
                    Subscription.user_id == outsider.id, Subscription.collection_id == collection.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_subscribe_private_collection_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "POST", f"/api/collections/{collection.id}/subscribe", token=outsider_token)

    assert resp.status_code == 404


async def test_subscribe_twice_does_not_create_duplicate_row(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    first = await _request(db_session, "POST", f"/api/collections/{collection.id}/subscribe", token=token)
    second = await _request(db_session, "POST", f"/api/collections/{collection.id}/subscribe", token=token)

    assert first.status_code == 204
    assert second.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(Subscription).where(
                    Subscription.user_id == owner.id, Subscription.collection_id == collection.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_unsubscribe_removes_subscription(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))
    await _request(db_session, "POST", f"/api/collections/{collection.id}/subscribe", token=token)

    resp = await _request(db_session, "DELETE", f"/api/collections/{collection.id}/subscribe", token=token)

    assert resp.status_code == 204
    rows = (
        (
            await db_session.execute(
                select(Subscription).where(
                    Subscription.user_id == owner.id, Subscription.collection_id == collection.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_unsubscribe_when_never_subscribed_still_succeeds(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/collections/{collection.id}/subscribe", token=token)

    assert resp.status_code == 204


def test_subscribe_requires_auth(client):
    resp = client.post(f"/api/collections/{uuid.uuid4()}/subscribe")
    assert resp.status_code in (401, 403)


def test_unsubscribe_requires_auth(client):
    resp = client.delete(f"/api/collections/{uuid.uuid4()}/subscribe")
    assert resp.status_code in (401, 403)
