# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/notifications/*: the list endpoint's pagination/filter/
unread_count shape (including that unread_count is always the caller's true
total, independent of the unread filter and of limit/offset), mark-one-read
(including the not-mine -> 404 case), mark-all-read, auth-required on every
endpoint, and that document_title/version are populated correctly by joining
against real ApiDocument/ApiDocumentVersion rows.

Uses the same ASGITransport + dependency_overrides[get_db] + db_session +
make_access_token() pattern as test_api_docs_router.py/test_teams_router.py.
Notification rows are built directly rather than via notify_new_version, so
each test can control created_at explicitly - Postgres's now() is fixed at
transaction start and this whole test runs inside one transaction
(db_session's savepoint wrapper, see conftest.py), so several rows inserted
in the same test would otherwise share one identical timestamp and make
"newest first" ordering non-deterministic (same issue/fix as
test_api_docs_router.py's test_list_versions_newest_first_and_archived_flag)."""

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

import app.security.jwt as jwt_module
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.notification import Notification
from app.models.team import Team
from app.models.user import User


@pytest.fixture(autouse=True)
def _signed_in(rsa_keypair, monkeypatch):
    """Every route in this file requires a verified JWT - seed the cached
    public key once per test instead of repeating this everywhere."""
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


async def _make_team(db_session, name: str = "Test Team") -> Team:
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    return team


async def _make_document(db_session, team: Team, creator: User, **overrides) -> ApiDocument:
    fields = dict(team_id=team.id, title="Some API", created_by_user_id=creator.id)
    fields.update(overrides)
    doc = ApiDocument(**fields)
    db_session.add(doc)
    await db_session.flush()
    return doc


async def _make_version(db_session, doc: ApiDocument, version: str = "1.0.0") -> ApiDocumentVersion:
    row = ApiDocumentVersion(
        documentation_id=doc.id,
        version=version,
        format="json",
        storage_path=f"{doc.id}/dummy.json",
        checksum="deadbeef",
        source="initial",
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _make_notification(
    db_session,
    user: User,
    doc: ApiDocument,
    version: ApiDocumentVersion,
    *,
    is_read: bool = False,
    created_at: datetime | None = None,
) -> Notification:
    notification = Notification(
        user_id=user.id, documentation_id=doc.id, version_id=version.id, is_read=is_read
    )
    db_session.add(notification)
    await db_session.flush()
    if created_at is not None:
        # Force an unambiguous, real-world-like ordering - see module
        # docstring for why every row would otherwise share one timestamp.
        notification.created_at = created_at
        await db_session.flush()
    return notification


# --- GET /api/notifications: shape, ordering, unread_count --------------------------


async def test_list_no_filters_returns_all_newest_first_with_unread_count(db_session, make_access_token):
    user = await _make_user(db_session)
    team = await _make_team(db_session)
    doc = await _make_document(db_session, team, user, title="Widgets API")
    version_a = await _make_version(db_session, doc, version="1.0.0")
    # ApiDocumentVersion's partial unique index allows only one
    # archived_at IS NULL row per document (see app/models/api_document.py) -
    # archive the first before adding a second, same as a real recheck.
    version_a.archived_at = datetime.now(timezone.utc)
    await db_session.flush()
    version_b = await _make_version(db_session, doc, version="2.0.0")
    older = await _make_notification(
        db_session, user, doc, version_a, created_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    newer = await _make_notification(
        db_session, user, doc, version_b, created_at=datetime.now(timezone.utc)
    )
    token = make_access_token(sub=str(user.auth_sub))

    resp = await _request(db_session, "GET", "/api/notifications", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 2
    assert [item["id"] for item in body["items"]] == [str(newer.id), str(older.id)]
    assert body["items"][0]["version"] == "2.0.0"
    assert body["items"][0]["document_title"] == "Widgets API"
    assert body["items"][0]["is_read"] is False


async def test_document_title_and_version_reflect_correct_document_per_notification(
    db_session, make_access_token
):
    """Guards against a join bug where every row picks up the same
    document's title/version regardless of its own documentation_id."""
    user = await _make_user(db_session)
    team = await _make_team(db_session)
    doc_a = await _make_document(db_session, team, user, title="Alpha API")
    doc_b = await _make_document(db_session, team, user, title="Beta API")
    version_a = await _make_version(db_session, doc_a, version="1.0.0")
    version_b = await _make_version(db_session, doc_b, version="9.9.9")
    await _make_notification(
        db_session, user, doc_a, version_a, created_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    await _make_notification(db_session, user, doc_b, version_b, created_at=datetime.now(timezone.utc))
    token = make_access_token(sub=str(user.auth_sub))

    resp = await _request(db_session, "GET", "/api/notifications", token=token)

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["document_title"] == "Beta API"
    assert items[0]["version"] == "9.9.9"
    assert items[1]["document_title"] == "Alpha API"
    assert items[1]["version"] == "1.0.0"


async def test_pagination_limit_offset_does_not_affect_unread_count(db_session, make_access_token):
    user = await _make_user(db_session)
    team = await _make_team(db_session)
    doc = await _make_document(db_session, team, user)
    version = await _make_version(db_session, doc)
    base = datetime.now(timezone.utc)
    for i in range(3):
        await _make_notification(db_session, user, doc, version, created_at=base - timedelta(minutes=i))
    token = make_access_token(sub=str(user.auth_sub))

    resp = await _request(db_session, "GET", "/api/notifications?limit=1", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["unread_count"] == 3


# --- documentation_id filter ---------------------------------------------------------


async def test_documentation_id_filter_scopes_items_and_unread_count(db_session, make_access_token):
    user = await _make_user(db_session)
    team = await _make_team(db_session)
    doc_a = await _make_document(db_session, team, user, title="Doc A")
    doc_b = await _make_document(db_session, team, user, title="Doc B")
    version_a = await _make_version(db_session, doc_a)
    version_b = await _make_version(db_session, doc_b)
    await _make_notification(db_session, user, doc_a, version_a, created_at=datetime.now(timezone.utc))
    await _make_notification(
        db_session, user, doc_a, version_a, created_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    await _make_notification(db_session, user, doc_b, version_b, created_at=datetime.now(timezone.utc))
    token = make_access_token(sub=str(user.auth_sub))

    resp = await _request(
        db_session, "GET", f"/api/notifications?documentation_id={doc_a.id}", token=token
    )

    assert resp.status_code == 200
    body = resp.json()
    # Global total would be 3 - scoped to doc_a it must be 2, not 3.
    assert body["unread_count"] == 2
    assert len(body["items"]) == 2
    assert all(item["documentation_id"] == str(doc_a.id) for item in body["items"])


# --- unread filter, independent of unread_count --------------------------------------


async def test_unread_filter_narrows_items_but_unread_count_stays_true_total(db_session, make_access_token):
    user = await _make_user(db_session)
    team = await _make_team(db_session)
    doc = await _make_document(db_session, team, user)
    version = await _make_version(db_session, doc)
    now = datetime.now(timezone.utc)
    await _make_notification(db_session, user, doc, version, is_read=False, created_at=now)
    await _make_notification(
        db_session, user, doc, version, is_read=False, created_at=now - timedelta(minutes=1)
    )
    await _make_notification(
        db_session, user, doc, version, is_read=True, created_at=now - timedelta(minutes=2)
    )
    token = make_access_token(sub=str(user.auth_sub))

    unread_resp = await _request(db_session, "GET", "/api/notifications?unread=true", token=token)
    # unread=false asks for only the already-read items - if unread_count
    # were naively computed from the filtered item count (a real bug this
    # guards against) it would come back 1 here instead of the true total 2.
    read_resp = await _request(db_session, "GET", "/api/notifications?unread=false", token=token)

    assert unread_resp.status_code == 200 and read_resp.status_code == 200
    unread_body, read_body = unread_resp.json(), read_resp.json()
    assert len(unread_body["items"]) == 2
    assert all(item["is_read"] is False for item in unread_body["items"])
    assert len(read_body["items"]) == 1
    assert read_body["items"][0]["is_read"] is True
    assert unread_body["unread_count"] == 2
    assert read_body["unread_count"] == 2


# --- POST /{id}/read -------------------------------------------------------------------


async def test_mark_notification_read(db_session, make_access_token):
    user = await _make_user(db_session)
    team = await _make_team(db_session)
    doc = await _make_document(db_session, team, user)
    version = await _make_version(db_session, doc)
    notification = await _make_notification(db_session, user, doc, version, is_read=False)
    token = make_access_token(sub=str(user.auth_sub))

    resp = await _request(db_session, "POST", f"/api/notifications/{notification.id}/read", token=token)

    assert resp.status_code == 204
    await db_session.refresh(notification)
    assert notification.is_read is True


async def test_mark_notification_read_not_mine_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session, email="owner@example.com")
    team = await _make_team(db_session)
    doc = await _make_document(db_session, team, owner)
    version = await _make_version(db_session, doc)
    notification = await _make_notification(db_session, owner, doc, version, is_read=False)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "POST", f"/api/notifications/{notification.id}/read", token=outsider_token
    )

    assert resp.status_code == 404
    await db_session.refresh(notification)
    assert notification.is_read is False


async def test_mark_notification_read_unknown_id_returns_404(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "POST", f"/api/notifications/{uuid.uuid4()}/read", token=token)

    assert resp.status_code == 404


# --- POST /read-all ----------------------------------------------------------------------


async def test_read_all_marks_only_callers_own_unread_notifications(db_session, make_access_token):
    user = await _make_user(db_session, email="user@example.com")
    other_user = await _make_user(db_session, email="other@example.com")
    team = await _make_team(db_session)
    doc = await _make_document(db_session, team, user)
    version = await _make_version(db_session, doc)
    already_read = await _make_notification(db_session, user, doc, version, is_read=True)
    unread_one = await _make_notification(db_session, user, doc, version, is_read=False)
    unread_two = await _make_notification(db_session, user, doc, version, is_read=False)
    other_users_notification = await _make_notification(db_session, other_user, doc, version, is_read=False)
    token = make_access_token(sub=str(user.auth_sub))

    resp = await _request(db_session, "POST", "/api/notifications/read-all", token=token)

    assert resp.status_code == 204
    await db_session.refresh(already_read)
    await db_session.refresh(unread_one)
    await db_session.refresh(unread_two)
    await db_session.refresh(other_users_notification)
    assert already_read.is_read is True
    assert unread_one.is_read is True
    assert unread_two.is_read is True
    # Someone else's notification must be untouched by this call.
    assert other_users_notification.is_read is False


# --- auth required --------------------------------------------------------------------


def test_list_notifications_requires_auth(client):
    resp = client.get("/api/notifications")
    assert resp.status_code in (401, 403)


def test_mark_notification_read_requires_auth(client):
    resp = client.post(f"/api/notifications/{uuid.uuid4()}/read")
    assert resp.status_code in (401, 403)


def test_read_all_requires_auth(client):
    resp = client.post("/api/notifications/read-all")
    assert resp.status_code in (401, 403)
