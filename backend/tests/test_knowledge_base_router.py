# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the Phase 7 Knowledge Base endpoints on both
/api/collections/{id}/kb/pages* and /api/integrations/{id}/kb*:

- Collection KB page CRUD with the same visibility matrix (member/
  non-member/anonymous x private/public) as every other collection GET, and
  member-only write access.
- The cross-owner 404 guarantee: patching/deleting a page through a
  collection (or integration) whose id doesn't match the page's own owner
  never succeeds, even when the page belongs to a *related* owner (e.g. a
  collection that's a genuine member of the integration being used to try
  to edit it).
- Integration own-page CRUD, strict member-only (no anonymous path at all,
  matching every other integration endpoint).
- GET /{integration_id}/kb's merged view assembly, and the load-bearing
  proof that it's computed live at read time rather than copied: editing a
  collection's page through the collection's own endpoint is immediately
  visible on a second fetch of the integration's merged view, with no extra
  step.

Uses the same ASGITransport + dependency_overrides[get_db] + db_session +
make_access_token() pattern as test_collections_router.py /
test_integrations_router.py."""

import uuid

import httpx
import pytest
from sqlalchemy import select

import app.security.jwt as jwt_module
from app.models.collection import Collection
from app.models.integration import Integration, IntegrationCollection
from app.models.knowledge_base import KnowledgeBasePage
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


async def _add_collection_to_integration(
    db_session, integration: Integration, collection: Collection, user: User
) -> None:
    db_session.add(
        IntegrationCollection(integration_id=integration.id, collection_id=collection.id, added_by_user_id=user.id)
    )
    await db_session.flush()


async def _make_kb_page(db_session, creator: User, **overrides) -> KnowledgeBasePage:
    fields = dict(title="Some Page", created_by_user_id=creator.id)
    fields.update(overrides)
    page = KnowledgeBasePage(**fields)
    db_session.add(page)
    await db_session.flush()
    return page


# === Collection KB pages: /api/collections/{id}/kb/pages* ==============================

# --- POST /{collection_id}/kb/pages (create) --------------------------------------------


async def test_create_kb_page_member_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        f"/api/collections/{collection.id}/kb/pages",
        token=token,
        json={"title": "Getting Started", "content": "# Hello", "position": 1},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Getting Started"
    assert body["content"] == "# Hello"
    assert body["position"] == 1
    assert "id" in body and "created_at" in body and "updated_at" in body

    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].integration_id is None
    assert rows[0].created_by_user_id == owner.id


async def test_create_kb_page_defaults(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/collections/{collection.id}/kb/pages", token=token, json={"title": "Minimal"}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["content"] == ""
    assert body["position"] == 0


async def test_create_kb_page_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        f"/api/collections/{collection.id}/kb/pages",
        token=outsider_token,
        json={"title": "Hack"},
    )

    assert resp.status_code == 404
    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.collection_id == collection.id)))
        .scalars()
        .all()
    )
    assert rows == []


def test_create_kb_page_requires_auth(client):
    resp = client.post(f"/api/collections/{uuid.uuid4()}/kb/pages", json={"title": "X"})
    assert resp.status_code in (401, 403)


# --- GET /{collection_id}/kb/pages (list, same visibility as the collection) -------------


async def test_list_kb_pages_member_sees_private(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)
    await _make_kb_page(db_session, owner, collection_id=collection.id, title="Private Page")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/kb/pages", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Private Page"


async def test_list_kb_pages_non_member_private_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/kb/pages", token=outsider_token)

    assert resp.status_code == 404


async def test_list_kb_pages_anonymous_private_returns_404(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=False)

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/kb/pages")

    assert resp.status_code == 404


async def test_list_kb_pages_anonymous_sees_public(db_session):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    await _make_kb_page(db_session, owner, collection_id=collection.id, title="Public Page")

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/kb/pages")

    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_kb_pages_non_member_sees_public(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    await _make_kb_page(db_session, owner, collection_id=collection.id)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/kb/pages", token=outsider_token)

    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_kb_pages_member_sees_public_empty(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner, is_public=True)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/kb/pages", token=token)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_kb_pages_unknown_collection_returns_404(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/collections/{uuid.uuid4()}/kb/pages", token=token)

    assert resp.status_code == 404


async def test_list_kb_pages_ordered_by_position_then_created_at(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    await _make_kb_page(db_session, owner, collection_id=collection.id, title="Second", position=5)
    await _make_kb_page(db_session, owner, collection_id=collection.id, title="First", position=0)
    await _make_kb_page(db_session, owner, collection_id=collection.id, title="Third", position=10)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/collections/{collection.id}/kb/pages", token=token)

    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()]
    assert titles == ["First", "Second", "Third"]


# --- PATCH /{collection_id}/kb/pages/{page_id} -------------------------------------------


async def test_update_kb_page_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    page = await _make_kb_page(
        db_session, owner, collection_id=collection.id, title="Old title", content="Old content", position=0
    )
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/collections/{collection.id}/kb/pages/{page.id}",
        token=token,
        json={"title": "New title", "content": "New content", "position": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "New title"
    assert body["content"] == "New content"
    assert body["position"] == 3
    await db_session.refresh(page)
    assert page.title == "New title"


async def test_update_kb_page_partial_update_leaves_other_fields(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    page = await _make_kb_page(
        db_session, owner, collection_id=collection.id, title="Keep me", content="Keep this too", position=2
    )
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/collections/{collection.id}/kb/pages/{page.id}",
        token=token,
        json={"position": 9},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Keep me"
    assert body["content"] == "Keep this too"
    assert body["position"] == 9


async def test_update_kb_page_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, collection_id=collection.id, title="Untouched")
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/collections/{collection.id}/kb/pages/{page.id}",
        token=outsider_token,
        json={"title": "Hack"},
    )

    assert resp.status_code == 404
    await db_session.refresh(page)
    assert page.title == "Untouched"


async def test_update_kb_page_different_collection_returns_404(db_session, make_access_token):
    """A page belonging to collection A is never editable through collection
    B's endpoint, even for a member of the same team that owns both."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection_a = await _make_collection(db_session, team, owner, name="Collection A")
    collection_b = await _make_collection(db_session, team, owner, name="Collection B")
    page = await _make_kb_page(db_session, owner, collection_id=collection_a.id, title="Belongs to A")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/collections/{collection_b.id}/kb/pages/{page.id}",
        token=token,
        json={"title": "Hijacked"},
    )

    assert resp.status_code == 404
    await db_session.refresh(page)
    assert page.title == "Belongs to A"


async def test_update_kb_page_unknown_page_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/collections/{collection.id}/kb/pages/{uuid.uuid4()}",
        token=token,
        json={"title": "X"},
    )

    assert resp.status_code == 404


# --- DELETE /{collection_id}/kb/pages/{page_id} ------------------------------------------


async def test_delete_kb_page_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, collection_id=collection.id)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/collections/{collection.id}/kb/pages/{page.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.id == page.id))).scalars().all()
    )
    assert rows == []


async def test_delete_kb_page_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection = await _make_collection(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, collection_id=collection.id)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "DELETE", f"/api/collections/{collection.id}/kb/pages/{page.id}", token=outsider_token
    )

    assert resp.status_code == 404
    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.id == page.id))).scalars().all()
    )
    assert len(rows) == 1


async def test_delete_kb_page_different_collection_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    collection_a = await _make_collection(db_session, team, owner, name="Collection A")
    collection_b = await _make_collection(db_session, team, owner, name="Collection B")
    page = await _make_kb_page(db_session, owner, collection_id=collection_a.id, title="Belongs to A")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/collections/{collection_b.id}/kb/pages/{page.id}", token=token
    )

    assert resp.status_code == 404
    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.id == page.id))).scalars().all()
    )
    assert len(rows) == 1


# === Integration KB: /api/integrations/{id}/kb, /kb/pages* ==============================

# --- POST /{integration_id}/kb/pages (create own page) ------------------------------------


async def test_create_integration_kb_page_member_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "POST",
        f"/api/integrations/{integration.id}/kb/pages",
        token=token,
        json={"title": "Overview", "content": "Body text", "position": 2},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Overview"
    assert body["content"] == "Body text"
    assert body["position"] == 2

    rows = (
        (
            await db_session.execute(
                select(KnowledgeBasePage).where(KnowledgeBasePage.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].collection_id is None


async def test_create_integration_kb_page_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        f"/api/integrations/{integration.id}/kb/pages",
        token=outsider_token,
        json={"title": "Hack"},
    )

    assert resp.status_code == 404
    rows = (
        (
            await db_session.execute(
                select(KnowledgeBasePage).where(KnowledgeBasePage.integration_id == integration.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_create_integration_kb_page_anonymous_returns_401_or_403(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)

    resp = await _request(
        db_session, "POST", f"/api/integrations/{integration.id}/kb/pages", json={"title": "X"}
    )  # no token at all

    assert resp.status_code in (401, 403)


def test_create_integration_kb_page_requires_auth(client):
    resp = client.post(f"/api/integrations/{uuid.uuid4()}/kb/pages", json={"title": "X"})
    assert resp.status_code in (401, 403)


# --- PATCH /{integration_id}/kb/pages/{page_id} --------------------------------------------


async def test_update_integration_kb_page_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, integration_id=integration.id, title="Old title")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/integrations/{integration.id}/kb/pages/{page.id}",
        token=token,
        json={"title": "New title"},
    )

    assert resp.status_code == 200
    assert resp.json()["title"] == "New title"
    await db_session.refresh(page)
    assert page.title == "New title"


async def test_update_integration_kb_page_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, integration_id=integration.id, title="Untouched")
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/integrations/{integration.id}/kb/pages/{page.id}",
        token=outsider_token,
        json={"title": "Hack"},
    )

    assert resp.status_code == 404
    await db_session.refresh(page)
    assert page.title == "Untouched"


async def test_update_integration_kb_page_anonymous_returns_401_or_403(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, integration_id=integration.id)

    resp = await _request(
        db_session, "PATCH", f"/api/integrations/{integration.id}/kb/pages/{page.id}", json={"title": "Hack"}
    )  # no token at all

    assert resp.status_code in (401, 403)


async def test_update_integration_kb_page_belonging_to_collection_returns_404(db_session, make_access_token):
    """Proves the ownership filter actually blocks cross-editing, not just
    that it happens to work in the happy path: a page owned by a Collection
    - even one that's a genuine member of this very integration - can never
    be edited through the integration's own kb/pages endpoint, since the
    lookup is filtered to integration_id == this integration and the
    collection-owned page's integration_id is NULL."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    await _add_collection_to_integration(db_session, integration, collection, owner)
    page = await _make_kb_page(db_session, owner, collection_id=collection.id, title="Collection's page")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/integrations/{integration.id}/kb/pages/{page.id}",
        token=token,
        json={"title": "Hijacked"},
    )

    assert resp.status_code == 404
    await db_session.refresh(page)
    assert page.title == "Collection's page"


async def test_update_integration_kb_page_unknown_page_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session,
        "PATCH",
        f"/api/integrations/{integration.id}/kb/pages/{uuid.uuid4()}",
        token=token,
        json={"title": "X"},
    )

    assert resp.status_code == 404


# --- DELETE /{integration_id}/kb/pages/{page_id} -------------------------------------------


async def test_delete_integration_kb_page_success(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, integration_id=integration.id)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/kb/pages/{page.id}", token=token
    )

    assert resp.status_code == 204
    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.id == page.id))).scalars().all()
    )
    assert rows == []


async def test_delete_integration_kb_page_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, integration_id=integration.id)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/kb/pages/{page.id}", token=outsider_token
    )

    assert resp.status_code == 404
    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.id == page.id))).scalars().all()
    )
    assert len(rows) == 1


async def test_delete_integration_kb_page_anonymous_returns_401_or_403(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    page = await _make_kb_page(db_session, owner, integration_id=integration.id)

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/kb/pages/{page.id}"
    )  # no token at all

    assert resp.status_code in (401, 403)


async def test_delete_integration_kb_page_belonging_to_collection_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner)
    await _add_collection_to_integration(db_session, integration, collection, owner)
    page = await _make_kb_page(db_session, owner, collection_id=collection.id, title="Collection's page")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "DELETE", f"/api/integrations/{integration.id}/kb/pages/{page.id}", token=token
    )

    assert resp.status_code == 404
    rows = (
        (await db_session.execute(select(KnowledgeBasePage).where(KnowledgeBasePage.id == page.id))).scalars().all()
    )
    assert len(rows) == 1


# --- GET /{integration_id}/kb (merged view) -------------------------------------------------


async def test_get_integration_kb_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/kb", token=outsider_token)

    assert resp.status_code == 404


async def test_get_integration_kb_anonymous_returns_401_or_403(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/kb")  # no token at all

    assert resp.status_code in (401, 403)


async def test_get_integration_kb_empty_when_no_pages(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/kb", token=token)

    assert resp.status_code == 200
    assert resp.json() == {"collection_pages": [], "own_pages": []}


async def test_get_integration_kb_merged_view_and_live_update(db_session, make_access_token):
    """The Definition of Done scenario: build an integration with one member
    collection holding 2 pages plus 1 integration-owned page; confirm the
    merged view assembles them correctly. Then, in the SAME test, PATCH one
    of the collection's pages through the collection's own endpoint and
    re-fetch the integration's merged view, confirming the change is
    immediately visible with no extra step - proving this is a genuinely
    live read-time computation, never a copy taken when the collection was
    linked."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration = await _make_integration(db_session, team, owner)
    collection = await _make_collection(db_session, team, owner, name="Collection A")
    await _add_collection_to_integration(db_session, integration, collection, owner)
    page_1 = await _make_kb_page(
        db_session, owner, collection_id=collection.id, title="Page 1", content="Original content", position=0
    )
    await _make_kb_page(db_session, owner, collection_id=collection.id, title="Page 2", position=1)
    own_page = await _make_kb_page(db_session, owner, integration_id=integration.id, title="Own Page")
    token = make_access_token(sub=str(owner.auth_sub))

    first_resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/kb", token=token)

    assert first_resp.status_code == 200
    body = first_resp.json()
    assert len(body["collection_pages"]) == 1
    group = body["collection_pages"][0]
    assert group["collection_id"] == str(collection.id)
    assert group["collection_name"] == "Collection A"
    assert [p["title"] for p in group["pages"]] == ["Page 1", "Page 2"]
    assert len(body["own_pages"]) == 1
    assert body["own_pages"][0]["id"] == str(own_page.id)
    assert body["own_pages"][0]["title"] == "Own Page"

    patch_resp = await _request(
        db_session,
        "PATCH",
        f"/api/collections/{collection.id}/kb/pages/{page_1.id}",
        token=token,
        json={"title": "Page 1 Updated", "content": "New content"},
    )
    assert patch_resp.status_code == 200

    second_resp = await _request(db_session, "GET", f"/api/integrations/{integration.id}/kb", token=token)

    assert second_resp.status_code == 200
    second_group = second_resp.json()["collection_pages"][0]
    updated_page = next(p for p in second_group["pages"] if p["id"] == str(page_1.id))
    assert updated_page["title"] == "Page 1 Updated"
    assert updated_page["content"] == "New content"
    # The untouched sibling page and the integration's own page are
    # unaffected by the collection-side edit.
    other_page = next(p for p in second_group["pages"] if p["id"] != str(page_1.id))
    assert other_page["title"] == "Page 2"
    assert second_resp.json()["own_pages"][0]["title"] == "Own Page"


async def test_get_integration_kb_does_not_include_other_integrations_own_pages(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    integration_a = await _make_integration(db_session, team, owner, name="Integration A")
    integration_b = await _make_integration(db_session, team, owner, name="Integration B")
    await _make_kb_page(db_session, owner, integration_id=integration_b.id, title="Belongs to B")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/integrations/{integration_a.id}/kb", token=token)

    assert resp.status_code == 200
    assert resp.json()["own_pages"] == []
