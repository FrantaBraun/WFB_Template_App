# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The endpoints of a document, whatever kind it is: one flat list a person can
read for the kinds that have no rendered documentation here (AsyncAPI, Postman,
GraphQL) and the endpoint search indexes for every kind.

An endpoint is a `method` and a `path`: the HTTP method and path of an OpenAPI
operation or a Postman request, the direction (PUBLISH / SUBSCRIBE in 2.x, SEND /
RECEIVE in 3.x) and the channel of an AsyncAPI operation, QUERY / MUTATION /
SUBSCRIPTION and the field name of a GraphQL root field - the same labels the
version comparison uses (app/services/spec_diff.py and the kinds' own diffs)."""

from dataclasses import dataclass

from app.services import postman_spec
from app.services.asyncapi_diff import operations as asyncapi_operations
from app.services.openapi_spec import KIND_ASYNCAPI, KIND_GRAPHQL, KIND_POSTMAN, ParsedSpec

MAX_ENDPOINTS = 5000
MAX_TEXT = 1000

_HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    name: str | None = None  # summary / request name / message names / "field(args): Type"
    description: str | None = None
    tags: tuple[str, ...] = ()
    deprecated: bool = False
    operation_id: str | None = None


def _text(value: object, limit: int = MAX_TEXT) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


def _openapi(document: dict) -> list[Endpoint]:
    found: list[Endpoint] = []
    paths = document.get("paths")
    if not isinstance(paths, dict):
        return found
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method in _HTTP_METHODS:
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags")
            found.append(
                Endpoint(
                    method=method.upper(),
                    path=str(path),
                    name=_text(operation.get("summary"), 300),
                    description=_text(operation.get("description")),
                    tags=tuple(t for t in tags if isinstance(t, str)) if isinstance(tags, list) else (),
                    deprecated=operation.get("deprecated") is True,
                    operation_id=_text(operation.get("operationId"), 200),
                )
            )
    return found


def _asyncapi(document: dict) -> list[Endpoint]:
    return [
        Endpoint(
            method=direction,
            path=channel,
            name=_text(", ".join(operation.messages), 300),
            deprecated=operation.deprecated,
        )
        for (direction, channel), operation in sorted(asyncapi_operations(document).items(), key=lambda pair: pair[0][1])
    ]


def _postman(document: dict) -> list[Endpoint]:
    return [
        Endpoint(
            method=request.method,
            path=request.path,
            name=_text(request.name, 300),
            description=_text(request.description),
        )
        for request in postman_spec.requests(document)
    ]


def _graphql(schema: object) -> list[Endpoint]:
    found: list[Endpoint] = []
    for label, root in (
        ("QUERY", schema.query_type),
        ("MUTATION", schema.mutation_type),
        ("SUBSCRIPTION", schema.subscription_type),
    ):
        if root is None:
            continue
        for field_name, field in root.fields.items():
            arguments = ", ".join(f"{name}: {argument.type}" for name, argument in field.args.items())
            signature = f"{field_name}({arguments}): {field.type}" if arguments else f"{field_name}: {field.type}"
            found.append(
                Endpoint(
                    method=label,
                    path=field_name,
                    name=_text(signature, 300),
                    description=_text(field.description),
                    deprecated=bool(field.deprecation_reason),
                )
            )
    return found


def extract_endpoints(parsed: ParsedSpec) -> list[Endpoint]:
    """The endpoints of a parsed document, in document order (AsyncAPI by
    channel), at most MAX_ENDPOINTS. Never raises on an odd document."""
    try:
        if parsed.kind == KIND_GRAPHQL:
            found = _graphql(parsed.schema)
        elif parsed.kind == KIND_POSTMAN:
            found = _postman(parsed.document)
        elif parsed.kind == KIND_ASYNCAPI:
            found = _asyncapi(parsed.document)
        else:
            found = _openapi(parsed.document)
    except (AttributeError, TypeError, ValueError):
        return []
    return found[:MAX_ENDPOINTS]
