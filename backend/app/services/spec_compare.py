# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""One place that compares two parsed documents whatever kind they are:
OpenAPI / Swagger (app/services/spec_diff.py), AsyncAPI, Postman collections
and GraphQL schemas, each by its own rules but all answering with the same
structured, severity-graded changes."""

from app.services.asyncapi_diff import diff_asyncapi
from app.services.graphql_diff import diff_graphql
from app.services.openapi_spec import KIND_ASYNCAPI, KIND_GRAPHQL, KIND_POSTMAN, ParsedSpec
from app.services.postman_diff import diff_postman
from app.services.spec_diff import Change, SpecDiff, diff_specs


def diff_parsed(old: ParsedSpec, new: ParsedSpec) -> SpecDiff:
    """The changes from `old` to `new`. A document that was one kind and is now
    another (an OpenAPI file replaced by a GraphQL schema, say) is a single
    breaking change - there is no meaningful comparison to make."""
    if old.kind != new.kind:
        return SpecDiff([Change("spec_type_changed", "breaking", detail={"from": old.kind, "to": new.kind})])
    if new.kind == KIND_GRAPHQL:
        return diff_graphql(old.schema, new.schema)
    if new.kind == KIND_POSTMAN:
        return diff_postman(old.document, new.document)
    if new.kind == KIND_ASYNCAPI:
        return diff_asyncapi(old.document, new.document)
    return diff_specs(old.document, new.document)
