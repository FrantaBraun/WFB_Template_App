# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The repository module's rules (app/modules/repository/logic.py) - pure,
no database."""

import uuid

import pytest

from app.modules.repository import logic
from app.modules.repository.logic import AttributeSpec, ValueIssue

TABLE_ID = str(uuid.uuid4())
RECORD_ID = str(uuid.uuid4())
IMAGE_ID = str(uuid.uuid4())


def _spec(attribute_type, *, required=False, **config) -> AttributeSpec:
    return AttributeSpec(id=str(uuid.uuid4()), type=attribute_type, required=required, config=config)


def _normalize(spec: AttributeSpec, value):
    return logic.normalize_record_data([spec], {spec.id: value})


# --- Slugs ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Moje knihovna", "moje-knihovna"),
        ("Příliš žluťoučký kůň", "prilis-zlutoucky-kun"),
        ("  --Hello,   World!!  ", "hello-world"),
        ("Łódź đ ø ß", "lodz-d-o-ss"),
        ("Vinyl 2024/25", "vinyl-2024-25"),
        ("!!!", ""),
        ("", ""),
    ],
)
def test_slugify(text, slug):
    assert logic.slugify(text) == slug


def test_slugify_is_cut_to_the_maximum_length_without_a_trailing_hyphen():
    slug = logic.slugify("a" * 79 + " b")

    assert len(slug) <= logic.MAX_SLUG_LENGTH
    assert not slug.endswith("-")


def test_unique_slug_is_the_plain_one_when_it_is_free():
    assert logic.unique_slug("Knihy", {"filmy"}) == "knihy"


def test_unique_slug_appends_the_first_free_number():
    assert logic.unique_slug("Knihy", {"knihy"}) == "knihy-2"
    assert logic.unique_slug("Knihy", {"knihy", "knihy-2", "knihy-3"}) == "knihy-4"


@pytest.mark.parametrize("name", ["New", "edit", "Tables"])
def test_unique_slug_never_returns_a_reserved_slug(name):
    assert logic.unique_slug(name, set()) == f"{name.lower()}-2"


def test_unique_slug_of_a_name_without_letters_falls_back_to_item():
    assert logic.unique_slug("???", set()) == "item"


def test_unique_slug_keeps_the_suffix_within_the_maximum_length():
    base = "a" * logic.MAX_SLUG_LENGTH

    slug = logic.unique_slug(base, {base})

    assert slug.endswith("-2")
    assert len(slug) == logic.MAX_SLUG_LENGTH


@pytest.mark.parametrize(
    ("slug", "problem"),
    [
        ("knihy", None),
        ("vinyl-2024", None),
        ("a", None),
        ("", "invalid"),
        ("Knihy", "invalid"),
        ("knihy-", "invalid"),
        ("-knihy", "invalid"),
        ("kni--hy", "invalid"),
        ("kn ihy", "invalid"),
        ("knihy_2", "invalid"),
        ("a" * 81, "invalid"),
        ("new", "reserved"),
        ("edit", "reserved"),
        ("tables", "reserved"),
    ],
)
def test_slug_problem(slug, problem):
    assert logic.slug_problem(slug) == problem


# --- Attribute configuration ----------------------------------------------------


@pytest.mark.parametrize("attribute_type", ["text", "number", "boolean", "date", "datetime", "image"])
def test_simple_types_take_no_configuration(attribute_type):
    assert logic.canonical_config(attribute_type, {}) == {}
    assert logic.canonical_config(attribute_type, None) == {}
    with pytest.raises(ValueError):
        logic.canonical_config(attribute_type, {"table_id": TABLE_ID})


def test_reference_needs_a_table_id_and_keeps_it_as_a_string():
    assert logic.canonical_config("reference", {"table_id": TABLE_ID.upper()}) == {"table_id": TABLE_ID}
    assert logic.canonical_config("reference", {"table_id": uuid.UUID(TABLE_ID)}) == {"table_id": TABLE_ID}
    for bad in ({}, {"table_id": "nope"}, {"table_id": 5}, {"table_id": TABLE_ID, "other": 1}):
        with pytest.raises(ValueError):
            logic.canonical_config("reference", bad)


@pytest.mark.parametrize("attribute_type", ["list", "map"])
def test_list_and_map_need_a_simple_element_type(attribute_type):
    assert logic.canonical_config(attribute_type, {"element_type": "number"}) == {"element_type": "number"}
    assert logic.canonical_config(attribute_type, {"element_type": "reference", "table_id": TABLE_ID}) == {
        "element_type": "reference",
        "table_id": TABLE_ID,
    }
    for bad in (
        {},
        {"element_type": "list"},
        {"element_type": "map"},
        {"element_type": "nope"},
        {"element_type": "reference"},
        {"element_type": "text", "table_id": TABLE_ID},
        {"element_type": "text", "other": 1},
    ):
        with pytest.raises(ValueError):
            logic.canonical_config(attribute_type, bad)


def test_unknown_type_is_refused():
    with pytest.raises(ValueError):
        logic.canonical_config("blob", {})


def test_referenced_table_id_for_references_and_lists_of_references_only():
    assert logic.referenced_table_id("reference", {"table_id": TABLE_ID}) == TABLE_ID
    assert logic.referenced_table_id("list", {"element_type": "reference", "table_id": TABLE_ID}) == TABLE_ID
    assert logic.referenced_table_id("map", {"element_type": "text"}) is None
    assert logic.referenced_table_id("text", {}) is None


def test_element_type_of():
    assert logic.element_type_of("number", {}) == "number"
    assert logic.element_type_of("list", {"element_type": "date"}) == "date"


# --- Scalar values --------------------------------------------------------------


def test_text_is_trimmed_and_empty_text_is_not_set():
    spec = _spec("text")

    assert _normalize(spec, "  hello  ").data == {spec.id: "hello"}
    assert _normalize(spec, "   ").data == {}
    assert _normalize(spec, None).data == {}
    assert _normalize(spec, "").errors == {}


@pytest.mark.parametrize(
    ("value", "code"),
    [(5, "invalid_type"), (True, "invalid_type"), (["a"], "invalid_type"), ("a" * 5001, "too_long"), ("a\x00b", "invalid_text")],
)
def test_text_errors(value, code):
    spec = _spec("text")

    assert _normalize(spec, value).errors == {spec.id: code}


def test_text_of_the_maximum_length_is_fine():
    assert _normalize(_spec("text"), "a" * logic.MAX_TEXT_LENGTH).errors == {}


@pytest.mark.parametrize("value", [0, 1, -3, 2.5, 1e15, -1e15])
def test_numbers(value):
    spec = _spec("number")

    assert _normalize(spec, value).data == {spec.id: value}


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (True, "invalid_type"),
        ("5", "invalid_type"),
        (float("nan"), "invalid_number"),
        (float("inf"), "invalid_number"),
        (1e15 + 1e9, "out_of_range"),
        (-1e16, "out_of_range"),
    ],
)
def test_number_errors(value, code):
    spec = _spec("number")

    assert _normalize(spec, value).errors == {spec.id: code}


def test_boolean_false_is_a_value():
    spec = _spec("boolean")

    assert _normalize(spec, False).data == {spec.id: False}
    assert _normalize(spec, True).data == {spec.id: True}
    assert _normalize(spec, 1).errors == {spec.id: "invalid_type"}
    assert _normalize(spec, "true").errors == {spec.id: "invalid_type"}


@pytest.mark.parametrize("value", ["2026-10-22", "2024-02-29", "1000-01-01", "9999-12-31"])
def test_dates(value):
    spec = _spec("date")

    assert _normalize(spec, value).data == {spec.id: value}


@pytest.mark.parametrize("value", ["2026-02-30", "2025-02-29", "22.10.2026", "2026-10-22T10:00", "20261022", "0999-01-01", 20261022, "2026-1-5"])
def test_date_errors(value):
    spec = _spec("date")

    assert _normalize(spec, value).errors == {spec.id: "invalid_date"}


@pytest.mark.parametrize("value", ["2026-10-22T08:30", "2024-02-29T23:59", "2026-10-22T00:00"])
def test_datetimes(value):
    spec = _spec("datetime")

    assert _normalize(spec, value).data == {spec.id: value}


@pytest.mark.parametrize("value", ["2026-10-22", "2026-10-22T24:00", "2026-10-22T10:60", "2026-10-22 10:00", "2026-10-22T10:00:00", "0999-10-22T10:00", 5])
def test_datetime_errors(value):
    spec = _spec("datetime")

    assert _normalize(spec, value).errors == {spec.id: "invalid_datetime"}


def test_image_and_reference_values_are_uuids_that_are_collected_for_the_caller_to_check():
    image = _spec("image")
    reference = _spec("reference", table_id=TABLE_ID)

    image_result = _normalize(image, IMAGE_ID.upper())
    reference_result = _normalize(reference, RECORD_ID)

    assert image_result.data == {image.id: IMAGE_ID}
    assert image_result.image_ids == {IMAGE_ID}
    assert reference_result.data == {reference.id: RECORD_ID}
    assert reference_result.references == {TABLE_ID: {RECORD_ID}}
    assert _normalize(image, "nope").errors == {image.id: "invalid_image"}
    assert _normalize(reference, "nope").errors == {reference.id: "invalid_reference"}
    assert _normalize(reference, 5).errors == {reference.id: "invalid_reference"}


# --- Lists and maps -------------------------------------------------------------


def test_a_list_is_stored_as_a_map_keyed_by_index():
    spec = _spec("list", element_type="text")

    result = _normalize(spec, ["a", "b", "c"])

    assert result.data == {spec.id: {"0": "a", "1": "b", "2": "c"}}


def test_a_list_given_as_an_index_map_is_renumbered_in_numeric_order():
    spec = _spec("list", element_type="number")

    result = _normalize(spec, {"10": 3, "2": 2, "0": 1})

    assert result.data == {spec.id: {"0": 1, "1": 2, "2": 3}}


def test_a_list_given_as_a_map_with_other_keys_is_refused():
    spec = _spec("list", element_type="number")

    assert _normalize(spec, {"a": 1}).errors == {spec.id: "invalid_type"}
    assert _normalize(spec, 5).errors == {spec.id: "invalid_type"}


def test_an_empty_list_or_map_is_not_set():
    list_spec = _spec("list", element_type="text")
    map_spec = _spec("map", element_type="text")

    assert _normalize(list_spec, []).data == {}
    assert _normalize(map_spec, {}).data == {}


def test_list_elements_are_validated_and_the_error_names_the_index():
    spec = _spec("list", element_type="number")

    result = _normalize(spec, [1, "x", 3, True])

    assert result.errors == {f"{spec.id}.1": "invalid_type", f"{spec.id}.3": "invalid_type"}


def test_a_blank_text_element_is_an_error_not_a_gap():
    spec = _spec("list", element_type="text")

    assert _normalize(spec, ["a", "  "]).errors == {f"{spec.id}.1": "required"}


def test_a_list_or_map_has_at_most_the_maximum_number_of_elements():
    list_spec = _spec("list", element_type="number")
    map_spec = _spec("map", element_type="number")

    assert _normalize(list_spec, list(range(logic.MAX_ELEMENTS))).errors == {}
    assert _normalize(list_spec, list(range(logic.MAX_ELEMENTS + 1))).errors == {list_spec.id: "too_many_elements"}
    too_many = {f"k{i}": i for i in range(logic.MAX_ELEMENTS + 1)}
    assert _normalize(map_spec, too_many).errors == {map_spec.id: "too_many_elements"}


def test_a_map_keeps_the_users_keys_trimmed():
    spec = _spec("map", element_type="number")

    result = _normalize(spec, {" width ": 3, "height": 4})

    assert result.data == {spec.id: {"width": 3, "height": 4}}


def test_map_key_errors():
    spec = _spec("map", element_type="text")

    result = _normalize(spec, {"": "a", "   ": "b", "k" * 101: "c", "ok": "d"})

    assert set(result.errors.values()) == {"invalid_key"}
    assert len(result.errors) == 3
    assert result.data == {spec.id: {"ok": "d"}}


def test_map_keys_that_collide_after_trimming_are_refused():
    spec = _spec("map", element_type="text")

    result = _normalize(spec, {"a": "x", " a": "y"})

    assert list(result.errors.values()) == ["duplicate_key"]


def test_a_map_must_be_an_object():
    spec = _spec("map", element_type="text")

    assert _normalize(spec, ["a"]).errors == {spec.id: "invalid_type"}


def test_references_and_images_inside_lists_and_maps_are_collected():
    other = str(uuid.uuid4())
    references = _spec("list", element_type="reference", table_id=TABLE_ID)
    images = _spec("map", element_type="image")

    result = logic.normalize_record_data(
        [references, images],
        {references.id: [RECORD_ID, other], images.id: {"front": IMAGE_ID}},
    )

    assert result.errors == {}
    assert result.references == {TABLE_ID: {RECORD_ID, other}}
    assert result.image_ids == {IMAGE_ID}


# --- A whole record -------------------------------------------------------------


def test_a_value_for_an_unknown_attribute_is_an_error():
    spec = _spec("text")
    unknown = str(uuid.uuid4())

    result = logic.normalize_record_data([spec], {unknown: "x"})

    assert result.errors == {unknown: "unknown_attribute"}


def test_a_required_attribute_must_have_a_value():
    required = _spec("text", required=True)
    optional = _spec("text")

    result = logic.normalize_record_data([required, optional], {optional.id: "x"})

    assert result.errors == {required.id: "required"}


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_empty_values_do_not_satisfy_a_required_text(empty):
    spec = _spec("text", required=True)

    assert _normalize(spec, empty).errors == {spec.id: "required"}


def test_a_required_list_needs_at_least_one_element():
    spec = _spec("list", required=True, element_type="text")

    assert _normalize(spec, []).errors == {spec.id: "required"}
    assert _normalize(spec, ["a"]).errors == {}


def test_a_required_attribute_with_an_invalid_value_reports_that_error_only():
    spec = _spec("number", required=True)

    assert _normalize(spec, "x").errors == {spec.id: "invalid_type"}


def test_a_record_without_attributes_has_no_data():
    result = logic.normalize_record_data([], {})

    assert result.data == {}
    assert result.errors == {}


# --- The name of a record -------------------------------------------------------


def test_record_name_is_trimmed():
    assert logic.normalize_record_name("  Dune  ") == "Dune"


@pytest.mark.parametrize(
    ("value", "code"),
    [("", "required"), ("   ", "required"), (None, "invalid_type"), (5, "invalid_type"), ("a" * 201, "too_long"), ("a\x00", "invalid_text")],
)
def test_record_name_errors(value, code):
    with pytest.raises(ValueIssue) as raised:
        logic.normalize_record_name(value)

    assert raised.value.code == code


def test_record_name_of_the_maximum_length_is_fine():
    assert len(logic.normalize_record_name("a" * logic.MAX_RECORD_NAME_LENGTH)) == logic.MAX_RECORD_NAME_LENGTH


# --- The ids a record holds -----------------------------------------------------


def test_reference_and_image_ids_are_found_through_every_kind_of_attribute():
    other = str(uuid.uuid4())
    reference = _spec("reference", table_id=TABLE_ID)
    references = _spec("list", element_type="reference", table_id=TABLE_ID)
    image = _spec("image")
    images = _spec("map", element_type="image")
    text = _spec("text")
    data = {
        reference.id: RECORD_ID,
        references.id: {"0": other},
        image.id: IMAGE_ID,
        images.id: {"front": IMAGE_ID, "back": other},
        text.id: "x",
    }
    specs = [reference, references, image, images, text]

    assert logic.reference_ids_in(specs, data) == {RECORD_ID, other}
    assert logic.image_ids_in(specs, data) == {IMAGE_ID, other}


def test_ids_of_attributes_with_no_value_are_not_found():
    reference = _spec("reference", table_id=TABLE_ID)

    assert logic.reference_ids_in([reference], {}) == set()
    assert logic.image_ids_in([reference], {reference.id: RECORD_ID}) == set()
