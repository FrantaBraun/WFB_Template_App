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
