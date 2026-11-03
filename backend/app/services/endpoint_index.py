# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The endpoint search index (ApiDocumentEndpoint, app/models/api_document.py):
the endpoints of every document's current version, so a search across all
documents is one query instead of a spec parsed per document.

Only the CURRENT version of a document is indexed - the search answers "where
do I find this endpoint now" - and a document's rows are replaced as a whole
whenever it gets a new current version (`index_version`, called from
app/services/api_document_versions.py's process_new_spec). Indexing never makes
a check fail: a version that could not be indexed keeps `endpoint_count` NULL,
and `backfill_missing` (run once at start-up, see app/main.py) picks it up
again - which is also how documents recorded before the index existed get into
it."""

import asyncio
import logging
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.api_document import ApiDocumentEndpoint, ApiDocumentVersion
from app.services.openapi_spec import ParsedSpec, SpecValidationError, parse_spec
from app.services.spec_outline import Endpoint, extract_endpoints
from app.services.spec_storage import read_spec_file
from app.services.text_search import fold

logger = logging.getLogger(__name__)


def search_text_of(endpoint: Endpoint) -> str:
    """What a search looks in for one endpoint: its method, path, name,
    description, tags and operation id, folded."""
    parts = [endpoint.method, endpoint.path, endpoint.name, endpoint.description, *endpoint.tags, endpoint.operation_id]
    return fold(" ".join(part for part in parts if part))


def _rows(documentation_id: uuid.UUID, version_id: uuid.UUID, endpoints: list[Endpoint]) -> list[ApiDocumentEndpoint]:
    return [
        ApiDocumentEndpoint(
            documentation_id=documentation_id,
            version_id=version_id,
            method=endpoint.method,
            path=endpoint.path,
            name=endpoint.name,
            description=endpoint.description,
            tags=list(endpoint.tags),
            deprecated=endpoint.deprecated,
            operation_id=endpoint.operation_id,
            search_text=search_text_of(endpoint),
        )
        for endpoint in endpoints
    ]


async def replace_index(
    db: AsyncSession, documentation_id: uuid.UUID, version_id: uuid.UUID, endpoints: list[Endpoint]
) -> None:
    """Replace every indexed endpoint of a document by `endpoints` of the given
    version and record their number on it. Does not commit."""
    await db.execute(delete(ApiDocumentEndpoint).where(ApiDocumentEndpoint.documentation_id == documentation_id))
    db.add_all(_rows(documentation_id, version_id, endpoints))
    await db.execute(
        update(ApiDocumentVersion).where(ApiDocumentVersion.id == version_id).values(endpoint_count=len(endpoints))
    )


async def index_version(db: AsyncSession, version: ApiDocumentVersion, parsed: ParsedSpec) -> None:
    """Index a document's new current version from its already parsed spec,
    and commit. Never raises: on a failure it is logged and the version stays
    unindexed for the backfill to retry. The work runs in a SAVEPOINT, so a
    failure undoes only the index and leaves the objects the caller still
    holds (the document, the version) usable - a plain rollback would expire
    them, and reading an expired attribute under the async driver raises."""
    version_id, documentation_id = version.id, version.documentation_id
    try:
        endpoints = extract_endpoints(parsed)
        async with db.begin_nested():
            await replace_index(db, documentation_id, version_id, endpoints)
        await db.commit()
    except Exception:
        logger.exception("Cannot index the endpoints of version %s (document %s)", version_id, documentation_id)
    await db.refresh(version)  # replace_index updated the row with a statement, not through the object


def _parse_stored(uploads_dir: str, storage_path: str) -> ParsedSpec:
    return parse_spec(read_spec_file(uploads_dir, storage_path))


async def backfill_missing(uploads_dir: str) -> int:
    """Index every current version that is not indexed yet, from its stored
    file, and return how many were done. One version that cannot be read or
    parsed is logged and skipped - it is tried again at the next start - and
    never stops the others. Opens its own session: it runs outside any request."""
    done = 0
    async with AsyncSessionLocal() as db:
        pending = (
            await db.execute(
                select(ApiDocumentVersion.id, ApiDocumentVersion.documentation_id, ApiDocumentVersion.storage_path).where(
                    ApiDocumentVersion.archived_at.is_(None), ApiDocumentVersion.endpoint_count.is_(None)
                )
            )
        ).all()
        for version_id, documentation_id, storage_path in pending:
            try:
                parsed = await asyncio.to_thread(_parse_stored, uploads_dir, storage_path)
                await replace_index(db, documentation_id, version_id, extract_endpoints(parsed))
                await db.commit()
                done += 1
            except (OSError, SpecValidationError):
                logger.warning("Cannot index version %s (document %s): its file is missing or no longer parses", version_id, documentation_id)
                await db.rollback()
            except Exception:
                logger.exception("Cannot index version %s (document %s)", version_id, documentation_id)
                await db.rollback()
    if done:
        logger.info("Indexed the endpoints of %d document version(s)", done)
    return done


async def run_backfill(uploads_dir: str) -> None:
    """backfill_missing as a background task: whatever goes wrong (a database
    that is not migrated yet, say) is logged and ends the task instead of
    surfacing as an exception nobody awaits."""
    try:
        await backfill_missing(uploads_dir)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Indexing the endpoints of existing documents failed")
