# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules of a form, as plain functions with no database and no I/O: which
questions are shown for the answers given so far, whether the answers are
valid, and the summary of a set of stored answers.

Question types and the shape of their answers (JSON):

- checkbox  a list of option ids        config: options, min_select, max_select
- radio     one option id               config: options
- text      a string                    config: multiline, min_length, max_length, regex
- number    a number                    config: kind ("integer" | "decimal"), min, max
- date      "YYYY-MM-DD"                config: min, max
- time      "HH:MM"                     config: min, max
- datetime  "YYYY-MM-DDTHH:MM"          config: min, max   (local time, no zone)

Conditions. A question may carry a list of conditions, all of which must hold
for it to be shown (AND). Each refers to an EARLIER question (so there is no
cycle) and compares that question's answer. A hidden question counts as
unanswered for the conditions that refer to it, so hiding chains. The
semantics - which the frontend's conditions.ts mirrors literally, both checked
against tests/data/forms_visibility_vectors.json:

  answered / not_answered   the source has / has not been answered
  equals / not_equals       radio, text, number, date/time: false / TRUE while unanswered
  contains / not_contains   checkbox includes the option: false / TRUE while unanswered
  gt gte lt lte             number, date/time: false while unanswered

(`not_*` read as plain logic: a question nobody answered does not equal or
contain anything.) Text is compared as typed after trimming, case-sensitive;
numbers numerically; dates and times as strings, which is chronological because
the formats are fixed-width.

Errors are short codes, not sentences, so the frontend can say them in the
visitor's language: required, invalid_type, unknown_option, duplicate,
too_few, too_many, too_short, too_long, no_newline, pattern, not_integer,
too_small, too_large, invalid_date, before_min, after_max, unknown_question.
"""

import logging
import math
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import regex

logger = logging.getLogger(__name__)

QUESTION_TYPES = ("checkbox", "radio", "text", "number", "date", "time", "datetime")
CHOICE_TYPES = ("checkbox", "radio")
DATE_TYPES = ("date", "time", "datetime")

MAX_OPTIONS = 50
MAX_CONDITIONS = 10
MAX_TEXT_LENGTH = 2000
MAX_REGEX_LENGTH = 200

# `re` has no timeout and runs inside the event loop: a pattern an administrator
# types, matched against a stranger's input, could hang the whole server
# ("catastrophic backtracking"). The `regex` package (already in
# requirements.txt) can be given one, so every match is bounded.
REGEX_TIMEOUT_SECONDS = 0.1

_ALWAYS = ("answered", "not_answered")
OPERATORS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "checkbox": (*_ALWAYS, "contains", "not_contains"),
    "radio": (*_ALWAYS, "equals", "not_equals"),
    "text": (*_ALWAYS, "equals", "not_equals"),
    "number": (*_ALWAYS, "equals", "not_equals", "gt", "gte", "lt", "lte"),
    "date": (*_ALWAYS, "equals", "not_equals", "gt", "gte", "lt", "lte"),
    "time": (*_ALWAYS, "equals", "not_equals", "gt", "gte", "lt", "lte"),
    "datetime": (*_ALWAYS, "equals", "not_equals", "gt", "gte", "lt", "lte"),
}
ALL_OPERATORS = tuple(dict.fromkeys(op for ops in OPERATORS_BY_TYPE.values() for op in ops))

_DATE_FORMATS = {"date": "%Y-%m-%d", "time": "%H:%M", "datetime": "%Y-%m-%dT%H:%M"}


@dataclass(frozen=True, eq=False)
class Question:
    """What the pure functions need to know about a question (a FormQuestion row converts to it)."""

    id: str
    type: str
    label: str = ""
    required: bool = False
    config: Mapping[str, Any] = field(default_factory=dict)
    conditions: Sequence[Mapping[str, Any]] = ()
    position: int = 0


class FormValidationError(Exception):
    """The answers don't fit the form; `errors` maps a question id to an error code."""

    def __init__(self, errors: dict[str, str]):
        super().__init__(f"invalid answers: {errors}")
        self.errors = errors

    def as_detail(self) -> dict[str, Any]:
        """The shape a consumer puts in its 422 response."""
        return {"errors": self.errors}


class _Invalid(Exception):
    """One answer is wrong; the message is the error code."""


# --- Values ------------------------------------------------------------------


def is_answered(value: Any) -> bool:
    """None, an empty / blank string and an empty list are "no answer"; 0 and False are answers."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    return True


def parse_date_value(question_type: str, value: Any) -> str | None:
    """`value` if it is a valid date / time / datetime string of exactly that
    type's fixed-width format, else None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, _DATE_FORMATS[question_type])
    except ValueError:
        return None
    # strptime accepts "2026-1-5"; the fixed-width form is what compares as a string.
    return value if parsed.strftime(_DATE_FORMATS[question_type]) == value else None


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def option_ids(config: Mapping[str, Any]) -> list[str]:
    return [option["id"] for option in config.get("options", [])]


def _options_of(question: Question) -> list[dict[str, str]]:
    if question.type not in CHOICE_TYPES:
        return []
    return [{"id": option["id"], "label": option["label"]} for option in question.config.get("options", [])]


# --- Conditions ---------------------------------------------------------------


def condition_holds(condition: Mapping[str, Any], source_type: str, value: Any) -> bool:
    """Does one condition hold, given the (typed) answer to its source question?"""
    operator = condition["operator"]
    expected = condition.get("value")
    answered = is_answered(value)
    if operator == "answered":
        return answered
    if operator == "not_answered":
        return not answered
    if operator == "contains":
        return answered and isinstance(value, (list, tuple)) and expected in value
    if operator == "not_contains":
        return not (answered and isinstance(value, (list, tuple)) and expected in value)
    if operator == "equals":
        return answered and _equal(source_type, value, expected)
    if operator == "not_equals":
        return not (answered and _equal(source_type, value, expected))
    if operator in ("gt", "gte", "lt", "lte"):
        return answered and _ordered(operator, source_type, value, expected)
    return False


def _equal(source_type: str, value: Any, expected: Any) -> bool:
    if source_type == "number":
        a, b = _as_number(value), _as_number(expected)
        return a is not None and b is not None and a == b
    return isinstance(value, str) and isinstance(expected, str) and value.strip() == expected.strip()


def _ordered(operator: str, source_type: str, value: Any, expected: Any) -> bool:
    if source_type == "number":
        a, b = _as_number(value), _as_number(expected)
    elif source_type in DATE_TYPES and isinstance(value, str) and isinstance(expected, str):
        a, b = value, expected  # fixed-width ISO forms: string order is time order
    else:
        return False
    if a is None or b is None:
        return False
    return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[operator]


def _conditions_hold(question: Question, by_id: Mapping[str, Question], effective: Mapping[str, Any]) -> bool:
    for condition in question.conditions:
        source_id = str(condition["question_id"])
        source = by_id.get(source_id)
        source_type = source.type if source is not None else "text"
        if not condition_holds(condition, source_type, effective.get(source_id)):
            return False
    return True


def visible_questions(questions: Sequence[Question], answers: Mapping[str, Any]) -> list[Question]:
    """The questions shown for these (typed) answers, in order. One pass is
    enough because a condition only refers to an earlier question."""
    by_id = {question.id: question for question in questions}
    effective: dict[str, Any] = {}
    shown: list[Question] = []
    for question in questions:
        if _conditions_hold(question, by_id, effective):
            shown.append(question)
            if question.id in answers:
                effective[question.id] = answers[question.id]
    return shown


def validate_condition_value(source_type: str, source_config: Mapping[str, Any], operator: str, value: Any) -> Any:
    """Checks a condition's operator and value against its source question
    (used when a form is saved) and returns the normalised value."""
    if operator not in OPERATORS_BY_TYPE[source_type]:
        raise ValueError(f"operator {operator!r} does not apply to a {source_type} question")
    if operator in _ALWAYS:
        return None
    if operator in ("contains", "not_contains") or source_type == "radio":
        if not isinstance(value, str) or value not in option_ids(source_config):
            raise ValueError("the value must be one of the source question's option ids")
        return value
    if source_type == "number":
        number = _as_number(value)
        if number is None:
            raise ValueError("the value must be a number")
        return int(number) if number.is_integer() else number
    if source_type in DATE_TYPES:
        parsed = parse_date_value(source_type, value)
        if parsed is None:
            raise ValueError(f"the value must be a valid {source_type}")
        return parsed
    if not isinstance(value, str) or value.strip() == "" or len(value) > MAX_TEXT_LENGTH:
        raise ValueError("the value must be a non-empty text")
    return value.strip()


# --- Validation of answers -------------------------------------------------------


def compile_pattern(pattern: str):
    return regex.compile(pattern)


def _clean_value(question: Question, raw: Any) -> tuple[Any, str]:
    """(value, display) for a shown question; value None = not answered. Raises _Invalid(code)."""
    config = question.config
    kind = question.type

    def unanswered():
        if question.required:
            raise _Invalid("required")
        return None, ""

    if kind == "checkbox":
        if raw is None or raw == []:
            return unanswered()
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise _Invalid("invalid_type")
        if len(set(raw)) != len(raw):
            raise _Invalid("duplicate")
        ids = option_ids(config)
        if any(item not in ids for item in raw):
            raise _Invalid("unknown_option")
        low = max(int(config.get("min_select") or 0), 1)
        high = config.get("max_select")
        high = len(ids) if high is None else int(high)
        if len(raw) < low:
            raise _Invalid("too_few")
        if len(raw) > high:
            raise _Invalid("too_many")
        chosen = [option for option in ids if option in raw]  # in the form's order, not the click order
        labels = {option["id"]: option["label"] for option in config["options"]}
        return chosen, ", ".join(labels[item] for item in chosen)

    if kind == "radio":
        if raw is None or raw == "":
            return unanswered()
        if not isinstance(raw, str):
            raise _Invalid("invalid_type")
        if raw not in option_ids(config):
            raise _Invalid("unknown_option")
        return raw, next(option["label"] for option in config["options"] if option["id"] == raw)

    if kind == "text":
        if raw is None:
            return unanswered()
        if not isinstance(raw, str):
            raise _Invalid("invalid_type")
        if len(raw) > MAX_TEXT_LENGTH * 2:  # before strip(): megabytes of blanks are not an answer
            raise _Invalid("too_long")
        text = raw.strip()
        if text == "":
            return unanswered()
        if len(text) > min(int(config.get("max_length", MAX_TEXT_LENGTH)), MAX_TEXT_LENGTH):
            raise _Invalid("too_long")
        if len(text) < int(config.get("min_length") or 0):
            raise _Invalid("too_short")
        if not config.get("multiline") and ("\n" in text or "\r" in text):
            raise _Invalid("no_newline")
        pattern = config.get("regex")
        if pattern:
            try:
                matched = regex.fullmatch(pattern, text, timeout=REGEX_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.warning("Form question %s: pattern %r timed out on an answer; treated as no match", question.id, pattern)
                matched = None
            if not matched:
                raise _Invalid("pattern")
        return text, text

    if kind == "number":
        if raw is None or raw == "":
            return unanswered()
        number = _as_number(raw)
        if number is None:
            raise _Invalid("invalid_type")
        if config.get("kind", "integer") == "integer" and not number.is_integer():
            raise _Invalid("not_integer")
        if config.get("min") is not None and number < float(config["min"]):
            raise _Invalid("too_small")
        if config.get("max") is not None and number > float(config["max"]):
            raise _Invalid("too_large")
        value = int(number) if number.is_integer() else number
        return value, str(value)

    if kind in DATE_TYPES:
        if raw is None or raw == "":
            return unanswered()
        value = parse_date_value(kind, raw)
        if value is None:
            raise _Invalid("invalid_date")
        if config.get("min") is not None and value < config["min"]:
            raise _Invalid("before_min")
        if config.get("max") is not None and value > config["max"]:
            raise _Invalid("after_max")
        return value, value

    raise _Invalid("invalid_type")


def validate_answers(questions: Sequence[Question], raw: Any) -> list[dict[str, Any]]:
    """Validates the answers to a form and returns the snapshot to store: one
    entry for EVERY question, in order -

        {question_id, position, label, type, shown, value, display, options}

    - the wording of the question as it was when answered (so editing or
    deleting it later breaks neither the view of the answer nor the statistics),
    `shown` (did the conditions let the question appear), `value` (only for a
    shown, answered question) and `display` (that value as readable text, an
    option by its label). Answers to a hidden question are neither validated nor
    kept, even when the client sends them; an answer to a question the form
    doesn't have is an error. Raises FormValidationError with every problem
    found, not just the first."""
    if not isinstance(raw, Mapping):
        raise FormValidationError({"_form": "invalid_type"})
    by_id = {question.id: question for question in questions}
    errors = {str(key): "unknown_question" for key in raw if key not in by_id}

    effective: dict[str, Any] = {}
    entries: list[dict[str, Any]] = []
    for question in questions:
        shown = _conditions_hold(question, by_id, effective)
        entry: dict[str, Any] = {
            "question_id": question.id,
            "position": question.position,
            "label": question.label,
            "type": question.type,
            "shown": shown,
            "value": None,
            "display": "",
            "options": _options_of(question),
        }
        if shown:
            try:
                value, display = _clean_value(question, raw.get(question.id))
            except _Invalid as invalid:
                errors[question.id] = str(invalid)  # unanswered as far as later conditions go
            else:
                if value is not None:
                    effective[question.id] = value
                    entry["value"], entry["display"] = value, display
        entries.append(entry)

    if errors:
        raise FormValidationError(errors)
    return entries


# --- Statistics -----------------------------------------------------------------


def _round(number: float, digits: int = 6) -> float | int:
    rounded = round(number, digits)
    return int(rounded) if float(rounded).is_integer() else rounded


def stats_from_answers(submissions: Sequence[Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """The basic summary of stored answers: `submissions` is each one's snapshot
    (see validate_answers), NEWEST FIRST.

    Computed from the snapshots, not the current form: a question deleted or
    reworded after people answered it keeps its original wording in the result,
    and an option that is no longer on the form but was chosen shows up under
    the name it had. Questions are grouped by id and type (a question whose type
    was changed counts as two) and ordered by the position of their latest
    version. Per question: shown_count (to how many it appeared), answered_count
    (how many answered) and, by type:

      checkbox / radio  `options`: count and share (of answered_count, %) per option;
                        checkbox also `average_selected`
      number            `numeric`: min, max, average, median
      date/time/datetime `range`: earliest, latest
      text              counts only (the texts are read in the list of answers)
    """
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for snapshot in submissions:
        for entry in snapshot:
            groups.setdefault((entry["question_id"], entry["type"]), []).append(entry)

    results = []
    for (question_id, question_type), entries in groups.items():
        latest = entries[0]
        answered = [e for e in entries if e.get("shown") and is_answered(e.get("value"))]
        result: dict[str, Any] = {
            "question_id": question_id,
            "type": question_type,
            "label": latest.get("label", ""),
            "position": latest.get("position", 0),
            "shown_count": sum(1 for e in entries if e.get("shown")),
            "answered_count": len(answered),
        }
        values = [e["value"] for e in answered]

        if question_type in CHOICE_TYPES:
            labels: dict[str, str] = {}
            for entry in entries:  # newest first, so the latest label of an option wins
                for option in entry.get("options") or []:
                    labels.setdefault(option["id"], option["label"])
            counts: Counter[str] = Counter()
            for value in values:
                counts.update(value if question_type == "checkbox" else [value])
            for option_id in counts:
                labels.setdefault(option_id, option_id)
            result["options"] = [
                {
                    "id": option_id,
                    "label": label,
                    "count": counts.get(option_id, 0),
                    "percent": round(100 * counts.get(option_id, 0) / len(answered), 1) if answered else 0.0,
                }
                for option_id, label in labels.items()
            ]
            if question_type == "checkbox" and values:
                result["average_selected"] = _round(sum(len(value) for value in values) / len(values), 2)
        elif question_type == "number" and values:
            result["numeric"] = {
                "min": min(values),
                "max": max(values),
                "average": _round(sum(values) / len(values)),
                "median": _round(statistics.median(values)),
            }
        elif question_type in DATE_TYPES and values:
            result["range"] = {"earliest": min(values), "latest": max(values)}
        results.append(result)

    results.sort(key=lambda r: (r["position"], r["question_id"]))
    return {"submission_count": len(submissions), "questions": results}
