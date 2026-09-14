# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.api_document import ApiDocument
from app.services.api_document_versions import fetch_and_process, find_docs_due_for_recheck

logger = logging.getLogger(__name__)

# Module-level singleton, matching app/security/jwt.py's _public_key
# convention: None until start_scheduler() runs, cleared again by
# shutdown_scheduler().
_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """Create, configure and start the module-level AsyncIOScheduler
    singleton: one repeating job scanning for due rechecks, on
    settings.recheck_scan_interval_minutes. Settings are read here (at call
    time via get_settings()), not at import time, so a test-injected
    override is honored. Called from app/main.py's lifespan, guarded by
    settings.scheduler_enabled."""
    global _scheduler
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_due_rechecks, "interval", minutes=settings.recheck_scan_interval_minutes)
    scheduler.start()
    _scheduler = scheduler


def shutdown_scheduler() -> None:
    """Stop the scheduler if running and clear the singleton - a no-op if
    start_scheduler() was never called. shutdown(wait=False) so app shutdown
    doesn't block on an in-flight recheck batch. Called from app/main.py's
    lifespan before the DB engine is disposed, since run_due_rechecks below
    uses it."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


async def run_due_rechecks() -> None:
    """The scheduler's one repeating job: scan for ApiDocuments whose
    recheck_period is due (find_docs_due_for_recheck) and recheck each one
    via the same fetch_and_process (app/services/api_document_versions.py) a
    manual recheck uses, tagged source="auto_recheck".

    Runs outside any request, so it opens its own session directly through
    AsyncSessionLocal (app/database.py) rather than Depends(get_db). Each
    document's fetch_and_process call is wrapped in its own try/except:
    logged via logger.exception and the batch moves on to the next document
    regardless - one document's failure must never abort the rest.

    db.rollback() in the except block is a defensive measure for the case
    where a failure left the shared session's transaction unusable for the
    next iteration (most failures are already cleanly committed by
    fetch_and_process's own error handling before they propagate here, but
    this guards the case where they aren't). That rollback expires every
    object still held by the session - including every not-yet-processed
    document from the due_docs query below - and plain attribute access on
    an expired object outside of an awaited SQLAlchemy call raises
    MissingGreenlet under the async driver (confirmed directly against this
    engine: a rollback followed by a bare `doc.source_url` on an
    already-loaded sibling row raises exactly that). So only ids are kept
    across iterations (captured up front, before any rollback can happen),
    and each iteration re-fetches its own document fresh via db.get() - an
    awaited call, so it transparently and safely re-queries even a
    since-expired identity-mapped instance instead of touching stale
    in-memory state.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        due_docs = await find_docs_due_for_recheck(db, now)
        due_doc_ids = [doc.id for doc in due_docs]
        for doc_id in due_doc_ids:
            try:
                doc = await db.get(ApiDocument, doc_id)
                if doc is None:
                    continue
                await fetch_and_process(doc, source="auto_recheck", db=db, settings=settings)
            except Exception:
                logger.exception("Automatic recheck failed for document %s", doc_id)
                await db.rollback()
