# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.author_contact: the name shown for a user, what is
stored and mailed when one user writes to the author of a document or
collection (reply-to, link, subject kept to one line), the refusals (the
author themselves, too many messages in an hour) that must leave nothing
behind, and that a failing mail never undoes the stored message.

socket.getfqdn is stubbed because building a message calls it for the
Message-ID and it costs about a second per e-mail on the development
machine."""

import socket
from datetime import timedelta
from email.utils import getaddresses

import pytest
from fastapi_mail import FastMail
from sqlalchemy import func, select

import app.services.author_contact as author_contact
from app.models.author_message import AuthorMessage
from app.models.notification import Notification
from app.services.author_contact import (
    AuthorContactError,
    display_name,
    get_author_info,
    one_line,
    preview,
    send_author_message,
)
from app.services.email import _connection_config
from tests.author_contact_support import (
    author_settings,
    make_collection,
    make_document,
    make_team,
    make_user,
)


@pytest.fixture(autouse=True)
def _fast_message_ids(monkeypatch):
    monkeypatch.setattr(socket, "getfqdn", lambda *args, **kwargs: "localhost")


def _body(message) -> str:
    return message.get_payload()[0].get_payload(decode=True).decode()


def _addresses(header: str) -> list[str]:
    return [addr for _, addr in getaddresses([header])]


# --- display_name / text helpers ----------------------------------------------------


async def test_display_name_prefers_nickname_then_login_then_nothing(db_session):
    both = await make_user(db_session, nickname="Honza", login="jnovak")
    login_only = await make_user(db_session, login="jnovak")
    blank_nickname = await make_user(db_session, nickname="   ", login="jnovak")
    neither = await make_user(db_session, email="private@example.com")

    assert display_name(both) == "Honza"
    assert display_name(login_only) == "jnovak"
    assert display_name(blank_nickname) == "jnovak"
    assert display_name(neither) is None  # the e-mail address is never a fallback
    assert display_name(None) is None


def test_one_line_collapses_every_kind_of_whitespace():
    assert one_line("a\r\nb\n\n c\t d") == "a b c d"


def test_preview_is_one_line_and_cut_with_an_ellipsis():
    assert preview("short\nmessage") == "short message"
    long = preview("word " * 100)
    assert len(long) <= author_contact.PREVIEW_LENGTH
    assert long.endswith("…")


async def test_author_info_has_name_and_team_but_no_address(db_session):
    author = await make_user(db_session, email="author@example.com", nickname="Ada")
    team = await make_team(db_session, name="Core Platform")

    info = await get_author_info(db_session, created_by_user_id=author.id, team_id=team.id)

    assert info.user_id == author.id
    assert info.display_name == "Ada"
    assert info.team_name == "Core Platform"
    assert info.accepts_messages is True
    assert not hasattr(info, "email")


# --- send_author_message ------------------------------------------------------------


async def test_stores_message_and_notification_and_emails_the_author(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com", nickname="Sam")
    doc = await make_document(db_session, await make_team(db_session), author, title="Payments API")
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        message = await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Is v2 coming?", document=doc, settings=settings
        )

    assert message.email_sent is True
    stored = await db_session.get(AuthorMessage, message.id)
    assert (stored.sender_user_id, stored.recipient_user_id) == (sender.id, author.id)
    assert (stored.documentation_id, stored.collection_id) == (doc.id, None)
    assert stored.body == "Is v2 coming?"
    notification = (
        await db_session.execute(select(Notification).where(Notification.message_id == message.id))
    ).scalar_one()
    assert (notification.kind, notification.user_id, notification.is_read) == ("author_message", author.id, False)

    assert len(outbox) == 1
    sent = outbox[0]
    assert _addresses(str(sent["To"])) == ["author@example.com"]
    assert _addresses(str(sent["Reply-To"])) == ["sender@example.com"]
    assert str(sent["Subject"]) == "Message from Sam about Payments API"
    body = _body(sent)
    assert "Is v2 coming?" in body
    assert f"http://app.test/api-docs/{doc.id}" in body
    assert "http://app.test/messages" in body


async def test_collection_message_links_to_the_collection(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com", login="sam")
    collection = await make_collection(db_session, await make_team(db_session), author, name="Billing APIs")
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        message = await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Hi", collection=collection, settings=settings
        )

    stored = await db_session.get(AuthorMessage, message.id)
    assert (stored.documentation_id, stored.collection_id) == (None, collection.id)
    assert str(outbox[0]["Subject"]) == "Message from sam about Billing APIs"
    assert f"http://app.test/collections/{collection.id}" in _body(outbox[0])


async def test_sender_without_address_means_no_reply_to(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email=None, login="sam")
    doc = await make_document(db_session, await make_team(db_session), author)
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        message = await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
        )

    assert message.email_sent is True
    assert outbox[0]["Reply-To"] is None


async def test_author_without_address_still_gets_the_in_app_notification(db_session):
    author = await make_user(db_session, email=None)
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        message = await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
        )

    assert outbox == []
    assert message.email_sent is False
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.message_id == message.id)
        )
        == 1
    )


async def test_failing_mail_keeps_the_message_and_reports_it(db_session, monkeypatch):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    async def boom(*args, **kwargs):
        raise ConnectionError("smtp down")

    monkeypatch.setattr(author_contact, "send_email", boom)

    message = await send_author_message(
        db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=author_settings()
    )

    assert message.email_sent is False
    stored = await db_session.get(AuthorMessage, message.id)
    assert stored is not None and stored.email_sent is False
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.message_id == message.id)
        )
        == 1
    )


async def test_line_breaks_in_names_cannot_reach_the_subject(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com", nickname="Sam\r\nBcc: x@example.com")
    doc = await make_document(
        db_session, await make_team(db_session), author, title="Payments\nAPI\r\nX-Injected: 1"
    )
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        message = await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
        )

    assert message.email_sent is True
    assert "\n" not in str(outbox[0]["Subject"]) and "\r" not in str(outbox[0]["Subject"])
    assert outbox[0]["Bcc"] is None and outbox[0]["X-Injected"] is None


async def test_the_author_cannot_write_to_themselves(db_session):
    author = await make_user(db_session, email="author@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    with pytest.raises(AuthorContactError) as exc_info:
        await send_author_message(
            db_session, sender=author, author_user_id=author.id, body="Hi", document=doc, settings=author_settings()
        )

    assert exc_info.value.code == "own_target"
    assert (
        await db_session.scalar(
            select(func.count()).select_from(AuthorMessage).where(AuthorMessage.sender_user_id == author.id)
        )
        == 0
    )


async def test_hourly_limit_refuses_the_next_message_and_stores_nothing(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)
    settings = author_settings(author_message_max_per_hour=2)

    for _ in range(2):
        await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
        )
    with pytest.raises(AuthorContactError) as exc_info:
        await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Hi again", document=doc, settings=settings
        )

    assert exc_info.value.code == "rate_limited"
    stored = await db_session.scalar(
        select(func.count()).select_from(AuthorMessage).where(AuthorMessage.sender_user_id == sender.id)
    )
    assert stored == 2


async def test_messages_older_than_an_hour_do_not_count(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)
    settings = author_settings(author_message_max_per_hour=1)
    first = await send_author_message(
        db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
    )
    stored = await db_session.get(AuthorMessage, first.id)
    stored.created_at = (await db_session.scalar(select(func.now()))) - timedelta(hours=1, minutes=1)
    await db_session.flush()

    await send_author_message(
        db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
    )  # must not raise


async def test_limit_of_zero_turns_it_off(db_session):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)
    settings = author_settings(author_message_max_per_hour=0)

    for _ in range(3):
        await send_author_message(
            db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
        )  # must not raise


async def test_exactly_one_target_is_required(db_session):
    author = await make_user(db_session)
    sender = await make_user(db_session)
    team = await make_team(db_session)
    doc = await make_document(db_session, team, author)
    collection = await make_collection(db_session, team, author)

    for kwargs in ({}, {"document": doc, "collection": collection}):
        with pytest.raises(ValueError):
            await send_author_message(
                db_session, sender=sender, author_user_id=author.id, body="Hi", settings=author_settings(), **kwargs
            )


async def test_author_info_reports_a_switched_off_author(db_session):
    author = await make_user(db_session, accept_author_messages=False)
    team = await make_team(db_session)

    info = await get_author_info(db_session, created_by_user_id=author.id, team_id=team.id)

    assert info.accepts_messages is False


async def test_author_who_switched_messages_off_gets_nothing(db_session):
    author = await make_user(db_session, email="author@example.com", accept_author_messages=False)
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        with pytest.raises(AuthorContactError) as exc_info:
            await send_author_message(
                db_session, sender=sender, author_user_id=author.id, body="Hi", document=doc, settings=settings
            )

    assert exc_info.value.code == "not_accepting"
    assert outbox == []
    assert (
        await db_session.scalar(
            select(func.count()).select_from(AuthorMessage).where(AuthorMessage.sender_user_id == sender.id)
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == author.id)
        )
        == 0
    )
