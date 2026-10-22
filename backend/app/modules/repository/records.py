# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Records: creating, editing, deleting (softly, and for good), listing with
filters, sorting and paging, and the search the reference picker uses. The
values' own rules are in logic.py, the filters' in filters.py and query.py;
this is where they meet the database.

What a refusal looks like is described in service.py. Specific to records:

- 422 `{"errors": {"name": code, <attribute id>: code, "<attribute id>.<key>": code}}`
  for values that cannot be stored - codes are logic.py's, plus
  `invalid_reference` (the record is not in the table the attribute points at,
  or is deleted - a reference that is ALREADY on the record may stay on a record
  deleted since) and `invalid_image` (not the caller's, or on another record);
- 409 `{"errors": {"record": "deleted"}}` when editing a deleted record (restore
  it first) and `{"errors": {"record": "not_deleted"}}` when deleting for good
  one that is not, 409 `{"referenced_by": [...], "count": n}` when something
  still refers to the record, and 409 `{"limit": ...}` at max_records_per_table.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.repository import filters, images, logic, query
from app.modules.repository.config import RepositoryConfig
from app.modules.repository.logic import AttributeSpec, NormalizedData, ValueIssue
from app.modules.repository.models import Attribute, Record, Repository, RepositoryTable
from app.modules.repository.schemas import (
    RecordCreate,
    RecordHit,
    RecordHitPage,
    RecordListItem,
    RecordOut,
    RecordPage,
    RecordQuery,
    RecordUpdate,
    RefInfo,
)
from app.modules.repository.service import commit_or_slug_taken, errors_422, limit_reached, resolve_slug, taken_slugs

SEARCH_PAGE_SIZE = 20
REFERRERS_SHOWN = 10


def specs_of(attributes: Sequence[Attribute]) -> list[AttributeSpec]:
    return [
        AttributeSpec(id=str(attribute.id), type=attribute.type, required=attribute.required, config=attribute.config)
        for attribute in attributes
    ]


async def get_record(db: AsyncSession, table: RepositoryTable, slug: str) -> Record:
    record = await db.scalar(select(Record).where(Record.table_id == table.id, Record.slug == slug))
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


# --- References ---------------------------------------------------------------------


async def resolve_refs(db: AsyncSession, repository: Repository, ids: set[str]) -> dict[str, RefInfo]:
    """RefInfo for the records among `ids` that are in this repository."""
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(Record.id, Record.name, Record.slug, Record.deleted_on, RepositoryTable.slug, RepositoryTable.name)
            .join(RepositoryTable, Record.table_id == RepositoryTable.id)
            .where(RepositoryTable.repository_id == repository.id, Record.id.in_([uuid.UUID(i) for i in ids]))
        )
    ).all()
    return {
        str(record_id): RefInfo(name=name, slug=slug, table_slug=table_slug, table_name=table_name, deleted=deleted_on is not None)
        for record_id, name, slug, deleted_on, table_slug, table_name in rows
    }


async def _check_references(
    db: AsyncSession,
    repository: Repository,
    attributes: Sequence[Attribute],
    normalized: NormalizedData,
    already_there: set[str],
) -> dict[str, str]:
    """Errors for references that point nowhere usable: not a record of the table
    the attribute points at (in this repository), or deleted - unless it is
    already on the record (`already_there`)."""
    bad: set[str] = set()
    for target, ids in normalized.references.items():
        rows = (
            await db.execute(
                select(Record.id, Record.deleted_on)
                .join(RepositoryTable, Record.table_id == RepositoryTable.id)
                .where(
                    Record.table_id == uuid.UUID(target),
                    RepositoryTable.repository_id == repository.id,
                    Record.id.in_([uuid.UUID(i) for i in ids]),
                )
            )
        ).all()
        usable = {str(record_id) for record_id, deleted_on in rows if deleted_on is None or str(record_id) in already_there}
        bad |= ids - usable
    errors: dict[str, str] = {}
    for attribute in attributes:
        if logic.referenced_table_id(attribute.type, attribute.config) is None:
            continue
        value = normalized.data.get(str(attribute.id))
        if value is None:
            continue
        if attribute.type == "reference":
            if value in bad:
                errors[str(attribute.id)] = "invalid_reference"
        else:
            for key, element in value.items():
                if element in bad:
                    errors[f"{attribute.id}.{key}"] = "invalid_reference"
    return errors


async def _check_images(
    db: AsyncSession, user: User, record_id: uuid.UUID | None, attributes: Sequence[Attribute], normalized: NormalizedData
) -> dict[str, str]:
    usable = await images.usable_image_ids(db, user, record_id, normalized.image_ids)
    bad = normalized.image_ids - usable
    errors: dict[str, str] = {}
    if not bad:
        return errors
    for attribute in attributes:
        value = normalized.data.get(str(attribute.id))
        if value is None:
            continue
        if attribute.type == "image":
            if value in bad:
                errors[str(attribute.id)] = "invalid_image"
        elif attribute.type in ("list", "map") and attribute.config.get("element_type") == "image":
            for key, element in value.items():
                if element in bad:
                    errors[f"{attribute.id}.{key}"] = "invalid_image"
    return errors


async def _normalize_data(
    db: AsyncSession,
    user: User,
    repository: Repository,
    attributes: Sequence[Attribute],
    data: Mapping[str, Any],
    record: Record | None,
) -> NormalizedData:
    """The values to store, or 422. Raises before anything is written."""
    normalized = logic.normalize_record_data(specs_of(attributes), data)
    if normalized.errors:
        raise errors_422(normalized.errors)
    already_there = logic.reference_ids_in(attributes, record.data) if record is not None else set()
    errors = await _check_references(db, repository, attributes, normalized, already_there)
    errors.update(await _check_images(db, user, record.id if record is not None else None, attributes, normalized))
    if errors:
        raise errors_422(errors)
    return normalized


def _clean_name(value: Any) -> str:
    try:
        return logic.normalize_record_name(value)
    except ValueIssue as issue:
        raise errors_422({"name": issue.code}) from issue


# --- Output --------------------------------------------------------------------------


async def record_out(db: AsyncSession, repository: Repository, attributes: Sequence[Attribute], record: Record) -> RecordOut:
    refs = await resolve_refs(db, repository, logic.reference_ids_in(attributes, record.data))
    return RecordOut.model_validate(record).model_copy(update={"refs": refs})


# --- Create, edit, delete ----------------------------------------------------------------


async def create_record(
    db: AsyncSession,
    user: User,
    repository: Repository,
    table: RepositoryTable,
    attributes: Sequence[Attribute],
    body: RecordCreate,
    limits: RepositoryConfig,
) -> Record:
    count = await db.scalar(select(func.count(Record.id)).where(Record.table_id == table.id))
    if count >= limits.max_records_per_table:
        raise limit_reached("max_records_per_table", limits.max_records_per_table)
    name = _clean_name(body.name)
    normalized = await _normalize_data(db, user, repository, attributes, body.data, None)
    taken = await taken_slugs(db, Record.slug, Record.table_id, table.id)
    record = Record(
        table_id=table.id,
        name=name,
        slug=resolve_slug(name, body.slug, taken),
        data=normalized.data,
    )
    db.add(record)
    await db.flush()
    await images.sync_record_images(db, record.id, normalized.image_ids)
    await commit_or_slug_taken(db)
    await db.refresh(record)
    return record


async def update_record(
    db: AsyncSession,
    user: User,
    repository: Repository,
    table: RepositoryTable,
    attributes: Sequence[Attribute],
    record: Record,
    body: RecordUpdate,
) -> Record:
    if record.deleted_on is not None:
        raise HTTPException(status_code=409, detail={"errors": {"record": "deleted"}})
    changes = body.model_dump(exclude_unset=True)
    new_name = _clean_name(changes["name"]) if changes.get("name") is not None else None
    normalized = None
    if changes.get("data") is not None:
        normalized = await _normalize_data(db, user, repository, attributes, changes["data"], record)
    if changes.get("slug") is not None and changes["slug"] != record.slug:
        taken = await taken_slugs(db, Record.slug, Record.table_id, table.id)
        record.slug = resolve_slug(new_name or record.name, changes["slug"], taken, own_slug=record.slug)
    if new_name is not None:
        record.name = new_name
    if normalized is not None:
        record.data = normalized.data
        await db.flush()
        await images.sync_record_images(db, record.id, normalized.image_ids)
    await commit_or_slug_taken(db)
    await db.refresh(record)
    return record


async def soft_delete(db: AsyncSession, record: Record) -> None:
    """Marks the record deleted (it can be restored). Deleting a deleted one changes nothing."""
    if record.deleted_on is None:
        record.deleted_on = datetime.now(timezone.utc)
        await db.commit()


async def restore(db: AsyncSession, record: Record) -> None:
    """Brings a deleted record back; restoring one that is not deleted changes nothing."""
    if record.deleted_on is not None:
        record.deleted_on = None
        await db.commit()


async def referrers_of(db: AsyncSession, repository: Repository, record: Record) -> tuple[list[dict[str, str]], int]:
    """The records (of any table of the repository, deleted ones included) that
    point at `record`, as {table, table_slug, record, record_slug} (the first
    REFERRERS_SHOWN), and how many there are. A record's own reference to itself
    does not count."""
    attributes = (
        await db.execute(
            select(Attribute.table_id, Attribute.id, Attribute.type)
            .join(RepositoryTable, Attribute.table_id == RepositoryTable.id)
            .where(
                RepositoryTable.repository_id == repository.id,
                Attribute.config["table_id"].astext == str(record.table_id),
            )
        )
    ).all()
    by_table: dict[uuid.UUID, list] = {}
    for table_id, attribute_id, attribute_type in attributes:
        key = str(attribute_id)
        if attribute_type == "reference":
            clause = Record.data[key].astext == str(record.id)
        else:  # a list or map of references: the id is one of the object's values
            clause = func.jsonb_path_exists(
                Record.data,
                cast(f'$."{key}".* ? (@ == $id)', JSONPATH),
                cast({"id": str(record.id)}, JSONB),
            )
        by_table.setdefault(table_id, []).append(clause)
    if not by_table:
        return [], 0
    condition = or_(*[(Record.table_id == table_id) & or_(*clauses) for table_id, clauses in by_table.items()])
    where = (condition, Record.id != record.id)
    count = await db.scalar(select(func.count(Record.id)).where(*where))
    rows = (
        await db.execute(
            select(RepositoryTable.name, RepositoryTable.slug, Record.name, Record.slug)
            .join(RepositoryTable, Record.table_id == RepositoryTable.id)
            .where(*where)
            .order_by(RepositoryTable.position, func.lower(Record.name))
            .limit(REFERRERS_SHOWN)
        )
    ).all()
    shown = [
        {"table": table_name, "table_slug": table_slug, "record": record_name, "record_slug": record_slug}
        for table_name, table_slug, record_name, record_slug in rows
    ]
    return shown, count


async def purge(db: AsyncSession, repository: Repository, record: Record) -> None:
    """Deletes a record that is already deleted, for good (its images go with it) -
    unless another record still points at it."""
    if record.deleted_on is None:
        raise HTTPException(status_code=409, detail={"errors": {"record": "not_deleted"}})
    shown, count = await referrers_of(db, repository, record)
    if count:
        raise HTTPException(status_code=409, detail={"referenced_by": shown, "count": count})
    await db.delete(record)
    await db.commit()


# --- Listing and searching -----------------------------------------------------------------


async def query_records(
    db: AsyncSession,
    repository: Repository,
    table: RepositoryTable,
    attributes: Sequence[Attribute],
    body: RecordQuery,
) -> RecordPage:
    """One page of the table's records for a filter and a sort. Each item carries
    only the values of the attributes shown on the content page."""
    fields = filters.fields_for(attributes)
    definition, errors = filters.normalize_filter(fields, body.model_dump(include={"conditions", "sort", "include_deleted", "q"}))
    if errors:
        raise errors_422(errors)
    clauses = query.where_clauses(table.id, fields, definition)
    total = await db.scalar(select(func.count(Record.id)).where(*clauses))
    rows = (
        await db.scalars(
            select(Record)
            .where(*clauses)
            .order_by(*query.order_clauses(fields, definition["sort"]))
            .offset((body.page - 1) * body.page_size)
            .limit(body.page_size)
        )
    ).all()
    listed = [attribute for attribute in attributes if attribute.show_in_list]
    items = []
    ids: set[str] = set()
    for record in rows:
        values = {str(a.id): record.data[str(a.id)] for a in listed if str(a.id) in record.data}
        ids |= logic.reference_ids_in(listed, values)
        items.append(
            RecordListItem(
                id=record.id, slug=record.slug, name=record.name, created_on=record.created_on, deleted_on=record.deleted_on, values=values
            )
        )
    return RecordPage(
        items=items, total=total, page=body.page, page_size=body.page_size, refs=await resolve_refs(db, repository, ids)
    )


async def search_records(db: AsyncSession, table: RepositoryTable, text: str | None, page: int) -> RecordHitPage:
    """The picker of a reference: the table's records that are not deleted, by name,
    those whose name or slug contains `text` when given."""
    clauses = [Record.table_id == table.id, Record.deleted_on.is_(None)]
    if text and text.strip():
        pattern = query.like_pattern(text.strip())
        clauses.append(or_(Record.name.ilike(pattern, escape="\\"), Record.slug.ilike(pattern, escape="\\")))
    total = await db.scalar(select(func.count(Record.id)).where(*clauses))
    rows = (
        await db.scalars(
            select(Record)
            .where(*clauses)
            .order_by(func.lower(Record.name), Record.created_on, Record.id)
            .offset((page - 1) * SEARCH_PAGE_SIZE)
            .limit(SEARCH_PAGE_SIZE)
        )
    ).all()
    return RecordHitPage(
        items=[RecordHit(id=record.id, name=record.name, slug=record.slug) for record in rows],
        total=total,
        page=page,
        page_size=SEARCH_PAGE_SIZE,
    )
