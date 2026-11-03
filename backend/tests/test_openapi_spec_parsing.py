# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.openapi_spec.parse_spec - JSON/YAML parsing and
info.version/info.title extraction. fetch_spec_from_url is exercised via
respx in the future router tests (a later phase), not here."""

import json

import pytest

from app.services.openapi_spec import ParsedSpec, SpecValidationError, parse_spec


def test_parse_spec_valid_minimal_json():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Example API", "version": "1.2.3"},
        "paths": {},
    }
    raw = json.dumps(spec).encode("utf-8")

    result = parse_spec(raw)

    assert result == ParsedSpec(version="1.2.3", title="Example API", format="json")


def test_parse_spec_valid_minimal_yaml():
    raw = b"""
openapi: "3.0.0"
info:
  title: Example API
  version: "1.2.3"
paths: {}
"""

    result = parse_spec(raw)

    assert result == ParsedSpec(version="1.2.3", title="Example API", format="yaml")


def test_parse_spec_json_missing_info_version_raises():
    spec = {"openapi": "3.0.0", "info": {"title": "Example API"}, "paths": {}}
    raw = json.dumps(spec).encode("utf-8")

    with pytest.raises(SpecValidationError):
        parse_spec(raw)


def test_parse_spec_yaml_missing_info_version_raises():
    raw = b"""
openapi: "3.0.0"
info:
  title: Example API
paths: {}
"""

    with pytest.raises(SpecValidationError):
        parse_spec(raw)


def test_parse_spec_garbage_bytes_raises():
    """Bytes that are invalid UTF-8 (0xff is not a valid byte anywhere in a
    UTF-8 sequence) fail to decode under both the JSON and YAML paths, so
    this exercises parse_spec's "neither format parses" branch specifically
    - distinct from the missing-info.version tests above, which parse fine
    but fail the content checks."""
    raw = b"\xff\xff\xff\xff"

    with pytest.raises(SpecValidationError):
        parse_spec(raw)


# --- content_hash: a fingerprint of what the spec says, not of its bytes ----------------


def _hash(spec: dict, as_yaml: bool = False, **dump_kwargs) -> str:
    import json

    import yaml

    raw = yaml.safe_dump(spec).encode() if as_yaml else json.dumps(spec, **dump_kwargs).encode()
    return parse_spec(raw).content_hash


_SPEC = {"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "paths": {"/a": {"get": {}}, "/b": {"get": {}}}}


def test_content_hash_ignores_formatting_key_order_and_json_vs_yaml():
    reordered = {"paths": {"/b": {"get": {}}, "/a": {"get": {}}}, "info": {"version": "1", "title": "T"}, "openapi": "3.0.0"}

    baseline = _hash(_SPEC)

    assert baseline
    assert _hash(_SPEC, indent=4) == baseline
    assert _hash(_SPEC, sort_keys=True, separators=(",", ":")) == baseline
    assert _hash(reordered) == baseline
    assert _hash(_SPEC, as_yaml=True) == baseline


def test_content_hash_changes_with_values_keys_and_list_order():
    baseline = _hash(_SPEC)
    other_value = {**_SPEC, "info": {"title": "T2", "version": "1"}}
    extra_key = {**_SPEC, "servers": [{"url": "https://x"}]}

    assert _hash(other_value) != baseline
    assert _hash(extra_key) != baseline
    assert _hash({**_SPEC, "tags": ["a", "b"]}) != _hash({**_SPEC, "tags": ["b", "a"]})


def test_content_hash_of_yaml_with_integer_keys_matches_the_json_spelling():
    """A bare `200:` is an integer key in YAML (a string in JSON), which
    sorted-key serialisation cannot order next to string keys unless every
    key is turned into a string first."""
    yaml_text = (
        "openapi: 3.0.0\ninfo: {title: T, version: '1'}\n"
        "paths:\n  /a:\n    get:\n      responses:\n        200: {description: ok}\n        default: {description: err}\n"
    )
    json_spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1"},
        "paths": {"/a": {"get": {"responses": {"200": {"description": "ok"}, "default": {"description": "err"}}}}},
    }

    assert parse_spec(yaml_text.encode()).content_hash == _hash(json_spec)


def test_content_hash_does_not_take_part_in_equality():
    assert ParsedSpec(version="1", title=None, format="json", content_hash="a") == ParsedSpec(
        version="1", title=None, format="json", content_hash="b"
    )
