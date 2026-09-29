# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.modules.notifications.service.create_notification: builds
and stages a Notification row without committing, leaving the caller in
control of the transaction boundary (e.g. to batch many recipients into one
commit)."""

import uuid

from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.modules.notifications.models import Notification
from app.modules.notifications.service import create_notification


async def _resolve_user(db_session, sub: str):
    """Direct call, not through HTTP - get_current_user both creates and
    resolves the local User row for a sub (and commits it), giving tests a
    real users.id to satisfy notifications.user_id's FK."""
    return await get_current_user(claims={"sub": sub}, db=db_session)


async def test_create_notification_creates_row_with_correct_fields(db_session):
    user = await _resolve_user(db_session, str(uuid.uuid4()))
    reference_id = uuid.uuid4()

    notification = await create_notification(
        db_session,
        user_id=user.id,
        message_key="notifications.example",
        message_params={"count": 3},
        link_url="/somewhere",
        reference_id=reference_id,
    )
    await db_session.commit()
    await db_session.refresh(notification)

    assert notification.user_id == user.id
    assert notification.message_key == "notifications.example"
    assert notification.message_params == {"count": 3}
    assert notification.link_url == "/somewhere"
    assert notification.reference_id == reference_id
    assert notification.is_read is False
    assert notification.created_at is not None

    persisted = await db_session.get(Notification, notification.id)
    assert persisted is not None
    assert persisted.message_key == "notifications.example"


async def test_create_notification_defaults_message_params_to_empty_dict(db_session):
    user = await _resolve_user(db_session, str(uuid.uuid4()))

    notification = await create_notification(db_session, user_id=user.id, message_key="notifications.bare")

    assert notification.message_params == {}


async def test_create_notification_leaves_optional_fields_none(db_session):
    user = await _resolve_user(db_session, str(uuid.uuid4()))

    notification = await create_notification(db_session, user_id=user.id, message_key="notifications.bare")
    await db_session.flush()  # is_read's default=False is applied at flush time, not on construction

    assert notification.link_url is None
    assert notification.reference_id is None
    assert notification.is_read is False


async def test_create_notification_does_not_commit(db_session):
    user = await _resolve_user(db_session, str(uuid.uuid4()))

    await create_notification(db_session, user_id=user.id, message_key="notifications.uncommitted")
    await db_session.rollback()

    count = await db_session.scalar(select(func.count()).select_from(Notification))
    assert count == 0
