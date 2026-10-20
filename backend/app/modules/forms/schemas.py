# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Any, Literal

import regex
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.modules.forms.logic import (
    MAX_CONDITIONS,
    MAX_OPTIONS,
    MAX_REGEX_LENGTH,
    MAX_TEXT_LENGTH,
    QUESTION_TYPES,
    compile_pattern,
    parse_date_value,
    validate_condition_value,
)

QuestionType = Literal["checkbox", "radio", "text", "number", "date", "time", "datetime"]
Operator = Literal["answered", "not_answered", "equals", "not_equals", "contains", "not_contains", "gt", "gte", "lt", "lte"]

MAX_QUESTIONS = 100

# Strings an administrator's pattern is tried against when it is saved: a
# pattern that cannot get through them in a few milliseconds is the kind that
# hangs on a stranger's input (catastrophic backtracking) and is refused.
_REGEX_PROBES = ("a" * 60 + "!", "ab" * 30 + "!", " " * 60 + "!", "a" * 30 + "b" * 30 + "!", "1" * 60 + "x")
_REGEX_PROBE_TIMEOUT = 0.05


# --- Per-type configuration -----------------------------------------------------


class OptionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    label: str = Field(min_length=1, max_length=200)


def _check_options(options: list[OptionConfig]) -> None:
    ids = [option.id for option in options]
    if len(set(ids)) != len(ids):
        raise ValueError("option ids must be unique")


class CheckboxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[OptionConfig] = Field(min_length=1, max_length=MAX_OPTIONS)
    min_select: int = Field(default=0, ge=0)
    max_select: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _consistent(self):
        _check_options(self.options)
        if self.min_select > len(self.options):
            raise ValueError("min_select is more than the number of options")
        if self.max_select is not None:
            if self.max_select > len(self.options):
                raise ValueError("max_select is more than the number of options")
            if self.max_select < self.min_select:
                raise ValueError("max_select is less than min_select")
        return self


class RadioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[OptionConfig] = Field(min_length=1, max_length=MAX_OPTIONS)

    @model_validator(mode="after")
    def _consistent(self):
        _check_options(self.options)
        return self


class TextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    multiline: bool = False
    min_length: int = Field(default=0, ge=0, le=MAX_TEXT_LENGTH)
    max_length: int = Field(default=MAX_TEXT_LENGTH, ge=1, le=MAX_TEXT_LENGTH)
    regex: str | None = Field(default=None, max_length=MAX_REGEX_LENGTH)

    @model_validator(mode="after")
    def _consistent(self):
        if self.min_length > self.max_length:
            raise ValueError("min_length is more than max_length")
        if self.regex is not None and self.regex.strip() == "":
            self.regex = None
        if self.regex is not None:
            try:
                compile_pattern(self.regex)
            except regex.error as exc:
                raise ValueError(f"invalid regular expression: {exc}") from exc
            for probe in _REGEX_PROBES:
                try:
                    regex.search(self.regex, probe, timeout=_REGEX_PROBE_TIMEOUT)
                except TimeoutError as exc:
                    raise ValueError("the regular expression is too complex (it backtracks catastrophically)") from exc
        return self


class NumberConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["integer", "decimal"] = "integer"
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min is more than max")
        return self


def _date_config(question_type: str):
    class _Config(BaseModel):
        model_config = ConfigDict(extra="forbid")

        min: str | None = None
        max: str | None = None

        @model_validator(mode="after")
        def _consistent(self):
            for name in ("min", "max"):
                value = getattr(self, name)
                if value is not None and parse_date_value(question_type, value) is None:
                    raise ValueError(f"{name} must be a valid {question_type}")
            if self.min is not None and self.max is not None and self.min > self.max:
                raise ValueError("min is later than max")
            return self

    _Config.__name__ = f"{question_type.capitalize()}Config"
    return _Config


CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "checkbox": CheckboxConfig,
    "radio": RadioConfig,
    "text": TextConfig,
    "number": NumberConfig,
    "date": _date_config("date"),
    "time": _date_config("time"),
    "datetime": _date_config("datetime"),
}
assert set(CONFIG_MODELS) == set(QUESTION_TYPES)


def normalize_config(question_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """The configuration of a question with the defaults filled in; ValueError
    if it doesn't fit the type."""
    try:
        return CONFIG_MODELS[question_type].model_validate(config).model_dump()
    except ValidationError as exc:
        raise ValueError("; ".join(f"{'.'.join(map(str, e['loc'])) or 'config'}: {e['msg']}" for e in exc.errors())) from exc


# --- Writing a form -------------------------------------------------------------


class ConditionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: uuid.UUID
    operator: Operator
    value: Any = None


class QuestionIn(BaseModel):
    """One question as the builder sends it. `id` is chosen by the client (a
    new question needs one before it is saved, so that other questions'
    conditions can refer to it); position is the question's place in the list."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    type: QuestionType
    label: str = Field(min_length=1, max_length=300)
    help_text: str = Field(default="", max_length=500)
    required: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    conditions: list[ConditionIn] = Field(default_factory=list, max_length=MAX_CONDITIONS)

    @model_validator(mode="after")
    def _normalise_config(self):
        self.config = normalize_config(self.type, self.config)
        return self


class QuestionsReplace(BaseModel):
    """The whole ordered list of a form's questions. Checked as a whole: ids
    unique, and every condition refers to an EARLIER question with an operator
    and value that suit it."""

    model_config = ConfigDict(extra="forbid")

    questions: list[QuestionIn] = Field(max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def _conditions_are_valid(self):
        ids = [question.id for question in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("question ids must be unique")
        earlier: dict[uuid.UUID, QuestionIn] = {}
        for question in self.questions:
            for condition in question.conditions:
                source = earlier.get(condition.question_id)
                if source is None:
                    raise ValueError(
                        f"a condition of {str(question.id)!r} refers to a question that is not earlier in the form"
                    )
                condition.value = validate_condition_value(source.type, source.config, condition.operator, condition.value)
            earlier[question.id] = question
        return self


class FormCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


# --- Reading --------------------------------------------------------------------


class QuestionOut(BaseModel):
    """A question as a client renders it - the same for the builder and for the
    visitor's form (there is nothing in a definition that must be kept back)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    type: str
    label: str
    help_text: str
    required: bool
    config: dict[str, Any]
    conditions: list[dict[str, Any]]


class FormOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    questions: list[QuestionOut]


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    form_id: uuid.UUID
    created_at: datetime
    answers: list[dict[str, Any]]


class SubmissionPage(BaseModel):
    items: list[SubmissionOut]
    has_more: bool


class StatsOut(BaseModel):
    submission_count: int
    questions: list[dict[str, Any]]

