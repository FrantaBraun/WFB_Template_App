# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import hashlib
import json
from dataclasses import dataclass, field

import httpx
import yaml


class SpecValidationError(Exception):
    """Raised when raw spec bytes can't be turned into a usable ParsedSpec -
    neither JSON nor YAML, not an object at the top level, or missing a
    usable info.version."""


@dataclass
class ParsedSpec:
    """content_hash is a fingerprint of what the spec says, not of its bytes
    (see _content_hash); document is the parsed spec itself, for the
    structural diff (app/services/spec_diff.py). Both are left out of == (and
    document out of repr), so they never matter to a caller that only
    compares version / title / format."""

    version: str
    title: str | None
    format: str
    content_hash: str = field(default="", compare=False)
    document: dict = field(default_factory=dict, compare=False, repr=False)


def _canonical(value: object) -> object:
    """The parsed document with every mapping key as a string, so it can be
    serialised with sorted keys: YAML happily produces integer keys (a bare
    `200:` response code) that json.dumps(sort_keys=True) cannot sort next to
    string ones, while the same spec in JSON has them as strings anyway."""
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _content_hash(parsed: object) -> str:
    """SHA-256 of the spec's content with keys sorted and no insignificant
    whitespace, so reformatting, reordering the keys of an object or sending
    the same spec as YAML instead of JSON gives the same value, while any
    change to a value, a list's order or a key does not. Used to tell a
    spec that changed from one that was only re-serialised, which a hash of
    the raw bytes (ApiDocumentVersion.checksum) cannot."""
    canonical = json.dumps(
        _canonical(parsed), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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

    return ParsedSpec(
        version=version, title=title, format=format, content_hash=_content_hash(parsed), document=parsed
    )


async def fetch_spec_from_url(url: str, timeout: float) -> bytes:
    """Fetch raw spec bytes from a documentation's source_url. Raises via
    response.raise_for_status() on a non-2xx response; a connection error
    (DNS failure, timeout, refused connection, ...) propagates as httpx's
    own exception - never swallowed here, callers decide how to react."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content
