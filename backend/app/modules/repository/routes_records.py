# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Records of a table."""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.repository import records, service
from app.modules.repository.config import RepositoryConfig, get_limits
from app.modules.repository.models import Attribute, Repository, RepositoryTable
from app.modules.repository.schemas import (
    RecordCreate,
    RecordHitPage,
    RecordOut,
    RecordPage,
    RecordQuery,
    RecordUpdate,
)

router = APIRouter(prefix="/repositories/{repository_slug}/tables/{table_slug}")


@dataclass
class TableContext:
    repository: Repository
    table: RepositoryTable
    attributes: list[Attribute]


async def table_context(
    repository_slug: str,
    table_slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableContext:
    """The caller's repository and table named in the path (404 for anything
    that is not theirs) with the table's attributes."""
    repository = await service.get_repository(db, user, repository_slug)
    table = await service.get_table(db, repository, table_slug)
    return TableContext(repository, table, await service.get_attributes(db, table.id))


@router.post("/records-query")
async def query_records(
    body: RecordQuery, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)
) -> RecordPage:
    """One page of the table's records for a filter and a sort (see filters.py
    for the body). Records that are deleted are left out unless `include_deleted`.
    Each item carries only the values of the attributes shown on the content page."""
    return await records.query_records(db, context.repository, context.table, context.attributes, body)


@router.get("/records-search")
async def search_records(
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1, le=100_000),
    context: TableContext = Depends(table_context),
    db: AsyncSession = Depends(get_db),
) -> RecordHitPage:
    """For the picker of a reference: records that are not deleted, by name, whose name or slug contains `q`."""
    return await records.search_records(db, context.table, q, page)


@router.post("/records", status_code=201)
async def create_record(
    body: RecordCreate,
    context: TableContext = Depends(table_context),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> RecordOut:
    """`data` maps attribute ids to values (see logic.py for the formats); the
    slug is made from the name when it is left out."""
    record = await records.create_record(db, user, context.repository, context.table, context.attributes, body, limits)
    return await records.record_out(db, context.repository, context.attributes, record)


@router.get("/records/{record_slug}")
async def get_record(record_slug: str, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> RecordOut:
    record = await records.get_record(db, context.table, record_slug)
    return await records.record_out(db, context.repository, context.attributes, record)


@router.patch("/records/{record_slug}")
async def update_record(
    record_slug: str,
    body: RecordUpdate,
    context: TableContext = Depends(table_context),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecordOut:
    """Only the fields sent change; `data`, when sent, replaces ALL the values.
    A deleted record cannot be edited (409) - restore it first."""
    record = await records.get_record(db, context.table, record_slug)
    await records.update_record(db, user, context.repository, context.table, context.attributes, record, body)
    return await records.record_out(db, context.repository, context.attributes, record)


@router.delete("/records/{record_slug}", status_code=204)
async def delete_record(record_slug: str, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> None:
    """Marks the record deleted; it can be restored."""
    await records.soft_delete(db, await records.get_record(db, context.table, record_slug))


@router.post("/records/{record_slug}/restore", status_code=204)
async def restore_record(record_slug: str, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> None:
    await records.restore(db, await records.get_record(db, context.table, record_slug))


@router.delete("/records/{record_slug}/permanent", status_code=204)
async def delete_record_permanently(
    record_slug: str, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)
) -> None:
    """Deletes a record that is already deleted, for good - refused (409,
    `referenced_by`) while another record still points at it."""
    await records.purge(db, context.repository, await records.get_record(db, context.table, record_slug))
