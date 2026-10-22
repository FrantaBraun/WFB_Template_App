# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""SQL for the records of one table, built from a filter definition that
filters.normalize_filter has already validated against the table's attributes.

Nothing a user typed is ever part of the SQL text: the attribute ids that
become keys of the JSONB column are the ids of the table's own attributes
(taken from `fields`, which holds only what the table has), and every value is
a bound parameter. A field that is not in `fields` cannot get here.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Numeric, cast, func, or_, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.modules.repository.filters import DISPLAY_TIMEZONE, Field
from app.modules.repository.models import Record


def like_pattern(text: str) -> str:
    """`text` as a LIKE pattern that matches it anywhere (wildcards in it are literal)."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _value_of(kind: str, value: Any) -> Any:
    """A validated value as the Python object the column's type binds."""
    if kind == "number":
        return Decimal(str(value))
    if kind in ("date", "timestamp"):
        return date.fromisoformat(value)
    if kind == "datetime":
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    return value


def expression(field: Field) -> ColumnElement:
    """The column or JSONB value of `field`, typed for its kind."""
    if field.attribute_id is None:
        if field.key == "created_on":
            return cast(func.timezone(DISPLAY_TIMEZONE, Record.created_on), Date)
        return Record.name if field.key == "name" else Record.slug
    text = Record.data[field.attribute_id].astext
    if field.kind == "number":
        return cast(text, Numeric)
    if field.kind == "boolean":
        return cast(text, Boolean)
    if field.kind == "date":
        return cast(text, Date)
    if field.kind == "datetime":
        return cast(text, DateTime)
    return text


def condition_clause(field: Field, operator: str, value: Any = None, value2: Any = None) -> ColumnElement:
    expr = expression(field)
    if operator in ("empty", "not_empty"):
        if field.attribute_id is not None:
            present = Record.data.has_key(field.attribute_id)
            return ~present if operator == "empty" else present
        return expr == "" if operator == "empty" else expr != ""
    if field.kind == "text":
        if operator == "contains":
            return expr.ilike(like_pattern(value), escape="\\")
        return func.lower(expr) == value.lower()  # equals
    bound = _value_of(field.kind, value)
    if operator in ("eq", "equals"):
        return expr == bound
    if operator == "ne":
        return expr != bound
    if operator in ("lt", "before"):
        return expr < bound
    if operator == "lte":
        return expr <= bound
    if operator in ("gt", "after"):
        return expr > bound
    if operator == "gte":
        return expr >= bound
    if operator == "between":
        return expr.between(bound, _value_of(field.kind, value2))
    raise ValueError(f"operator {operator!r} is not handled")  # filters.OPERATORS and this must agree


def where_clauses(table_id: uuid.UUID, fields: Mapping[str, Field], definition: Mapping[str, Any]) -> list[ColumnElement]:
    """The WHERE of a records query for a normalized filter definition."""
    clauses: list[ColumnElement] = [Record.table_id == table_id]
    if not definition.get("include_deleted"):
        clauses.append(Record.deleted_on.is_(None))
    quick = definition.get("q")
    if quick:
        pattern = like_pattern(quick)
        clauses.append(or_(Record.name.ilike(pattern, escape="\\"), Record.slug.ilike(pattern, escape="\\")))
    for condition in definition.get("conditions") or []:
        clauses.append(
            condition_clause(fields[condition["field"]], condition["op"], condition.get("value"), condition.get("value2"))
        )
    return clauses


def sort_expression(field: Field) -> ColumnElement:
    """What a column is ordered by: text without regard to case, a reference by
    the name of the record it points at, the rest as they are."""
    if field.kind == "text":
        return func.lower(expression(field))
    if field.kind == "reference":
        target = aliased(Record)
        return (
            select(func.lower(target.name))
            .where(target.id == cast(expression(field), UUID(as_uuid=True)))
            .correlate(Record)
            .scalar_subquery()
        )
    return expression(field)


def order_clauses(fields: Mapping[str, Field], sort: Mapping[str, Any] | None) -> Sequence[ColumnElement]:
    """ORDER BY for a normalized `sort` (None = by name). Empty values come last
    either way, and ties are broken by creation time and id so a page never
    shuffles between requests."""
    sort = sort or {"field": "name", "dir": "asc"}
    expr = sort_expression(fields[sort["field"]])
    ordered = expr.desc().nulls_last() if sort["dir"] == "desc" else expr.asc().nulls_last()
    return [ordered, Record.created_on.asc(), Record.id.asc()]


# --- Statistics ---------------------------------------------------------------------------

_BUCKET_FORMATS = {"day": "YYYY-MM-DD", "month": "YYYY-MM", "year": "YYYY"}


def group_expression(field: Field, bucket: str | None) -> ColumnElement:
    """What a statistic groups by: a date as the text of its day, month or year
    (which sorts chronologically), a number as itself, anything else (text,
    yes/no, a reference's record id) as its text. A record without a value gets NULL."""
    if field.attribute_id is None:  # created_on, in the display time zone
        return func.to_char(func.timezone(DISPLAY_TIMEZONE, Record.created_on), _BUCKET_FORMATS[bucket])
    text = Record.data[field.attribute_id].astext
    if field.kind == "number":
        return cast(text, Numeric)
    if field.kind == "date":
        return func.to_char(cast(text, Date), _BUCKET_FORMATS[bucket])
    if field.kind == "datetime":
        return func.to_char(cast(text, DateTime), _BUCKET_FORMATS[bucket])
    return text


def number_expression(attribute_id: str) -> ColumnElement:
    """The value of a number attribute, for sum / avg / min / max."""
    return cast(Record.data[attribute_id].astext, Numeric)
