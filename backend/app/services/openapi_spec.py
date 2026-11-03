# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import hashlib
import json
from dataclasses import dataclass, field

import httpx
import yaml

from app.services import graphql_spec, postman_spec
from app.services.safe_http import UnsafeUrlError, safe_get


KIND_OPENAPI = "openapi"  # OpenAPI 3.x, Swagger 2.0 - and any other document with info.version
KIND_ASYNCAPI = "asyncapi"
KIND_POSTMAN = "postman"
KIND_GRAPHQL = "graphql"


class SpecValidationError(Exception):
    """Raised when raw spec bytes can't be turned into a usable ParsedSpec -
    not JSON, YAML or a GraphQL schema, not an object at the top level, or
    missing a usable info.version."""


@dataclass
class ParsedSpec:
    """What a stored document is. kind says which sort it is - "openapi" (also
    Swagger, and any other JSON/YAML with info.version), "asyncapi", "postman"
    (a Postman collection) or "graphql" (SDL, or an introspection result) -
    and format how it is written: "json", "yaml" or "graphql" (SDL text).

    content_hash is a fingerprint of what the document says, not of its bytes
    (see _content_hash); document is the parsed JSON/YAML (for a GraphQL
    schema given as SDL it is empty) and schema the GraphQL schema object
    (None for the others), both for the structural comparison
    (app/services/spec_compare.py). These are left out of == (and out of
    repr), so they never matter to a caller that only compares version /
    title / format / kind."""

    version: str
    title: str | None
    format: str
    kind: str = KIND_OPENAPI
    content_hash: str = field(default="", compare=False)
    document: dict = field(default_factory=dict, compare=False, repr=False)
    schema: object | None = field(default=None, compare=False, repr=False)


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


def _parse_graphql(schema: object, format: str, document: dict) -> ParsedSpec:
    return ParsedSpec(
        version=graphql_spec.revision_label(graphql_spec.structure_signature(schema)),
        title=None,
        format=format,
        kind=KIND_GRAPHQL,
        content_hash=graphql_spec.content_hash(schema),
        document=document,
        schema=schema,
    )


def _parse_document(parsed: dict, format: str) -> ParsedSpec:
    """A JSON/YAML object, recognised by what it is: a GraphQL introspection
    result, a Postman collection, an AsyncAPI document - or, failing those,
    anything with info.version, which is what an OpenAPI / Swagger document is
    (and what this application accepted before it knew other kinds)."""
    introspection = graphql_spec.introspection_data(parsed)
    if introspection is not None:
        try:
            schema = graphql_spec.schema_from_introspection(introspection)
        except ValueError as exc:
            raise SpecValidationError(str(exc)) from exc
        return _parse_graphql(schema, format, parsed)

    if "asyncapi" not in parsed and postman_spec.is_postman(parsed):
        return ParsedSpec(
            version=postman_spec.version_of(parsed),
            title=postman_spec.title(parsed),
            format=format,
            kind=KIND_POSTMAN,
            content_hash=_content_hash(parsed),
            document=parsed,
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
        version=version,
        title=title,
        format=format,
        kind=KIND_ASYNCAPI if "asyncapi" in parsed else KIND_OPENAPI,
        content_hash=_content_hash(parsed),
        document=parsed,
    )


def _text_of(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def parse_spec(raw: bytes) -> ParsedSpec:
    """Parse the raw bytes of a stored document. JSON is tried first, then YAML
    (a JSON document is also valid YAML, but not vice versa, so JSON is tried
    first rather than relying on YAML alone); what parses to an object is
    recognised by what it is (_parse_document). What does not parse to an
    object - GraphQL SDL, which YAML takes for a plain string - is tried as a
    GraphQL schema last.

    Raises SpecValidationError - with a message describing which check failed
    - if nothing parses, the parsed content isn't an object at the top level,
    "info" is missing/not an object, or info.version is missing or not a
    non-empty string (the last two for documents that are not a GraphQL
    schema or a Postman collection).
    """
    parsed: object = None
    yaml_failed = False
    try:
        parsed = json.loads(raw)
        format = "json"
        is_json = True
    except (json.JSONDecodeError, UnicodeDecodeError):
        is_json = False
        format = "yaml"
        try:
            parsed = yaml.safe_load(raw)
        except yaml.YAMLError:
            yaml_failed = True

    if isinstance(parsed, dict):
        return _parse_document(parsed, format)

    if not is_json:
        text = _text_of(raw)
        if text is not None and text.strip():
            try:
                schema = graphql_spec.schema_from_sdl(text)
            except ValueError:
                pass
            else:
                return _parse_graphql(schema, "graphql", {})
        if yaml_failed or not isinstance(parsed, (list, dict)):
            raise SpecValidationError("Spec content could not be parsed as either JSON or YAML, or as a GraphQL schema.")

    raise SpecValidationError("Parsed spec content must be a JSON/YAML object at the top level.")


async def fetch_spec_from_url(url: str, timeout: float, *, max_bytes: int, allow_private: bool = False) -> bytes:
    """Fetch raw spec bytes from a documentation's source_url - an address a
    user typed in, called from this server, so it goes through
    app/services/safe_http.py: unless `allow_private` (the deployment's
    Settings.outbound_allow_private_addresses) it must resolve only to public
    addresses, and redirects are not followed. The body is read only up to
    `max_bytes`; a longer one is a SpecValidationError, not something held
    in memory first and measured afterwards.

    Raises SpecValidationError for an address that may not be called or a body
    that is too large, httpx.HTTPStatusError (as raise_for_status does) for a
    non-2xx answer, a redirect included, and a connection error (DNS failure,
    timeout, refused connection, ...) propagates as httpx's own exception -
    never swallowed here, callers decide how to react."""
    try:
        response = await safe_get(url, {}, timeout=timeout, max_bytes=max_bytes, allow_private=allow_private)
    except UnsafeUrlError as exc:
        raise SpecValidationError(str(exc)) from exc
    if not 200 <= response.status_code < 300:
        request = httpx.Request("GET", url)
        raise httpx.HTTPStatusError(
            f"The server answered {response.status_code}",
            request=request,
            response=httpx.Response(response.status_code, request=request),
        )
    if response.truncated:
        raise SpecValidationError(f"Spec content is larger than the {max_bytes} byte limit.")
    return response.body
