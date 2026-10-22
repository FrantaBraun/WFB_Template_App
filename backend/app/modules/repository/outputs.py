# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Response bodies assembled from rows and counts, shared by the routes."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.repository import service
from app.modules.repository.models import Attribute, Repository, RepositoryTable
from app.modules.repository.schemas import AttributeOut, RepositoryDetail, RepositoryOut, TableOut, TableSummary


def repository_out(repository: Repository, table_count: int, record_count: int) -> RepositoryOut:
    return RepositoryOut.model_validate(repository).model_copy(
        update={"table_count": table_count, "record_count": record_count}
    )


async def repository_outs(db: AsyncSession, repositories: Sequence[Repository]) -> list[RepositoryOut]:
    counts = await service.repository_counts(db, [repository.id for repository in repositories])
    return [repository_out(repository, *counts[repository.id]) for repository in repositories]


async def table_summaries(db: AsyncSession, tables: Sequence[RepositoryTable]) -> list[TableSummary]:
    counts = await service.table_record_counts(db, [table.id for table in tables])
    return [
        TableSummary.model_validate(table).model_copy(update={"record_count": counts[table.id]}) for table in tables
    ]


async def repository_detail(db: AsyncSession, repository: Repository) -> RepositoryDetail:
    tables = await service.list_tables(db, repository.id)
    summaries = await table_summaries(db, tables)
    return RepositoryDetail(
        **(await repository_outs(db, [repository]))[0].model_dump(),
        tables=summaries,
    )


def table_out(summary: TableSummary, attributes: Sequence[Attribute]) -> TableOut:
    return TableOut(**summary.model_dump(), attributes=[AttributeOut.model_validate(attribute) for attribute in attributes])


async def table_detail(db: AsyncSession, table: RepositoryTable) -> TableOut:
    (summary,) = await table_summaries(db, [table])
    return table_out(summary, await service.get_attributes(db, table.id))
