# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Saved filters and statistics of a table."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.repository import saved
from app.modules.repository.config import RepositoryConfig, get_limits
from app.modules.repository.routes_records import TableContext, table_context
from app.modules.repository.schemas import (
    FilterIn,
    FilterOut,
    OrderIn,
    StatisticIn,
    StatisticOut,
    StatisticResult,
    StatisticWithResult,
)

router = APIRouter(prefix="/repositories/{repository_slug}/tables/{table_slug}")


# --- Saved filters ---------------------------------------------------------------------


@router.get("/filters")
async def list_filters(context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> list[FilterOut]:
    return [FilterOut.model_validate(row) for row in await saved.list_filters(db, context.table)]


@router.post("/filters", status_code=201)
async def create_filter(
    body: FilterIn,
    context: TableContext = Depends(table_context),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> FilterOut:
    """A name and the definition of a records query (conditions, sort, include_deleted, q)."""
    return FilterOut.model_validate(await saved.create_filter(db, context.table, context.attributes, body, limits))


@router.put("/filters-order", status_code=204)
async def reorder_filters(body: OrderIn, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> None:
    await saved.reorder(db, await saved.list_filters(db, context.table), body.ids)


@router.put("/filters/{filter_id}")
async def update_filter(
    filter_id: uuid.UUID, body: FilterIn, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)
) -> FilterOut:
    """Replaces the whole filter."""
    found = await saved.get_filter(db, context.table, filter_id)
    return FilterOut.model_validate(await saved.update_filter(db, context.attributes, found, body))


@router.delete("/filters/{filter_id}", status_code=204)
async def delete_filter(filter_id: uuid.UUID, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> None:
    """Refused (409, `in_use`) while a statistic is based on the filter."""
    await saved.delete_filter(db, await saved.get_filter(db, context.table, filter_id))


# --- Statistics ---------------------------------------------------------------------------


@router.get("/statistics")
async def list_statistics(context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> list[StatisticOut]:
    return [StatisticOut.model_validate(row) for row in await saved.list_statistics(db, context.table)]


@router.post("/statistics", status_code=201)
async def create_statistic(
    body: StatisticIn,
    context: TableContext = Depends(table_context),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> StatisticOut:
    """One or two dimensions to group by, an aggregation, optionally a saved filter,
    and how it is shown (see pivot.py)."""
    return StatisticOut.model_validate(await saved.create_statistic(db, context.table, context.attributes, body, limits))


@router.put("/statistics-order", status_code=204)
async def reorder_statistics(body: OrderIn, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> None:
    await saved.reorder(db, await saved.list_statistics(db, context.table), body.ids)


@router.post("/statistics-preview")
async def preview_statistic(
    body: StatisticIn, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)
) -> StatisticResult:
    """The result of a statistic that is not saved - what the editor shows while it is being made."""
    return StatisticResult(**await saved.compute_preview(db, context.repository, context.table, context.attributes, body))


@router.get("/statistics-results")
async def statistics_results(
    context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)
) -> list[StatisticWithResult]:
    """Every statistic that is shown (display is not `hidden`) with its result - the tiles of the content page."""
    shown = [row for row in await saved.list_statistics(db, context.table) if row.display != "hidden"]
    return [
        StatisticWithResult(
            statistic=StatisticOut.model_validate(row),
            result=StatisticResult(**await saved.compute_saved(db, context.repository, context.table, context.attributes, row)),
        )
        for row in shown
    ]


@router.put("/statistics/{statistic_id}")
async def update_statistic(
    statistic_id: uuid.UUID, body: StatisticIn, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)
) -> StatisticOut:
    """Replaces the whole statistic."""
    found = await saved.get_statistic(db, context.table, statistic_id)
    return StatisticOut.model_validate(await saved.update_statistic(db, context.table, context.attributes, found, body))


@router.delete("/statistics/{statistic_id}", status_code=204)
async def delete_statistic(statistic_id: uuid.UUID, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> None:
    await saved.delete_statistic(db, await saved.get_statistic(db, context.table, statistic_id))


@router.get("/statistics/{statistic_id}/result")
async def statistic_result(statistic_id: uuid.UUID, context: TableContext = Depends(table_context), db: AsyncSession = Depends(get_db)) -> StatisticResult:
    found = await saved.get_statistic(db, context.table, statistic_id)
    return StatisticResult(**await saved.compute_saved(db, context.repository, context.table, context.attributes, found))
