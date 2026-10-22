# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules of a statistic and how the database's rows become its result
(app/modules/repository/pivot.py) - pure, no database. The SQL is exercised in
test_modules_repository_statistics.py."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.repository import filters, pivot


def _attribute(attribute_type: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), type=attribute_type)


ATTRIBUTES = {t: _attribute(t) for t in ("text", "number", "boolean", "date", "datetime", "reference", "image", "list", "map")}
FIELDS = filters.fields_for(list(ATTRIBUTES.values()))


def _key(attribute_type: str) -> str:
    return str(ATTRIBUTES[attribute_type].id)


def _validate(group_by, aggregation=None, **extra):
    return pivot.validate_statistic(FIELDS, {"group_by": group_by, "aggregation": aggregation or {"fn": "count"}, **extra})


# --- What a statistic may be -----------------------------------------------------------


def test_a_statistic_is_normalized_with_its_defaults():
    definition, errors = _validate([{"field": _key("text")}])

    assert errors == {}
    assert definition == {
        "group_by": [{"field": _key("text"), "bucket": None}],
        "aggregation": {"fn": "count", "attribute_id": None},
        "display": "both",
        "chart_type": "bar",
    }


@pytest.mark.parametrize("kind", ["text", "boolean", "number", "reference"])
def test_simple_kinds_are_grouped_by_their_value(kind):
    _, errors = _validate([{"field": _key(kind)}])

    assert errors == {}


@pytest.mark.parametrize("bucket", ["day", "month", "year"])
@pytest.mark.parametrize("field", ["date", "datetime", "created_on"])
def test_dates_are_grouped_by_a_bucket(field, bucket):
    key = "created_on" if field == "created_on" else _key(field)

    definition, errors = _validate([{"field": key, "bucket": bucket}])

    assert errors == {}
    assert definition["group_by"] == [{"field": key, "bucket": bucket}]


@pytest.mark.parametrize("field", ["date", "datetime", "created_on"])
@pytest.mark.parametrize("bucket", [None, "week", "hour", ""])
def test_a_date_without_a_valid_bucket_is_refused(field, bucket):
    key = "created_on" if field == "created_on" else _key(field)

    _, errors = _validate([{"field": key, "bucket": bucket}])

    assert errors == {"group_by.0": "bucket_required"}


@pytest.mark.parametrize("kind", ["text", "boolean", "number", "reference"])
def test_a_bucket_on_something_that_is_not_a_date_is_refused(kind):
    _, errors = _validate([{"field": _key(kind), "bucket": "month"}])

    assert errors == {"group_by.0": "bucket_not_allowed"}


@pytest.mark.parametrize("field", ["name", "slug"])
def test_the_name_and_the_slug_have_no_groups_worth_the_name(field):
    _, errors = _validate([{"field": field}])

    assert errors == {"group_by.0": "not_groupable"}


@pytest.mark.parametrize("field", ["nope", "", None, "id", "deleted_on", "data->>'x'"])
def test_an_unknown_dimension_is_refused(field):
    _, errors = _validate([{"field": field}])

    assert errors == {"group_by.0": "unknown_field"}


@pytest.mark.parametrize("kind", ["image", "list", "map"])
def test_images_lists_and_maps_are_not_dimensions(kind):
    _, errors = _validate([{"field": _key(kind)}])

    assert errors == {"group_by.0": "unknown_field"}


def test_one_or_two_dimensions_are_needed():
    assert _validate([])[1] == {"group_by": "invalid_dimensions"}
    three = [{"field": _key("text")}, {"field": _key("boolean")}, {"field": _key("number")}]
    assert _validate(three)[1].get("group_by") == "invalid_dimensions"
    assert _validate([{"field": _key("text")}, {"field": _key("boolean")}])[1] == {}


def test_the_same_field_cannot_be_two_dimensions():
    _, errors = _validate([{"field": _key("text")}, {"field": _key("text")}])

    assert errors == {"group_by.1": "duplicate_dimension"}


@pytest.mark.parametrize("fn", ["sum", "avg", "min", "max"])
def test_the_other_functions_work_on_a_number(fn):
    definition, errors = _validate([{"field": _key("text")}], {"fn": fn, "attribute_id": _key("number")})

    assert errors == {}
    assert definition["aggregation"] == {"fn": fn, "attribute_id": _key("number")}


def test_count_counts_records_and_takes_no_attribute():
    assert _validate([{"field": _key("text")}], {"fn": "count"})[1] == {}
    assert _validate([{"field": _key("text")}], {"fn": "count", "attribute_id": None})[1] == {}
    assert _validate([{"field": _key("text")}], {"fn": "count", "attribute_id": _key("number")})[1] == {"aggregation": "attribute_not_allowed"}


@pytest.mark.parametrize(
    ("aggregation", "code"),
    [
        ({"fn": "median"}, "invalid_function"),
        ({"fn": None}, "invalid_function"),
        ({"fn": "sum"}, "attribute_required"),
        ({"fn": "sum", "attribute_id": str(uuid.uuid4())}, "unknown_field"),
        ({"fn": "sum", "attribute_id": "name"}, "not_a_number"),
        ({"fn": "avg", "attribute_id": "created_on"}, "not_a_number"),
    ],
)
def test_aggregation_errors(aggregation, code):
    _, errors = _validate([{"field": _key("text")}], aggregation)

    assert errors == {"aggregation": code}


@pytest.mark.parametrize("kind", ["text", "boolean", "date", "datetime", "reference"])
def test_only_a_number_can_be_summed(kind):
    _, errors = _validate([{"field": _key("text")}], {"fn": "sum", "attribute_id": _key(kind)})

    assert errors == {"aggregation": "not_a_number"}


def test_a_pie_needs_exactly_one_dimension():
    one = _validate([{"field": _key("text")}], chart_type="pie")[1]
    two = _validate([{"field": _key("text")}, {"field": _key("boolean")}], chart_type="pie")[1]

    assert one == {}
    assert two == {"chart_type": "pie_needs_one_dimension"}
    assert _validate([{"field": _key("text")}, {"field": _key("boolean")}], chart_type="bar")[1] == {}
    assert _validate([{"field": _key("text")}, {"field": _key("boolean")}], chart_type="line")[1] == {}


def test_a_missing_aggregation_is_refused():
    _, errors = pivot.validate_statistic(FIELDS, {"group_by": [{"field": _key("text")}]})

    assert errors == {"aggregation": "invalid_function"}


def test_the_attribute_ids_a_statistic_uses_leave_out_created_on():
    group_by = [{"field": "created_on", "bucket": "month"}, {"field": _key("text"), "bucket": None}]
    aggregation = {"fn": "sum", "attribute_id": _key("number")}

    assert pivot.attribute_ids_used(group_by, aggregation) == {_key("text"), _key("number")}
    assert pivot.attribute_ids_used([{"field": "created_on", "bucket": "day"}], {"fn": "count", "attribute_id": None}) == set()


# --- Numbers and ordering ---------------------------------------------------------------


def test_numbers_become_json_numbers():
    assert pivot.to_number(Decimal("12")) == 12 and isinstance(pivot.to_number(Decimal("12")), int)
    assert pivot.to_number(Decimal("12.50")) == 12.5
    assert pivot.to_number(Decimal("10.000")) == 10
    assert pivot.to_number(None) is None
    assert pivot.to_number(7) == 7


def test_keys_are_ordered_by_kind_with_empty_last():
    assert pivot.ordered_keys("number", [Decimal("10"), Decimal("2"), None, Decimal("-1")], {}) == [Decimal("-1"), Decimal("2"), Decimal("10"), None]
    assert pivot.ordered_keys("text", ["banana", "Apple", None, "cherry"], {}) == ["Apple", "banana", "cherry", None]
    assert pivot.ordered_keys("date", ["2026-03", "2025-12", "2026-01"], {}) == ["2025-12", "2026-01", "2026-03"]
    assert pivot.ordered_keys("boolean", ["true", None, "false"], {}) == ["false", "true", None]


def test_references_are_ordered_by_the_name_they_point_at():
    labels = {"id-1": "Zed", "id-2": "adam", "id-3": "Mia"}

    assert pivot.ordered_keys("reference", ["id-1", "id-2", None, "id-3"], labels) == ["id-2", "id-3", "id-1", None]


# --- Assembling the result ----------------------------------------------------------------


def test_one_dimension_is_a_list_of_groups_with_a_total():
    result = pivot.assemble(
        kinds=["text"],
        function="sum",
        cells=[("b", Decimal("5")), ("a", Decimal("2.5")), (None, Decimal("1"))],
        totals=[[("b", Decimal("5")), ("a", Decimal("2.5")), (None, Decimal("1"))]],
        grand_total=Decimal("8.5"),
        labels={},
    )

    assert result == {
        "dimensions": 1,
        "rows": [{"key": "a", "label": None}, {"key": "b", "label": None}, {"key": None, "label": None}],
        "columns": [],
        "values": [[2.5], [5], [1]],
        "row_totals": [2.5, 5, 1],
        "column_totals": [],
        "total": 8.5,
        "truncated": False,
    }


def test_two_dimensions_are_a_matrix_with_row_and_column_totals():
    result = pivot.assemble(
        kinds=["text", "boolean"],
        function="count",
        cells=[("a", "true", 2), ("a", "false", 1), ("b", "true", 4)],
        totals=[[("a", 3), ("b", 4)], [("true", 6), ("false", 1)]],
        grand_total=7,
        labels={},
    )

    assert [row["key"] for row in result["rows"]] == ["a", "b"]
    assert [column["key"] for column in result["columns"]] == ["false", "true"]
    assert result["values"] == [[1, 2], [0, 4]]  # a combination with no records counts 0
    assert (result["row_totals"], result["column_totals"], result["total"]) == ([3, 4], [1, 6], 7)
    assert result["truncated"] is False


def test_a_combination_with_no_records_is_empty_for_everything_but_count():
    result = pivot.assemble(
        kinds=["text", "text"],
        function="avg",
        cells=[("a", "x", Decimal("2")), ("b", "y", Decimal("4"))],
        totals=[[("a", Decimal("2")), ("b", Decimal("4"))], [("x", Decimal("2")), ("y", Decimal("4"))]],
        grand_total=Decimal("3"),
        labels={},
    )

    assert result["values"] == [[2, None], [None, 4]]


def test_the_totals_come_from_the_database_not_from_the_cells():
    # An average of averages would be 3; the database says the real average is 4.
    result = pivot.assemble(
        kinds=["text"],
        function="avg",
        cells=[("a", Decimal("2")), ("b", Decimal("4"))],
        totals=[[("a", Decimal("2")), ("b", Decimal("4"))]],
        grand_total=Decimal("4"),
        labels={},
    )

    assert result["total"] == 4


def test_references_carry_the_name_they_point_at_and_are_ordered_by_it():
    result = pivot.assemble(
        kinds=["reference"],
        function="count",
        cells=[("id-1", 3), ("id-2", 5), (None, 1)],
        totals=[[("id-1", 3), ("id-2", 5), (None, 1)]],
        grand_total=9,
        labels={"id-1": "Zed", "id-2": "adam"},
    )

    assert [(row["key"], row["label"]) for row in result["rows"]] == [("id-2", "adam"), ("id-1", "Zed"), (None, None)]
    assert result["values"] == [[5], [3], [1]]


def test_number_keys_are_numbers():
    result = pivot.assemble(
        kinds=["number"],
        function="count",
        cells=[(Decimal("10"), 1), (Decimal("2.5"), 2)],
        totals=[[(Decimal("10"), 1), (Decimal("2.5"), 2)]],
        grand_total=3,
        labels={},
    )

    assert [row["key"] for row in result["rows"]] == [2.5, 10.0]


def test_one_dimension_is_cut_to_the_group_limit_and_says_so():
    keys = [f"k{index:03d}" for index in range(pivot.MAX_GROUPS + 20)]
    result = pivot.assemble(
        kinds=["text"],
        function="count",
        cells=[(key, 1) for key in keys],
        totals=[[(key, 1) for key in keys]],
        grand_total=len(keys),
        labels={},
    )

    assert len(result["rows"]) == pivot.MAX_GROUPS
    assert result["truncated"] is True
    assert result["total"] == len(keys)  # the total still counts everything
    assert result["rows"][0]["key"] == "k000"


def test_one_dimension_at_the_limit_is_not_cut():
    keys = [f"k{index:03d}" for index in range(pivot.MAX_GROUPS)]
    result = pivot.assemble(
        kinds=["text"], function="count", cells=[(key, 1) for key in keys], totals=[[(key, 1) for key in keys]], grand_total=len(keys), labels={}
    )

    assert len(result["rows"]) == pivot.MAX_GROUPS
    assert result["truncated"] is False


def test_two_dimensions_are_cut_to_the_cell_limit_and_the_column_limit():
    rows = [f"r{index:03d}" for index in range(40)]
    columns = [f"c{index:03d}" for index in range(15)]
    cells = [(row, column, 1) for row in rows for column in columns]
    result = pivot.assemble(
        kinds=["text", "text"],
        function="count",
        cells=cells,
        totals=[[(row, len(columns)) for row in rows], [(column, len(rows)) for column in columns]],
        grand_total=len(cells),
        labels={},
    )

    assert len(result["columns"]) == pivot.MAX_COLUMNS
    assert len(result["rows"]) == pivot.MAX_CELLS // pivot.MAX_COLUMNS
    assert len(result["rows"]) * len(result["columns"]) <= pivot.MAX_CELLS
    assert result["truncated"] is True
    assert result["total"] == 600
    assert all(len(row) == len(result["columns"]) for row in result["values"])


def test_nothing_at_all_is_an_empty_result():
    result = pivot.assemble(kinds=["text"], function="count", cells=[], totals=[[]], grand_total=0, labels={})

    assert (result["rows"], result["values"], result["total"], result["truncated"]) == ([], [], 0, False)
