# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for contacting the author through the API: the `author` block of the
document and collection details (a name and a team, never an address), POST
.../contact-author on both (who may write, what is stored and mailed, the
refusals), GET /api/author-messages (the author's own inbox), and how the
messages appear in /api/notifications without ever reaching the per-document
version banner.

Same ASGITransport + dependency_overrides[get_db] + db_session +
make_access_token() pattern as test_notifications_router.py. socket.getfqdn
is stubbed, see test_author_contact_service.py."""

import socket
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses

import httpx
import pytest
from fastapi_mail import FastMail
from sqlalchemy import func, select

import app.security.jwt as jwt_module
from app.config import get_settings
from app.models.api_document import ApiDocumentVersion
from app.models.author_message import AuthorMessage
from app.models.notification import Notification
from app.services.email import _connection_config
from tests.author_contact_support import (
    author_settings,
    make_collection,
    make_document,
    make_team,
    make_user,
)


@pytest.fixture(autouse=True)
def _signed_in(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    monkeypatch.setattr(socket, "getfqdn", lambda *args, **kwargs: "localhost")


async def _request(db_session, method: str, path: str, *, token: str | None = None, settings=None, **kwargs):
    from app.database import get_db
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    fastapi_app.dependency_overrides[get_settings] = lambda: settings or author_settings()
    headers = kwargs.pop("headers", {}) or {}
    if token is not None:
        headers = {**headers, "Authorization": f"Bearer {token}"}
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, path, headers=headers, **kwargs)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        fastapi_app.dependency_overrides.pop(get_settings, None)


def _token(make_access_token, user) -> str:
    """A token that agrees with the user row, so resolving it changes
    neither the cached e-mail nor the cached login."""
    return make_access_token(sub=str(user.auth_sub), email=user.email, login=user.login)


async def _count_messages(db_session, sender) -> int:
    return await db_session.scalar(
        select(func.count()).select_from(AuthorMessage).where(AuthorMessage.sender_user_id == sender.id)
    )


# --- the author block of the details ------------------------------------------------


async def test_document_detail_shows_name_and_team_but_never_the_address(db_session, make_access_token):
    author = await make_user(db_session, email="secret-author@example.com", nickname="Ada", login="ada1")
    team = await make_team(db_session, name="Core Platform")
    doc = await make_document(db_session, team, author)

    response = await _request(db_session, "GET", f"/api/api-docs/{doc.id}")  # anonymous, public

    assert response.status_code == 200
    assert response.json()["author"] == {
        "display_name": "Ada",
        "team_name": "Core Platform",
        "accepts_messages": True,
        "is_self": False,
    }
    assert "secret-author@example.com" not in response.text


async def test_document_detail_falls_back_to_login_then_to_no_name(db_session):
    team = await make_team(db_session)
    with_login = await make_user(db_session, login="ada1")
    without_name = await make_user(db_session, email="x@example.com")
    doc_a = await make_document(db_session, team, with_login)
    doc_b = await make_document(db_session, team, without_name)

    a = await _request(db_session, "GET", f"/api/api-docs/{doc_a.id}")
    b = await _request(db_session, "GET", f"/api/api-docs/{doc_b.id}")

    assert a.json()["author"]["display_name"] == "ada1"
    assert b.json()["author"]["display_name"] is None


async def test_is_self_is_true_only_for_the_author(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com", nickname="Ada")
    other = await make_user(db_session, email="other@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    as_author = await _request(db_session, "GET", f"/api/api-docs/{doc.id}", token=_token(make_access_token, author))
    as_other = await _request(db_session, "GET", f"/api/api-docs/{doc.id}", token=_token(make_access_token, other))

    assert as_author.json()["author"]["is_self"] is True
    assert as_other.json()["author"]["is_self"] is False


async def test_collection_detail_has_the_author_block_too(db_session, make_access_token):
    author = await make_user(db_session, email="secret-author@example.com", nickname="Ada")
    collection = await make_collection(db_session, await make_team(db_session, name="Billing"), author)

    response = await _request(db_session, "GET", f"/api/collections/{collection.id}")

    assert response.status_code == 200
    assert response.json()["author"] == {
        "display_name": "Ada",
        "team_name": "Billing",
        "accepts_messages": True,
        "is_self": False,
    }
    assert "secret-author@example.com" not in response.text


# --- POST /api/api-docs/{id}/contact-author -----------------------------------------


async def test_contact_requires_signing_in(db_session):
    author = await make_user(db_session, email="author@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    response = await _request(db_session, "POST", f"/api/api-docs/{doc.id}/contact-author", json={"message": "Hi"})

    assert response.status_code in (401, 403)


async def test_signed_in_user_writes_to_the_author_of_a_public_document(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com", nickname="Ada")
    sender = await make_user(db_session, email="sender@example.com", nickname="Sam")
    doc = await make_document(db_session, await make_team(db_session), author, title="Payments API")
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        response = await _request(
            db_session,
            "POST",
            f"/api/api-docs/{doc.id}/contact-author",
            token=_token(make_access_token, sender),
            json={"message": "  Is v2 coming?  "},
            settings=settings,
        )

    assert response.status_code == 201
    assert response.json()["email_sent"] is True
    stored = (
        await db_session.execute(select(AuthorMessage).where(AuthorMessage.sender_user_id == sender.id))
    ).scalar_one()
    assert str(stored.id) == response.json()["id"]
    assert (stored.recipient_user_id, stored.documentation_id, stored.body) == (author.id, doc.id, "Is v2 coming?")
    notification = (
        await db_session.execute(select(Notification).where(Notification.message_id == stored.id))
    ).scalar_one()
    assert (notification.user_id, notification.kind, notification.is_read) == (author.id, "author_message", False)
    assert [addr for _, addr in getaddresses([str(outbox[0]["To"])])] == ["author@example.com"]
    assert [addr for _, addr in getaddresses([str(outbox[0]["Reply-To"])])] == ["sender@example.com"]


async def test_team_member_may_write_about_a_private_document(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    colleague = await make_user(db_session, email="colleague@example.com")
    team = await make_team(db_session, members=(author, colleague))
    doc = await make_document(db_session, team, author, is_public=False)

    response = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/contact-author",
        token=_token(make_access_token, colleague),
        json={"message": "Hi"},
    )

    assert response.status_code == 201


async def test_private_document_is_404_for_an_outsider_and_nothing_is_stored(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    outsider = await make_user(db_session, email="outsider@example.com")
    doc = await make_document(db_session, await make_team(db_session), author, is_public=False)

    response = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/contact-author",
        token=_token(make_access_token, outsider),
        json={"message": "Hi"},
    )

    assert response.status_code == 404
    assert await _count_messages(db_session, outsider) == 0


async def test_unknown_document_is_404(db_session, make_access_token):
    sender = await make_user(db_session, email="sender@example.com")

    response = await _request(
        db_session,
        "POST",
        "/api/api-docs/00000000-0000-0000-0000-000000000001/contact-author",
        token=_token(make_access_token, sender),
        json={"message": "Hi"},
    )

    assert response.status_code == 404


async def test_the_author_cannot_write_to_themselves(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    response = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/contact-author",
        token=_token(make_access_token, author),
        json={"message": "Hi"},
    )

    assert response.status_code == 422
    assert await _count_messages(db_session, author) == 0


@pytest.mark.parametrize("message", ["", "   \n ", "x" * 2001])
async def test_blank_or_too_long_message_is_422(db_session, make_access_token, message):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    response = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/contact-author",
        token=_token(make_access_token, sender),
        json={"message": message},
    )

    assert response.status_code == 422
    assert await _count_messages(db_session, sender) == 0


async def test_message_of_exactly_the_maximum_length_is_accepted(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    response = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/contact-author",
        token=_token(make_access_token, sender),
        json={"message": "x" * 2000},
    )

    assert response.status_code == 201


async def test_the_hourly_limit_answers_429(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)
    settings = author_settings(author_message_max_per_hour=1)
    token = _token(make_access_token, sender)
    path = f"/api/api-docs/{doc.id}/contact-author"

    first = await _request(db_session, "POST", path, token=token, json={"message": "Hi"}, settings=settings)
    second = await _request(db_session, "POST", path, token=token, json={"message": "Hi"}, settings=settings)

    assert (first.status_code, second.status_code) == (201, 429)
    assert await _count_messages(db_session, sender) == 1


async def test_author_without_an_address_gets_it_in_the_app_only(db_session, make_access_token):
    author = await make_user(db_session, email=None)
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)

    response = await _request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/contact-author",
        token=_token(make_access_token, sender),
        json={"message": "Hi"},
    )

    assert response.status_code == 201
    assert response.json()["email_sent"] is False


# --- POST /api/collections/{id}/contact-author --------------------------------------


async def test_signed_in_user_writes_to_the_author_of_a_public_collection(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    collection = await make_collection(db_session, await make_team(db_session), author)

    response = await _request(
        db_session,
        "POST",
        f"/api/collections/{collection.id}/contact-author",
        token=_token(make_access_token, sender),
        json={"message": "Hi"},
    )

    assert response.status_code == 201
    stored = (
        await db_session.execute(select(AuthorMessage).where(AuthorMessage.sender_user_id == sender.id))
    ).scalar_one()
    assert (stored.recipient_user_id, stored.documentation_id, stored.collection_id) == (
        author.id,
        None,
        collection.id,
    )


async def test_private_collection_is_404_for_an_outsider(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    outsider = await make_user(db_session, email="outsider@example.com")
    collection = await make_collection(db_session, await make_team(db_session), author, is_public=False)

    response = await _request(
        db_session,
        "POST",
        f"/api/collections/{collection.id}/contact-author",
        token=_token(make_access_token, outsider),
        json={"message": "Hi"},
    )

    assert response.status_code == 404
    assert await _count_messages(db_session, outsider) == 0


async def test_collection_author_cannot_write_to_themselves(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com")
    collection = await make_collection(db_session, await make_team(db_session), author)

    response = await _request(
        db_session,
        "POST",
        f"/api/collections/{collection.id}/contact-author",
        token=_token(make_access_token, author),
        json={"message": "Hi"},
    )

    assert response.status_code == 422


# --- GET /api/author-messages -------------------------------------------------------


async def _store(db_session, sender, recipient, *, doc=None, collection=None, body="Hi", minutes_ago=0):
    message = AuthorMessage(
        sender_user_id=sender.id,
        recipient_user_id=recipient.id,
        documentation_id=doc.id if doc else None,
        collection_id=collection.id if collection else None,
        body=body,
    )
    db_session.add(message)
    await db_session.flush()
    message.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    await db_session.flush()
    return message


async def test_inbox_requires_signing_in(db_session):
    response = await _request(db_session, "GET", "/api/author-messages")

    assert response.status_code in (401, 403)


async def test_inbox_lists_only_my_messages_newest_first(db_session, make_access_token):
    me = await make_user(db_session, email="me@example.com", nickname="Me")
    sender = await make_user(db_session, email="sender@example.com", nickname="Sam")
    someone_else = await make_user(db_session, email="else@example.com")
    team = await make_team(db_session)
    doc = await make_document(db_session, team, me, title="Payments API")
    collection = await make_collection(db_session, team, me, name="Billing APIs")
    await _store(db_session, sender, me, doc=doc, body="older", minutes_ago=10)
    await _store(db_session, sender, me, collection=collection, body="newer", minutes_ago=1)
    await _store(db_session, sender, someone_else, doc=doc, body="not mine", minutes_ago=5)

    response = await _request(db_session, "GET", "/api/author-messages", token=_token(make_access_token, me))

    assert response.status_code == 200
    items = response.json()
    assert [item["body"] for item in items] == ["newer", "older"]
    assert items[0]["target"] == {"kind": "collection", "id": str(collection.id), "title": "Billing APIs"}
    assert items[1]["target"] == {"kind": "document", "id": str(doc.id), "title": "Payments API"}
    assert (items[0]["sender_name"], items[0]["sender_email"]) == ("Sam", "sender@example.com")


async def test_inbox_paginates(db_session, make_access_token):
    me = await make_user(db_session, email="me@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), me)
    for minutes in (3, 2, 1):
        await _store(db_session, sender, me, doc=doc, body=f"m{minutes}", minutes_ago=minutes)

    response = await _request(
        db_session, "GET", "/api/author-messages?limit=1&offset=1", token=_token(make_access_token, me)
    )

    assert [item["body"] for item in response.json()] == ["m2"]


# --- /api/notifications ------------------------------------------------------------


async def test_bell_shows_the_message_and_counts_it_unread(db_session, make_access_token):
    me = await make_user(db_session, email="me@example.com")
    sender = await make_user(db_session, email="sender@example.com", nickname="Sam")
    doc = await make_document(db_session, await make_team(db_session), me, title="Payments API")
    message = await _store(db_session, sender, me, doc=doc, body="Is v2\ncoming?")
    db_session.add(Notification(kind="author_message", user_id=me.id, message_id=message.id))
    await db_session.flush()

    response = await _request(db_session, "GET", "/api/notifications", token=_token(make_access_token, me))

    assert response.status_code == 200
    data = response.json()
    assert data["unread_count"] == 1
    (item,) = data["items"]
    assert item["kind"] == "author_message"
    assert (item["documentation_id"], item["document_title"], item["version"]) == (None, None, None)
    assert item["message"] == {
        "id": str(message.id),
        "sender_name": "Sam",
        "target_kind": "document",
        "target_id": str(doc.id),
        "target_title": "Payments API",
        "preview": "Is v2 coming?",
    }


async def test_version_banner_query_never_sees_messages(db_session, make_access_token):
    """The per-document banner asks for documentation_id + unread: a message
    about that very document must not turn up there, nor in its count."""
    me = await make_user(db_session, email="me@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), me)
    version = ApiDocumentVersion(
        documentation_id=doc.id, version="1.0.0", format="json", storage_path="x/y.json", checksum="c", source="initial"
    )
    db_session.add(version)
    await db_session.flush()
    db_session.add(Notification(user_id=me.id, documentation_id=doc.id, version_id=version.id))
    message = await _store(db_session, sender, me, doc=doc)
    db_session.add(Notification(kind="author_message", user_id=me.id, message_id=message.id))
    await db_session.flush()

    scoped = await _request(
        db_session,
        "GET",
        f"/api/notifications?documentation_id={doc.id}&unread=true",
        token=_token(make_access_token, me),
    )
    everything = await _request(db_session, "GET", "/api/notifications", token=_token(make_access_token, me))

    assert [item["kind"] for item in scoped.json()["items"]] == ["new_version"]
    assert scoped.json()["unread_count"] == 1
    assert everything.json()["unread_count"] == 2


async def test_opening_the_bell_marks_message_notifications_read(db_session, make_access_token):
    me = await make_user(db_session, email="me@example.com")
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), me)
    message = await _store(db_session, sender, me, doc=doc)
    notification = Notification(kind="author_message", user_id=me.id, message_id=message.id)
    db_session.add(notification)
    await db_session.flush()
    token = _token(make_access_token, me)

    read_all = await _request(db_session, "POST", "/api/notifications/read-all", token=token)
    after = await _request(db_session, "GET", "/api/notifications", token=token)

    assert read_all.status_code == 204
    assert after.json()["unread_count"] == 0
    assert after.json()["items"][0]["is_read"] is True


# --- an author who has switched messages off ----------------------------------------


async def test_detail_says_when_the_author_does_not_accept_messages(db_session):
    author = await make_user(db_session, email="author@example.com", nickname="Ada", accept_author_messages=False)
    team = await make_team(db_session)
    doc = await make_document(db_session, team, author)
    collection = await make_collection(db_session, team, author)

    doc_detail = await _request(db_session, "GET", f"/api/api-docs/{doc.id}")
    collection_detail = await _request(db_session, "GET", f"/api/collections/{collection.id}")

    assert doc_detail.json()["author"]["accepts_messages"] is False
    assert collection_detail.json()["author"]["accepts_messages"] is False
    assert doc_detail.json()["author"]["display_name"] == "Ada"  # still shown, only contact is off


@pytest.mark.parametrize("target", ["api-docs", "collections"])
async def test_contact_is_refused_with_403_and_leaves_nothing_behind(db_session, make_access_token, target):
    author = await make_user(db_session, email="author@example.com", accept_author_messages=False)
    sender = await make_user(db_session, email="sender@example.com")
    team = await make_team(db_session)
    item = (
        await make_document(db_session, team, author)
        if target == "api-docs"
        else await make_collection(db_session, team, author)
    )
    settings = author_settings()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        response = await _request(
            db_session,
            "POST",
            f"/api/{target}/{item.id}/contact-author",
            token=_token(make_access_token, sender),
            json={"message": "Hi"},
            settings=settings,
        )

    assert response.status_code == 403
    assert outbox == []
    assert await _count_messages(db_session, sender) == 0
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == author.id)
        )
        == 0
    )


async def test_switching_messages_back_on_makes_contact_work_again(db_session, make_access_token):
    author = await make_user(db_session, email="author@example.com", accept_author_messages=False)
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), author)
    token = _token(make_access_token, sender)
    path = f"/api/api-docs/{doc.id}/contact-author"

    refused = await _request(db_session, "POST", path, token=token, json={"message": "Hi"})
    author.accept_author_messages = True
    await db_session.flush()
    accepted = await _request(db_session, "POST", path, token=token, json={"message": "Hi"})

    assert (refused.status_code, accepted.status_code) == (403, 201)


async def test_messages_received_earlier_stay_readable_after_switching_off(db_session, make_access_token):
    me = await make_user(db_session, email="me@example.com", accept_author_messages=False)
    sender = await make_user(db_session, email="sender@example.com")
    doc = await make_document(db_session, await make_team(db_session), me)
    await _store(db_session, sender, me, doc=doc, body="from before")

    response = await _request(db_session, "GET", "/api/author-messages", token=_token(make_access_token, me))

    assert [item["body"] for item in response.json()] == ["from before"]
