# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.scheduler: find_docs_due_for_recheck's
recheck_period x last_checked_at matrix (it lives in
app.services.api_document_versions, tested here since it's the scheduler's
own selection query), run_due_rechecks' per-document isolation, and
start_scheduler/shutdown_scheduler's lifecycle safety. Deliberately never
tests real-time scheduling (no short interval + sleep-and-poll) - only the
plain functions the scheduler's job wraps, called directly."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app.services.scheduler as scheduler_module
from app.config import Settings
from app.models.api_document import ApiDocument
from app.models.team import Team
from app.models.user import User
from app.services.api_document_versions import find_docs_due_for_recheck
from app.services.scheduler import run_due_rechecks, shutdown_scheduler, start_scheduler


@pytest.fixture(autouse=True)
def _reset_scheduler_singleton():
    """Mirrors conftest.py's _reset_public_key_cache for app.security.jwt:
    this file's own tests drive the module-level scheduler singleton
    directly, so reset it around every test rather than let one test's
    start leak into the next (or into another test module)."""
    scheduler_module._scheduler = None
    yield
    if scheduler_module._scheduler is not None:
        scheduler_module._scheduler.shutdown(wait=False)
    scheduler_module._scheduler = None


class _UseExistingSession:
    """Stands in for AsyncSessionLocal() in tests: hands run_due_rechecks
    the test's own db_session (so it reads/writes the same rolled-back
    transaction its fixture set up) instead of opening a real new
    connection, and - unlike a real AsyncSessionLocal() session - never
    closes it on exit, since db_session's own fixture owns that."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _make_document(db_session, **overrides) -> ApiDocument:
    team = Team(name="Test Team")
    db_session.add(team)
    await db_session.flush()
    user = User(auth_sub=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()

    fields = dict(team_id=team.id, title="Some API", created_by_user_id=user.id)
    fields.update(overrides)
    document = ApiDocument(**fields)
    db_session.add(document)
    await db_session.flush()
    return document


# --- find_docs_due_for_recheck -------------------------------------------------------


async def test_never_checked_is_due_immediately(db_session):
    doc = await _make_document(
        db_session,
        source_url="https://example.com/openapi.json",
        recheck_period="daily",
        last_checked_at=None,
    )

    due = await find_docs_due_for_recheck(db_session, datetime.now(timezone.utc))

    assert doc.id in {d.id for d in due}


async def test_daily_period_29_hours_ago_is_due(db_session):
    now = datetime.now(timezone.utc)
    doc = await _make_document(
        db_session,
        source_url="https://example.com/openapi.json",
        recheck_period="daily",
        last_checked_at=now - timedelta(hours=29),
    )

    due = await find_docs_due_for_recheck(db_session, now)

    assert doc.id in {d.id for d in due}


async def test_monthly_period_29_days_ago_is_not_due(db_session):
    now = datetime.now(timezone.utc)
    doc = await _make_document(
        db_session,
        source_url="https://example.com/openapi.json",
        recheck_period="monthly",
        last_checked_at=now - timedelta(days=29),
    )

    due = await find_docs_due_for_recheck(db_session, now)

    assert doc.id not in {d.id for d in due}


async def test_no_source_url_is_never_due_regardless_of_period(db_session):
    now = datetime.now(timezone.utc)
    doc = await _make_document(
        db_session, source_url=None, recheck_period="daily", last_checked_at=None
    )

    due = await find_docs_due_for_recheck(db_session, now)

    assert doc.id not in {d.id for d in due}


async def test_manual_period_is_never_due_even_with_old_last_checked_at(db_session):
    now = datetime.now(timezone.utc)
    doc = await _make_document(
        db_session,
        source_url="https://example.com/openapi.json",
        recheck_period="manual",
        last_checked_at=now - timedelta(days=365),
    )

    due = await find_docs_due_for_recheck(db_session, now)

    assert doc.id not in {d.id for d in due}


async def test_due_matrix_together_in_one_scan(db_session):
    """The five cases above, in a single query, to confirm the SQL-narrow
    then Python-filter split (app.services.api_document_versions'
    find_docs_due_for_recheck) doesn't let one case leak into another."""
    now = datetime.now(timezone.utc)
    never_checked = await _make_document(
        db_session, source_url="https://x/a.json", recheck_period="weekly", last_checked_at=None
    )
    daily_due = await _make_document(
        db_session,
        source_url="https://x/b.json",
        recheck_period="daily",
        last_checked_at=now - timedelta(hours=29),
    )
    monthly_not_due = await _make_document(
        db_session,
        source_url="https://x/c.json",
        recheck_period="monthly",
        last_checked_at=now - timedelta(days=29),
    )
    no_url = await _make_document(
        db_session, source_url=None, recheck_period="daily", last_checked_at=None
    )
    manual = await _make_document(
        db_session,
        source_url="https://x/d.json",
        recheck_period="manual",
        last_checked_at=now - timedelta(days=365),
    )

    due_ids = {d.id for d in await find_docs_due_for_recheck(db_session, now)}

    # Subset check, not exact equality - the DB isn't guaranteed to contain
    # only this test's own rows (e.g. real usage data alongside the test
    # DB), only that our expected docs are included and our not-due ones
    # are excluded.
    assert {never_checked.id, daily_due.id} <= due_ids
    assert monthly_not_due.id not in due_ids
    assert no_url.id not in due_ids
    assert manual.id not in due_ids


# --- run_due_rechecks ------------------------------------------------------------------


async def test_run_due_rechecks_only_processes_due_documents(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    due_doc = await _make_document(
        db_session,
        source_url="https://example.com/a.json",
        recheck_period="daily",
        last_checked_at=None,
    )
    not_due_doc = await _make_document(
        db_session,
        source_url="https://example.com/b.json",
        recheck_period="monthly",
        last_checked_at=now - timedelta(days=1),
    )

    calls = []

    async def fake_fetch_and_process(doc, source, db, settings):
        calls.append((doc.id, source))

    monkeypatch.setattr(scheduler_module, "fetch_and_process", fake_fetch_and_process)
    monkeypatch.setattr(scheduler_module, "AsyncSessionLocal", lambda: _UseExistingSession(db_session))

    await run_due_rechecks()

    # Membership check, not exact list equality - the DB isn't guaranteed to
    # contain only this test's own rows (e.g. real usage data alongside the
    # test DB), only that our expected doc was processed and our not-due one
    # wasn't.
    assert (due_doc.id, "auto_recheck") in calls
    assert not_due_doc.id not in [doc_id for doc_id, _ in calls]


async def test_run_due_rechecks_continues_past_one_documents_failure(db_session, monkeypatch):
    failing_doc = await _make_document(
        db_session,
        title="Failing",
        source_url="https://example.com/a.json",
        recheck_period="daily",
        last_checked_at=None,
    )
    ok_doc = await _make_document(
        db_session,
        title="OK",
        source_url="https://example.com/b.json",
        recheck_period="daily",
        last_checked_at=None,
    )
    # Committed, not just flushed: run_due_rechecks's own db.rollback() (for
    # failing_doc, below) must not be able to undo ok_doc's row too - in
    # production this can never happen (find_docs_due_for_recheck only ever
    # returns rows already durably committed by past, unrelated requests),
    # but within this single shared test session, an uncommitted sibling row
    # would otherwise be wiped out by that same rollback.
    await db_session.commit()
    # Captured as plain values before run_due_rechecks runs: its own
    # db.rollback() (for failing_doc) expires every object still held by
    # this shared session - these test-local references included - and
    # touching an expired object's attribute outside of an awaited
    # SQLAlchemy call raises MissingGreenlet under the async driver (the
    # same hazard run_due_rechecks itself is written to avoid). Plain UUIDs
    # have no such lifecycle, so they stay safe to assert on afterward.
    failing_doc_id, ok_doc_id = failing_doc.id, ok_doc.id

    processed = []

    async def fake_fetch_and_process(doc, source, db, settings):
        if doc.id == failing_doc_id:
            raise RuntimeError("simulated failure")
        processed.append(doc.id)

    monkeypatch.setattr(scheduler_module, "fetch_and_process", fake_fetch_and_process)
    monkeypatch.setattr(scheduler_module, "AsyncSessionLocal", lambda: _UseExistingSession(db_session))

    await run_due_rechecks()  # must not raise despite failing_doc's exception

    assert ok_doc_id in processed
    assert failing_doc_id not in processed


# --- start_scheduler / shutdown_scheduler lifecycle -------------------------------------


async def test_start_scheduler_creates_and_starts_the_singleton():
    start_scheduler()

    assert scheduler_module._scheduler is not None
    assert scheduler_module._scheduler.running is True


async def test_shutdown_scheduler_after_start_is_safe():
    start_scheduler()

    shutdown_scheduler()

    assert scheduler_module._scheduler is None


async def test_shutdown_scheduler_without_ever_starting_is_a_safe_noop():
    assert scheduler_module._scheduler is None

    shutdown_scheduler()  # must not raise

    assert scheduler_module._scheduler is None


async def test_scheduler_enabled_false_prevents_starting():
    """Mirrors app/main.py's lifespan guard (`if settings.scheduler_enabled:
    start_scheduler()`) directly, rather than booting the real FastAPI app -
    doing that would run the app's actual lifespan, which also disposes the
    shared, session-scoped DB engine (see conftest.py/pytest.ini) every
    other test in this session still needs."""
    settings = Settings(scheduler_enabled=False)

    if settings.scheduler_enabled:
        start_scheduler()

    assert scheduler_module._scheduler is None


async def test_scheduler_enabled_true_allows_starting():
    settings = Settings(scheduler_enabled=True)

    if settings.scheduler_enabled:
        start_scheduler()

    assert scheduler_module._scheduler is not None
