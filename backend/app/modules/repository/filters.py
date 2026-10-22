# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What a table's records can be filtered and sorted by, and the validation
of a filter definition - pure and database-free (query.py turns a validated
definition into SQL).

A filter definition (the body of a records query, and what a saved filter
stores) is:

    {"conditions": [{"field", "op", "value", "value2"}, ...],   # combined with AND
     "sort": {"field", "dir": "asc" | "desc"} | null,
     "include_deleted": false,
     "q": null}                                                # quick search in name / slug

`field` is `name`, `slug`, `created_on` or the id of an attribute of a simple
type (text, number, boolean, date, datetime, reference). Images, lists and maps
are neither filtered nor sorted by. Which operators a field takes depends on
its kind (OPERATORS); `value` is checked and normalized to the kind's format
(text: trimmed, at most MAX_FILTER_TEXT; number; true/false; "YYYY-MM-DD";
"YYYY-MM-DDTHH:MM"; a record id), `between` takes both `value` and `value2`
(inclusive, the second not before the first), `empty` / `not_empty` take
neither. Text comparison ignores case, and so does `contains`.

`created_on` is compared by its DATE in DISPLAY_TIMEZONE - a record made at
00:30 in Prague belongs to that day, not to the previous one in UTC.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.repository import logic
from app.modules.repository.logic import ValueIssue

DISPLAY_TIMEZONE = "Europe/Prague"

MAX_CONDITIONS = 20
MAX_FILTER_TEXT = 200

# Kinds of field. `timestamp` is created_on (compared by date).
OPERATORS: dict[str, tuple[str, ...]] = {
    "text": ("contains", "equals", "empty", "not_empty"),
    "number": ("eq", "ne", "lt", "lte", "gt", "gte", "between", "empty", "not_empty"),
    "boolean": ("equals", "empty", "not_empty"),
    "date": ("eq", "before", "after", "between", "empty", "not_empty"),
    "datetime": ("eq", "before", "after", "between", "empty", "not_empty"),
    "reference": ("equals", "empty", "not_empty"),
    "timestamp": ("eq", "before", "after", "between"),
}
NO_VALUE_OPERATORS = frozenset({"empty", "not_empty"})
TWO_VALUE_OPERATORS = frozenset({"between"})

# Attribute types a filter or a sort can use (the rest - image, list, map - cannot).
FILTERABLE_TYPES = ("text", "number", "boolean", "date", "datetime", "reference")


@dataclass(frozen=True)
class Field:
    """A column of the content page: a system attribute or a user's attribute.
    `attribute_id` is None for the system ones."""

    key: str
    kind: str
    attribute_id: str | None = None


SYSTEM_FIELDS = {
    "name": Field("name", "text"),
    "slug": Field("slug", "text"),
    "created_on": Field("created_on", "timestamp"),
}


def fields_for(attributes: Sequence[Any]) -> dict[str, Field]:
    """The fields of a table (its attributes need `id` and `type`): the system
    ones and every attribute of a filterable type, by key."""
    fields = dict(SYSTEM_FIELDS)
    for attribute in attributes:
        if attribute.type in FILTERABLE_TYPES:
            key = str(attribute.id)
            fields[key] = Field(key, attribute.type, key)
    return fields


def _normalize_value(kind: str, value: Any) -> Any:
    if value is None:
        raise ValueIssue("value_required")
    if kind == "text":
        if not isinstance(value, str):
            raise ValueIssue("invalid_type")
        text = value.strip()
        if text == "":
            raise ValueIssue("value_required")
        if "\x00" in text:
            raise ValueIssue("invalid_text")
        if len(text) > MAX_FILTER_TEXT:
            raise ValueIssue("too_long")
        return text
    if kind in ("number", "boolean", "date", "datetime"):
        return logic.normalize_scalar(kind, value)
    if kind == "timestamp":
        return logic.parse_date(value)
    if kind == "reference":
        if not isinstance(value, str):
            raise ValueIssue("invalid_reference")
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ValueIssue("invalid_reference") from exc
    raise ValueIssue("invalid_type")


def normalize_condition(fields: Mapping[str, Field], condition: Mapping[str, Any]) -> dict[str, Any]:
    """One condition, validated and normalized, or ValueIssue (`unknown_field`,
    `invalid_operator`, `value_required`, `invalid_range`, or the value's own code)."""
    field = fields.get(condition.get("field"))
    if field is None:
        raise ValueIssue("unknown_field")
    operator = condition.get("op")
    if operator not in OPERATORS[field.kind]:
        raise ValueIssue("invalid_operator")
    normalized: dict[str, Any] = {"field": field.key, "op": operator}
    if operator in NO_VALUE_OPERATORS:
        return normalized
    normalized["value"] = _normalize_value(field.kind, condition.get("value"))
    if operator in TWO_VALUE_OPERATORS:
        normalized["value2"] = _normalize_value(field.kind, condition.get("value2"))
        if normalized["value2"] < normalized["value"]:
            raise ValueIssue("invalid_range")
    return normalized


def normalize_filter(fields: Mapping[str, Field], definition: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """A whole filter definition, normalized, and its errors (empty when it is
    fine): `conditions.<i>` -> code for a condition, `sort` -> `unknown_field`
    for a sort on something the table does not have. Unknown keys are ignored
    here - the request schema is what refuses them."""
    errors: dict[str, str] = {}
    conditions: list[dict[str, Any]] = []
    for index, condition in enumerate(definition.get("conditions") or []):
        try:
            conditions.append(normalize_condition(fields, condition))
        except ValueIssue as issue:
            errors[f"conditions.{index}"] = issue.code
    sort = definition.get("sort")
    if sort is not None:
        if sort.get("field") not in fields:
            errors["sort"] = "unknown_field"
        elif sort.get("dir") not in ("asc", "desc"):
            errors["sort"] = "invalid_direction"
        else:
            sort = {"field": sort["field"], "dir": sort["dir"]}
    query = definition.get("q")
    if query is not None:
        query = query.strip() or None
    return (
        {"conditions": conditions, "sort": sort, "include_deleted": bool(definition.get("include_deleted")), "q": query},
        errors,
    )


def attribute_ids_used(definition: Mapping[str, Any]) -> set[str]:
    """The attribute ids a (normalized) filter definition refers to, conditions and sort."""
    used = {condition["field"] for condition in definition.get("conditions") or []}
    sort = definition.get("sort")
    if sort:
        used.add(sort["field"])
    return used - set(SYSTEM_FIELDS)
