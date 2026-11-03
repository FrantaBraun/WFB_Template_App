# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""GraphQL schemas as documentation: reading one (SDL text, or the JSON an
introspection query answers with), the fingerprints that tell whether it
changed, and - further down - comparing two of them.

A GraphQL schema has no version number, so the "version" of one is derived
from its STRUCTURE: `rev-` and eight hex digits of a hash over the types,
fields, arguments, enum values and so on (never descriptions or the order
things are written in). A change of structure is therefore a new version, with
the breaking changes between the two worked out; a change of wording only
keeps the version and counts as a content change - exactly the pair of cases an
OpenAPI document has, where the vendor types the number instead."""

import hashlib

from graphql import (
    Undefined,
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLUnionType,
    build_client_schema,
    build_schema,
    lexicographic_sort_schema,
    print_schema,
)
from graphql.language import print_ast
from graphql.type import specified_directives

REVISION_PREFIX = "rev-"

_BUILT_IN_DIRECTIVES = {directive.name for directive in specified_directives}


def revision_label(signature: str) -> str:
    """The version string of a document that carries none: `rev-` and the
    first eight hex digits of a hash of its structure."""
    return REVISION_PREFIX + hashlib.sha256(signature.encode("utf-8")).hexdigest()[:8]


def introspection_data(document: object) -> dict | None:
    """The `__schema` part of an introspection result - the document either is
    `{"data": {"__schema": ...}}` (what a GraphQL endpoint answers with) or
    `{"__schema": ...}` - or None when this is not one."""
    if not isinstance(document, dict):
        return None
    candidate = document.get("data") if isinstance(document.get("data"), dict) else document
    return candidate if isinstance(candidate.get("__schema"), dict) else None


def schema_from_introspection(data: dict) -> GraphQLSchema:
    """Raises ValueError for an introspection result that does not describe a schema."""
    try:
        return build_client_schema(data)
    except Exception as exc:  # graphql-core raises TypeError / GraphQLError / KeyError for malformed input
        raise ValueError("The introspection result is not a valid GraphQL schema") from exc


def schema_from_sdl(text: str) -> GraphQLSchema:
    """Raises ValueError for text that is not a valid GraphQL schema."""
    try:
        return build_schema(text)
    except Exception as exc:
        raise ValueError("The text is not a valid GraphQL schema") from exc


def canonical_sdl(schema: GraphQLSchema) -> str:
    """The schema printed with its types, fields and arguments sorted: one
    text for one schema however it was written (SDL in any order, or an
    introspection result). Descriptions are in it, so a reworded description
    is a different text."""
    return print_schema(lexicographic_sort_schema(schema))


def content_hash(schema: GraphQLSchema) -> str:
    return hashlib.sha256(canonical_sdl(schema).encode("utf-8")).hexdigest()


def default_text(item) -> str:
    """The default value of an argument or input field as text, "" when it has
    none. graphql-core 3.3 keeps a default as a literal in `.default` (and
    leaves `.default_value` Undefined), older versions as a value."""
    default = getattr(item, "default", None)
    if default is not None:
        literal = getattr(default, "literal", None)
        if literal is not None:
            return print_ast(literal)
        value = getattr(default, "value", Undefined)
        if value is not Undefined:
            return repr(value)
    value = getattr(item, "default_value", Undefined)
    return "" if value is Undefined else repr(value)


def _user_types(schema: GraphQLSchema):
    for name in sorted(schema.type_map):
        if not name.startswith("__"):
            yield schema.type_map[name]


def structure_signature(schema: GraphQLSchema) -> str:
    """A text that is the same for two schemas of the same structure and
    differs when any type, field, argument (and its type or default), enum
    value, union member, implemented interface or directive does - and says
    nothing about descriptions or about the order anything is written in."""
    lines: list[str] = []
    for named in _user_types(schema):
        if isinstance(named, (GraphQLObjectType, GraphQLInterfaceType)):
            interfaces = ",".join(sorted(interface.name for interface in named.interfaces))
            lines.append(f"{type(named).__name__} {named.name} implements {interfaces}")
            for field_name in sorted(named.fields):
                field = named.fields[field_name]
                args = ",".join(
                    f"{arg_name}:{field.args[arg_name].type}={default_text(field.args[arg_name])}"
                    for arg_name in sorted(field.args)
                )
                lines.append(f"  {field_name}({args}): {field.type}")
        elif isinstance(named, GraphQLInputObjectType):
            lines.append(f"Input {named.name}")
            for field_name in sorted(named.fields):
                field = named.fields[field_name]
                lines.append(f"  {field_name}: {field.type}={default_text(field)}")
        elif isinstance(named, GraphQLEnumType):
            lines.append(f"Enum {named.name} {','.join(sorted(named.values))}")
        elif isinstance(named, GraphQLUnionType):
            lines.append(f"Union {named.name} {','.join(sorted(member.name for member in named.types))}")
        elif isinstance(named, GraphQLScalarType):
            lines.append(f"Scalar {named.name}")
    for directive in sorted(schema.directives, key=lambda d: d.name):
        if directive.name in _BUILT_IN_DIRECTIVES:
            continue
        args = ",".join(f"{name}:{directive.args[name].type}={default_text(directive.args[name])}" for name in sorted(directive.args))
        locations = ",".join(sorted(location.name for location in directive.locations))
        lines.append(f"Directive {directive.name}({args}) on {locations}")
    roots = {
        "query": schema.query_type.name if schema.query_type else None,
        "mutation": schema.mutation_type.name if schema.mutation_type else None,
        "subscription": schema.subscription_type.name if schema.subscription_type else None,
    }
    lines.append(f"Roots {roots}")
    return "\n".join(lines)
