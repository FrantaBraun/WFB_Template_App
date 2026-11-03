# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""A structural diff of two OpenAPI 3.x / Swagger 2.0 documents, seen from the
point of view of someone who CONSUMES the API: what in the contract can make
an existing client stop working. Pure and database-free - it takes the two
parsed documents (ParsedSpec.document) and returns structured changes; the
wording is the frontend's, so a change carries a `kind`, where it is and a
little `detail`, never a sentence.

Every change has a severity:

- "breaking": an existing client can fail (an operation or a successful
  response removed, a new required parameter, a property type changed, a
  property a response used to promise removed, ...).
- "warning": it may break a client, depending on how it uses the API (a
  parameter or an optional request property removed, an enum value added to a
  response, a format changed, an operation deprecated, security changed).
- "info": safe for existing clients (something added, a restriction lifted).

The direction decides the severity of schema changes: what a client SENDS
(parameters, request bodies) breaks when it gets stricter, what it RECEIVES
(responses) breaks when it gets looser - a required request property added is
breaking, a response property removed is breaking, the opposite is not.

What is compared: operations (path + method) and their parameters, request
bodies, responses (per status and media type) and security. Schemas are
followed through local `$ref`s and `allOf` and compared by type, format, enum,
nullability, properties (and whether they are required) and array items.
Limits worth knowing: `oneOf` / `anyOf` branches are compared only as a whole
(one "composition_changed"), constraints such as minLength or pattern are not
compared, and anything outside operations - unreferenced component schemas,
descriptions, examples, servers - is not a structural change, so a spec that
changed only there yields no changes at all.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["breaking", "warning", "info"]
SEVERITY_ORDER: dict[str, int] = {"breaking": 0, "warning": 1, "info": 2}

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")

# A runaway spec (generated, thousands of operations with deep schemas) must
# not produce an answer of unbounded size: past this many changes the diff
# stops and says so.
MAX_CHANGES = 500
MAX_DEPTH = 25
_NO_SECURITY = "(none)"


@dataclass
class Change:
    """kind names what changed (the frontend words it), severity how much it
    matters to a consumer. method / path (upper-case method, as written path)
    say which operation, None for a change that belongs to none. scope is
    "parameter", "request" or "response"; status the response's status code
    ("200", "default"); media_type the body's; location where inside it - a
    parameter as "query:limit", a property as a dotted path ("address.zip",
    "items[].id"), "" for the root. detail is the few facts the wording needs
    ({"from": "string", "to": "integer"}, {"values": [...]}, ...)."""

    kind: str
    severity: Severity
    method: str | None = None
    path: str | None = None
    scope: str | None = None
    status: str | None = None
    media_type: str | None = None
    location: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def sort_key(self) -> tuple:
        return (SEVERITY_ORDER[self.severity], self.path or "", self.method or "", self.scope or "", self.location)


@dataclass
class SpecDiff:
    changes: list[Change]
    truncated: bool = False

    def summary(self) -> dict[str, int]:
        """How many changes of each severity - what is stored on a version
        (ApiDocumentVersion.change_summary) and shown next to it."""
        counts = {"breaking": 0, "warning": 0, "info": 0}
        for change in self.changes:
            counts[change.severity] += 1
        return counts


# --- reading the document -----------------------------------------------------------


def _pointer(spec: Any, ref: str) -> Any:
    """The node a local `#/a/b` reference points at, None if it does not exist
    (or is not local - external references are not followed)."""
    if not ref.startswith("#/"):
        return None
    node = spec
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def _deref(spec: Any, node: Any) -> tuple[Any, str | None]:
    """node with local $refs followed (a reference to a reference too), and the
    last reference followed - the name a recursive schema is recognised by. An
    unresolvable reference is an empty object, which compares equal to
    another unresolvable one rather than raising."""
    ref = None
    for _ in range(10):
        if isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            target = _pointer(spec, ref)
            if target is None:
                return {}, ref
            node = target
        else:
            break
    return node, ref


def _flatten(spec: Any, schema: Any, stack: frozenset = frozenset(), depth: int = 0) -> dict[str, Any]:
    """The facts the comparison needs about one schema, with `allOf` merged in
    and the type inferred when it is only implied (properties -> object,
    items -> array), so one side leaving `type` out is not a type change.
    Children (property schemas, items) stay unresolved: they are followed when
    compared."""
    out: dict[str, Any] = {
        "type": None,
        "format": None,
        "enum": None,
        "nullable": False,
        "properties": {},
        "required": set(),
        "items": None,
        "additional": None,
        "composition": None,
    }
    schema, ref = _deref(spec, schema)
    if not isinstance(schema, dict) or depth > 10 or (ref is not None and ref in stack):
        return out
    if ref is not None:
        stack = stack | {ref}

    for part in schema.get("allOf") or []:
        sub = _flatten(spec, part, stack, depth + 1)
        for key in ("type", "format", "enum", "items", "additional", "composition"):
            if out[key] is None:
                out[key] = sub[key]
        out["nullable"] = out["nullable"] or sub["nullable"]
        out["properties"].update(sub["properties"])
        out["required"] |= sub["required"]

    declared = schema.get("type")
    if isinstance(declared, list):  # OpenAPI 3.1: ["string", "null"]
        if "null" in declared:
            out["nullable"] = True
        declared = ",".join(sorted(str(t) for t in declared if t != "null")) or None
    if isinstance(declared, str):
        out["type"] = declared
    if isinstance(schema.get("format"), str):
        out["format"] = schema["format"]
    if isinstance(schema.get("enum"), list):
        out["enum"] = schema["enum"]
    if schema.get("nullable") is True or schema.get("x-nullable") is True:
        out["nullable"] = True
    if isinstance(schema.get("properties"), dict):
        out["properties"].update(schema["properties"])
    if isinstance(schema.get("required"), list):
        out["required"] |= {name for name in schema["required"] if isinstance(name, str)}
    if isinstance(schema.get("items"), dict):
        out["items"] = schema["items"]
    if isinstance(schema.get("additionalProperties"), dict):
        out["additional"] = schema["additionalProperties"]
    for key in ("oneOf", "anyOf"):
        if isinstance(schema.get(key), list):
            out["composition"] = json.dumps({key: schema[key]}, sort_keys=True, default=str)

    if out["type"] is None:
        if out["properties"]:
            out["type"] = "object"
        elif out["items"] is not None:
            out["type"] = "array"
    return out


def _operations(spec: dict) -> dict[tuple[str, str], dict[str, Any]]:
    """Every operation as {(METHOD, path): normalised operation}. The two
    formats put the same things in different places - a body is a
    `requestBody` in 3.x and an `in: body` parameter in 2.0, a response schema
    sits under `content` or directly under the response - so both are turned
    into one shape: deprecated, params {(in, name): {required, schema}},
    request None or {required, content {media type: schema}}, responses
    {status: {media type: schema}}, security (set of names of alternatives)."""
    result: dict[tuple[str, str], dict[str, Any]] = {}
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return result
    is_v2 = "swagger" in spec
    for path, item in paths.items():
        item, _ = _deref(spec, item)
        if not isinstance(item, dict):
            continue
        shared = item.get("parameters") if isinstance(item.get("parameters"), list) else []
        for method in HTTP_METHODS:
            operation = item.get(method)
            if isinstance(operation, dict):
                result[(method.upper(), str(path))] = _normalise_operation(spec, operation, shared, is_v2)
    return result


def _security_names(spec: dict, operation: dict) -> set[str]:
    requirements = operation["security"] if "security" in operation else spec.get("security")
    if not isinstance(requirements, list) or not requirements:
        return {_NO_SECURITY}
    names = set()
    for requirement in requirements:
        if isinstance(requirement, dict):
            names.add("+".join(sorted(requirement)) if requirement else _NO_SECURITY)
    return names or {_NO_SECURITY}


def _normalise_operation(spec: dict, operation: dict, shared: list, is_v2: bool) -> dict[str, Any]:
    consumes = operation.get("consumes") or spec.get("consumes") or ["*/*"]
    produces = operation.get("produces") or spec.get("produces") or ["*/*"]
    params: dict[tuple[str, str], dict[str, Any]] = {}
    request = None

    own = operation.get("parameters") if isinstance(operation.get("parameters"), list) else []
    for raw in [*shared, *own]:  # an operation's own parameter replaces a shared one of the same key
        parameter, _ = _deref(spec, raw)
        if not isinstance(parameter, dict):
            continue
        location, name = parameter.get("in"), parameter.get("name")
        if not isinstance(location, str) or not isinstance(name, str):
            continue
        required = bool(parameter.get("required")) or location == "path"
        if is_v2 and location == "body":
            request = {"required": required, "content": {str(mt): parameter.get("schema") for mt in consumes}}
            continue
        if is_v2:  # a 2.0 parameter is its own schema
            schema = {k: parameter[k] for k in ("type", "format", "enum", "items", "x-nullable") if k in parameter}
        else:
            schema = parameter.get("schema")
            if schema is None and isinstance(parameter.get("content"), dict):
                schema = next((m.get("schema") for m in parameter["content"].values() if isinstance(m, dict)), None)
        params[(location, name)] = {"required": required, "schema": schema}

    if not is_v2:
        body, _ = _deref(spec, operation.get("requestBody"))
        if isinstance(body, dict):
            content = body.get("content") if isinstance(body.get("content"), dict) else {}
            request = {
                "required": bool(body.get("required")),
                "content": {str(mt): m.get("schema") if isinstance(m, dict) else None for mt, m in content.items()},
            }

    responses: dict[str, dict[str, Any]] = {}
    declared = operation.get("responses") if isinstance(operation.get("responses"), dict) else {}
    for status, raw in declared.items():
        response, _ = _deref(spec, raw)
        if not isinstance(response, dict):
            responses[str(status)] = {}
        elif is_v2:
            responses[str(status)] = {str(mt): response["schema"] for mt in produces} if "schema" in response else {}
        else:
            content = response.get("content") if isinstance(response.get("content"), dict) else {}
            responses[str(status)] = {
                str(mt): m.get("schema") if isinstance(m, dict) else None for mt, m in content.items()
            }

    return {
        "deprecated": operation.get("deprecated") is True,
        "params": params,
        "request": request,
        "responses": responses,
        "security": _security_names(spec, operation),
    }


# --- comparing ----------------------------------------------------------------------


class _Comparison:
    def __init__(self, old: dict, new: dict) -> None:
        self.old = old
        self.new = new
        self.changes: list[Change] = []
        self.truncated = False

    # -- bookkeeping --

    def add(self, change: Change) -> None:
        if len(self.changes) >= MAX_CHANGES:
            self.truncated = True
        else:
            self.changes.append(change)

    # -- operations --

    def run(self) -> SpecDiff:
        old_ops, new_ops = _operations(self.old), _operations(self.new)
        for key in sorted(old_ops.keys() | new_ops.keys()):
            method, path = key
            if key not in new_ops:
                self.add(Change("operation_removed", "breaking", method, path))
            elif key not in old_ops:
                self.add(Change("operation_added", "info", method, path))
            else:
                self._operation(method, path, old_ops[key], new_ops[key])
        self.changes.sort(key=Change.sort_key)
        return SpecDiff(self.changes, self.truncated)

    def _operation(self, method: str, path: str, old: dict, new: dict) -> None:
        def at(kind: str, severity: Severity, **fields: Any) -> None:
            self.add(Change(kind, severity, method, path, **fields))

        if new["deprecated"] and not old["deprecated"]:
            at("operation_deprecated", "warning")
        elif old["deprecated"] and not new["deprecated"]:
            at("operation_undeprecated", "info")

        self._security(old["security"], new["security"], at)
        self._parameters(old["params"], new["params"], method, path, at)
        self._request(old["request"], new["request"], method, path, at)
        self._responses(old["responses"], new["responses"], method, path, at)

    def _security(self, old: set[str], new: set[str], at) -> None:
        if old == new:
            return
        if _NO_SECURITY not in old and _NO_SECURITY in new:
            at("security_relaxed", "info")
        elif _NO_SECURITY in old and _NO_SECURITY not in new:
            at("security_added", "breaking", detail={"schemes": sorted(new)})
        else:
            at("security_changed", "warning", detail={"added": sorted(new - old), "removed": sorted(old - new)})

    def _parameters(self, old: dict, new: dict, method: str, path: str, at) -> None:
        for key in sorted(old.keys() | new.keys()):
            location = f"{key[0]}:{key[1]}"
            if key not in new:
                at("parameter_removed", "warning", scope="parameter", location=location)
            elif key not in old:
                required = new[key]["required"]
                at(
                    "parameter_added",
                    "breaking" if required else "info",
                    scope="parameter",
                    location=location,
                    detail={"required": required},
                )
            else:
                before, after = old[key], new[key]
                if after["required"] and not before["required"]:
                    at("parameter_became_required", "breaking", scope="parameter", location=location)
                elif before["required"] and not after["required"]:
                    at("parameter_became_optional", "info", scope="parameter", location=location)
                self._schema(
                    before["schema"],
                    after["schema"],
                    dict(method=method, path=path, scope="parameter"),
                    sending=True,
                    location=location,
                )

    def _request(self, old: dict | None, new: dict | None, method: str, path: str, at) -> None:
        if old is None and new is None:
            return
        if old is None:
            at("request_body_added", "breaking" if new["required"] else "info", scope="request", detail={"required": new["required"]})
            return
        if new is None:
            at("request_body_removed", "warning", scope="request")
            return
        if new["required"] and not old["required"]:
            at("request_body_became_required", "breaking", scope="request")
        elif old["required"] and not new["required"]:
            at("request_body_became_optional", "info", scope="request")
        self._bodies(old["content"], new["content"], dict(method=method, path=path, scope="request"), sending=True)

    def _responses(self, old: dict, new: dict, method: str, path: str, at) -> None:
        for status in sorted(old.keys() | new.keys()):
            if status not in new:
                success = status.startswith("2")
                at("response_removed", "breaking" if success else "warning", scope="response", status=status)
            elif status not in old:
                at("response_added", "info", scope="response", status=status)
            else:
                self._bodies(
                    old[status],
                    new[status],
                    dict(method=method, path=path, scope="response", status=status),
                    sending=False,
                )

    def _bodies(self, old: dict, new: dict, where: dict, *, sending: bool) -> None:
        """The media types of one body, then the schema of each one both sides have."""
        for media_type in sorted(old.keys() | new.keys()):
            if media_type not in new:
                self.add(Change("media_type_removed", "breaking", media_type=media_type, **where))
            elif media_type not in old:
                self.add(Change("media_type_added", "info", media_type=media_type, **where))
            else:
                self._schema(
                    old[media_type], new[media_type], {**where, "media_type": media_type}, sending=sending, location=""
                )

    # -- schemas --

    def _schema(
        self,
        old: Any,
        new: Any,
        where: dict,
        *,
        sending: bool,
        location: str,
        seen: frozenset = frozenset(),
        depth: int = 0,
    ) -> None:
        """Compare two schemas. `sending` is the direction: True for what the
        client sends (parameters, request bodies), False for what it receives -
        the same change has opposite severity in the two."""
        old, old_ref = _deref(self.old, old)
        new, new_ref = _deref(self.new, new)
        if not isinstance(old, dict) or not isinstance(new, dict) or depth > MAX_DEPTH:
            return
        if old_ref is not None or new_ref is not None:
            if (old_ref, new_ref) in seen:  # a recursive schema: already comparing this very pair
                return
            seen = seen | {(old_ref, new_ref)}

        before = _flatten(self.old, old)
        after = _flatten(self.new, new)

        def add(kind: str, severity: Severity, **detail: Any) -> None:
            self.add(Change(kind, severity, location=location, detail=detail, **where))

        if before["type"] and after["type"] and before["type"] != after["type"]:
            numeric = {before["type"], after["type"]} == {"integer", "number"}
            add("type_changed", "warning" if numeric else "breaking", **{"from": before["type"], "to": after["type"]})
        if before["format"] and after["format"] and before["format"] != after["format"]:
            add("format_changed", "warning", **{"from": before["format"], "to": after["format"]})
        if before["nullable"] != after["nullable"]:
            # The client sending null is hurt by "no longer nullable"; the
            # client receiving null is hurt by "now nullable".
            hurts = (before["nullable"] and not after["nullable"]) if sending else (after["nullable"] and not before["nullable"])
            add("nullable_changed", "breaking" if hurts else "info", nullable=after["nullable"])
        if isinstance(before["enum"], list) and isinstance(after["enum"], list):
            old_values = {json.dumps(v, sort_keys=True, default=str): v for v in before["enum"]}
            new_values = {json.dumps(v, sort_keys=True, default=str): v for v in after["enum"]}
            removed = [v for k, v in old_values.items() if k not in new_values]
            added = [v for k, v in new_values.items() if k not in old_values]
            if removed:
                add("enum_value_removed", "breaking" if sending else "info", values=removed)
            if added:
                add("enum_value_added", "info" if sending else "warning", values=added)
        if before["composition"] != after["composition"]:
            add("composition_changed", "warning")

        self._properties(before, after, where, sending=sending, location=location, seen=seen, depth=depth)

        if before["items"] is not None and after["items"] is not None:
            self._schema(
                before["items"], after["items"], where, sending=sending, location=f"{location}[]", seen=seen, depth=depth + 1
            )
        if before["additional"] is not None and after["additional"] is not None:
            self._schema(
                before["additional"], after["additional"], where, sending=sending,
                location=f"{location}.*" if location else "*", seen=seen, depth=depth + 1,
            )

    def _properties(self, before: dict, after: dict, where: dict, *, sending: bool, location: str, seen: frozenset, depth: int) -> None:
        old_props, new_props = before["properties"], after["properties"]
        for name in sorted(old_props.keys() | new_props.keys(), key=str):
            here = f"{location}.{name}" if location else str(name)

            def add(kind: str, severity: Severity, **detail: Any) -> None:
                self.add(Change(kind, severity, location=here, detail=detail, **where))

            if name not in new_props:
                add("property_removed", "warning" if sending else "breaking")
            elif name not in old_props:
                required = name in after["required"]
                # A required property a client must now send is breaking; one
                # it merely receives never is.
                add("property_added", "breaking" if (sending and required) else "info", required=required)
            else:
                was, is_now = name in before["required"], name in after["required"]
                if is_now and not was:
                    add("property_became_required", "breaking" if sending else "info")
                elif was and not is_now:
                    add("property_became_optional", "info" if sending else "breaking")
                self._schema(
                    old_props[name], new_props[name], where, sending=sending, location=here, seen=seen, depth=depth + 1
                )


def diff_specs(old: dict, new: dict) -> SpecDiff:
    """The structural changes from `old` to `new` (both parsed documents),
    most severe first, then by operation. Never raises on an odd document: a
    part that is not shaped as expected is skipped."""
    return _Comparison(old, new).run()
