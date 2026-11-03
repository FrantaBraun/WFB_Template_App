# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.spec_diff: what counts as a breaking change, a
warning or a harmless one for someone who consumes the API, in both
directions (what a client sends vs. what it receives), through $ref / allOf,
for OpenAPI 3.x and Swagger 2.0, and that an odd document never raises.

Pure - no database. Specs are built with the small helpers below so each test
shows only the one thing that differs."""

import copy

import pytest

from app.services.spec_diff import MAX_CHANGES, diff_specs


# --- builders -----------------------------------------------------------------------


def spec3(paths: dict, components: dict | None = None, **top) -> dict:
    document = {"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "paths": paths, **top}
    if components is not None:
        document["components"] = components
    return document


def body(schema: dict, required: bool = True, media_type: str = "application/json") -> dict:
    return {"required": required, "content": {media_type: {"schema": schema}}}


def reply(schema: dict | None = None, status: str = "200", media_type: str = "application/json") -> dict:
    response: dict = {"description": "r"}
    if schema is not None:
        response["content"] = {media_type: {"schema": schema}}
    return {status: response}


def obj(properties: dict, required: tuple[str, ...] = ()) -> dict:
    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = list(required)
    return schema


def get(path: str = "/pets", **operation) -> dict:
    operation.setdefault("responses", reply())
    return {path: {"get": operation}}


def post(path: str = "/pets", **operation) -> dict:
    operation.setdefault("responses", reply())
    return {path: {"post": operation}}


def found(diff, kind: str, **where):
    """The one change of this kind (with these fields), failing when there is none or several."""
    matches = [
        c for c in diff.changes if c.kind == kind and all(getattr(c, key) == value for key, value in where.items())
    ]
    assert len(matches) == 1, f"{kind} {where}: {[(c.kind, c.severity, c.location) for c in diff.changes]}"
    return matches[0]


def kinds(diff) -> list[str]:
    return [c.kind for c in diff.changes]


# --- nothing / operations -----------------------------------------------------------


def test_identical_specs_have_no_changes():
    spec = spec3(get(responses=reply(obj({"id": {"type": "integer"}}))))

    diff = diff_specs(spec, copy.deepcopy(spec))

    assert diff.changes == [] and diff.truncated is False
    assert diff.summary() == {"breaking": 0, "warning": 0, "info": 0}


def test_only_descriptions_and_examples_changing_is_no_structural_change():
    old = spec3(get(summary="List", responses=reply(obj({"id": {"type": "integer", "description": "the id"}}))))
    new = copy.deepcopy(old)
    new["info"]["description"] = "something new"
    new["paths"]["/pets"]["get"]["summary"] = "List all"
    new["paths"]["/pets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["id"] = {
        "type": "integer",
        "description": "the identifier",
        "example": 5,
    }

    assert diff_specs(old, new).changes == []


def test_removed_operation_is_breaking_and_added_is_info():
    old = spec3({**get("/a"), **get("/b")})
    new = spec3({**get("/a"), **get("/c")})

    diff = diff_specs(old, new)

    removed = found(diff, "operation_removed")
    assert (removed.severity, removed.method, removed.path) == ("breaking", "GET", "/b")
    added = found(diff, "operation_added")
    assert (added.severity, added.method, added.path) == ("info", "GET", "/c")


def test_a_second_method_on_the_same_path_is_a_new_operation():
    old = spec3(get())
    new = spec3({"/pets": {**get()["/pets"], **post()["/pets"]}})

    diff = diff_specs(old, new)

    assert [(c.kind, c.method) for c in diff.changes] == [("operation_added", "POST")]


def test_deprecating_an_operation_is_a_warning_and_undeprecating_is_info():
    plain, deprecated = spec3(get()), spec3(get(deprecated=True))

    assert found(diff_specs(plain, deprecated), "operation_deprecated").severity == "warning"
    assert found(diff_specs(deprecated, plain), "operation_undeprecated").severity == "info"


# --- parameters ---------------------------------------------------------------------


def param(name: str, required: bool = False, location: str = "query", **schema) -> dict:
    return {"name": name, "in": location, "required": required, "schema": schema or {"type": "string"}}


def test_new_required_parameter_is_breaking_and_optional_one_is_info():
    old = spec3(get(parameters=[]))
    new = spec3(get(parameters=[param("must", required=True), param("may")]))

    diff = diff_specs(old, new)

    must = found(diff, "parameter_added", location="query:must")
    assert (must.severity, must.scope, must.detail) == ("breaking", "parameter", {"required": True})
    assert found(diff, "parameter_added", location="query:may").severity == "info"


def test_removed_parameter_is_a_warning():
    old = spec3(get(parameters=[param("limit")]))
    new = spec3(get(parameters=[]))

    assert found(diff_specs(old, new), "parameter_removed", location="query:limit").severity == "warning"


def test_parameter_required_flag_flipping():
    optional = spec3(get(parameters=[param("q")]))
    required = spec3(get(parameters=[param("q", required=True)]))

    assert found(diff_specs(optional, required), "parameter_became_required").severity == "breaking"
    assert found(diff_specs(required, optional), "parameter_became_optional").severity == "info"


def test_parameter_type_change_is_breaking_and_numeric_widening_a_warning():
    string = spec3(get(parameters=[param("n", type="string")]))
    integer = spec3(get(parameters=[param("n", type="integer")]))
    number = spec3(get(parameters=[param("n", type="number")]))

    changed = found(diff_specs(string, integer), "type_changed", location="query:n")
    assert (changed.severity, changed.scope, changed.detail) == ("breaking", "parameter", {"from": "string", "to": "integer"})
    assert found(diff_specs(integer, number), "type_changed").severity == "warning"


def test_path_level_parameters_apply_to_every_operation_and_an_operation_can_override_them():
    shared = {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
    old = spec3({"/pets/{id}": {"parameters": [shared], "get": {"responses": reply()}}})
    changed = copy.deepcopy(old)
    changed["paths"]["/pets/{id}"]["parameters"][0]["schema"] = {"type": "integer"}
    overridden = copy.deepcopy(changed)
    overridden["paths"]["/pets/{id}"]["get"]["parameters"] = [shared]  # the operation says "string" again

    assert found(diff_specs(old, changed), "type_changed").location == "path:id"
    assert diff_specs(old, overridden).changes == []


def test_parameters_that_are_references_are_followed():
    old = spec3(get(parameters=[{"$ref": "#/components/parameters/Limit"}]), {"parameters": {"Limit": param("limit")}})
    new = copy.deepcopy(old)
    new["components"]["parameters"]["Limit"] = param("limit", required=True)

    assert found(diff_specs(old, new), "parameter_became_required").location == "query:limit"


# --- request bodies -----------------------------------------------------------------


def test_request_body_added_removed_and_required_flag():
    none = spec3(post())
    required = spec3(post(requestBody=body(obj({}), required=True)))
    optional = spec3(post(requestBody=body(obj({}), required=False)))

    assert found(diff_specs(none, required), "request_body_added").severity == "breaking"
    assert found(diff_specs(none, optional), "request_body_added").severity == "info"
    assert found(diff_specs(required, none), "request_body_removed").severity == "warning"
    assert found(diff_specs(optional, required), "request_body_became_required").severity == "breaking"
    assert found(diff_specs(required, optional), "request_body_became_optional").severity == "info"


def test_request_media_types():
    json_only = spec3(post(requestBody=body(obj({}))))
    both = copy.deepcopy(json_only)
    both["paths"]["/pets"]["post"]["requestBody"]["content"]["application/xml"] = {"schema": obj({})}

    assert found(diff_specs(json_only, both), "media_type_added", media_type="application/xml").severity == "info"
    removed = found(diff_specs(both, json_only), "media_type_removed", media_type="application/xml")
    assert (removed.severity, removed.scope) == ("breaking", "request")


def test_request_property_changes_follow_the_direction_of_what_the_client_sends():
    old = spec3(post(requestBody=body(obj({"name": {"type": "string"}, "tag": {"type": "string"}}, required=("name",)))))
    new = spec3(
        post(
            requestBody=body(
                obj({"name": {"type": "string"}, "owner": {"type": "string"}, "age": {"type": "integer"}}, required=("name", "owner"))
            )
        )
    )

    diff = diff_specs(old, new)

    assert found(diff, "property_removed", location="tag").severity == "warning"  # optional, ignored by the server now
    assert found(diff, "property_added", location="owner").severity == "breaking"  # a client must now send it
    assert found(diff, "property_added", location="age").severity == "info"


def test_request_property_becoming_required_is_breaking_and_optional_is_info():
    optional = spec3(post(requestBody=body(obj({"a": {"type": "string"}}))))
    required = spec3(post(requestBody=body(obj({"a": {"type": "string"}}, required=("a",)))))

    assert found(diff_specs(optional, required), "property_became_required").severity == "breaking"
    assert found(diff_specs(required, optional), "property_became_optional").severity == "info"


def test_request_enum_values_removed_break_clients_and_added_are_harmless():
    old = spec3(post(requestBody=body(obj({"kind": {"type": "string", "enum": ["a", "b", "c"]}}))))
    new = spec3(post(requestBody=body(obj({"kind": {"type": "string", "enum": ["a", "d"]}}))))

    diff = diff_specs(old, new)

    removed = found(diff, "enum_value_removed", location="kind")
    assert (removed.severity, sorted(removed.detail["values"])) == ("breaking", ["b", "c"])
    assert found(diff, "enum_value_added").severity == "info"


def test_request_nullable():
    nullable = spec3(post(requestBody=body(obj({"a": {"type": "string", "nullable": True}}))))
    strict = spec3(post(requestBody=body(obj({"a": {"type": "string"}}))))

    assert found(diff_specs(nullable, strict), "nullable_changed").severity == "breaking"  # null is refused now
    assert found(diff_specs(strict, nullable), "nullable_changed").severity == "info"


# --- responses ----------------------------------------------------------------------


def test_removed_success_response_is_breaking_and_removed_error_response_a_warning():
    old = spec3(get(responses={**reply(), **reply(status="404")}))
    no_404 = spec3(get(responses=reply()))
    no_200 = spec3(get(responses=reply(status="404")))

    assert found(diff_specs(old, no_404), "response_removed", status="404").severity == "warning"
    assert found(diff_specs(old, no_200), "response_removed", status="200").severity == "breaking"
    assert found(diff_specs(no_404, old), "response_added", status="404").severity == "info"


def test_removed_default_response_is_a_warning():
    old = spec3(get(responses={**reply(), **reply(status="default")}))
    new = spec3(get(responses=reply()))

    assert found(diff_specs(old, new), "response_removed", status="default").severity == "warning"


def test_response_media_type_removed_is_breaking():
    old = spec3(get(responses={"200": {"description": "r", "content": {"application/json": {"schema": obj({})}, "text/csv": {"schema": {"type": "string"}}}}}))
    new = spec3(get(responses=reply(obj({}))))

    change = found(diff_specs(old, new), "media_type_removed", media_type="text/csv")
    assert (change.severity, change.scope, change.status) == ("breaking", "response", "200")


def test_response_property_changes_follow_the_direction_of_what_the_client_receives():
    old = spec3(get(responses=reply(obj({"id": {"type": "integer"}, "name": {"type": "string"}}, required=("id", "name")))))
    new = spec3(get(responses=reply(obj({"id": {"type": "string"}, "extra": {"type": "string"}}, required=("id",)))))

    diff = diff_specs(old, new)

    assert found(diff, "property_removed", location="name").severity == "breaking"  # clients read it
    assert found(diff, "property_added", location="extra").severity == "info"
    changed = found(diff, "type_changed", location="id")
    assert (changed.severity, changed.status, changed.media_type) == ("breaking", "200", "application/json")


def test_a_required_property_added_to_a_response_is_not_breaking():
    """Only a client that has to SEND it is hurt by a new required property."""
    old = spec3(get(responses=reply(obj({"a": {"type": "string"}}, required=("a",)))))
    new = spec3(get(responses=reply(obj({"a": {"type": "string"}, "b": {"type": "string"}}, required=("a", "b")))))

    added = found(diff_specs(old, new), "property_added", location="b")

    assert (added.severity, added.detail) == ("info", {"required": True})


def test_response_property_no_longer_guaranteed_is_breaking_and_newly_guaranteed_is_info():
    required = spec3(get(responses=reply(obj({"a": {"type": "string"}}, required=("a",)))))
    optional = spec3(get(responses=reply(obj({"a": {"type": "string"}}))))

    assert found(diff_specs(required, optional), "property_became_optional").severity == "breaking"
    assert found(diff_specs(optional, required), "property_became_required").severity == "info"


def test_response_enum_value_added_is_a_warning_and_removed_is_info():
    old = spec3(get(responses=reply(obj({"s": {"type": "string", "enum": ["a"]}}))))
    new = spec3(get(responses=reply(obj({"s": {"type": "string", "enum": ["a", "b"]}}))))

    assert found(diff_specs(old, new), "enum_value_added").severity == "warning"  # clients may not handle "b"
    assert found(diff_specs(new, old), "enum_value_removed").severity == "info"


def test_response_that_may_now_be_null_is_breaking():
    strict = spec3(get(responses=reply(obj({"a": {"type": "string"}}))))
    nullable = spec3(get(responses=reply(obj({"a": {"type": "string", "nullable": True}}))))

    assert found(diff_specs(strict, nullable), "nullable_changed").severity == "breaking"
    assert found(diff_specs(nullable, strict), "nullable_changed").severity == "info"


def test_format_change_is_a_warning():
    old = spec3(get(responses=reply(obj({"at": {"type": "string", "format": "date"}}))))
    new = spec3(get(responses=reply(obj({"at": {"type": "string", "format": "date-time"}}))))

    change = found(diff_specs(old, new), "format_changed")
    assert (change.severity, change.detail) == ("warning", {"from": "date", "to": "date-time"})


# --- nesting, $ref, allOf -----------------------------------------------------------


def test_locations_of_nested_properties_and_array_items():
    old = spec3(get(responses=reply(obj({"owner": obj({"address": obj({"zip": {"type": "string"}})}), "items": {"type": "array", "items": obj({"id": {"type": "integer"}})}}))))
    new = copy.deepcopy(old)
    schema = new["paths"]["/pets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    schema["properties"]["owner"]["properties"]["address"]["properties"]["zip"] = {"type": "integer"}
    schema["properties"]["items"]["items"]["properties"]["id"] = {"type": "string"}

    diff = diff_specs(old, new)

    assert sorted(c.location for c in diff.changes) == ["items[].id", "owner.address.zip"]


def test_a_change_in_a_referenced_schema_is_found_through_the_reference():
    ref = {"$ref": "#/components/schemas/Pet"}
    old = spec3(get(responses=reply(ref)), {"schemas": {"Pet": obj({"id": {"type": "integer"}, "name": {"type": "string"}})}})
    new = copy.deepcopy(old)
    del new["components"]["schemas"]["Pet"]["properties"]["name"]

    change = found(diff_specs(old, new), "property_removed")
    assert (change.severity, change.location) == ("breaking", "name")


def test_references_to_equal_schemas_under_different_names_are_no_change():
    old = spec3(get(responses=reply({"$ref": "#/components/schemas/Pet"})), {"schemas": {"Pet": obj({"id": {"type": "integer"}})}})
    new = spec3(get(responses=reply({"$ref": "#/components/schemas/Animal"})), {"schemas": {"Animal": obj({"id": {"type": "integer"}})}})

    assert diff_specs(old, new).changes == []


def test_a_recursive_schema_terminates():
    def tree(extra: dict | None = None) -> dict:
        node = obj({"value": {"type": "string"}, "children": {"type": "array", "items": {"$ref": "#/components/schemas/Node"}}, **(extra or {})})
        return spec3(get(responses=reply({"$ref": "#/components/schemas/Node"})), {"schemas": {"Node": node}})

    assert diff_specs(tree(), tree()).changes == []
    diff = diff_specs(tree(), tree({"id": {"type": "integer"}}))
    assert [c.kind for c in diff.changes] == ["property_added"]  # reported once, not once per level


def test_allof_parts_are_merged():
    base = {"$ref": "#/components/schemas/Base"}
    old = spec3(get(responses=reply({"allOf": [base, obj({"name": {"type": "string"}})]})), {"schemas": {"Base": obj({"id": {"type": "integer"}})}})
    new = copy.deepcopy(old)
    del new["components"]["schemas"]["Base"]["properties"]["id"]

    change = found(diff_specs(old, new), "property_removed")
    assert (change.severity, change.location) == ("breaking", "id")


def test_a_type_that_is_only_implied_is_not_a_type_change():
    explicit = spec3(get(responses=reply({"type": "object", "properties": {"a": {"type": "string"}}})))
    implied = spec3(get(responses=reply({"properties": {"a": {"type": "string"}}})))

    assert diff_specs(explicit, implied).changes == []


def test_composition_is_compared_as_a_whole():
    old = spec3(get(responses=reply({"oneOf": [{"type": "string"}, {"type": "integer"}]})))
    same = copy.deepcopy(old)
    new = spec3(get(responses=reply({"oneOf": [{"type": "string"}, {"type": "boolean"}]})))

    assert diff_specs(old, same).changes == []
    assert found(diff_specs(old, new), "composition_changed").severity == "warning"


def test_openapi_31_type_lists_mean_nullable():
    strict = spec3(get(responses=reply(obj({"a": {"type": "string"}}))))
    nullable = spec3(get(responses=reply(obj({"a": {"type": ["string", "null"]}}))))

    diff = diff_specs(strict, nullable)

    assert kinds(diff) == ["nullable_changed"]  # not a type change


# --- security -----------------------------------------------------------------------


def test_security_becoming_required_is_breaking_and_relaxed_is_info():
    open_op = spec3(get())
    secured = spec3(get(security=[{"oauth": []}]))

    assert found(diff_specs(open_op, secured), "security_added").severity == "breaking"
    assert found(diff_specs(secured, open_op), "security_relaxed").severity == "info"


def test_swapping_the_security_scheme_is_a_warning():
    old = spec3(get(security=[{"apiKey": []}]))
    new = spec3(get(security=[{"oauth": []}]))

    change = found(diff_specs(old, new), "security_changed")
    assert (change.severity, change.detail) == ("warning", {"added": ["oauth"], "removed": ["apiKey"]})


def test_global_security_is_inherited_and_an_operation_can_override_it():
    inherited = spec3(get(), security=[{"oauth": []}])
    explicit = spec3(get(security=[{"oauth": []}]))
    opened = spec3(get(security=[]), security=[{"oauth": []}])

    assert diff_specs(inherited, explicit).changes == []
    assert found(diff_specs(inherited, opened), "security_relaxed").severity == "info"


# --- Swagger 2.0 --------------------------------------------------------------------


def swagger(paths: dict, definitions: dict | None = None, **top) -> dict:
    document = {"swagger": "2.0", "info": {"title": "T", "version": "1"}, "paths": paths, **top}
    if definitions is not None:
        document["definitions"] = definitions
    return document


def test_swagger_body_parameter_and_response_schema_are_compared_like_openapi_3():
    pet = {"$ref": "#/definitions/Pet"}
    old = swagger(
        {"/pets": {"post": {"parameters": [{"in": "body", "name": "pet", "required": True, "schema": pet}], "responses": {"200": {"description": "ok", "schema": pet}}}}},
        {"Pet": obj({"id": {"type": "integer"}, "name": {"type": "string"}})},
        consumes=["application/json"],
        produces=["application/json"],
    )
    new = copy.deepcopy(old)
    new["definitions"]["Pet"]["properties"]["name"] = {"type": "integer"}
    new["definitions"]["Pet"]["required"] = ["id"]

    diff = diff_specs(old, new)

    assert {(c.scope, c.kind, c.severity, c.media_type) for c in diff.changes} == {
        ("request", "type_changed", "breaking", "application/json"),
        ("request", "property_became_required", "breaking", "application/json"),
        ("response", "type_changed", "breaking", "application/json"),
        ("response", "property_became_required", "info", "application/json"),
    }


def test_swagger_non_body_parameter_is_its_own_schema():
    def spec(kind: str) -> dict:
        return swagger({"/pets": {"get": {"parameters": [{"in": "query", "name": "n", "type": kind}], "responses": {"200": {"description": "ok"}}}}})

    change = found(diff_specs(spec("string"), spec("integer")), "type_changed")
    assert (change.severity, change.location, change.scope) == ("breaking", "query:n", "parameter")


def test_swagger_response_without_schema_has_no_media_types():
    old = swagger({"/pets": {"get": {"responses": {"200": {"description": "ok"}}}}})
    new = swagger({"/pets": {"get": {"responses": {"200": {"description": "ok", "schema": {"type": "string"}}}}}})

    # "ok" with no body and "ok" with a body: the body appears, which is not a break
    assert [(c.kind, c.severity) for c in diff_specs(old, new).changes] == [("media_type_added", "info")]


# --- robustness ---------------------------------------------------------------------


def test_documents_that_are_not_shaped_as_expected_never_raise():
    odd = [
        {},
        {"paths": None},
        {"paths": {"/a": None}},
        {"paths": {"/a": {"get": "nope"}}},
        {"paths": {"/a": {"get": {"parameters": "x", "responses": []}}}},
        {"paths": {"/a": {"get": {"parameters": [None, {"in": 1}], "responses": {"200": None}}}}},
        {"paths": {"/a": {"$ref": "#/nowhere"}}},
        {"paths": {"/a": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"$ref": "http://elsewhere/x.json"}}}}}}}}},
        {"paths": {"/a": {"post": {"requestBody": {"content": {"application/json": "bad"}}, "responses": {}}}}},
    ]
    for old in odd:
        for new in odd:
            diff_specs(old, new)  # must not raise


def test_unresolvable_references_compare_equal():
    old = spec3(get(responses=reply({"$ref": "#/components/schemas/Gone"})))
    new = spec3(get(responses=reply({"$ref": "#/components/schemas/AlsoGone"})))

    assert diff_specs(old, new).changes == []


def test_changes_are_most_severe_first_and_summarised():
    old = spec3({**get("/a", parameters=[param("x")]), **get("/b"), **get("/c")})
    new = spec3({**get("/a", parameters=[param("x", required=True)]), **get("/c", deprecated=True), **get("/d")})

    diff = diff_specs(old, new)

    assert [c.severity for c in diff.changes] == sorted((c.severity for c in diff.changes), key=["breaking", "warning", "info"].index)
    assert diff.summary() == {"breaking": 2, "warning": 1, "info": 1}  # /b removed, x required | /c deprecated | /d added


def test_a_huge_diff_is_cut_off_and_says_so():
    old = spec3({f"/p{i}": {"get": {"responses": reply()}} for i in range(MAX_CHANGES + 100)})
    new = spec3({})

    diff = diff_specs(old, new)

    assert len(diff.changes) == MAX_CHANGES
    assert diff.truncated is True


@pytest.mark.parametrize("spec", [spec3(get()), swagger({"/pets": {"get": {"responses": {"200": {"description": "ok"}}}}})])
def test_the_inputs_are_not_modified(spec):
    before = copy.deepcopy(spec)

    diff_specs(spec, spec3({}))

    assert spec == before
