# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What the routes do, with the database: owner-scoped lookups (what belongs
to somebody else is a 404 - never a 403), slugs, limits, and the one place a
table's attributes are saved (`replace_attributes`).

Refusals are HTTPExceptions with a detail the frontend can act on:

- 404 `{"detail": "... not found"}` - missing, or not the caller's;
- 409 `{"errors": {"slug": "taken"}}` - a unique slug is already used;
- 409 `{"limit": "<limits key>", "max": N}` - a configured limit is reached;
- 409 `{"purge_required": [...]}` / `{"referenced_by": [...]}` - see below;
- 422 `{"errors": {<field or attribute id>: <code>}}` - the request makes no
  sense (the same shape forms and event_booking use).

Nothing here commits except where it says so: the routes decide the
transaction, and every check that can refuse comes before the first write.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from sqlalchemy import ARRAY, Text, cast, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.user import User
from app.modules.repository import filters, logic, pivot
from app.modules.repository.config import RepositoryConfig
from app.modules.repository.models import Attribute, Image, Record, Repository, RepositoryTable, SavedFilter, Statistic
from app.modules.repository.schemas import AttributeIn


def errors_422(errors: dict[str, str]) -> HTTPException:
    return HTTPException(status_code=422, detail={"errors": errors})


def limit_reached(key: str, maximum: int) -> HTTPException:
    return HTTPException(status_code=409, detail={"limit": key, "max": maximum})


def slug_taken() -> HTTPException:
    return HTTPException(status_code=409, detail={"errors": {"slug": "taken"}})


async def commit_or_slug_taken(db: AsyncSession) -> None:
    """Commits; a unique violation (two requests took the same slug at once) is the 409 a taken slug is."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "_slug" not in str(exc.orig):  # only the slug's unique constraints (uq_module_repository_*_slug) mean "taken"
            raise
        raise slug_taken() from exc


# --- Lookups, always through the owner --------------------------------------------


async def get_repository(db: AsyncSession, user: User, slug: str) -> Repository:
    repository = await db.scalar(select(Repository).where(Repository.owner_id == user.id, Repository.slug == slug))
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository


async def get_table(db: AsyncSession, repository: Repository, slug: str) -> RepositoryTable:
    table = await db.scalar(
        select(RepositoryTable).where(RepositoryTable.repository_id == repository.id, RepositoryTable.slug == slug)
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return table


async def get_attributes(db: AsyncSession, table_id: uuid.UUID) -> list[Attribute]:
    return list((await db.scalars(select(Attribute).where(Attribute.table_id == table_id).order_by(Attribute.position))).all())


async def list_tables(db: AsyncSession, repository_id: uuid.UUID) -> list[RepositoryTable]:
    return list(
        (
            await db.scalars(
                select(RepositoryTable)
                .where(RepositoryTable.repository_id == repository_id)
                .order_by(RepositoryTable.position, func.lower(RepositoryTable.name), RepositoryTable.created_at)
            )
        ).all()
    )


# --- Counts -----------------------------------------------------------------------


async def repository_counts(db: AsyncSession, repository_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    """(tables, records that are not deleted) per repository."""
    if not repository_ids:
        return {}
    tables = dict(
        (
            await db.execute(
                select(RepositoryTable.repository_id, func.count(RepositoryTable.id))
                .where(RepositoryTable.repository_id.in_(repository_ids))
                .group_by(RepositoryTable.repository_id)
            )
        ).all()
    )
    records = dict(
        (
            await db.execute(
                select(RepositoryTable.repository_id, func.count(Record.id))
                .join(Record, Record.table_id == RepositoryTable.id)
                .where(RepositoryTable.repository_id.in_(repository_ids), Record.deleted_on.is_(None))
                .group_by(RepositoryTable.repository_id)
            )
        ).all()
    )
    return {rid: (tables.get(rid, 0), records.get(rid, 0)) for rid in repository_ids}


async def table_record_counts(db: AsyncSession, table_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Records that are not deleted, per table."""
    if not table_ids:
        return {}
    counts = dict(
        (
            await db.execute(
                select(Record.table_id, func.count(Record.id))
                .where(Record.table_id.in_(table_ids), Record.deleted_on.is_(None))
                .group_by(Record.table_id)
            )
        ).all()
    )
    return {tid: counts.get(tid, 0) for tid in table_ids}


# --- Slugs --------------------------------------------------------------------------


async def taken_slugs(
    db: AsyncSession, slug_column: InstrumentedAttribute, scope_column: InstrumentedAttribute, scope_id: uuid.UUID
) -> set[str]:
    return set((await db.scalars(select(slug_column).where(scope_column == scope_id))).all())


def resolve_slug(name: str, requested: str | None, taken: set[str], own_slug: str | None = None) -> str:
    """The slug to save: generated from `name` when none was asked for, else the
    requested one - which must be valid (422) and not used by another row in the
    same scope (409). `own_slug` is the row's current slug, which is not 'taken'."""
    taken = taken - {own_slug} if own_slug else taken
    if requested is None:
        return logic.unique_slug(name, taken)
    problem = logic.slug_problem(requested)
    if problem:
        raise errors_422({"slug": problem})
    if requested in taken:
        raise slug_taken()
    return requested


# --- Repositories ---------------------------------------------------------------------


async def create_repository(
    db: AsyncSession, user: User, *, name: str, description: str, slug: str | None, color_scheme: str, limits: RepositoryConfig
) -> Repository:
    count = await db.scalar(select(func.count(Repository.id)).where(Repository.owner_id == user.id))
    if count >= limits.max_repositories_per_user:
        raise limit_reached("max_repositories_per_user", limits.max_repositories_per_user)
    taken = await taken_slugs(db, Repository.slug, Repository.owner_id, user.id)
    repository = Repository(
        owner_id=user.id,
        name=name,
        description=description,
        slug=resolve_slug(name, slug, taken),
        color_scheme=color_scheme,
    )
    db.add(repository)
    await commit_or_slug_taken(db)
    return repository


async def update_repository(db: AsyncSession, user: User, repository: Repository, changes: dict[str, Any]) -> Repository:
    if "slug" in changes and changes["slug"] is not None and changes["slug"] != repository.slug:
        taken = await taken_slugs(db, Repository.slug, Repository.owner_id, user.id)
        repository.slug = resolve_slug(repository.name, changes["slug"], taken, own_slug=repository.slug)
    for field in ("name", "description", "color_scheme"):
        if changes.get(field) is not None:
            setattr(repository, field, changes[field])
    await commit_or_slug_taken(db)
    await db.refresh(repository)
    return repository


async def delete_repository(db: AsyncSession, repository: Repository, confirm_name: str | None) -> None:
    """Deletes the repository with everything in it (the foreign keys cascade) once its name is confirmed."""
    if confirm_name != repository.name:
        raise errors_422({"confirm_name": "mismatch"})
    await db.delete(repository)
    await db.commit()


# --- Tables -----------------------------------------------------------------------------


async def create_table(
    db: AsyncSession,
    repository: Repository,
    *,
    name: str,
    description: str,
    slug: str | None,
    view_type: str,
    limits: RepositoryConfig,
) -> RepositoryTable:
    count = await db.scalar(select(func.count(RepositoryTable.id)).where(RepositoryTable.repository_id == repository.id))
    if count >= limits.max_tables_per_repository:
        raise limit_reached("max_tables_per_repository", limits.max_tables_per_repository)
    taken = await taken_slugs(db, RepositoryTable.slug, RepositoryTable.repository_id, repository.id)
    last_position = await db.scalar(
        select(func.max(RepositoryTable.position)).where(RepositoryTable.repository_id == repository.id)
    )
    table = RepositoryTable(
        repository_id=repository.id,
        name=name,
        description=description,
        slug=resolve_slug(name, slug, taken),
        view_type=view_type,
        position=0 if last_position is None else last_position + 1,
    )
    db.add(table)
    await commit_or_slug_taken(db)
    return table


async def update_table(db: AsyncSession, repository: Repository, table: RepositoryTable, changes: dict[str, Any]) -> RepositoryTable:
    if "slug" in changes and changes["slug"] is not None and changes["slug"] != table.slug:
        taken = await taken_slugs(db, RepositoryTable.slug, RepositoryTable.repository_id, repository.id)
        table.slug = resolve_slug(table.name, changes["slug"], taken, own_slug=table.slug)
    for field in ("name", "description", "view_type"):
        if changes.get(field) is not None:
            setattr(table, field, changes[field])
    await commit_or_slug_taken(db)
    await db.refresh(table)
    return table


async def reorder_tables(db: AsyncSession, repository: Repository, ids: Sequence[uuid.UUID]) -> None:
    tables = {table.id: table for table in await list_tables(db, repository.id)}
    if len(set(ids)) != len(ids) or set(ids) != set(tables):
        raise errors_422({"ids": "must_list_every_table_once"})
    for position, table_id in enumerate(ids):
        tables[table_id].position = position
    await db.commit()


async def tables_referring_to(db: AsyncSession, repository: Repository, table: RepositoryTable) -> list[dict[str, str]]:
    """The attributes of OTHER tables of the repository that point at `table` (a
    reference, or a list/map of references). A table's own attributes go with it."""
    rows = (
        await db.execute(
            select(RepositoryTable.name, RepositoryTable.slug, Attribute.name)
            .join(Attribute, Attribute.table_id == RepositoryTable.id)
            .where(
                RepositoryTable.repository_id == repository.id,
                RepositoryTable.id != table.id,
                Attribute.config["table_id"].astext == str(table.id),
            )
            .order_by(RepositoryTable.position, Attribute.position)
        )
    ).all()
    return [{"table": table_name, "table_slug": table_slug, "attribute": attribute_name} for table_name, table_slug, attribute_name in rows]


async def delete_table(db: AsyncSession, repository: Repository, table: RepositoryTable, confirm_name: str | None) -> None:
    """Deletes the table with its attributes and records once its name is
    confirmed - unless another table's attribute points at it (409 with
    `referenced_by`)."""
    if confirm_name != table.name:
        raise errors_422({"confirm_name": "mismatch"})
    referring = await tables_referring_to(db, repository, table)
    if referring:
        raise HTTPException(status_code=409, detail={"referenced_by": referring})
    await db.delete(table)
    await db.commit()


# --- Attributes ---------------------------------------------------------------------------


async def records_holding_values(db: AsyncSession, table_id: uuid.UUID, attribute_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    """How many records of the table hold a value for each of these attributes."""
    counts: dict[uuid.UUID, int] = {}
    for attribute_id in attribute_ids:
        counts[attribute_id] = await db.scalar(
            select(func.count(Record.id)).where(Record.table_id == table_id, Record.data.has_key(str(attribute_id)))
        )
    return counts


async def attribute_dependants(db: AsyncSession, table: RepositoryTable, attribute_ids: set[str]) -> list[dict[str, str]]:
    """The saved filters and statistics of the table that use any of these attributes
    (a condition, a sort, a dimension, the aggregated number), as {kind, id, name}."""
    found: list[dict[str, str]] = []
    for saved in (await db.scalars(select(SavedFilter).where(SavedFilter.table_id == table.id).order_by(SavedFilter.position))).all():
        if filters.attribute_ids_used(saved.definition) & attribute_ids:
            found.append({"kind": "filter", "id": str(saved.id), "name": saved.name})
    for statistic in (await db.scalars(select(Statistic).where(Statistic.table_id == table.id).order_by(Statistic.position))).all():
        if pivot.attribute_ids_used(statistic.group_by, statistic.aggregation) & attribute_ids:
            found.append({"kind": "statistic", "id": str(statistic.id), "name": statistic.name})
    return found


async def _images_left_behind(
    db: AsyncSession, table: RepositoryTable, removed: Sequence[Attribute], kept: Sequence[AttributeIn]
) -> list[uuid.UUID]:
    """The images held only through attributes that are being removed - they go
    with the values. An image that a remaining attribute of the same record
    still holds stays."""
    if not any(logic.element_type_of(attribute.type, attribute.config) == "image" for attribute in removed):
        return []
    leaving: set[str] = set()
    staying: set[str] = set()
    for (data,) in (await db.execute(select(Record.data).where(Record.table_id == table.id))).all():
        leaving |= logic.image_ids_in(removed, data)
        staying |= logic.image_ids_in(kept, data)
    return [uuid.UUID(image_id) for image_id in leaving - staying]


async def replace_attributes(
    db: AsyncSession,
    repository: Repository,
    table: RepositoryTable,
    incoming: Sequence[AttributeIn],
    *,
    confirm_purge: bool,
    limits: RepositoryConfig,
) -> list[Attribute]:
    """Makes the table's attributes exactly `incoming`, in that order: those
    whose id is already on the table are updated, new ids are inserted, ids no
    longer listed are removed. All or nothing (the caller's transaction); every
    refusal comes before the first write.

    - More than max_attributes_per_table: 409 `limit`.
    - An id that belongs to another table: 422 (`id_in_use`) - an attribute id is
      the key of its values in a record, so it must not be shared.
    - A saved attribute changing `type` or what its `config` points at: 422
      (`type_immutable` / `config_immutable`) - remove it and add it again.
    - A new reference (or list/map of references) to a table that is not in this
      repository: 422 (`invalid_table`). The table itself is fine.
    - Removing an attribute that a saved filter or statistic uses: 409
      `{"in_use": [{kind, id, name}]}` - those have to go (or change) first.
    - Removing an attribute that records hold values for: 409
      `{"purge_required": [{id, name, record_count}]}` unless `confirm_purge`;
      the values are then removed from those records.
    """
    if len(incoming) > limits.max_attributes_per_table:
        raise limit_reached("max_attributes_per_table", limits.max_attributes_per_table)

    ids = [attribute.id for attribute in incoming]
    if ids:
        foreign = await db.scalar(select(Attribute.id).where(Attribute.id.in_(ids), Attribute.table_id != table.id))
        if foreign is not None:
            raise errors_422({str(foreign): "id_in_use"})

    existing = {row.id: row for row in await get_attributes(db, table.id)}

    errors: dict[str, str] = {}
    for attribute in incoming:
        row = existing.get(attribute.id)
        if row is None:
            continue
        if row.type != attribute.type:
            errors[str(attribute.id)] = "type_immutable"
        elif row.config != attribute.config:
            errors[str(attribute.id)] = "config_immutable"
    new_targets = {
        target
        for attribute in incoming
        if attribute.id not in existing and (target := logic.referenced_table_id(attribute.type, attribute.config)) is not None
    }
    if new_targets:
        in_repository = {
            str(table_id)
            for table_id in (
                await db.scalars(
                    select(RepositoryTable.id).where(
                        RepositoryTable.repository_id == repository.id,
                        RepositoryTable.id.in_([uuid.UUID(target) for target in new_targets]),
                    )
                )
            ).all()
        }
        for attribute in incoming:
            target = logic.referenced_table_id(attribute.type, attribute.config)
            if attribute.id not in existing and target is not None and target not in in_repository:
                errors[str(attribute.id)] = "invalid_table"
    if errors:
        raise errors_422(errors)

    removed = [attribute_id for attribute_id in existing if attribute_id not in set(ids)]
    if removed:
        dependants = await attribute_dependants(db, table, {str(attribute_id) for attribute_id in removed})
        if dependants:
            raise HTTPException(status_code=409, detail={"in_use": dependants})
    if removed and not confirm_purge:
        holding = await records_holding_values(db, table.id, removed)
        needed = [
            {"id": str(attribute_id), "name": existing[attribute_id].name, "record_count": count}
            for attribute_id, count in holding.items()
            if count
        ]
        if needed:
            raise HTTPException(status_code=409, detail={"purge_required": needed})

    orphaned_images = await _images_left_behind(db, table, [existing[attribute_id] for attribute_id in removed], incoming)
    for attribute_id in removed:
        await db.delete(existing[attribute_id])
    if removed:
        await db.flush()
        await db.execute(
            update(Record)
            .where(Record.table_id == table.id)
            .values(data=Record.data.op("-")(cast([str(attribute_id) for attribute_id in removed], ARRAY(Text))))
        )
    if orphaned_images:
        await db.execute(delete(Image).where(Image.id.in_(orphaned_images)))

    rows: list[Attribute] = []
    for position, attribute in enumerate(incoming):
        row = existing.get(attribute.id)
        if row is None:
            row = Attribute(id=attribute.id, table_id=table.id, type=attribute.type, config=attribute.config)
            db.add(row)
        row.position = position
        row.name = attribute.name
        row.description = attribute.description
        row.required = attribute.required
        row.show_in_list = attribute.show_in_list
        rows.append(row)
    await db.commit()
    return rows
