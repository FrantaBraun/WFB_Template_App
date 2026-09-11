# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.notifications.notify_new_version: recipient dedup
across team members and subscribers, the in-app-notification-without-email
case, the zero-recipients/zero-email skip of send_email, email content, and
- the most important case - that a notification failure never disturbs
process_new_spec's own success path.

Every test below that expects an email attempt passes mail_test_settings
explicitly (the same opt-in pattern test_teams_router.py already uses for
create_invitation) - see tests/conftest.py's MAIL_SUPPRESS_SEND note for why
that's still needed even though get_settings()'s own session-wide fallback
is also forced safe."""

import json
import uuid
from email.utils import getaddresses

from fastapi_mail import FastMail
from sqlalchemy import select

import app.services.notifications as notifications_module
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.notification import Notification, Subscription
from app.models.team import Team, TeamMembership
from app.models.user import User
from app.services.api_document_versions import process_new_spec
from app.services.email import _connection_config
from app.services.notifications import notify_new_version


def _spec_bytes(version: str, title: str = "Example API") -> bytes:
    return json.dumps({"openapi": "3.0.0", "info": {"title": title, "version": version}}).encode()


def _recipients(message) -> list[str]:
    """Bare email addresses from a message's To: header - fastapi_mail
    renders each as "local-part <address>", not just the bare address, so a
    naive comma-split isn't enough (unlike test_teams_router.py's simpler
    substring-only check, dedup here needs the exact address list)."""
    return [addr for _, addr in getaddresses([str(message["To"])])]


def _email_body(message) -> str:
    return message.get_payload()[0].get_payload(decode=True).decode()


async def _make_team(db_session, name: str = "Test Team") -> Team:
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    return team


async def _make_user(db_session, email: str | None = None) -> User:
    user = User(auth_sub=uuid.uuid4(), email=email)
    db_session.add(user)
    await db_session.flush()
    return user


async def _add_member(db_session, team: Team, user: User, role: str = "member") -> TeamMembership:
    membership = TeamMembership(team_id=team.id, user_id=user.id, role=role)
    db_session.add(membership)
    await db_session.flush()
    return membership


async def _add_subscription(db_session, user: User, doc: ApiDocument) -> Subscription:
    subscription = Subscription(user_id=user.id, documentation_id=doc.id)
    db_session.add(subscription)
    await db_session.flush()
    return subscription


async def _make_document(db_session, team: Team, creator: User, **overrides) -> ApiDocument:
    fields = dict(team_id=team.id, title="Example API", created_by_user_id=creator.id)
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


async def _notification_count(db_session, doc_id, version_id) -> int:
    result = await db_session.execute(
        select(Notification).where(
            Notification.documentation_id == doc_id, Notification.version_id == version_id
        )
    )
    return len(result.scalars().all())


# --- recipient computation / dedup --------------------------------------------------


async def test_recipient_dedup_team_member_and_subscriber_gets_one_notification_and_one_email(
    db_session, mail_test_settings
):
    team = await _make_team(db_session)
    dual_user = await _make_user(db_session, email="dual@example.com")
    await _add_member(db_session, team, dual_user)
    doc = await _make_document(db_session, team, dual_user)
    await _add_subscription(db_session, dual_user, doc)
    version = await _make_version(db_session, doc)

    mail = FastMail(_connection_config(mail_test_settings))
    with mail.record_messages() as outbox:
        await notify_new_version(doc, version, db_session, settings=mail_test_settings)

    assert await _notification_count(db_session, doc.id, version.id) == 1
    assert len(outbox) == 1
    assert _recipients(outbox[0]) == ["dual@example.com"]


async def test_member_without_email_gets_notification_row_but_not_emailed(db_session, mail_test_settings):
    team = await _make_team(db_session)
    creator = await _make_user(db_session, email="creator@example.com")
    no_email_member = await _make_user(db_session, email=None)
    await _add_member(db_session, team, creator)
    await _add_member(db_session, team, no_email_member)
    doc = await _make_document(db_session, team, creator)
    version = await _make_version(db_session, doc)

    mail = FastMail(_connection_config(mail_test_settings))
    with mail.record_messages() as outbox:
        await notify_new_version(doc, version, db_session, settings=mail_test_settings)

    # Both team members get an in-app row, including the one with no email -
    # only the email step itself excludes them.
    assert await _notification_count(db_session, doc.id, version.id) == 2
    assert len(outbox) == 1
    assert _recipients(outbox[0]) == ["creator@example.com"]


async def test_zero_recipients_skips_send_email_and_creates_no_notifications(
    db_session, mail_test_settings, monkeypatch
):
    team = await _make_team(db_session)
    creator = await _make_user(db_session, email="creator@example.com")
    doc = await _make_document(db_session, team, creator)  # no membership, no subscription rows at all
    version = await _make_version(db_session, doc)

    called = False

    async def _fake_send_email(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(notifications_module, "send_email", _fake_send_email)

    await notify_new_version(doc, version, db_session, settings=mail_test_settings)

    assert called is False
    assert await _notification_count(db_session, doc.id, version.id) == 0


# --- email content --------------------------------------------------------------------


async def test_email_content_includes_document_title_and_version(db_session, mail_test_settings):
    team = await _make_team(db_session)
    member = await _make_user(db_session, email="member@example.com")
    await _add_member(db_session, team, member)
    doc = await _make_document(db_session, team, member, title="Widgets API")
    version = await _make_version(db_session, doc, version="3.1.4")

    mail = FastMail(_connection_config(mail_test_settings))
    with mail.record_messages() as outbox:
        await notify_new_version(doc, version, db_session, settings=mail_test_settings)

    assert len(outbox) == 1
    subject = str(outbox[0]["Subject"])
    body = _email_body(outbox[0])
    assert "Widgets API" in subject
    assert "3.1.4" in subject
    assert "Widgets API" in body
    assert "3.1.4" in body


# --- integration with process_new_spec -------------------------------------------------


async def test_notify_failure_does_not_disturb_process_new_spec_success(db_session, tmp_path, monkeypatch):
    """The most important test in this file: process_new_spec (not
    notify_new_version directly) must still succeed and return the new
    version row even when the notification step's email send raises."""
    team = await _make_team(db_session)
    member = await _make_user(db_session, email="member@example.com")
    await _add_member(db_session, team, member)
    doc = await _make_document(db_session, team, member)

    async def _raise_send_email(*args, **kwargs):
        raise RuntimeError("simulated SMTP failure")

    monkeypatch.setattr(notifications_module, "send_email", _raise_send_email)

    result = await process_new_spec(
        doc,
        _spec_bytes("1.0.0"),
        source="initial",
        db=db_session,
        uploads_dir=str(tmp_path),
        max_size_bytes=10_000_000,
    )

    assert result is not None
    assert result.version == "1.0.0"
    await db_session.refresh(doc)
    # The notify failure is process_new_spec's own concern to never see -
    # last_check_error is reserved for the spec fetch/parse/storage failure
    # path (see api_document_versions.py), not a downstream notify failure.
    assert doc.last_check_error is None
    # The in-app row is still created - it's committed before the email step
    # that fails.
    assert await _notification_count(db_session, doc.id, result.id) == 1


async def test_process_new_spec_with_no_recipients_never_calls_send_email(db_session, tmp_path, monkeypatch):
    """Confirms the pre-existing test_api_document_versions_service.py tests
    are unaffected by process_new_spec's new notify_new_version call: their
    _make_document test helper never creates a TeamMembership row, so
    recipient_ids is always empty and send_email is never attempted -
    verified directly here rather than assumed."""
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    doc = await _make_document(db_session, team, creator)  # no membership, no subscription

    called = False

    async def _fake_send_email(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(notifications_module, "send_email", _fake_send_email)

    result = await process_new_spec(
        doc,
        _spec_bytes("1.0.0"),
        source="initial",
        db=db_session,
        uploads_dir=str(tmp_path),
        max_size_bytes=10_000_000,
    )

    assert result is not None
    assert called is False
