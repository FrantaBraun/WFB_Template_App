# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What a table can be filtered and sorted by, and the validation of a filter
definition (app/modules/repository/filters.py) - pure, no database. The SQL
these definitions become is exercised in test_modules_repository_records.py."""

import uuid
from types import SimpleNamespace

import pytest

from app.modules.repository import filters
from app.modules.repository.filters import Field
from app.modules.repository.logic import ValueIssue


def _attribute(attribute_type: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), type=attribute_type)


ATTRIBUTES = {t: _attribute(t) for t in ("text", "number", "boolean", "date", "datetime", "reference", "image", "list", "map")}
FIELDS = filters.fields_for(list(ATTRIBUTES.values()))


def _key(attribute_type: str) -> str:
    return str(ATTRIBUTES[attribute_type].id)


def _condition(attribute_type: str, op: str, **values) -> dict:
    return {"field": _key(attribute_type), "op": op, **values}


def test_the_fields_of_a_table_are_the_system_ones_and_the_attributes_that_can_be_filtered():
    assert set(FIELDS) == {"name", "slug", "created_on"} | {_key(t) for t in ("text", "number", "boolean", "date", "datetime", "reference")}
    assert FIELDS["name"] == Field("name", "text")
    assert FIELDS["created_on"] == Field("created_on", "timestamp")
    assert FIELDS[_key("number")] == Field(_key("number"), "number", _key("number"))


@pytest.mark.parametrize("attribute_type", ["image", "list", "map"])
def test_images_lists_and_maps_are_neither_filtered_nor_sorted_by(attribute_type):
    assert _key(attribute_type) not in FIELDS
    with pytest.raises(ValueIssue) as raised:
        filters.normalize_condition(FIELDS, _condition(attribute_type, "empty"))
    assert raised.value.code == "unknown_field"


def test_every_operator_of_every_kind_is_accepted_with_a_fitting_value():
    values = {
        "text": {"value": "abc"},
        "number": {"value": 5},
        "boolean": {"value": True},
        "date": {"value": "2026-10-22"},
        "datetime": {"value": "2026-10-22T10:30"},
        "reference": {"value": str(uuid.uuid4())},
    }
    for kind, operators in filters.OPERATORS.items():
        if kind == "timestamp":
            continue
        for op in operators:
            condition = _condition(kind, op, **values[kind])
            if op in filters.TWO_VALUE_OPERATORS:
                condition["value2"] = values[kind]["value"] if kind != "number" else 9
                if kind == "date":
                    condition["value2"] = "2026-12-31"
                if kind == "datetime":
                    condition["value2"] = "2026-12-31T00:00"
            normalized = filters.normalize_condition(FIELDS, condition)
            assert normalized["op"] == op


@pytest.mark.parametrize(
    ("attribute_type", "op"),
    [
        ("text", "between"),
        ("text", "lt"),
        ("number", "contains"),
        ("number", "equals"),
        ("boolean", "eq"),
        ("boolean", "between"),
        ("date", "contains"),
        ("datetime", "lt"),
        ("reference", "contains"),
        ("reference", "eq"),
        ("text", "nope"),
        ("text", None),
    ],
)
def test_an_operator_the_kind_does_not_take_is_refused(attribute_type, op):
    with pytest.raises(ValueIssue) as raised:
        filters.normalize_condition(FIELDS, _condition(attribute_type, op, value="x"))

    assert raised.value.code == "invalid_operator"


def test_operators_without_a_value_ignore_any_value_given():
    normalized = filters.normalize_condition(FIELDS, _condition("text", "empty", value="ignored", value2="ignored"))

    assert normalized == {"field": _key("text"), "op": "empty"}


def test_text_values_are_trimmed_and_must_not_be_blank():
    assert filters.normalize_condition(FIELDS, _condition("text", "contains", value="  abc  "))["value"] == "abc"
    for value, code in (("   ", "value_required"), (None, "value_required"), (5, "invalid_type"), ("a" * 201, "too_long"), ("a\x00", "invalid_text")):
        with pytest.raises(ValueIssue) as raised:
            filters.normalize_condition(FIELDS, _condition("text", "contains", value=value))
        assert raised.value.code == code


@pytest.mark.parametrize(
    ("attribute_type", "value", "code"),
    [
        ("number", "5", "invalid_type"),
        ("number", True, "invalid_type"),
        ("number", None, "value_required"),
        ("boolean", "true", "invalid_type"),
        ("date", "22.10.2026", "invalid_date"),
        ("date", "2026-02-30", "invalid_date"),
        ("datetime", "2026-10-22", "invalid_datetime"),
        ("reference", "nope", "invalid_reference"),
        ("reference", 5, "invalid_reference"),
    ],
)
def test_values_are_checked_for_their_kind(attribute_type, value, code):
    op = "equals" if attribute_type in ("boolean", "reference") else "eq"
    with pytest.raises(ValueIssue) as raised:
        filters.normalize_condition(FIELDS, _condition(attribute_type, op, value=value))

    assert raised.value.code == code


def test_between_needs_two_values_in_order():
    ok = filters.normalize_condition(FIELDS, _condition("number", "between", value=1, value2=5))
    same = filters.normalize_condition(FIELDS, _condition("number", "between", value=3, value2=3))
    assert (ok["value"], ok["value2"], same["value"], same["value2"]) == (1, 5, 3, 3)

    for condition, code in (
        (_condition("number", "between", value=5, value2=1), "invalid_range"),
        (_condition("number", "between", value=5), "value_required"),
        (_condition("date", "between", value="2026-12-31", value2="2026-01-01"), "invalid_range"),
        (_condition("datetime", "between", value="2026-10-22T10:00", value2="2026-10-22T09:00"), "invalid_range"),
    ):
        with pytest.raises(ValueIssue) as raised:
            filters.normalize_condition(FIELDS, condition)
        assert raised.value.code == code


def test_created_on_is_filtered_by_date_and_cannot_be_empty():
    assert filters.normalize_condition(FIELDS, {"field": "created_on", "op": "after", "value": "2026-01-01"})["value"] == "2026-01-01"
    for condition, code in (
        ({"field": "created_on", "op": "empty"}, "invalid_operator"),
        ({"field": "created_on", "op": "after", "value": "2026-01-01T10:00"}, "invalid_date"),
    ):
        with pytest.raises(ValueIssue) as raised:
            filters.normalize_condition(FIELDS, condition)
        assert raised.value.code == code


@pytest.mark.parametrize("field", ["nope", "", None, "id", "deleted_on", "'; drop table x; --", "data->>'x'"])
def test_an_unknown_field_is_refused(field):
    with pytest.raises(ValueIssue) as raised:
        filters.normalize_condition(FIELDS, {"field": field, "op": "empty"})

    assert raised.value.code == "unknown_field"


# --- A whole definition ---------------------------------------------------------------


def test_a_definition_is_normalized_with_its_defaults():
    definition, errors = filters.normalize_filter(FIELDS, {})

    assert errors == {}
    assert definition == {"conditions": [], "sort": None, "include_deleted": False, "q": None}


def test_a_definition_keeps_its_parts():
    definition, errors = filters.normalize_filter(
        FIELDS,
        {
            "conditions": [_condition("text", "contains", value=" a "), {"field": "name", "op": "empty"}],
            "sort": {"field": "name", "dir": "desc", "extra": 1},
            "include_deleted": True,
            "q": "  dune ",
        },
    )

    assert errors == {}
    assert definition["conditions"] == [{"field": _key("text"), "op": "contains", "value": "a"}, {"field": "name", "op": "empty"}]
    assert definition["sort"] == {"field": "name", "dir": "desc"}
    assert definition["include_deleted"] is True
    assert definition["q"] == "dune"


def test_a_blank_quick_search_is_none():
    assert filters.normalize_filter(FIELDS, {"q": "   "})[0]["q"] is None


def test_errors_are_keyed_by_condition_and_by_sort():
    definition, errors = filters.normalize_filter(
        FIELDS,
        {
            "conditions": [
                _condition("text", "contains", value="ok"),
                _condition("text", "lt", value="x"),
                {"field": "nope", "op": "empty"},
            ],
            "sort": {"field": _key("image"), "dir": "asc"},
        },
    )

    assert errors == {"conditions.1": "invalid_operator", "conditions.2": "unknown_field", "sort": "unknown_field"}
    assert [c["op"] for c in definition["conditions"]] == ["contains"]


def test_a_sort_direction_other_than_asc_or_desc_is_an_error():
    _, errors = filters.normalize_filter(FIELDS, {"sort": {"field": "name", "dir": "up"}})

    assert errors == {"sort": "invalid_direction"}


def test_the_attribute_ids_a_definition_uses_leave_out_the_system_fields():
    definition, _ = filters.normalize_filter(
        FIELDS,
        {
            "conditions": [_condition("text", "empty"), {"field": "name", "op": "empty"}, {"field": "created_on", "op": "before", "value": "2026-01-01"}],
            "sort": {"field": _key("number"), "dir": "asc"},
        },
    )

    assert filters.attribute_ids_used(definition) == {_key("text"), _key("number")}
    assert filters.attribute_ids_used({}) == set()
