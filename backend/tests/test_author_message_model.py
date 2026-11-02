# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for AuthorMessage and the kind-aware Notification: the
exactly-one-target and per-kind column rules the database itself enforces,
and that deleting the target takes its messages and their notifications with
it."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.author_message import AuthorMessage
from app.models.notification import Notification
from tests.author_contact_support import make_collection, make_document, make_team, make_user


async def _setup(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    team = await make_team(db_session)
    return author, sender, team


async def test_message_defaults(db_session):
    author, sender, team = await _setup(db_session)
    doc = await make_document(db_session, team, author)

    message = AuthorMessage(
        sender_user_id=sender.id, recipient_user_id=author.id, documentation_id=doc.id, body="Hello"
    )
    db_session.add(message)
    await db_session.flush()

    assert message.id is not None
    assert message.email_sent is False
    assert message.collection_id is None


async def test_message_rejects_both_targets(db_session):
    author, sender, team = await _setup(db_session)
    doc = await make_document(db_session, team, author)
    collection = await make_collection(db_session, team, author)

    db_session.add(
        AuthorMessage(
            sender_user_id=sender.id,
            recipient_user_id=author.id,
            documentation_id=doc.id,
            collection_id=collection.id,
            body="Hello",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_message_rejects_no_target(db_session):
    author, sender, _ = await _setup(db_session)

    db_session.add(AuthorMessage(sender_user_id=sender.id, recipient_user_id=author.id, body="Hello"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_notification_of_a_message_needs_the_message_and_nothing_else(db_session):
    author, sender, team = await _setup(db_session)
    doc = await make_document(db_session, team, author)
    message = AuthorMessage(
        sender_user_id=sender.id, recipient_user_id=author.id, documentation_id=doc.id, body="Hello"
    )
    db_session.add(message)
    await db_session.flush()

    ok = Notification(kind="author_message", user_id=author.id, message_id=message.id)
    db_session.add(ok)
    await db_session.flush()
    assert ok.is_read is False

    # A message notification that also points at a document is rejected ...
    db_session.add(
        Notification(kind="author_message", user_id=author.id, message_id=message.id, documentation_id=doc.id)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_notification_of_a_message_without_the_message_is_rejected(db_session):
    author, _, _ = await _setup(db_session)

    db_session.add(Notification(kind="author_message", user_id=author.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_default_kind_still_needs_a_document_and_version(db_session):
    """The old shape (no kind given) is a new_version notification, so it
    keeps needing both columns."""
    author, _, team = await _setup(db_session)
    doc = await make_document(db_session, team, author)

    db_session.add(Notification(user_id=author.id, documentation_id=doc.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_the_document_removes_its_messages_and_their_notifications(db_session):
    author, sender, team = await _setup(db_session)
    doc = await make_document(db_session, team, author)
    message = AuthorMessage(
        sender_user_id=sender.id, recipient_user_id=author.id, documentation_id=doc.id, body="Hello"
    )
    db_session.add(message)
    await db_session.flush()
    db_session.add(Notification(kind="author_message", user_id=author.id, message_id=message.id))
    await db_session.flush()

    await db_session.delete(doc)
    await db_session.flush()

    assert (
        await db_session.scalar(
            select(func.count()).select_from(AuthorMessage).where(AuthorMessage.recipient_user_id == author.id)
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == author.id)
        )
        == 0
    )
