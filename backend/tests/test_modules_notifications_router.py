# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the notifications module's endpoints: GET "" (list), POST
/{id}/read and POST /read-all.

Deliberately does NOT use conftest.py's `client` fixture (TestClient over
the real app.main app): whether this module's routes exist at all depends
on ENABLED_MODULES at the moment app.api.router was first imported, which
is ambient environment state this test file shouldn't have to assume one
way or the other - a fresh clone's real .env ships ENABLED_MODULES=[] by
design. Mounting just this module's router on a throwaway FastAPI app tests
the same route handler and the same URL shape without depending on that -
same approach as test_modules_kontaktni_formular_router.py.

Uses ASGITransport rather than TestClient because these routes need both a
real JWT dependency chain (get_current_user) and db_session's connection on
the same event loop - see conftest.py's own note on this, and
test_account_router.py for the established pattern this mirrors."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.database import get_db
from app.modules.notifications.models import Notification
from app.modules.notifications.router import router as notifications_router

_notifications_app = FastAPI()
_notifications_app.include_router(notifications_router, prefix="/api/modules/notifications")

_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _override_db(db_session):
    _notifications_app.dependency_overrides[get_db] = lambda: db_session
    yield
    _notifications_app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _signed_in(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_notifications_app), base_url="http://test") as ac:
        yield ac


async def _resolve_user(db_session, sub: str):
    """Direct call, not through HTTP - see
    test_modules_notifications_service.py's identical helper for why."""
    return await get_current_user(claims={"sub": sub}, db=db_session)


async def _seed_notification(
    db_session,
    user_id,
    *,
    created_at,
    message_key: str = "notifications.test",
    message_params: dict | None = None,
    link_url: str | None = None,
    reference_id: uuid.UUID | None = None,
    is_read: bool = False,
) -> Notification:
    """Bypasses the create_notification service (whose created_at always
    comes from the DB's server_default) so ordering/pagination tests can
    seed rows with distinct, known timestamps instead of depending on
    Postgres's now() - which is transaction-start time, not per-statement,
    so several plain create_notification calls in one test's transaction
    would otherwise tie."""
    notification = Notification(
        user_id=user_id,
        message_key=message_key,
        message_params=message_params or {},
        link_url=link_url,
        reference_id=reference_id,
        is_read=is_read,
        created_at=created_at,
    )
    db_session.add(notification)
    await db_session.commit()
    return notification


async def test_list_empty_for_new_user(client, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await client.get("/api/modules/notifications", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json() == {"items": [], "unread_count": 0}


async def test_list_returns_items_newest_first(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    await _seed_notification(db_session, user.id, created_at=_BASE_TIME, message_key="k.older")
    await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=2), message_key="k.newest"
    )
    await _seed_notification(db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=1), message_key="k.mid")

    resp = await client.get("/api/modules/notifications", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert [item["message_key"] for item in body["items"]] == ["k.newest", "k.mid", "k.older"]
    assert body["unread_count"] == 3


async def test_list_unread_filter(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    await _seed_notification(db_session, user.id, created_at=_BASE_TIME, message_key="k.read", is_read=True)
    await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=1), message_key="k.unread", is_read=False
    )

    resp = await client.get(
        "/api/modules/notifications", params={"unread": "true"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 200
    assert [item["message_key"] for item in resp.json()["items"]] == ["k.unread"]


async def test_list_reference_id_filter(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    target_ref = uuid.uuid4()
    await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME, message_key="k.match", reference_id=target_ref
    )
    await _seed_notification(
        db_session,
        user.id,
        created_at=_BASE_TIME + timedelta(minutes=1),
        message_key="k.other_ref",
        reference_id=uuid.uuid4(),
    )
    await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=2), message_key="k.no_ref"
    )

    resp = await client.get(
        "/api/modules/notifications",
        params={"reference_id": str(target_ref)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert [item["message_key"] for item in resp.json()["items"]] == ["k.match"]


async def test_list_unread_count_ignores_unread_filter(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    await _seed_notification(db_session, user.id, created_at=_BASE_TIME, is_read=True, message_key="k.read")
    await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=1), is_read=False, message_key="k.unread1"
    )
    await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=2), is_read=False, message_key="k.unread2"
    )

    resp_unread = await client.get(
        "/api/modules/notifications", params={"unread": "true"}, headers={"Authorization": f"Bearer {token}"}
    )
    resp_all = await client.get("/api/modules/notifications", headers={"Authorization": f"Bearer {token}"})

    assert resp_unread.json()["unread_count"] == 2
    assert resp_all.json()["unread_count"] == 2
    assert len(resp_unread.json()["items"]) == 2
    assert len(resp_all.json()["items"]) == 3


async def test_list_unread_count_scoped_by_reference_id(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    target_ref = uuid.uuid4()
    await _seed_notification(db_session, user.id, created_at=_BASE_TIME, reference_id=target_ref, is_read=False)
    await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=1), reference_id=uuid.uuid4(), is_read=False
    )

    resp = await client.get(
        "/api/modules/notifications",
        params={"reference_id": str(target_ref)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.json()["unread_count"] == 1


async def test_list_pagination(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    for i in range(5):
        await _seed_notification(db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=i), message_key=f"k.{i}")

    resp_page1 = await client.get(
        "/api/modules/notifications", params={"limit": 2, "offset": 0}, headers={"Authorization": f"Bearer {token}"}
    )
    resp_page2 = await client.get(
        "/api/modules/notifications", params={"limit": 2, "offset": 2}, headers={"Authorization": f"Bearer {token}"}
    )

    assert [item["message_key"] for item in resp_page1.json()["items"]] == ["k.4", "k.3"]
    assert [item["message_key"] for item in resp_page2.json()["items"]] == ["k.2", "k.1"]


async def test_list_only_returns_callers_own_notifications(client, db_session, make_access_token):
    sub_a = str(uuid.uuid4())
    sub_b = str(uuid.uuid4())
    user_a = await _resolve_user(db_session, sub_a)
    user_b = await _resolve_user(db_session, sub_b)
    token_a = make_access_token(sub=sub_a)
    await _seed_notification(db_session, user_a.id, created_at=_BASE_TIME, message_key="k.mine")
    await _seed_notification(
        db_session, user_b.id, created_at=_BASE_TIME + timedelta(minutes=1), message_key="k.not_mine"
    )

    resp = await client.get("/api/modules/notifications", headers={"Authorization": f"Bearer {token_a}"})

    assert [item["message_key"] for item in resp.json()["items"]] == ["k.mine"]


async def test_mark_notification_read_success(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    notification = await _seed_notification(db_session, user.id, created_at=_BASE_TIME, is_read=False)

    resp = await client.post(
        f"/api/modules/notifications/{notification.id}/read", headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 204
    refreshed = await db_session.get(Notification, notification.id)
    assert refreshed.is_read is True


async def test_mark_notification_read_404_for_nonexistent(client, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await client.post(
        f"/api/modules/notifications/{uuid.uuid4()}/read", headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 404


async def test_mark_notification_read_404_for_someone_elses(client, db_session, make_access_token):
    sub_owner = str(uuid.uuid4())
    owner = await _resolve_user(db_session, sub_owner)
    token_other = make_access_token(sub=str(uuid.uuid4()))
    notification = await _seed_notification(db_session, owner.id, created_at=_BASE_TIME, is_read=False)

    resp = await client.post(
        f"/api/modules/notifications/{notification.id}/read", headers={"Authorization": f"Bearer {token_other}"}
    )

    assert resp.status_code == 404
    refreshed = await db_session.get(Notification, notification.id)
    assert refreshed.is_read is False


async def test_mark_all_notifications_read(client, db_session, make_access_token):
    sub = str(uuid.uuid4())
    user = await _resolve_user(db_session, sub)
    token = make_access_token(sub=sub)
    already_read = await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME, is_read=True, message_key="k.already"
    )
    unread1 = await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=1), is_read=False, message_key="k.u1"
    )
    unread2 = await _seed_notification(
        db_session, user.id, created_at=_BASE_TIME + timedelta(minutes=2), is_read=False, message_key="k.u2"
    )

    resp = await client.post("/api/modules/notifications/read-all", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 204
    for notification in (already_read, unread1, unread2):
        refreshed = await db_session.get(Notification, notification.id)
        assert refreshed.is_read is True


async def test_mark_all_notifications_read_does_not_affect_other_users(client, db_session, make_access_token):
    sub_a = str(uuid.uuid4())
    sub_b = str(uuid.uuid4())
    await _resolve_user(db_session, sub_a)
    user_b = await _resolve_user(db_session, sub_b)
    token_a = make_access_token(sub=sub_a)
    notification_b = await _seed_notification(db_session, user_b.id, created_at=_BASE_TIME, is_read=False)

    resp = await client.post("/api/modules/notifications/read-all", headers={"Authorization": f"Bearer {token_a}"})

    assert resp.status_code == 204
    refreshed = await db_session.get(Notification, notification_b.id)
    assert refreshed.is_read is False
