# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The forms module's rules as pure functions (no database): which questions
show for the answers given, validation of every question type, the snapshot
that is stored, the summary statistics, and what is checked when a form is
saved (configuration, conditions, regular expressions)."""

import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.modules.forms.logic import (
    FormValidationError,
    Question,
    condition_holds,
    is_answered,
    stats_from_answers,
    validate_answers,
    validate_condition_value,
    visible_questions,
)
from app.modules.forms.schemas import QuestionIn, QuestionsReplace, normalize_config

VECTORS = json.loads((Path(__file__).parent / "data" / "forms_visibility_vectors.json").read_text(encoding="utf-8"))["vectors"]

OPTIONS = {"options": [{"id": "a", "label": "Alpha"}, {"id": "b", "label": "Beta"}, {"id": "c", "label": "Gamma"}]}


def _q(id, type, *, required=False, config=None, conditions=(), label=None, position=0) -> Question:
    return Question(
        id=id,
        type=type,
        label=label or f"Question {id}",
        required=required,
        config=config or {},
        conditions=tuple(conditions),
        position=position,
    )


def _error(question: Question, raw, **more) -> str:
    """The error code validate_answers reports for an answer to one question."""
    with pytest.raises(FormValidationError) as excinfo:
        validate_answers([question], {question.id: raw, **more})
    return excinfo.value.errors[question.id]


def _value(question: Question, raw):
    (entry,) = validate_answers([question], {question.id: raw})
    return entry["value"], entry["display"]


# --- Conditions: the vectors shared with the frontend ------------------------------------


def _questions_of(vector) -> list[Question]:
    return [
        Question(
            id=q["id"],
            type=q["type"],
            config=q.get("config", {}),
            conditions=tuple(q.get("conditions", ())),
            position=index,
        )
        for index, q in enumerate(vector["questions"])
    ]


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_visible_questions_matches_the_shared_vectors(vector):
    shown = visible_questions(_questions_of(vector), vector["answers"])

    assert [q.id for q in shown] == vector["visible"]


def test_the_shared_vectors_cover_every_operator_and_question_type():
    used_operators = {c["operator"] for v in VECTORS for q in v["questions"] for c in q.get("conditions", ())}
    used_types = {q["type"] for v in VECTORS for q in v["questions"]}

    assert used_operators == {"answered", "not_answered", "equals", "not_equals", "contains", "not_contains", "gt", "gte", "lt", "lte"}
    assert used_types == {"checkbox", "radio", "text", "number", "date", "time", "datetime"}


def test_condition_holds_never_raises_on_values_of_the_wrong_shape():
    for operator in ("equals", "not_equals", "contains", "not_contains", "gt", "gte", "lt", "lte"):
        for source_type in ("checkbox", "radio", "text", "number", "date"):
            for value in (None, "x", 3, 2.5, True, [], ["a"], {"k": 1}):
                assert condition_holds({"operator": operator, "value": "a"}, source_type, value) in (True, False)


@pytest.mark.parametrize(
    ("value", "answered"),
    [(None, False), ("", False), ("  ", False), ([], False), ("x", True), (0, True), (0.0, True), (["a"], True), (False, True)],
)
def test_is_answered(value, answered):
    assert is_answered(value) is answered


# --- Validation: choices ------------------------------------------------------------------


def test_checkbox_accepts_options_and_stores_them_in_the_forms_order():
    question = _q("q", "checkbox", config=OPTIONS)

    assert _value(question, ["c", "a"]) == (["a", "c"], "Alpha, Gamma")


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (["a", "x"], "unknown_option"),
        (["a", "a"], "duplicate"),
        ("a", "invalid_type"),
        ([1], "invalid_type"),
        ({"a": 1}, "invalid_type"),
    ],
)
def test_checkbox_rejects_bad_values(raw, code):
    assert _error(_q("q", "checkbox", config=OPTIONS), raw) == code


def test_checkbox_selection_count_limits_are_inclusive():
    question = _q("q", "checkbox", config={**OPTIONS, "min_select": 2, "max_select": 2})

    assert _value(question, ["a", "b"])[0] == ["a", "b"]
    assert _error(question, ["a"]) == "too_few"
    assert _error(question, ["a", "b", "c"]) == "too_many"


def test_checkbox_unrequired_may_be_left_empty_even_with_a_minimum_but_a_partial_choice_must_meet_it():
    question = _q("q", "checkbox", config={**OPTIONS, "min_select": 2})

    assert _value(question, []) == (None, "")
    assert _value(question, None) == (None, "")
    assert _error(question, ["a"]) == "too_few"


def test_checkbox_required_needs_at_least_one_even_without_a_minimum():
    question = _q("q", "checkbox", required=True, config=OPTIONS)

    assert _error(question, []) == "required"
    assert _error(question, None) == "required"
    assert _value(question, ["b"])[0] == ["b"]


def test_radio_accepts_one_option_by_id_and_shows_its_label():
    question = _q("q", "radio", config=OPTIONS)

    assert _value(question, "b") == ("b", "Beta")
    assert _error(question, "x") == "unknown_option"
    assert _error(question, ["a"]) == "invalid_type"


def test_radio_required_versus_optional():
    assert _error(_q("q", "radio", required=True, config=OPTIONS), None) == "required"
    assert _error(_q("q", "radio", required=True, config=OPTIONS), "") == "required"
    assert _value(_q("q", "radio", config=OPTIONS), None) == (None, "")


# --- Validation: text ------------------------------------------------------------------------


def test_text_is_trimmed_and_blank_is_unanswered():
    question = _q("q", "text")

    assert _value(question, "  hello  ") == ("hello", "hello")
    assert _value(question, "   ") == (None, "")
    assert _error(_q("q", "text", required=True), "   ") == "required"
    assert _error(question, 5) == "invalid_type"


def test_text_length_limits_are_inclusive_and_count_the_trimmed_text():
    question = _q("q", "text", config={"min_length": 3, "max_length": 5})

    assert _value(question, " abc ")[0] == "abc"
    assert _value(question, "abcde")[0] == "abcde"
    assert _error(question, "ab") == "too_short"
    assert _error(question, "abcdef") == "too_long"


def test_text_never_exceeds_the_hard_limit_whatever_the_configuration_says():
    assert _error(_q("q", "text", config={"max_length": 99999}), "x" * 2001) == "too_long"
    assert _error(_q("q", "text"), " " * 5000 + "x") == "too_long"


def test_text_single_line_refuses_newlines_multiline_allows_them():
    assert _error(_q("q", "text"), "a\nb") == "no_newline"
    assert _value(_q("q", "text", config={"multiline": True}), "a\nb")[0] == "a\nb"


def test_text_regex_must_match_the_whole_answer():
    question = _q("q", "text", config={"regex": r"\d{3} \d{2}"})

    assert _value(question, "602 00")[0] == "602 00"
    assert _error(question, "602 00 Brno") == "pattern"
    assert _error(question, "x602 00") == "pattern"


def test_text_regex_that_would_hang_is_cut_off_and_the_answer_refused_quickly():
    """A pattern that slipped past the save-time check must not hang the server on a stranger's input."""
    question = _q("q", "text", config={"regex": r"(a|aa)+$"})

    started = time.perf_counter()
    code = _error(question, "a" * 60 + "b")

    assert code == "pattern"
    assert time.perf_counter() - started < 2


# --- Validation: numbers, dates ----------------------------------------------------------------


def test_integer_number_rejects_fractions_and_non_numbers():
    question = _q("q", "number")

    assert _value(question, 7) == (7, "7")
    assert _value(question, 7.0) == (7, "7")
    assert _error(question, 7.5) == "not_integer"
    for raw in ("7", True, [7], float("nan"), float("inf")):
        assert _error(question, raw) == "invalid_type"


def test_decimal_number_and_bounds_are_inclusive():
    question = _q("q", "number", config={"kind": "decimal", "min": 0.5, "max": 2.5})

    assert _value(question, 0.5) == (0.5, "0.5")
    assert _value(question, 2.5) == (2.5, "2.5")
    assert _error(question, 0.4) == "too_small"
    assert _error(question, 2.6) == "too_large"


def test_number_zero_is_an_answer_and_required_does_not_reject_it():
    assert _value(_q("q", "number", required=True), 0) == (0, "0")
    assert _error(_q("q", "number", required=True), None) == "required"


@pytest.mark.parametrize(
    ("kind", "good", "bad"),
    [
        ("date", "2026-02-28", ["2026-02-30", "2026-2-8", "28.2.2026", "2026-02-28T10:00", 20260228]),
        ("time", "09:05", ["24:00", "9:05", "09:05:00", "9am"]),
        ("datetime", "2026-02-28T23:59", ["2026-02-28 23:59", "2026-02-28T24:00", "2026-02-28", "2026-02-28T9:00"]),
    ],
)
def test_date_types_accept_only_the_fixed_width_form(kind, good, bad):
    question = _q("q", kind)

    assert _value(question, good) == (good, good)
    for raw in bad:
        assert _error(question, raw) == "invalid_date", raw


def test_date_bounds_are_inclusive():
    question = _q("q", "date", config={"min": "2026-03-01", "max": "2026-03-31"})

    assert _value(question, "2026-03-01")[0] == "2026-03-01"
    assert _value(question, "2026-03-31")[0] == "2026-03-31"
    assert _error(question, "2026-02-28") == "before_min"
    assert _error(question, "2026-04-01") == "after_max"


def test_time_and_datetime_bounds():
    assert _error(_q("q", "time", config={"min": "09:00", "max": "17:00"}), "08:59") == "before_min"
    assert _error(_q("q", "time", config={"min": "09:00", "max": "17:00"}), "17:01") == "after_max"
    window = {"min": "2026-03-01T10:00", "max": "2026-03-01T12:00"}
    assert _value(_q("q", "datetime", config=window), "2026-03-01T11:00")[0] == "2026-03-01T11:00"
    assert _error(_q("q", "datetime", config=window), "2026-03-01T12:01") == "after_max"


# --- Validation of a whole form ---------------------------------------------------------------


def test_every_problem_is_reported_not_just_the_first():
    questions = [_q("a", "text", required=True), _q("b", "number", config={"min": 5}), _q("c", "text")]

    with pytest.raises(FormValidationError) as excinfo:
        validate_answers(questions, {"a": "", "b": 1, "c": "fine"})

    assert excinfo.value.errors == {"a": "required", "b": "too_small"}
    assert excinfo.value.as_detail() == {"errors": {"a": "required", "b": "too_small"}}


def test_an_answer_to_a_question_the_form_does_not_have_is_an_error():
    with pytest.raises(FormValidationError) as excinfo:
        validate_answers([_q("a", "text")], {"a": "x", "stranger": "y"})

    assert excinfo.value.errors == {"stranger": "unknown_question"}


def test_answers_must_be_an_object():
    for raw in (None, [], "x", 5):
        with pytest.raises(FormValidationError) as excinfo:
            validate_answers([_q("a", "text")], raw)
        assert excinfo.value.errors == {"_form": "invalid_type"}


def test_the_snapshot_has_an_entry_for_every_question_in_order_with_the_wording_and_options():
    questions = [
        _q("a", "text", label="Your name", position=0),
        _q("b", "radio", label="Colour", config=OPTIONS, position=1),
        _q("c", "number", label="How many", position=2),
    ]

    entries = validate_answers(questions, {"a": "Eva", "b": "b"})

    assert [e["question_id"] for e in entries] == ["a", "b", "c"]
    assert entries[0] == {
        "question_id": "a", "position": 0, "label": "Your name", "type": "text",
        "shown": True, "value": "Eva", "display": "Eva", "options": [],
    }
    assert entries[1]["display"] == "Beta" and entries[1]["value"] == "b"
    assert entries[1]["options"] == OPTIONS["options"]
    assert entries[2]["shown"] is True and entries[2]["value"] is None and entries[2]["display"] == ""


def test_answers_to_a_hidden_question_are_neither_validated_nor_kept():
    questions = [
        _q("q1", "radio", config=OPTIONS, position=0),
        _q("q2", "number", config={"min": 10}, conditions=[{"question_id": "q1", "operator": "equals", "value": "a"}], position=1),
    ]

    entries = validate_answers(questions, {"q1": "b", "q2": 1})  # 1 would be too small, but q2 is hidden

    assert entries[1]["shown"] is False
    assert entries[1]["value"] is None and entries[1]["display"] == ""
    assert entries[1]["label"] == "Question q2"  # still in the snapshot, as "not shown"


def test_a_required_question_that_is_hidden_is_not_required():
    questions = [
        _q("q1", "radio", config=OPTIONS, position=0),
        _q("q2", "text", required=True, conditions=[{"question_id": "q1", "operator": "equals", "value": "a"}], position=1),
    ]

    assert validate_answers(questions, {"q1": "b"})[1]["shown"] is False
    with pytest.raises(FormValidationError) as excinfo:
        validate_answers(questions, {"q1": "a"})
    assert excinfo.value.errors == {"q2": "required"}


def test_an_invalid_answer_counts_as_unanswered_for_the_conditions_that_follow():
    questions = [
        _q("q1", "number", config={"max": 10}, position=0),
        _q("q2", "text", conditions=[{"question_id": "q1", "operator": "answered"}], position=1),
    ]

    with pytest.raises(FormValidationError) as excinfo:
        validate_answers(questions, {"q1": 99, "q2": "x"})

    assert excinfo.value.errors == {"q1": "too_large"}  # q2 is hidden, so its answer raises nothing


def test_validation_chains_through_hidden_questions():
    questions = [
        _q("q1", "radio", config=OPTIONS, position=0),
        _q("q2", "text", conditions=[{"question_id": "q1", "operator": "equals", "value": "a"}], position=1),
        _q("q3", "text", required=True, conditions=[{"question_id": "q2", "operator": "answered"}], position=2),
    ]

    # q1 = b hides q2; q3 depends on q2 being answered, so it is hidden too, required or not.
    entries = validate_answers(questions, {"q1": "b", "q2": "left over", "q3": ""})

    assert [e["shown"] for e in entries] == [True, False, False]


# --- What is checked when a form is saved ---------------------------------------------------


def _question_in(id, type, config=None, conditions=(), label="L", required=False) -> dict:
    return {"id": id, "type": type, "label": label, "required": required, "config": config or {}, "conditions": list(conditions)}


IDS = [f"00000000-0000-0000-0000-00000000000{i}" for i in range(1, 6)]


def _replace(*questions) -> QuestionsReplace:
    return QuestionsReplace.model_validate({"questions": list(questions)})


def test_configuration_defaults_are_filled_in():
    assert normalize_config("text", {}) == {"multiline": False, "min_length": 0, "max_length": 2000, "regex": None}
    assert normalize_config("number", {}) == {"kind": "integer", "min": None, "max": None}
    assert normalize_config("checkbox", OPTIONS)["min_select"] == 0


@pytest.mark.parametrize(
    ("question_type", "config"),
    [
        ("checkbox", {}),
        ("checkbox", {"options": []}),
        ("checkbox", {"options": [{"id": "a", "label": "A"}, {"id": "a", "label": "Again"}]}),
        ("checkbox", {"options": [{"id": "has space", "label": "A"}]}),
        ("checkbox", {**OPTIONS, "min_select": 4}),
        ("checkbox", {**OPTIONS, "max_select": 4}),
        ("checkbox", {**OPTIONS, "min_select": 3, "max_select": 2}),
        ("radio", {"options": [{"id": "a", "label": ""}]}),
        ("text", {"min_length": 5, "max_length": 3}),
        ("text", {"max_length": 5000}),
        ("text", {"unknown_key": 1}),
        ("number", {"kind": "float"}),
        ("number", {"min": 5, "max": 1}),
        ("date", {"min": "2026-1-1"}),
        ("date", {"min": "2026-03-02", "max": "2026-03-01"}),
        ("time", {"max": "25:00"}),
        ("datetime", {"min": "2026-03-01"}),
    ],
)
def test_invalid_configurations_are_refused(question_type, config):
    with pytest.raises(ValueError):
        normalize_config(question_type, config)


def test_a_regex_that_does_not_compile_or_is_too_long_is_refused():
    for pattern in ("(unclosed", "[z-a]", "x" * 201):
        with pytest.raises(ValueError):
            normalize_config("text", {"regex": pattern})


def test_a_regex_that_backtracks_catastrophically_is_refused_when_the_form_is_saved():
    started = time.perf_counter()
    with pytest.raises(ValueError, match="too complex"):
        normalize_config("text", {"regex": r"(a|aa)+$"})
    assert time.perf_counter() - started < 3


def test_ordinary_regexes_are_accepted_and_a_blank_one_means_none():
    assert normalize_config("text", {"regex": r"^\d{3} \d{2}$"})["regex"] == r"^\d{3} \d{2}$"
    assert normalize_config("text", {"regex": r"[A-Z]{2}\d+"})["regex"] == r"[A-Z]{2}\d+"
    assert normalize_config("text", {"regex": "   "})["regex"] is None


def test_a_question_needs_a_label_and_a_known_type():
    with pytest.raises(ValidationError):
        QuestionIn.model_validate(_question_in(IDS[0], "text", label=""))
    with pytest.raises(ValidationError):
        QuestionIn.model_validate(_question_in(IDS[0], "slider"))
    with pytest.raises(ValidationError):
        QuestionIn.model_validate({**_question_in(IDS[0], "text"), "surprise": True})


def test_question_ids_must_be_unique():
    with pytest.raises(ValidationError, match="unique"):
        _replace(_question_in(IDS[0], "text"), _question_in(IDS[0], "text"))


def test_a_condition_may_refer_only_to_an_earlier_question():
    later = {"question_id": IDS[1], "operator": "answered"}
    with pytest.raises(ValidationError, match="not earlier"):
        _replace(_question_in(IDS[0], "text", conditions=[later]), _question_in(IDS[1], "text"))
    with pytest.raises(ValidationError, match="not earlier"):
        _replace(_question_in(IDS[0], "text", conditions=[{"question_id": IDS[0], "operator": "answered"}]))
    with pytest.raises(ValidationError, match="not earlier"):
        _replace(_question_in(IDS[0], "text", conditions=[{"question_id": IDS[4], "operator": "answered"}]))

    ok = _replace(_question_in(IDS[0], "text"), _question_in(IDS[1], "text", conditions=[{"question_id": IDS[0], "operator": "answered"}]))
    assert len(ok.questions) == 2


@pytest.mark.parametrize(
    ("source_type", "source_config", "operator", "value"),
    [
        ("checkbox", OPTIONS, "equals", "a"),
        ("checkbox", OPTIONS, "gt", 1),
        ("radio", OPTIONS, "contains", "a"),
        ("radio", OPTIONS, "gt", "a"),
        ("text", {}, "contains", "x"),
        ("text", {}, "lt", "x"),
        ("number", {}, "contains", 1),
    ],
)
def test_an_operator_that_does_not_suit_the_source_type_is_refused(source_type, source_config, operator, value):
    with pytest.raises(ValueError, match="does not apply"):
        validate_condition_value(source_type, source_config, operator, value)


@pytest.mark.parametrize(
    ("source_type", "source_config", "operator", "value"),
    [
        ("checkbox", OPTIONS, "contains", "zzz"),
        ("checkbox", OPTIONS, "not_contains", 5),
        ("radio", OPTIONS, "equals", "zzz"),
        ("number", {}, "gt", "5"),
        ("number", {}, "equals", True),
        ("date", {}, "gt", "2026-1-1"),
        ("time", {}, "equals", "25:00"),
        ("text", {}, "equals", ""),
        ("text", {}, "equals", 5),
    ],
)
def test_a_value_that_does_not_suit_the_source_question_is_refused(source_type, source_config, operator, value):
    with pytest.raises(ValueError):
        validate_condition_value(source_type, source_config, operator, value)


def test_condition_values_are_normalised():
    assert validate_condition_value("number", {}, "gt", 5.0) == 5
    assert validate_condition_value("number", {}, "gt", 5.5) == 5.5
    assert validate_condition_value("text", {}, "equals", "  yes ") == "yes"
    assert validate_condition_value("text", {}, "answered", "ignored") is None
    assert validate_condition_value("date", {}, "lte", "2026-06-30") == "2026-06-30"


def test_a_saved_form_validates_and_hides_just_like_the_unsaved_one():
    saved = _replace(
        _question_in(IDS[0], "radio", OPTIONS),
        _question_in(IDS[1], "text", conditions=[{"question_id": IDS[0], "operator": "equals", "value": "a"}], required=True),
    )
    questions = [
        Question(id=str(q.id), type=q.type, label=q.label, required=q.required, config=q.config,
                 conditions=[c.model_dump(mode="json") for c in q.conditions], position=i)
        for i, q in enumerate(saved.questions)
    ]

    assert validate_answers(questions, {IDS[0]: "b"})[1]["shown"] is False
    with pytest.raises(FormValidationError):
        validate_answers(questions, {IDS[0]: "a"})


# --- Statistics ---------------------------------------------------------------------------


def _entry(question_id, type, position, label, *, shown=True, value=None, options=()):
    return {
        "question_id": question_id, "position": position, "label": label, "type": type,
        "shown": shown, "value": value, "display": "", "options": list(options),
    }


def _by_id(stats):
    return {q["question_id"]: q for q in stats["questions"]}


def test_stats_of_no_answers():
    assert stats_from_answers([]) == {"submission_count": 0, "questions": []}


def test_stats_counts_and_shares_per_option_for_radio_and_checkbox():
    colour = [{"id": "r", "label": "Red"}, {"id": "g", "label": "Green"}, {"id": "b", "label": "Blue"}]
    answers = [
        [_entry("radio", "radio", 0, "Colour", value="r", options=colour), _entry("check", "checkbox", 1, "Likes", value=["r", "g"], options=colour)],
        [_entry("radio", "radio", 0, "Colour", value="r", options=colour), _entry("check", "checkbox", 1, "Likes", value=["g"], options=colour)],
        [_entry("radio", "radio", 0, "Colour", value="g", options=colour), _entry("check", "checkbox", 1, "Likes", value=None, options=colour)],
    ]

    stats = _by_id(stats_from_answers(answers))

    assert stats["radio"]["answered_count"] == 3 and stats["radio"]["shown_count"] == 3
    assert [(o["id"], o["count"], o["percent"]) for o in stats["radio"]["options"]] == [("r", 2, 66.7), ("g", 1, 33.3), ("b", 0, 0.0)]
    assert stats["check"]["answered_count"] == 2
    assert [(o["id"], o["count"], o["percent"]) for o in stats["check"]["options"]] == [("r", 1, 50.0), ("g", 2, 100.0), ("b", 0, 0.0)]
    assert stats["check"]["average_selected"] == 1.5
    assert "average_selected" not in stats["radio"]


def test_stats_shown_count_differs_from_answered_count_for_a_conditional_question():
    answers = [
        [_entry("cond", "text", 0, "Why?", shown=True, value="because")],
        [_entry("cond", "text", 0, "Why?", shown=True, value=None)],
        [_entry("cond", "text", 0, "Why?", shown=False)],
        [_entry("cond", "text", 0, "Why?", shown=False)],
    ]

    stats = _by_id(stats_from_answers(answers))["cond"]

    assert (stats["shown_count"], stats["answered_count"]) == (2, 1)
    assert "options" not in stats and "numeric" not in stats and "range" not in stats  # a text: counts only


def test_stats_number_summary():
    answers = [[_entry("n", "number", 0, "How many", value=v)] for v in (4, 1, 9, 2)]

    numeric = _by_id(stats_from_answers(answers))["n"]["numeric"]

    assert numeric == {"min": 1, "max": 9, "average": 4, "median": 3}


def test_stats_number_zero_is_counted_as_an_answer():
    answers = [[_entry("n", "number", 0, "How many", value=0)], [_entry("n", "number", 0, "How many", value=None)]]

    stats = _by_id(stats_from_answers(answers))["n"]

    assert stats["answered_count"] == 1 and stats["numeric"]["min"] == 0 and stats["numeric"]["average"] == 0


@pytest.mark.parametrize(
    ("kind", "values", "earliest", "latest"),
    [
        ("date", ["2026-05-02", "2026-01-10", "2026-03-01"], "2026-01-10", "2026-05-02"),
        ("time", ["09:30", "18:00", "07:05"], "07:05", "18:00"),
        ("datetime", ["2026-01-01T10:00", "2025-12-31T23:59"], "2025-12-31T23:59", "2026-01-01T10:00"),
    ],
)
def test_stats_date_types_report_the_earliest_and_latest(kind, values, earliest, latest):
    answers = [[_entry("d", kind, 0, "When", value=v)] for v in values]

    assert _by_id(stats_from_answers(answers))["d"]["range"] == {"earliest": earliest, "latest": latest}


def test_stats_use_the_wording_the_question_had_when_it_was_answered():
    """Newest first: the latest label wins, a question deleted since stays with its old wording."""
    answers = [
        [_entry("kept", "text", 0, "Name (new wording)")],
        [_entry("kept", "text", 0, "Name"), _entry("deleted", "text", 1, "Phone")],
    ]

    stats = _by_id(stats_from_answers(answers))

    assert stats["kept"]["label"] == "Name (new wording)"
    assert stats["deleted"]["label"] == "Phone"
    # It is in one of the two snapshots (the newer was taken after it had been deleted), shown there, unanswered.
    assert (stats["deleted"]["shown_count"], stats["deleted"]["answered_count"]) == (1, 0)


def test_stats_show_an_option_that_is_no_longer_on_the_form_under_its_old_name():
    old = [{"id": "x", "label": "Old choice"}, {"id": "y", "label": "Kept"}]
    new = [{"id": "y", "label": "Kept (renamed)"}]
    answers = [
        [_entry("c", "radio", 0, "Pick", value="y", options=new)],
        [_entry("c", "radio", 0, "Pick", value="x", options=old)],
        [_entry("c", "radio", 0, "Pick", value="y", options=old)],
    ]

    options = _by_id(stats_from_answers(answers))["c"]["options"]

    assert [(o["id"], o["label"], o["count"]) for o in options] == [("y", "Kept (renamed)", 2), ("x", "Old choice", 1)]


def test_stats_treat_a_question_whose_type_changed_as_two():
    answers = [
        [_entry("q", "number", 0, "Age", value=30)],
        [_entry("q", "text", 0, "Age", value="thirty")],
    ]

    stats = stats_from_answers(answers)["questions"]

    assert sorted(q["type"] for q in stats) == ["number", "text"]


def test_stats_are_ordered_by_the_latest_position():
    answers = [[_entry("second", "text", 1, "B"), _entry("first", "text", 0, "A"), _entry("third", "text", 2, "C")]]

    assert [q["question_id"] for q in stats_from_answers(answers)["questions"]] == ["first", "second", "third"]
