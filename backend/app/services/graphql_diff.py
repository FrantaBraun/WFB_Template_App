# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What changed between two GraphQL schemas, for someone who sends queries to
the API: the same breaking / warning / info judgement app/services/spec_diff.py
makes for OpenAPI, with the same structured changes (kind, where, detail) the
frontend words in either language.

A change breaks an existing client when a query it already sends stops being
valid or stops meaning the same: a type, field, argument or enum value removed,
an argument that must now be given, an argument or field whose type changed
incompatibly. Things a client has to cope with but that do not invalidate a
query - a value added to an enum or a member to a union (a client's `switch`
may not know it), an argument's default changed, a field deprecated - are
warnings; additions are info.

The changes carry the type name as `path` (the frontend groups by it) and the
field, `field(argument)` or enum value as `location`. graphql-core's own
find_breaking_changes is not used: it describes changes in English sentences
only, which cannot be worded in the user's language."""

from graphql import (
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLUnionType,
    is_list_type,
    is_named_type,
    is_non_null_type,
)
from graphql.type import specified_directives

from app.services.graphql_spec import default_text
from app.services.spec_diff import MAX_CHANGES, Change, Severity, SpecDiff

_BUILT_IN_DIRECTIVES = {directive.name for directive in specified_directives}


def type_kind(named: GraphQLNamedType) -> str:
    if isinstance(named, GraphQLObjectType):
        return "object"
    if isinstance(named, GraphQLInterfaceType):
        return "interface"
    if isinstance(named, GraphQLInputObjectType):
        return "input"
    if isinstance(named, GraphQLEnumType):
        return "enum"
    if isinstance(named, GraphQLUnionType):
        return "union"
    if isinstance(named, GraphQLScalarType):
        return "scalar"
    return "type"


def _output_safe(old, new) -> bool:
    """Whether a field of type `old` may become `new` without breaking a
    client that reads it: only by becoming stricter (`String` -> `String!`)."""
    if is_non_null_type(old):
        return is_non_null_type(new) and _output_safe(old.of_type, new.of_type)
    if is_non_null_type(new):
        return _output_safe(old, new.of_type)
    if is_list_type(old):
        return is_list_type(new) and _output_safe(old.of_type, new.of_type)
    return is_named_type(new) and old.name == new.name


def _input_safe(old, new) -> bool:
    """Whether an argument or input field of type `old` may become `new`
    without breaking a client that sends it: only by becoming more lenient
    (`Int!` -> `Int`)."""
    if is_non_null_type(old):
        return _input_safe(old.of_type, new.of_type if is_non_null_type(new) else new)
    if is_non_null_type(new):
        return False
    if is_list_type(old):
        return is_list_type(new) and _input_safe(old.of_type, new.of_type)
    return is_named_type(new) and old.name == new.name


def _required(item) -> bool:
    """An argument or input field a client must give: non-null and no default."""
    return is_non_null_type(item.type) and not default_text(item)


class _Diff:
    def __init__(self) -> None:
        self.changes: list[Change] = []
        self.truncated = False

    def add(self, kind: str, severity: Severity, type_name: str, location: str = "", /, **detail) -> None:
        if len(self.changes) >= MAX_CHANGES:
            self.truncated = True
        else:
            self.changes.append(Change(kind, severity, path=type_name, location=location, detail=detail))


def _compare_fields(diff: _Diff, name: str, old_fields: dict, new_fields: dict) -> None:
    for field_name in sorted(old_fields.keys() | new_fields.keys()):
        if field_name not in new_fields:
            diff.add("graphql_field_removed", "breaking", name, field_name)
        elif field_name not in old_fields:
            diff.add("graphql_field_added", "info", name, field_name)
        else:
            before, after = old_fields[field_name], new_fields[field_name]
            if str(before.type) != str(after.type):
                safe = _output_safe(before.type, after.type)
                diff.add(
                    "graphql_field_type_changed", "info" if safe else "breaking", name, field_name,
                    **{"from": str(before.type), "to": str(after.type)},
                )
            if after.deprecation_reason is not None and before.deprecation_reason is None:
                diff.add("graphql_field_deprecated", "warning", name, field_name)
            _compare_arguments(diff, name, field_name, before.args, after.args)


def _compare_arguments(diff: _Diff, type_name: str, field_name: str, old_args: dict, new_args: dict) -> None:
    for arg_name in sorted(old_args.keys() | new_args.keys()):
        place = f"{field_name}({arg_name})"
        if arg_name not in new_args:
            diff.add("graphql_argument_removed", "breaking", type_name, place)
        elif arg_name not in old_args:
            required = _required(new_args[arg_name])
            diff.add("graphql_argument_added", "breaking" if required else "info", type_name, place, required=required)
        else:
            before, after = old_args[arg_name], new_args[arg_name]
            if str(before.type) != str(after.type):
                safe = _input_safe(before.type, after.type)
                diff.add(
                    "graphql_argument_type_changed", "info" if safe else "breaking", type_name, place,
                    **{"from": str(before.type), "to": str(after.type)},
                )
            if default_text(before) != default_text(after):
                diff.add(
                    "graphql_default_changed", "warning", type_name, place,
                    **{"from": default_text(before) or None, "to": default_text(after) or None},
                )


def _compare_input_fields(diff: _Diff, name: str, old_fields: dict, new_fields: dict) -> None:
    for field_name in sorted(old_fields.keys() | new_fields.keys()):
        if field_name not in new_fields:
            diff.add("graphql_input_field_removed", "breaking", name, field_name)
        elif field_name not in old_fields:
            required = _required(new_fields[field_name])
            diff.add("graphql_input_field_added", "breaking" if required else "info", name, field_name, required=required)
        else:
            before, after = old_fields[field_name], new_fields[field_name]
            if str(before.type) != str(after.type):
                safe = _input_safe(before.type, after.type)
                diff.add(
                    "graphql_input_field_type_changed", "info" if safe else "breaking", name, field_name,
                    **{"from": str(before.type), "to": str(after.type)},
                )
            if default_text(before) != default_text(after):
                diff.add(
                    "graphql_default_changed", "warning", name, field_name,
                    **{"from": default_text(before) or None, "to": default_text(after) or None},
                )


def _compare_names(diff: _Diff, name: str, old: set[str], new: set[str], removed: tuple[str, Severity], added: tuple[str, Severity]) -> None:
    for item in sorted(old - new):
        diff.add(removed[0], removed[1], name, item)
    for item in sorted(new - old):
        diff.add(added[0], added[1], name, item)


def _compare_type(diff: _Diff, name: str, old: GraphQLNamedType, new: GraphQLNamedType) -> None:
    old_kind, new_kind = type_kind(old), type_kind(new)
    if old_kind != new_kind:
        diff.add("graphql_type_kind_changed", "breaking", name, **{"from": old_kind, "to": new_kind})
        return
    if isinstance(old, (GraphQLObjectType, GraphQLInterfaceType)):
        _compare_fields(diff, name, old.fields, new.fields)
        _compare_names(
            diff, name, {i.name for i in old.interfaces}, {i.name for i in new.interfaces},
            ("graphql_interface_removed", "breaking"), ("graphql_interface_added", "warning"),
        )
    elif isinstance(old, GraphQLInputObjectType):
        _compare_input_fields(diff, name, old.fields, new.fields)
    elif isinstance(old, GraphQLEnumType):
        _compare_names(
            diff, name, set(old.values), set(new.values),
            ("graphql_enum_value_removed", "breaking"), ("graphql_enum_value_added", "warning"),
        )
    elif isinstance(old, GraphQLUnionType):
        _compare_names(
            diff, name, {t.name for t in old.types}, {t.name for t in new.types},
            ("graphql_union_member_removed", "breaking"), ("graphql_union_member_added", "warning"),
        )


def _user_types(schema: GraphQLSchema) -> dict[str, GraphQLNamedType]:
    return {name: named for name, named in schema.type_map.items() if not name.startswith("__")}


def diff_graphql(old: GraphQLSchema, new: GraphQLSchema) -> SpecDiff:
    """The changes from schema `old` to schema `new`, most severe first, then
    by type. Never raises on an odd schema."""
    diff = _Diff()
    old_types, new_types = _user_types(old), _user_types(new)
    for name in sorted(old_types.keys() | new_types.keys()):
        if name not in new_types:
            diff.add("graphql_type_removed", "breaking", name, kind=type_kind(old_types[name]))
        elif name not in old_types:
            diff.add("graphql_type_added", "info", name, kind=type_kind(new_types[name]))
        else:
            _compare_type(diff, name, old_types[name], new_types[name])

    old_directives = {d.name for d in old.directives} - _BUILT_IN_DIRECTIVES
    new_directives = {d.name for d in new.directives} - _BUILT_IN_DIRECTIVES
    for name in sorted(old_directives - new_directives):
        diff.add("graphql_directive_removed", "breaking", f"@{name}")
    for name in sorted(new_directives - old_directives):
        diff.add("graphql_directive_added", "info", f"@{name}")

    diff.changes.sort(key=Change.sort_key)
    return SpecDiff(diff.changes, diff.truncated)
