# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Statistics, the pivot-table way: the rules for what a statistic is, and
how the rows the database returns become the result the frontend draws - pure
and database-free (query.py builds the SQL, saved.py runs it).

A statistic is (see schemas.StatisticIn):

    group_by:     one or two dimensions {"field", "bucket"}
    aggregation:  {"fn": count | sum | avg | min | max, "attribute_id"}
    filter:       optionally a saved filter (its conditions and deleted switch)
    display:      hidden | table | chart | both
    chart_type:   bar | line | pie (pie needs exactly one dimension)

A dimension is an attribute of a simple type - text, yes/no, number (each
value its own group), a reference (grouped by the record it points at) - or a
date, a date and time or `created_on`, which MUST say how to bucket them: by
`day`, `month` or `year`. `count` counts records (it takes no attribute); every
other function works on a number attribute and ignores records without a value.

The result for ONE dimension is a list of groups; for TWO it is a matrix (the
first dimension down the rows, the second across the columns) with the totals
of every row and column and a grand total. All totals are computed from the
records themselves, never from the cells (so an average total is the average of
all the records, not an average of averages) and are not affected by cutting
the result down: at most MAX_GROUPS groups for one dimension and MAX_CELLS cells
for two (at most MAX_COLUMNS columns), in order of the key, with `truncated` saying
that something was left out. An empty value is a group of its own (key null), last.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from app.modules.repository.filters import Field

FUNCTIONS = ("count", "sum", "avg", "min", "max")
BUCKETS = ("day", "month", "year")
DISPLAYS = ("hidden", "table", "chart", "both")
CHART_TYPES = ("bar", "line", "pie")

GROUPABLE_KINDS = frozenset({"text", "boolean", "number", "date", "datetime", "reference", "timestamp"})
BUCKETED_KINDS = frozenset({"date", "datetime", "timestamp"})

MAX_DIMENSIONS = 2
MAX_GROUPS = 100
MAX_CELLS = 100
MAX_COLUMNS = 10


def validate_statistic(
    fields: Mapping[str, Field],
    definition: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """The statistic's shape (`group_by`, `aggregation`, `display`, `chart_type`)
    checked against the fields of its table (filters.fields_for), normalized, and
    the errors - `group_by.<i>`, `aggregation`, `chart_type` -> code (empty when
    it is fine):

    - `unknown_field`, `not_groupable` (name, slug, or a type that has no groups);
    - `bucket_required` (a date needs day / month / year), `bucket_not_allowed`;
    - `duplicate_dimension`, `invalid_dimensions` (one or two are needed);
    - `invalid_function`, `attribute_not_allowed` (count counts records),
      `attribute_required` (the others need a number), `not_a_number`;
    - `pie_needs_one_dimension`.
    """
    errors: dict[str, str] = {}
    dimensions: list[dict[str, Any]] = []
    raw_dimensions = list(definition.get("group_by") or [])
    if not 1 <= len(raw_dimensions) <= MAX_DIMENSIONS:
        errors["group_by"] = "invalid_dimensions"
    seen: set[str] = set()
    for index, raw in enumerate(raw_dimensions):
        field = fields.get(raw.get("field"))
        bucket = raw.get("bucket")
        if field is None:
            errors[f"group_by.{index}"] = "unknown_field"
        elif field.key in ("name", "slug") or field.kind not in GROUPABLE_KINDS:
            errors[f"group_by.{index}"] = "not_groupable"
        elif field.kind in BUCKETED_KINDS and bucket not in BUCKETS:
            errors[f"group_by.{index}"] = "bucket_required"
        elif field.kind not in BUCKETED_KINDS and bucket is not None:
            errors[f"group_by.{index}"] = "bucket_not_allowed"
        elif field.key in seen:
            errors[f"group_by.{index}"] = "duplicate_dimension"
        else:
            seen.add(field.key)
            dimensions.append({"field": field.key, "bucket": bucket})

    aggregation = dict(definition.get("aggregation") or {})
    function = aggregation.get("fn")
    attribute_id = aggregation.get("attribute_id")
    if function not in FUNCTIONS:
        errors["aggregation"] = "invalid_function"
    elif function == "count":
        if attribute_id is not None:
            errors["aggregation"] = "attribute_not_allowed"
        else:
            aggregation = {"fn": "count", "attribute_id": None}
    elif attribute_id is None:
        errors["aggregation"] = "attribute_required"
    else:
        field = fields.get(str(attribute_id))
        if field is None:
            errors["aggregation"] = "unknown_field"
        elif field.kind != "number" or field.attribute_id is None:
            errors["aggregation"] = "not_a_number"
        else:
            aggregation = {"fn": function, "attribute_id": field.key}

    display = definition.get("display", "both")
    chart_type = definition.get("chart_type", "bar")
    if chart_type == "pie" and len(raw_dimensions) != 1:
        errors["chart_type"] = "pie_needs_one_dimension"
    return (
        {"group_by": dimensions, "aggregation": aggregation, "display": display, "chart_type": chart_type},
        errors,
    )


def attribute_ids_used(group_by: Sequence[Mapping[str, Any]], aggregation: Mapping[str, Any]) -> set[str]:
    """The attribute ids a statistic refers to (dimensions and the aggregated attribute)."""
    used = {dimension["field"] for dimension in group_by if dimension["field"] != "created_on"}
    if aggregation.get("attribute_id"):
        used.add(aggregation["attribute_id"])
    return used


# --- The result -----------------------------------------------------------------------


def to_number(value: Any) -> int | float | None:
    """A database number as a JSON number: whole values as integers."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _sort_key(kind: str, key: Any, labels: Mapping[Any, str]):
    """Order of the groups of a dimension: by key (numbers numerically, text
    without regard to case, a reference by the name it points at), empty last."""
    if key is None:
        return (1, 0, "")
    if kind == "number":
        return (0, float(key), "")
    text = labels.get(key, str(key)) if kind == "reference" else str(key)
    return (0, 0, text.casefold())


def ordered_keys(kind: str, keys: Sequence[Any], labels: Mapping[Any, str]) -> list[Any]:
    return sorted(set(keys), key=lambda key: _sort_key(kind, key, labels))


def assemble(
    *,
    kinds: Sequence[str],
    function: str,
    cells: Sequence[tuple[Any, ...]],
    totals: Sequence[Sequence[tuple[Any, ...]]],
    grand_total: Any,
    labels: Mapping[Any, str],
) -> dict[str, Any]:
    """The result of a statistic from what the database returned.

    `kinds`: the kind of each dimension. `cells`: rows of (key1[, key2], value)
    for every combination that has records. `totals`: one list per dimension of
    (key, value) rows - that dimension's own groups with the aggregate over all
    their records. `grand_total`: the aggregate over everything. `labels`: the
    name to show for each key that has one (references)."""
    dimensions = len(kinds)
    row_keys = ordered_keys(kinds[0], [key for key, _ in totals[0]], labels)
    column_keys: list[Any] = ordered_keys(kinds[1], [key for key, _ in totals[1]], labels) if dimensions == 2 else [None]

    kept_columns = column_keys[:MAX_COLUMNS] if dimensions == 2 else column_keys
    limit = MAX_GROUPS if dimensions == 1 else max(1, MAX_CELLS // max(1, len(kept_columns)))
    kept_rows = row_keys[:limit]
    truncated = len(kept_rows) < len(row_keys) or len(kept_columns) < len(column_keys)

    empty = 0 if function == "count" else None
    matrix = {(row, column): empty for row in kept_rows for column in kept_columns}
    for cell in cells:
        row = cell[0]
        column = cell[1] if dimensions == 2 else None
        if (row, column) in matrix:
            matrix[(row, column)] = to_number(cell[-1])

    def describe(kind: str, key: Any) -> dict[str, Any]:
        return {"key": float(key) if kind == "number" and key is not None else key, "label": labels.get(key)}

    row_totals = dict(totals[0])
    result: dict[str, Any] = {
        "dimensions": dimensions,
        "rows": [describe(kinds[0], key) for key in kept_rows],
        "columns": [describe(kinds[1], key) for key in kept_columns] if dimensions == 2 else [],
        "values": [[matrix[(row, column)] for column in kept_columns] for row in kept_rows],
        "row_totals": [to_number(row_totals.get(row)) for row in kept_rows],
        "column_totals": [],
        "total": to_number(grand_total),
        "truncated": truncated,
    }
    if dimensions == 2:
        column_totals = dict(totals[1])
        result["column_totals"] = [to_number(column_totals.get(column)) for column in kept_columns]
    return result
