# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import json
from dataclasses import dataclass

import httpx
import yaml


class SpecValidationError(Exception):
    """Raised when raw spec bytes can't be turned into a usable ParsedSpec -
    neither JSON nor YAML, not an object at the top level, or missing a
    usable info.version."""


@dataclass
class ParsedSpec:
    version: str
    title: str | None
    format: str


def parse_spec(raw: bytes) -> ParsedSpec:
    """Parse raw OpenAPI/Swagger spec bytes: try JSON first, fall back to
    YAML (a JSON document is also valid YAML, but not vice versa, so JSON is
    tried first rather than relying on YAML alone). Extracts info.version /
    info.title. Raises SpecValidationError - with a message describing which
    check failed - if neither format parses, the parsed content isn't an
    object at the top level, "info" is missing/not an object, or
    info.version is missing or not a non-empty string.
    """
    try:
        parsed = json.loads(raw)
        format = "json"
    except (json.JSONDecodeError, UnicodeDecodeError):
        try:
            parsed = yaml.safe_load(raw)
            format = "yaml"
        except yaml.YAMLError as exc:
            raise SpecValidationError(
                "Spec content could not be parsed as either JSON or YAML."
            ) from exc

    if not isinstance(parsed, dict):
        raise SpecValidationError(
            "Parsed spec content must be a JSON/YAML object at the top level."
        )

    info = parsed.get("info")
    if not isinstance(info, dict):
        raise SpecValidationError('Spec is missing a top-level "info" object.')

    version = info.get("version")
    if not isinstance(version, str) or not version:
        raise SpecValidationError('Spec\'s "info.version" must be a non-empty string.')

    title = info.get("title")
    if not isinstance(title, str):
        title = None

    return ParsedSpec(version=version, title=title, format=format)


async def fetch_spec_from_url(url: str, timeout: float) -> bytes:
    """Fetch raw spec bytes from a documentation's source_url. Raises via
    response.raise_for_status() on a non-2xx response; a connection error
    (DNS failure, timeout, refused connection, ...) propagates as httpx's
    own exception - never swallowed here, callers decide how to react."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content
