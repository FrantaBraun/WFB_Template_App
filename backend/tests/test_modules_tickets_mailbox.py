# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.modules.tickets.mailbox: one polling cycle (against a fake
mailbox, filing into db_session's rolled-back transaction), the IMAP
connection (against a fake imaplib) and the background loop."""

import asyncio
import imaplib
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.modules.crm.models import Partner
from app.modules.tickets import mailbox, service
from app.modules.tickets.models import Ticket, TicketEntry
from tests.tickets_support import PDF, make_mail, tickets_settings


@pytest.fixture(autouse=True)
async def _clean(db_session, monkeypatch):
    await db_session.execute(delete(Ticket))
    await db_session.execute(delete(Partner))
    # The poll lock ends with a rollback of this (shared) session; without a
    # commit - which here only ends a savepoint of the test's own transaction -
    # that rollback would undo the deletes above whenever a test files no mail.
    await db_session.commit()
    monkeypatch.setattr(service, "crm_enabled", lambda: False)
    mailbox._attempts.clear()
    mailbox.status.__init__()
    yield
    mailbox._attempts.clear()
    mailbox.status.__init__()


@pytest.fixture()
def settings(tmp_path):
    return tickets_settings(tmp_path)


@pytest.fixture()
def session_factory(db_session):
    @asynccontextmanager
    async def factory():
        yield db_session

    return factory


class FakeMailbox:
    """The ImapMailbox interface over a dict of uid -> raw message."""

    folder = "INBOX"

    def __init__(self, messages: dict[bytes, bytes | None]):
        self.messages = messages
        self.seen: list[bytes] = []
        self.failed: list[bytes] = []
        self.opened = self.closed = False
        self.open_error: Exception | None = None

    async def open(self):
        if self.open_error:
            raise self.open_error
        self.opened = True

    async def unseen(self):
        return [uid for uid in self.messages if uid not in self.seen and uid not in self.failed]

    async def fetch(self, uid):
        return self.messages[uid]

    async def mark_seen(self, uid):
        self.seen.append(uid)

    async def mark_failed(self, uid):
        self.failed.append(uid)

    async def close(self):
        self.closed = True


async def _count(db, model) -> int:
    return await db.scalar(select(func.count(model.id)))


async def test_unread_mail_is_filed_and_marked_read(db_session, settings, session_factory):
    box = FakeMailbox({b"1": make_mail(subject="První", message_id="<1@x>"), b"2": make_mail(subject="Druhý", message_id="<2@x>")})

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert (result.fetched, result.created, result.attached, result.failed) == (2, 2, 0, 0)
    assert box.seen == [b"1", b"2"] and box.failed == []
    assert box.opened and box.closed
    assert await _count(db_session, Ticket) == 2


async def test_a_reply_is_attached_and_counted_as_such(db_session, settings, session_factory):
    first = await mailbox.poll_once(settings, mailbox=FakeMailbox({b"1": make_mail(message_id="<1@x>")}), session_factory=session_factory)
    ticket = await db_session.scalar(select(Ticket))

    result = await mailbox.poll_once(
        settings,
        mailbox=FakeMailbox({b"2": make_mail(subject=f"Re: [Ticket#{ticket.number}] - Dotaz", message_id="<2@x>")}),
        session_factory=session_factory,
    )

    assert (first.created, result.created, result.attached) == (1, 0, 1)
    assert await _count(db_session, Ticket) == 1 and await _count(db_session, TicketEntry) == 2


async def test_mail_that_was_filed_before_is_only_marked_read(db_session, settings, session_factory):
    mail = make_mail(message_id="<same@x>")
    await mailbox.poll_once(settings, mailbox=FakeMailbox({b"1": mail}), session_factory=session_factory)
    box = FakeMailbox({b"9": mail})

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert (result.skipped, result.created) == (1, 0)
    assert box.seen == [b"9"]
    assert await _count(db_session, TicketEntry) == 1


async def test_a_mail_that_cannot_be_filed_stays_unread_and_the_others_go_through(db_session, settings, session_factory, monkeypatch):
    original = service.import_message

    async def picky(db, mail, settings):
        if mail.subject == "Špatný":
            raise RuntimeError("boom")
        return await original(db, mail, settings)

    monkeypatch.setattr(service, "import_message", picky)
    box = FakeMailbox({b"1": make_mail(subject="Špatný", message_id="<1@x>"), b"2": make_mail(subject="Dobrý", message_id="<2@x>")})

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert (result.created, result.failed) == (1, 1)
    assert box.seen == [b"2"] and box.failed == []
    assert [t.subject for t in (await db_session.scalars(select(Ticket))).all()] == ["Dobrý"]


async def test_a_mail_that_keeps_failing_is_flagged_and_given_up_on(db_session, settings, session_factory, monkeypatch):
    async def broken(db, mail, settings):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "import_message", broken)
    box = FakeMailbox({b"1": make_mail(message_id="<1@x>")})

    for _ in range(mailbox.MAX_ATTEMPTS - 1):
        await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)
    assert box.failed == []

    await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert box.failed == [b"1"] and box.seen == []
    assert mailbox._attempts == {}


async def test_the_files_of_a_commit_that_fails_are_removed(db_session, settings, session_factory, monkeypatch):
    box = FakeMailbox({b"1": make_mail(attachments=[("a.pdf", "application/pdf", PDF)], message_id="<1@x>")})
    real_commit = db_session.commit
    calls = {"n": 0}

    async def commit_fails_once():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("commit failed")
        await real_commit()

    monkeypatch.setattr(db_session, "commit", commit_fails_once)

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert result.failed == 1 and box.seen == []
    assert not list(Path(settings.uploads_dir, "tickets").glob("*"))


async def test_an_oversized_mail_is_flagged_without_being_parsed(db_session, settings, session_factory, monkeypatch):
    monkeypatch.setattr(mailbox, "MAX_RAW_BYTES", 10)
    box = FakeMailbox({b"1": make_mail()})

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert (result.failed, box.failed, box.seen) == (1, [b"1"], [])
    assert await _count(db_session, Ticket) == 0


async def test_a_mail_that_cannot_be_fetched_is_left_alone(db_session, settings, session_factory):
    box = FakeMailbox({b"1": None})

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert (result.fetched, result.failed) == (0, 0)
    assert box.seen == [] and box.failed == []


async def test_only_a_limited_number_of_mails_is_taken_per_cycle(db_session, settings, session_factory, monkeypatch):
    monkeypatch.setattr(mailbox, "MAX_PER_CYCLE", 2)
    box = FakeMailbox({str(i).encode(): make_mail(subject=f"T{i}", message_id=f"<{i}@x>") for i in range(5)})

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert result.created == 2 and len(box.seen) == 2


async def test_no_mailbox_configured_means_nothing_happens(db_session, tmp_path, session_factory):
    box = FakeMailbox({b"1": make_mail()})

    result = await mailbox.poll_once(tickets_settings(tmp_path, tickets_imap_host=""), mailbox=box, session_factory=session_factory)

    assert result.fetched == 0 and not box.opened


async def test_a_mailbox_that_cannot_be_opened_is_reported(db_session, settings, session_factory):
    box = FakeMailbox({})
    box.open_error = imaplib.IMAP4.error("LOGIN failed")

    with pytest.raises(imaplib.IMAP4.error):
        await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert "LOGIN failed" in mailbox.status.last_error
    assert mailbox.status.last_checked_at is not None and mailbox.status.checking is False


async def test_a_successful_cycle_clears_the_error_and_keeps_the_result(db_session, settings, session_factory):
    mailbox.status.last_error = "old"

    await mailbox.poll_once(settings, mailbox=FakeMailbox({b"1": make_mail(message_id="<1@x>")}), session_factory=session_factory)

    assert mailbox.status.last_error is None
    assert mailbox.status.last_result.created == 1


async def test_a_cycle_does_not_run_while_another_process_holds_the_lock(db_session, settings, session_factory, monkeypatch):
    @asynccontextmanager
    async def not_ours(factory):
        yield False

    monkeypatch.setattr(mailbox, "_poll_lock", not_ours)
    box = FakeMailbox({b"1": make_mail()})

    result = await mailbox.poll_once(settings, mailbox=box, session_factory=session_factory)

    assert result.fetched == 0 and not box.opened


# --- The IMAP connection --------------------------------------------------------


class FakeImap:
    instances: list["FakeImap"] = []
    error = imaplib.IMAP4.error  # the tests swap imaplib.IMAP4 for this class; the exception stays real

    def __init__(self, host, port, **kwargs):
        self.host, self.port, self.kwargs = host, port, kwargs
        self.capabilities = ("IMAP4REV1", "STARTTLS")
        self.calls: list[tuple] = []
        self.search_result = b"3 4"
        FakeImap.instances.append(self)

    def starttls(self, context):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def select(self, folder):
        self.calls.append(("select", folder))
        return ("OK", [b"2"])

    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            return ("OK", [self.search_result])
        if command == "FETCH":
            return ("OK", [(b"3 (UID 3 BODY[] {5}", b"RAW!!"), b")"])
        return ("OK", [None])

    def logout(self):
        self.calls.append(("logout",))


@pytest.fixture()
def fake_imap(monkeypatch):
    FakeImap.instances = []
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeImap)
    monkeypatch.setattr(imaplib, "IMAP4", FakeImap)
    return FakeImap


async def test_the_connection_logs_in_selects_the_folder_and_reads_unseen_mail(fake_imap, tmp_path):
    settings = tickets_settings(tmp_path, tickets_imap_folder="Support", tickets_imap_port=1993)
    box = mailbox.ImapMailbox(settings)

    await box.open()
    uids = await box.unseen()
    raw = await box.fetch(b"3")
    await box.mark_seen(b"3")
    await box.mark_failed(b"4")
    await box.close()

    [connection] = fake_imap.instances
    assert (connection.host, connection.port) == ("imap.example.com", 1993)
    assert connection.kwargs["timeout"] == mailbox.IMAP_TIMEOUT_SECONDS
    assert ("login", "tickets@example.com", "imap-secret") in connection.calls
    assert ("select", '"Support"') in connection.calls
    assert uids == [b"3", b"4"] and raw == b"RAW!!"
    assert ("uid", "FETCH", b"3", "(BODY.PEEK[])") in connection.calls
    assert ("uid", "STORE", b"3", "+FLAGS", r"(\Seen)") in connection.calls
    assert ("uid", "STORE", b"4", "+FLAGS", r"(\Seen \Flagged)") in connection.calls
    assert connection.calls[-1] == ("logout",)
    assert "starttls" not in [c[0] for c in connection.calls]


async def test_an_empty_search_means_no_mail(fake_imap, tmp_path):
    box = mailbox.ImapMailbox(tickets_settings(tmp_path))
    await box.open()
    fake_imap.instances[0].search_result = b""

    assert await box.unseen() == []


async def test_without_ssl_the_connection_is_upgraded_with_starttls(fake_imap, tmp_path):
    box = mailbox.ImapMailbox(tickets_settings(tmp_path, tickets_imap_ssl=False, tickets_imap_port=143))

    await box.open()

    calls = [c[0] for c in fake_imap.instances[0].calls]
    assert calls.index("starttls") < calls.index("login")


async def test_a_folder_that_cannot_be_selected_is_an_error(fake_imap, tmp_path, monkeypatch):
    monkeypatch.setattr(FakeImap, "select", lambda self, folder: ("NO", [b"nope"]))
    box = mailbox.ImapMailbox(tickets_settings(tmp_path))

    with pytest.raises(imaplib.IMAP4.error):
        await box.open()


async def test_closing_a_connection_that_never_opened_is_harmless(tmp_path):
    await mailbox.ImapMailbox(tickets_settings(tmp_path)).close()


# --- The background task ------------------------------------------------------------


async def test_the_poller_ends_at_once_without_a_mailbox_or_with_interval_zero(tmp_path, monkeypatch, caplog):
    async def never(*args, **kwargs):
        raise AssertionError("must not poll")

    monkeypatch.setattr(mailbox, "poll_once", never)
    for overrides in ({"tickets_imap_host": ""}, {"tickets_poll_seconds": 0}):
        monkeypatch.setattr(mailbox, "get_settings", lambda o=overrides: tickets_settings(tmp_path, **o))

        await asyncio.wait_for(mailbox.mailbox_poller(), timeout=1)


async def test_the_poller_keeps_going_after_a_failed_check(tmp_path, monkeypatch):
    settings = tickets_settings(tmp_path, tickets_poll_seconds=30)
    monkeypatch.setattr(mailbox, "get_settings", lambda: settings)
    polls, sleeps = [], []

    async def poll(settings):
        polls.append(1)
        if len(polls) == 1:
            raise RuntimeError("down")

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(mailbox, "poll_once", poll)
    monkeypatch.setattr(mailbox.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await mailbox.mailbox_poller()

    assert len(polls) == 3 and sleeps == [30, 30, 30]


async def test_the_poll_interval_has_a_floor(tmp_path, monkeypatch):
    monkeypatch.setattr(mailbox, "get_settings", lambda: tickets_settings(tmp_path, tickets_poll_seconds=1))
    sleeps = []

    async def poll(settings):
        return None

    async def sleep(seconds):
        sleeps.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(mailbox, "poll_once", poll)
    monkeypatch.setattr(mailbox.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await mailbox.mailbox_poller()

    assert sleeps == [mailbox.MIN_POLL_SECONDS]
