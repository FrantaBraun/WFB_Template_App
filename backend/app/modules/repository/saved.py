# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Saved filters and statistics of a table, and computing a statistic.

Refusals follow service.py: 404 for what is not the caller's, 422
`{"errors": {...}}` for a definition that makes no sense (the keys of
filters.normalize_filter - `conditions.<i>`, `sort` - and of
pivot.validate_statistic - `group_by.<i>`, `aggregation`, `chart_type` - plus
`filter_id` = `unknown_filter`), 409 `{"limit": ...}` at max_filters_per_table /
max_statistics_per_table, and 409 `{"in_use": [{id, name}]}` when a saved filter
is deleted while statistics are based on it.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.repository import filters, pivot, query, records
from app.modules.repository.config import RepositoryConfig
from app.modules.repository.models import Attribute, Repository, RepositoryTable, SavedFilter, Statistic
from app.modules.repository.schemas import FilterIn, FilterOut, RefInfo, StatisticIn
from app.modules.repository.service import errors_422, limit_reached

_FILTER_PARTS = {"conditions", "sort", "include_deleted", "q"}


# --- Saved filters ----------------------------------------------------------------------


async def list_filters(db: AsyncSession, table: RepositoryTable) -> list[SavedFilter]:
    return list(
        (await db.scalars(select(SavedFilter).where(SavedFilter.table_id == table.id).order_by(SavedFilter.position, SavedFilter.created_at))).all()
    )


async def get_filter(db: AsyncSession, table: RepositoryTable, filter_id: uuid.UUID) -> SavedFilter:
    found = await db.scalar(select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.table_id == table.id))
    if found is None:
        raise HTTPException(status_code=404, detail="Filter not found")
    return found


async def filter_refs(
    db: AsyncSession, repository: Repository, attributes: Sequence[Attribute], saved_filters: Sequence[SavedFilter]
) -> dict[str, RefInfo]:
    """The records the reference conditions of these saved filters point at."""
    fields = filters.fields_for(attributes)
    ids = {
        condition["value"]
        for saved in saved_filters
        for condition in saved.definition.get("conditions", [])
        if fields.get(condition["field"]) is not None and fields[condition["field"]].kind == "reference" and condition.get("value")
    }
    return await records.resolve_refs(db, repository, ids)


def filter_out(saved: SavedFilter, refs: dict[str, RefInfo]) -> FilterOut:
    """The saved filter with the records its conditions point at (only those of its own conditions)."""
    own = {
        condition["value"]
        for condition in saved.definition.get("conditions", [])
        if isinstance(condition.get("value"), str) and condition["value"] in refs
    }
    return FilterOut.model_validate(saved).model_copy(update={"refs": {key: refs[key] for key in own}})


def _normalized_definition(attributes: Sequence[Attribute], body: FilterIn) -> dict[str, Any]:
    definition, errors = filters.normalize_filter(filters.fields_for(attributes), body.model_dump(include=_FILTER_PARTS))
    if errors:
        raise errors_422(errors)
    return definition


async def create_filter(
    db: AsyncSession, table: RepositoryTable, attributes: Sequence[Attribute], body: FilterIn, limits: RepositoryConfig
) -> SavedFilter:
    definition = _normalized_definition(attributes, body)
    count = await db.scalar(select(func.count(SavedFilter.id)).where(SavedFilter.table_id == table.id))
    if count >= limits.max_filters_per_table:
        raise limit_reached("max_filters_per_table", limits.max_filters_per_table)
    last = await db.scalar(select(func.max(SavedFilter.position)).where(SavedFilter.table_id == table.id))
    saved = SavedFilter(table_id=table.id, name=body.name, definition=definition, position=0 if last is None else last + 1)
    db.add(saved)
    await db.commit()
    return saved


async def update_filter(db: AsyncSession, attributes: Sequence[Attribute], saved: SavedFilter, body: FilterIn) -> SavedFilter:
    saved.definition = _normalized_definition(attributes, body)
    saved.name = body.name
    await db.commit()
    return saved


async def statistics_based_on(db: AsyncSession, saved: SavedFilter) -> list[dict[str, str]]:
    rows = (await db.execute(select(Statistic.id, Statistic.name).where(Statistic.filter_id == saved.id).order_by(Statistic.position))).all()
    return [{"id": str(statistic_id), "name": name} for statistic_id, name in rows]


async def delete_filter(db: AsyncSession, saved: SavedFilter) -> None:
    dependants = await statistics_based_on(db, saved)
    if dependants:
        raise HTTPException(status_code=409, detail={"in_use": dependants})
    await db.delete(saved)
    await db.commit()


# --- Statistics ----------------------------------------------------------------------------


async def list_statistics(db: AsyncSession, table: RepositoryTable) -> list[Statistic]:
    return list(
        (await db.scalars(select(Statistic).where(Statistic.table_id == table.id).order_by(Statistic.position, Statistic.created_at))).all()
    )


async def get_statistic(db: AsyncSession, table: RepositoryTable, statistic_id: uuid.UUID) -> Statistic:
    found = await db.scalar(select(Statistic).where(Statistic.id == statistic_id, Statistic.table_id == table.id))
    if found is None:
        raise HTTPException(status_code=404, detail="Statistic not found")
    return found


async def _checked_statistic(db: AsyncSession, table: RepositoryTable, attributes: Sequence[Attribute], body: StatisticIn) -> dict[str, Any]:
    """The statistic's shape, normalized, or 422."""
    definition, errors = pivot.validate_statistic(filters.fields_for(attributes), body.model_dump(mode="json"))
    if body.filter_id is not None and await db.scalar(
        select(SavedFilter.id).where(SavedFilter.id == body.filter_id, SavedFilter.table_id == table.id)
    ) is None:
        errors["filter_id"] = "unknown_filter"
    if errors:
        raise errors_422(errors)
    return definition


async def create_statistic(
    db: AsyncSession, table: RepositoryTable, attributes: Sequence[Attribute], body: StatisticIn, limits: RepositoryConfig
) -> Statistic:
    definition = await _checked_statistic(db, table, attributes, body)
    count = await db.scalar(select(func.count(Statistic.id)).where(Statistic.table_id == table.id))
    if count >= limits.max_statistics_per_table:
        raise limit_reached("max_statistics_per_table", limits.max_statistics_per_table)
    last = await db.scalar(select(func.max(Statistic.position)).where(Statistic.table_id == table.id))
    statistic = Statistic(
        table_id=table.id,
        filter_id=body.filter_id,
        name=body.name,
        group_by=definition["group_by"],
        aggregation=definition["aggregation"],
        display=definition["display"],
        chart_type=definition["chart_type"],
        position=0 if last is None else last + 1,
    )
    db.add(statistic)
    await db.commit()
    return statistic


async def update_statistic(
    db: AsyncSession, table: RepositoryTable, attributes: Sequence[Attribute], statistic: Statistic, body: StatisticIn
) -> Statistic:
    definition = await _checked_statistic(db, table, attributes, body)
    statistic.name = body.name
    statistic.filter_id = body.filter_id
    statistic.group_by = definition["group_by"]
    statistic.aggregation = definition["aggregation"]
    statistic.display = definition["display"]
    statistic.chart_type = definition["chart_type"]
    await db.commit()
    return statistic


async def delete_statistic(db: AsyncSession, statistic: Statistic) -> None:
    await db.delete(statistic)
    await db.commit()


async def reorder(db: AsyncSession, rows: Sequence[SavedFilter] | Sequence[Statistic], ids: Sequence[uuid.UUID]) -> None:
    """Gives the rows the order of `ids`, which must list every one of them exactly once."""
    by_id = {row.id: row for row in rows}
    if len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise errors_422({"ids": "must_list_every_item_once"})
    for position, row_id in enumerate(ids):
        by_id[row_id].position = position
    await db.commit()


# --- Computing a statistic ---------------------------------------------------------------------


async def compute(
    db: AsyncSession,
    repository: Repository,
    table: RepositoryTable,
    attributes: Sequence[Attribute],
    *,
    group_by: Sequence[dict[str, Any]],
    aggregation: dict[str, Any],
    filter_definition: dict[str, Any] | None,
) -> dict[str, Any]:
    """The result of a statistic (see pivot.py): the records of the table that
    pass the filter (none deleted unless the filter says so), grouped and
    aggregated by the database. Each dimension's own totals and the grand total are
    separate queries over the records, so they are exact however the cells are cut.

    The expressions that make the keys are computed once, in a subquery, and the
    outer query groups by its plain columns: grouping by the expression twice
    would give the database two different bind parameters and it would refuse."""
    fields = filters.fields_for(attributes)
    clauses = query.where_clauses(
        table.id, fields, filter_definition or {"conditions": [], "include_deleted": False, "q": None}
    )
    dimensions = [(fields[dimension["field"]], dimension["bucket"]) for dimension in group_by]
    function = aggregation["fn"]

    columns = [query.group_expression(field, bucket).label(f"k{index}") for index, (field, bucket) in enumerate(dimensions)]
    if function != "count":
        columns.append(query.number_expression(aggregation["attribute_id"]).label("v"))
    inner = select(*columns).where(*clauses).subquery()

    def aggregate():
        if function == "count":
            return func.count()
        return {"sum": func.sum, "avg": func.avg, "min": func.min, "max": func.max}[function](inner.c.v)

    # ONE query for the cells, each dimension's own totals and the grand total: GROUPING SETS
    # groups by every combination, and GROUPING(column) says which columns a row is rolled up over
    # (a NULL key is then an empty value, not a rolled-up column).
    key_columns = [inner.c[f"k{index}"] for index in range(len(dimensions))]
    sets = [tuple(key_columns)] + [(column,) for column in key_columns] + [()] if len(dimensions) == 2 else [(key_columns[0],), ()]
    statement = (
        select(*key_columns, *[func.grouping(column) for column in key_columns], aggregate())
        .select_from(inner)
        .group_by(func.grouping_sets(*[tuple_(*columns) for columns in sets]))
    )
    cells: list[tuple[Any, ...]] = []
    totals: list[list[tuple[Any, Any]]] = [[] for _ in dimensions]
    grand_total: Any = None
    count = len(dimensions)
    for row in (await db.execute(statement)).all():
        keys, rolled_up, value = row[:count], row[count : 2 * count], row[-1]
        if all(rolled_up):
            grand_total = value
        elif not any(rolled_up):
            cells.append((*keys, value))
        else:  # one of two dimensions kept: that dimension's own totals
            index = rolled_up.index(0)
            totals[index].append((keys[index], value))
    if count == 1:  # the groups of the only dimension are its cells and its totals
        totals[0] = [(key, value) for key, value in cells]

    labels: dict[Any, str] = {}
    reference_ids = {
        key
        for (field, _), rows in zip(dimensions, totals)
        if field.kind == "reference"
        for key, _ in rows
        if key is not None
    }
    if reference_ids:
        labels = {key: info.name for key, info in (await records.resolve_refs(db, repository, reference_ids)).items()}

    return pivot.assemble(
        kinds=[field.kind for field, _ in dimensions],
        function=function,
        cells=cells,
        totals=[[(row[0], row[1]) for row in rows] for rows in totals],
        grand_total=grand_total,
        labels=labels,
    )


async def compute_saved(
    db: AsyncSession, repository: Repository, table: RepositoryTable, attributes: Sequence[Attribute], statistic: Statistic
) -> dict[str, Any]:
    filter_definition = None
    if statistic.filter_id is not None:
        filter_definition = (await db.get(SavedFilter, statistic.filter_id)).definition
    return await compute(
        db,
        repository,
        table,
        attributes,
        group_by=statistic.group_by,
        aggregation=statistic.aggregation,
        filter_definition=filter_definition,
    )


async def compute_preview(
    db: AsyncSession, repository: Repository, table: RepositoryTable, attributes: Sequence[Attribute], body: StatisticIn
) -> dict[str, Any]:
    """The result of a statistic that is not saved (what the editor shows while it is being made)."""
    definition = await _checked_statistic(db, table, attributes, body)
    filter_definition = None
    if body.filter_id is not None:
        filter_definition = (await db.get(SavedFilter, body.filter_id)).definition
    return await compute(
        db,
        repository,
        table,
        attributes,
        group_by=definition["group_by"],
        aggregation=definition["aggregation"],
        filter_definition=filter_definition,
    )
