# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Reading the ticket mailbox: an IMAP connection (standard library, blocking
calls moved to a thread), one polling cycle that files every unread mail
through service.import_message, and the background task that repeats it.

Design points worth knowing:

- Mail is fetched with BODY.PEEK and marked \\Seen only after it was filed, so
  a crash between the two files it again next time - which is harmless, the
  Message-ID of a filed mail is unique.
- A mail that cannot be filed is left unread and tried again next cycle, up
  to MAX_ATTEMPTS times; then it is marked read and flagged for a human to
  look at, so one bad mail never makes every cycle fail.
- Only one process polls at a time (a transaction-scoped Postgres advisory
  lock held for the cycle), so several workers never file the same mail twice.
- Nothing here ever deletes mail from the mailbox.
"""

import asyncio
import imaplib
import logging
import ssl
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import AsyncSessionLocal
from app.modules.tickets import service, storage
from app.modules.tickets.mailparse import parse_message

logger = logging.getLogger(__name__)

MAX_PER_CYCLE = 50
MAX_ATTEMPTS = 5
MAX_RAW_BYTES = 25 * 1024 * 1024
MIN_POLL_SECONDS = 10
IMAP_TIMEOUT_SECONDS = 30
# Arbitrary, fixed key of the advisory lock that makes one process poll at a time.
POLL_LOCK_KEY = 7_412_390_001


def mailbox_configured(settings: Settings) -> bool:
    return bool(settings.tickets_imap_host.strip())


@dataclass
class PollResult:
    fetched: int = 0
    created: int = 0
    attached: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class MailboxStatus:
    """What the administrators' page shows about the mailbox. Per process:
    with several workers each has its own view of its own last check."""

    last_checked_at: datetime | None = None
    last_error: str | None = None
    last_result: PollResult | None = None
    checking: bool = False


status = MailboxStatus()
# (folder, uid) -> how many times filing that mail failed; cleared on success.
_attempts: dict[tuple[str, bytes], int] = {}


class ImapMailbox:
    """A connection to the configured mailbox. Every method is a coroutine
    (the blocking imaplib call runs in a thread), which is also the shape
    tests replace it with."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._connection: imaplib.IMAP4 | None = None

    @property
    def folder(self) -> str:
        return self.settings.tickets_imap_folder or "INBOX"

    def _open(self) -> None:
        s = self.settings
        if s.tickets_imap_ssl:
            connection: imaplib.IMAP4 = imaplib.IMAP4_SSL(
                s.tickets_imap_host, s.tickets_imap_port, ssl_context=ssl.create_default_context(), timeout=IMAP_TIMEOUT_SECONDS
            )
        else:
            connection = imaplib.IMAP4(s.tickets_imap_host, s.tickets_imap_port, timeout=IMAP_TIMEOUT_SECONDS)
            if "STARTTLS" in connection.capabilities:
                connection.starttls(ssl.create_default_context())
        connection.login(s.tickets_imap_username, s.tickets_imap_password)
        typ, _ = connection.select(f'"{self.folder}"')
        if typ != "OK":
            raise imaplib.IMAP4.error(f"Cannot open the mailbox folder {self.folder!r}")
        self._connection = connection

    def _unseen(self) -> list[bytes]:
        typ, data = self._connection.uid("SEARCH", None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return []
        return data[0].split()

    def _fetch(self, uid: bytes) -> bytes | None:
        typ, data = self._connection.uid("FETCH", uid, "(BODY.PEEK[])")
        if typ != "OK":
            return None
        for item in data or []:
            if isinstance(item, tuple):
                return item[1]
        return None

    def _flag(self, uid: bytes, flags: str) -> None:
        self._connection.uid("STORE", uid, "+FLAGS", f"({flags})")

    def _close(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.logout()
        except Exception:  # noqa: BLE001 - closing must never mask the real outcome
            pass
        self._connection = None

    async def open(self) -> None:
        await asyncio.to_thread(self._open)

    async def unseen(self) -> list[bytes]:
        return await asyncio.to_thread(self._unseen)

    async def fetch(self, uid: bytes) -> bytes | None:
        return await asyncio.to_thread(self._fetch, uid)

    async def mark_seen(self, uid: bytes) -> None:
        await asyncio.to_thread(self._flag, uid, r"\Seen")

    async def mark_failed(self, uid: bytes) -> None:
        await asyncio.to_thread(self._flag, uid, r"\Seen \Flagged")

    async def close(self) -> None:
        await asyncio.to_thread(self._close)


def _default_session() -> AbstractAsyncContextManager[AsyncSession]:
    return AsyncSessionLocal()


@asynccontextmanager
async def _poll_lock(session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]) -> AsyncIterator[bool]:
    """Yields whether this process got the right to poll. The lock lives as
    long as the transaction of the session opened here, i.e. until it is closed."""
    async with session_factory() as session:
        got = await session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": POLL_LOCK_KEY})
        try:
            yield bool(got)
        finally:
            await session.rollback()


async def poll_once(
    settings: Settings | None = None,
    *,
    mailbox: ImapMailbox | None = None,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
) -> PollResult:
    """One cycle: file every unread mail of the mailbox. Returns what happened
    (also kept in `status`); raises when the mailbox cannot be reached or
    opened - the cause is in `status.last_error` too."""
    settings = settings or get_settings()
    session_factory = session_factory or _default_session
    result = PollResult()
    if not mailbox_configured(settings):
        return result
    async with _poll_lock(session_factory) as got:
        if not got:
            logger.debug("Another process is checking the ticket mailbox")
            return result
        status.checking = True
        mailbox = mailbox or ImapMailbox(settings)
        try:
            await mailbox.open()
            try:
                for uid in (await mailbox.unseen())[:MAX_PER_CYCLE]:
                    await _file_one(uid, mailbox, settings, session_factory, result)
            finally:
                await mailbox.close()
            status.last_error = None
        except Exception as exc:
            status.last_error = f"{type(exc).__name__}: {exc}"[:500]
            raise
        finally:
            status.checking = False
            status.last_checked_at = datetime.now(timezone.utc)
            status.last_result = result
    return result


async def _file_one(
    uid: bytes,
    mailbox: ImapMailbox,
    settings: Settings,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    result: PollResult,
) -> None:
    key = (mailbox.folder, uid)
    raw = await mailbox.fetch(uid)
    if raw is None:
        return
    result.fetched += 1
    if len(raw) > MAX_RAW_BYTES:
        logger.warning("Ticket mailbox: mail %s is over the size limit - flagged and skipped", uid)
        await mailbox.mark_failed(uid)
        result.failed += 1
        return

    files: list[str] = []
    try:
        mail = parse_message(raw)
        async with session_factory() as db:
            outcome = await service.import_message(db, mail, settings)
            files = outcome.files
            try:
                await db.commit()
            except IntegrityError:
                # Another process filed the same mail between our check and our commit.
                await db.rollback()
                storage.delete_files(settings, files)
                outcome = service.ImportOutcome(skipped="already imported")
    except Exception:
        storage.delete_files(settings, files)
        attempts = _attempts.get(key, 0) + 1
        _attempts[key] = attempts
        result.failed += 1
        if attempts >= MAX_ATTEMPTS:
            logger.exception("Ticket mailbox: mail %s could not be filed %d times - flagged and given up", uid, attempts)
            _attempts.pop(key, None)
            await mailbox.mark_failed(uid)
        else:
            logger.exception("Ticket mailbox: mail %s could not be filed (attempt %d)", uid, attempts)
        return

    _attempts.pop(key, None)
    if outcome.skipped:
        result.skipped += 1
        logger.info("Ticket mailbox: mail %s skipped (%s)", uid, outcome.skipped)
    elif outcome.created:
        result.created += 1
    else:
        result.attached += 1
    await mailbox.mark_seen(uid)


async def mailbox_poller() -> None:
    """The module's background task (see ModuleManifest.background_tasks):
    check the mailbox every TICKETS_POLL_SECONDS for as long as the application
    runs. Returns at once when there is no mailbox or the interval is 0."""
    settings = get_settings()
    if not mailbox_configured(settings):
        logger.info("Tickets: no mailbox configured (TICKETS_IMAP_HOST) - mail is not read")
        return
    if settings.tickets_poll_seconds <= 0:
        logger.info("Tickets: TICKETS_POLL_SECONDS is 0 - the mailbox is only read on request")
        return
    interval = max(settings.tickets_poll_seconds, MIN_POLL_SECONDS)
    logger.info("Tickets: checking the mailbox every %d s", interval)
    while True:
        try:
            await poll_once(settings)
        except Exception:
            logger.exception("Tickets: checking the mailbox failed")
        await asyncio.sleep(interval)
