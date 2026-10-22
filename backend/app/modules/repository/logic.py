# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules of the repository module, pure and database-free: slugs, what an
attribute may be configured as, and how a record's values are validated and
normalized. Everything that needs the database (does this reference point at a
record that exists, is this image the caller's) is reported back for the
caller to check - `normalize_record_data` collects the reference and image ids
it met instead of looking them up.

How a record stores its values (`Record.data`, JSONB): a map from the attribute's
id (a UUID string - stable, so renaming an attribute costs nothing) to a value.
A value that is not set is simply absent; "" and an empty list/map count as not
set. Per type:

- text: a string of at most MAX_TEXT_LENGTH characters, trimmed;
- number: a JSON number (finite, at most MAX_ABS_NUMBER in size);
- boolean: true / false;
- date: "YYYY-MM-DD"; datetime: "YYYY-MM-DDTHH:MM" (no time zone, like forms);
- image: the id (UUID string) of a row of the images table;
- reference: the id (UUID string) of a record of the table the attribute points to;
- list / map: an object whose values are all of the attribute's one simple
  element type. A list is technically a map whose keys are "0".."n-1" - they
  are renumbered here whenever the order changes or an element is removed;
  the keys of a map are the user's (non-empty, MAX_MAP_KEY_LENGTH, unique).

Errors are short codes (`required`, `too_long`, `invalid_date`, ...) keyed by
the attribute id - or `<attribute id>.<index or key>` for one element, or `data`
for the record as a whole (`record_too_large`: more than MAX_RECORD_BYTES of
values together) - so the frontend can turn them into the user's language (the
shape `forms` uses).
"""

import json
import math
import re
import unicodedata
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

ATTRIBUTE_TYPES = ("text", "number", "boolean", "date", "datetime", "image", "reference", "list", "map")
# What a list or map may hold: one simple type, never another list or map.
ELEMENT_TYPES = ("text", "number", "boolean", "date", "datetime", "image", "reference")
VIEW_TYPES = ("table", "grid")

# The colour schemes of a repository. Only the keys live here (the backend
# validates them); the colours - a light and a dark variant of each - belong to
# the frontend.
COLOR_SCHEMES = ("blue", "teal", "green", "amber", "orange", "red", "pink", "violet")
DEFAULT_COLOR_SCHEME = "blue"

# Slugs that would collide with a route (`/repository/new`, `/table/:t/edit`, `/repository/:r/tables`).
RESERVED_SLUGS = frozenset({"new", "edit", "tables"})

MAX_NAME_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 2000
MAX_SLUG_LENGTH = 80
MAX_RECORD_NAME_LENGTH = 200
MAX_TEXT_LENGTH = 5000
MAX_ELEMENTS = 200
MAX_MAP_KEY_LENGTH = 100
MAX_ABS_NUMBER = 1e15
# What all the values of one record may take together, serialized: 50 attributes of 200 texts of 5000
# characters would be 50 MB, which is not a record.
MAX_RECORD_BYTES = 256 * 1024
MIN_YEAR = 1000

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")

# Letters NFKD does not take apart.
_TRANSLITERATE = str.maketrans({"ł": "l", "đ": "d", "ø": "o", "ð": "d", "ß": "ss", "æ": "ae", "œ": "oe", "þ": "th"})


# --- Slugs ----------------------------------------------------------------------


def slugify(text: str) -> str:
    """A slug for `text`: lower case, diacritics removed, anything outside
    [a-z0-9] turned into single hyphens, at most MAX_SLUG_LENGTH characters.
    Can be empty (a name with no letters or digits)."""
    decomposed = unicodedata.normalize("NFKD", text.lower().translate(_TRANSLITERATE))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    return slug[:MAX_SLUG_LENGTH].strip("-")


def slug_problem(slug: str) -> str | None:
    """Why `slug` cannot be used as it is - "invalid" or "reserved" - or None."""
    if len(slug) > MAX_SLUG_LENGTH or not SLUG_RE.match(slug):
        return "invalid"
    if slug in RESERVED_SLUGS:
        return "reserved"
    return None


def unique_slug(name: str, taken: Collection[str]) -> str:
    """The slug for `name` that is neither `taken` nor reserved: the plain one
    if it is free, else `-2`, `-3`, ... appended."""
    base = slugify(name) or "item"
    candidate, number = base, 2
    while candidate in taken or candidate in RESERVED_SLUGS:
        suffix = f"-{number}"
        candidate = base[: MAX_SLUG_LENGTH - len(suffix)].rstrip("-") + suffix
        number += 1
    return candidate


# --- Attribute configuration ----------------------------------------------------


def _canonical_uuid(value: Any) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if not isinstance(value, str):
        raise ValueError("not a UUID")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ValueError("not a UUID") from exc


def canonical_config(attribute_type: str, config: Mapping[str, Any] | None) -> dict[str, str]:
    """The configuration an attribute of this type is saved with (ids as plain
    strings), or ValueError when it is wrong for the type:

    - reference: {"table_id"} - the table of the same repository it points to;
    - list / map: {"element_type"} and, for references, {"table_id"};
    - everything else: none."""
    config = dict(config or {})
    if attribute_type == "reference":
        _only_keys(config, {"table_id"})
        return {"table_id": _table_id(config)}
    if attribute_type in ("list", "map"):
        _only_keys(config, {"element_type", "table_id"})
        element_type = config.get("element_type")
        if element_type not in ELEMENT_TYPES:
            raise ValueError(f"element_type must be one of {', '.join(ELEMENT_TYPES)}")
        if element_type == "reference":
            return {"element_type": element_type, "table_id": _table_id(config)}
        if "table_id" in config:
            raise ValueError("table_id is only for a list or map of references")
        return {"element_type": element_type}
    if attribute_type not in ATTRIBUTE_TYPES:
        raise ValueError(f"type must be one of {', '.join(ATTRIBUTE_TYPES)}")
    if config:
        raise ValueError(f"a {attribute_type} attribute takes no configuration")
    return {}


def _only_keys(config: Mapping[str, Any], allowed: set[str]) -> None:
    extra = set(config) - allowed
    if extra:
        raise ValueError(f"unknown configuration: {', '.join(sorted(extra))}")


def _table_id(config: Mapping[str, Any]) -> str:
    if "table_id" not in config:
        raise ValueError("table_id is required")
    try:
        return _canonical_uuid(config["table_id"])
    except ValueError as exc:
        raise ValueError("table_id must be a UUID") from exc


def referenced_table_id(attribute_type: str, config: Mapping[str, Any]) -> str | None:
    """The table an attribute points at (a reference, or a list/map of
    references), else None."""
    if attribute_type == "reference":
        return config.get("table_id")
    if attribute_type in ("list", "map") and config.get("element_type") == "reference":
        return config.get("table_id")
    return None


def element_type_of(attribute_type: str, config: Mapping[str, Any]) -> str:
    """The simple type of the values an attribute holds: its own, or the element type of a list/map."""
    if attribute_type in ("list", "map"):
        return config["element_type"]
    return attribute_type


# --- Values ---------------------------------------------------------------------


class ValueIssue(Exception):
    """A value that cannot be stored; `code` is what the frontend translates."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AttributeSpec:
    """The part of an attribute that validating a record's values needs."""

    id: str
    type: str
    required: bool = False
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedData:
    """What `normalize_record_data` returns: the values to store, the errors
    (empty when it is fine), and what the caller still has to check in the
    database - the record ids met in references (by the table they must belong
    to) and the image ids."""

    data: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    references: dict[str, set[str]] = field(default_factory=dict)
    image_ids: set[str] = field(default_factory=set)


def parse_date(value: Any) -> str:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ValueIssue("invalid_date")
    try:
        parsed = date(int(value[:4]), int(value[5:7]), int(value[8:10]))
    except ValueError as exc:
        raise ValueIssue("invalid_date") from exc
    if parsed.year < MIN_YEAR:
        raise ValueIssue("invalid_date")
    return value


def parse_datetime(value: Any) -> str:
    if not isinstance(value, str) or not _DATETIME_RE.match(value):
        raise ValueIssue("invalid_datetime")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError as exc:
        raise ValueIssue("invalid_datetime") from exc
    if parsed.year < MIN_YEAR:
        raise ValueIssue("invalid_datetime")
    return value


def normalize_scalar(value_type: str, value: Any) -> Any:
    """`value` as a simple type stores it, or ValueIssue. A text may come back
    empty - the caller decides what that means."""
    if value_type == "text":
        if not isinstance(value, str):
            raise ValueIssue("invalid_type")
        text = value.strip()
        if "\x00" in text:
            raise ValueIssue("invalid_text")  # PostgreSQL cannot store a NUL in text or JSONB
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueIssue("too_long")
        return text
    if value_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueIssue("invalid_type")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueIssue("invalid_number")
        if abs(value) > MAX_ABS_NUMBER:
            raise ValueIssue("out_of_range")
        return value
    if value_type == "boolean":
        if not isinstance(value, bool):
            raise ValueIssue("invalid_type")
        return value
    if value_type == "date":
        return parse_date(value)
    if value_type == "datetime":
        return parse_datetime(value)
    if value_type in ("image", "reference"):
        try:
            return _canonical_uuid(value)
        except ValueError as exc:
            raise ValueIssue("invalid_reference" if value_type == "reference" else "invalid_image") from exc
    raise ValueIssue("invalid_type")


def _collect(spec_type: str, value: Any, table_id: str | None, result: NormalizedData) -> None:
    if spec_type == "image":
        result.image_ids.add(value)
    elif spec_type == "reference" and table_id is not None:
        result.references.setdefault(table_id, set()).add(value)


def _list_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if not all(isinstance(key, str) and key.isdigit() for key in value):
            raise ValueIssue("invalid_type")
        return [value[key] for key in sorted(value, key=int)]
    raise ValueIssue("invalid_type")


def _normalize_attribute(spec: AttributeSpec, value: Any, result: NormalizedData) -> Any | None:
    """The stored value of one attribute (None = not set); problems go to result.errors."""
    table_id = referenced_table_id(spec.type, spec.config)
    if spec.type in ("list", "map"):
        element_type = spec.config["element_type"]
        if spec.type == "list":
            try:
                items = list(enumerate(_list_items(value)))
            except ValueIssue as issue:
                result.errors[spec.id] = issue.code
                return None
        else:
            if not isinstance(value, dict):
                result.errors[spec.id] = "invalid_type"
                return None
            items = list(value.items())
        if len(items) > MAX_ELEMENTS:
            result.errors[spec.id] = "too_many_elements"
            return None
        stored: dict[str, Any] = {}
        for key, element in items:
            if spec.type == "map":
                if not isinstance(key, str):
                    result.errors[spec.id] = "invalid_key"
                    return None
                name = key.strip()
                if name == "" or len(name) > MAX_MAP_KEY_LENGTH or "\x00" in name:
                    result.errors[f"{spec.id}.{key}"] = "invalid_key"
                    continue
            else:
                name = str(key)
            if name in stored:
                result.errors[f"{spec.id}.{key}"] = "duplicate_key"
                continue
            try:
                normalized = normalize_scalar(element_type, element)
                if normalized == "":
                    raise ValueIssue("required")
            except ValueIssue as issue:
                result.errors[f"{spec.id}.{key}"] = issue.code
                continue
            _collect(element_type, normalized, table_id, result)
            stored[name] = normalized
        return stored or None
    try:
        normalized = normalize_scalar(spec.type, value)
    except ValueIssue as issue:
        result.errors[spec.id] = issue.code
        return None
    if normalized == "" and spec.type == "text":
        return None
    _collect(spec.type, normalized, table_id, result)
    return normalized


def normalize_record_data(specs: Sequence[AttributeSpec], data: Mapping[str, Any]) -> NormalizedData:
    """Validates and normalizes the values a user sent for a record (`data`:
    attribute id -> value; null, "" and an empty list/map mean "not set") against
    the table's attributes. A value for an attribute the table does not have is
    an error (`unknown_attribute`), as is a missing value of a required one
    (`required`)."""
    by_id = {spec.id: spec for spec in specs}
    result = NormalizedData()
    for key, value in data.items():
        spec = by_id.get(key)
        if spec is None:
            result.errors[key] = "unknown_attribute"
            continue
        if value is None:
            continue
        stored = _normalize_attribute(spec, value, result)
        if stored is not None:
            result.data[key] = stored
    for spec in specs:
        if spec.required and spec.id not in result.data and spec.id not in result.errors:
            result.errors[spec.id] = "required"
    if not result.errors and len(json.dumps(result.data, ensure_ascii=False).encode("utf-8")) > MAX_RECORD_BYTES:
        result.errors["data"] = "record_too_large"
    return result


def normalize_record_name(value: Any) -> str:
    """The name of a record (`name`): a non-empty text of at most MAX_RECORD_NAME_LENGTH characters."""
    if not isinstance(value, str):
        raise ValueIssue("invalid_type")
    name = value.strip()
    if name == "":
        raise ValueIssue("required")
    if "\x00" in name:
        raise ValueIssue("invalid_text")
    if len(name) > MAX_RECORD_NAME_LENGTH:
        raise ValueIssue("too_long")
    return name


def ids_in(attributes: Sequence[Any], data: Mapping[str, Any], simple_type: str) -> set[str]:
    """The ids a record's `data` holds through the attributes of one simple type
    (image or reference): the value itself, or the values of a list or map of
    that type. `attributes` need `id`, `type` and `config` (rows, AttributeSpec
    and the request's AttributeIn all do)."""
    found: set[str] = set()
    for attribute in attributes:
        if element_type_of(attribute.type, attribute.config) != simple_type:
            continue
        value = data.get(str(attribute.id))
        if value is None:
            continue
        if attribute.type in ("list", "map"):
            found.update(value.values())
        else:
            found.add(value)
    return found


def reference_ids_in(attributes: Sequence[Any], data: Mapping[str, Any]) -> set[str]:
    """The record ids `data` points at."""
    return ids_in(attributes, data, "reference")


def image_ids_in(attributes: Sequence[Any], data: Mapping[str, Any]) -> set[str]:
    """The image ids `data` holds."""
    return ids_in(attributes, data, "image")
