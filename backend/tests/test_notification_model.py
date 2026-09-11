# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the Subscription/Notification models' own defaults and
constraints, independent of app.services.notifications (see
test_notifications_service.py for that)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.notification import Notification, Subscription
from app.models.team import Team
from app.models.user import User


async def _make_user(db_session, email: str | None = None) -> User:
    user = User(auth_sub=uuid.uuid4(), email=email)
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_document(db_session, **overrides) -> ApiDocument:
    team = Team(name="Test Team")
    db_session.add(team)
    await db_session.flush()
    creator = await _make_user(db_session)
    fields = dict(team_id=team.id, title="Some API", created_by_user_id=creator.id)
    fields.update(overrides)
    document = ApiDocument(**fields)
    db_session.add(document)
    await db_session.flush()
    return document


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


async def test_subscription_create_sets_defaults(db_session):
    doc = await _make_document(db_session)
    user = await _make_user(db_session)

    subscription = Subscription(user_id=user.id, documentation_id=doc.id)
    db_session.add(subscription)
    await db_session.flush()

    assert subscription.id is not None
    assert subscription.created_at is not None


async def test_subscription_user_documentation_pair_must_be_unique(db_session):
    doc = await _make_document(db_session)
    user = await _make_user(db_session)
    db_session.add(Subscription(user_id=user.id, documentation_id=doc.id))
    await db_session.flush()

    db_session.add(Subscription(user_id=user.id, documentation_id=doc.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_subscription_same_user_can_subscribe_to_different_documents(db_session):
    """The unique constraint is on the (user_id, documentation_id) pair, not
    on user_id alone - a user subscribed to several documents is normal."""
    doc_a = await _make_document(db_session, title="Doc A")
    doc_b = await _make_document(db_session, title="Doc B")
    user = await _make_user(db_session)

    db_session.add(Subscription(user_id=user.id, documentation_id=doc_a.id))
    db_session.add(Subscription(user_id=user.id, documentation_id=doc_b.id))
    await db_session.flush()  # must not raise


async def test_notification_create_defaults_to_unread(db_session):
    doc = await _make_document(db_session)
    version = await _make_version(db_session, doc)
    recipient = await _make_user(db_session, email="recipient@example.com")

    notification = Notification(user_id=recipient.id, documentation_id=doc.id, version_id=version.id)
    db_session.add(notification)
    await db_session.flush()

    assert notification.id is not None
    assert notification.is_read is False
    assert notification.created_at is not None


async def test_notification_same_user_can_have_several_rows(db_session):
    """No uniqueness constraint on Notification - one row per recipient per
    version-archive event, and a recipient may have many over time."""
    doc = await _make_document(db_session)
    first_version = await _make_version(db_session, doc, version="1.0.0")
    # ApiDocumentVersion's partial unique index allows only one
    # archived_at IS NULL row per document (see app/models/api_document.py)
    # - archive the first before adding a second, same as a real recheck.
    first_version.archived_at = datetime.now(timezone.utc)
    await db_session.flush()
    second_version = await _make_version(db_session, doc, version="2.0.0")
    recipient = await _make_user(db_session, email="recipient@example.com")

    db_session.add(Notification(user_id=recipient.id, documentation_id=doc.id, version_id=first_version.id))
    db_session.add(Notification(user_id=recipient.id, documentation_id=doc.id, version_id=second_version.id))
    await db_session.flush()  # must not raise
