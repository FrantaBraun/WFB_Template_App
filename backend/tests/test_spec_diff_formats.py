# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for comparing two versions of the kinds of document besides OpenAPI:
GraphQL schemas, Postman collections and AsyncAPI documents - what is a
breaking change, a warning or a harmless one for whoever consumes the API, the
same structured changes the frontend words, the dispatcher that picks the right
comparison (and treats a change of kind as one breaking change), and the whole
way through the API for a GraphQL schema.

The comparisons are pure; only the last tests need the database."""

import copy
import json

import pytest
from graphql import build_schema, introspection_from_schema

import app.security.jwt as jwt_module
from app.services.openapi_spec import parse_spec
from app.services.spec_compare import diff_parsed
from tests.version_support import docs_settings, make_team, make_user, pets_spec, request, token_for

# --- GraphQL ------------------------------------------------------------------------

BASE_SDL = """
directive @cache(ttl: Int) on FIELD_DEFINITION
interface Node { id: ID! }
enum Role { ADMIN USER }
input UserFilter { role: Role  name: String }
type Error { message: String! }
type User implements Node { id: ID!  name: String  role: Role }
union Result = User | Error
type Query {
  users(limit: Int, filter: UserFilter): [User!]!
  user(id: ID!): User
}
"""


def gql(text: str):
    return parse_spec(text.encode())


def graphql_changes(old: str, new: str):
    return diff_parsed(gql(old), gql(new)).changes


def one(changes, kind: str, **where):
    matches = [c for c in changes if c.kind == kind and all(getattr(c, key) == value for key, value in where.items())]
    assert len(matches) == 1, f"{kind} {where}: {[(c.kind, c.severity, c.path, c.location) for c in changes]}"
    return matches[0]


def test_identical_graphql_schemas_have_no_changes_even_when_written_differently():
    reordered = "\n".join(reversed(BASE_SDL.strip().splitlines()))  # silly, but a different text of a different layout

    assert graphql_changes(BASE_SDL, BASE_SDL) == []
    assert diff_parsed(gql(BASE_SDL), gql("# a comment\n" + BASE_SDL.replace("  ", "    "))).changes == []
    assert reordered != BASE_SDL


def test_a_schema_and_its_introspection_result_are_the_same_schema():
    introspection = json.dumps({"data": introspection_from_schema(build_schema(BASE_SDL))}).encode()

    assert diff_parsed(gql(BASE_SDL), parse_spec(introspection)).changes == []


def test_a_type_removed_is_breaking_and_a_type_added_is_info():
    removed = graphql_changes(BASE_SDL, BASE_SDL.replace("type Error { message: String! }", "").replace("User | Error", "User"))
    added = graphql_changes(BASE_SDL, BASE_SDL + "\ntype Pet { id: ID! }\n")

    gone = one(removed, "graphql_type_removed", path="Error")
    assert (gone.severity, gone.detail) == ("breaking", {"kind": "object"})
    new = one(added, "graphql_type_added", path="Pet")
    assert (new.severity, new.detail) == ("info", {"kind": "object"})


def test_a_type_that_changes_kind_is_breaking():
    changed = graphql_changes(BASE_SDL, BASE_SDL.replace("enum Role { ADMIN USER }", "type Role { name: String }"))

    change = one(changed, "graphql_type_kind_changed", path="Role")
    assert (change.severity, change.detail) == ("breaking", {"from": "enum", "to": "object"})


def test_fields_removed_added_and_deprecated():
    removed = graphql_changes(BASE_SDL, BASE_SDL.replace("name: String  role", "role"))
    added = graphql_changes(BASE_SDL, BASE_SDL.replace("name: String  role", "name: String  email: String  role"))
    deprecated = graphql_changes(BASE_SDL, BASE_SDL.replace("name: String", "name: String @deprecated(reason: \"x\")"))

    gone = one(removed, "graphql_field_removed", path="User", location="name")
    assert gone.severity == "breaking"
    assert one(added, "graphql_field_added", path="User", location="email").severity == "info"
    assert one(deprecated, "graphql_field_deprecated", path="User", location="name").severity == "warning"


@pytest.mark.parametrize(
    ("old", "new", "severity"),
    [
        ("name: String", "name: Int", "breaking"),  # a different type altogether
        ("name: String", "name: String!", "info"),  # promises more: a client that reads it is fine
        ("name: String!", "name: String", "breaking"),  # may now be null
        ("[User!]!", "[User]!", "breaking"),  # the items may now be null
        ("[User!]!", "[User!]", "breaking"),
    ],
)
def test_a_field_whose_type_changed_is_judged_by_what_a_client_reads(old, new, severity):
    base = BASE_SDL.replace("name: String", "name: String!") if old == "name: String!" else BASE_SDL

    changes = graphql_changes(base, base.replace(old, new))

    (change,) = [c for c in changes if c.kind == "graphql_field_type_changed"]
    assert (change.severity, change.detail["from"], change.detail["to"]) == (severity, old.split(": ")[-1], new.split(": ")[-1])


def test_arguments_removed_added_and_with_a_default():
    removed = graphql_changes(BASE_SDL, BASE_SDL.replace("users(limit: Int, filter: UserFilter)", "users(filter: UserFilter)"))
    optional = graphql_changes(BASE_SDL, BASE_SDL.replace("users(limit: Int,", "users(offset: Int, limit: Int,"))
    required = graphql_changes(BASE_SDL, BASE_SDL.replace("users(limit: Int,", "users(tenant: ID!, limit: Int,"))
    with_default = graphql_changes(BASE_SDL, BASE_SDL.replace("users(limit: Int,", "users(tenant: ID! = \"main\", limit: Int,"))

    assert one(removed, "graphql_argument_removed", path="Query", location="users(limit)").severity == "breaking"
    assert one(optional, "graphql_argument_added", location="users(offset)").severity == "info"
    must = one(required, "graphql_argument_added", location="users(tenant)")
    assert (must.severity, must.detail) == ("breaking", {"required": True})
    assert one(with_default, "graphql_argument_added", location="users(tenant)").severity == "info"  # a default means it need not be given


@pytest.mark.parametrize(("old", "new", "severity"), [("limit: Int,", "limit: Int!,", "breaking"), ("user(id: ID!)", "user(id: ID)", "info"), ("limit: Int,", "limit: String,", "breaking")])
def test_an_argument_whose_type_changed_is_judged_by_what_a_client_sends(old, new, severity):
    changes = graphql_changes(BASE_SDL, BASE_SDL.replace(old, new))

    (change,) = [c for c in changes if c.kind == "graphql_argument_type_changed"]
    assert change.severity == severity


def test_a_default_that_changed_is_a_warning():
    changes = graphql_changes(BASE_SDL.replace("limit: Int,", "limit: Int = 10,"), BASE_SDL.replace("limit: Int,", "limit: Int = 50,"))
    added = graphql_changes(BASE_SDL, BASE_SDL.replace("limit: Int,", "limit: Int = 10,"))

    change = one(changes, "graphql_default_changed", location="users(limit)")
    assert (change.severity, change.detail) == ("warning", {"from": "10", "to": "50"})
    assert one(added, "graphql_default_changed").detail == {"from": None, "to": "10"}


def test_input_object_fields():
    removed = graphql_changes(BASE_SDL, BASE_SDL.replace("role: Role  name: String", "role: Role"))
    optional = graphql_changes(BASE_SDL, BASE_SDL.replace("name: String }", "name: String  limit: Int }"))
    required = graphql_changes(BASE_SDL, BASE_SDL.replace("name: String }", "name: String  limit: Int! }"))
    tightened = graphql_changes(BASE_SDL, BASE_SDL.replace("name: String }", "name: String! }"))

    assert one(removed, "graphql_input_field_removed", path="UserFilter", location="name").severity == "breaking"
    assert one(optional, "graphql_input_field_added", location="limit").severity == "info"
    assert one(required, "graphql_input_field_added", location="limit").severity == "breaking"
    assert one(tightened, "graphql_input_field_type_changed", location="name").severity == "breaking"


def test_enum_values_union_members_and_interfaces():
    enum_removed = graphql_changes(BASE_SDL, BASE_SDL.replace("ADMIN USER", "ADMIN"))
    enum_added = graphql_changes(BASE_SDL, BASE_SDL.replace("ADMIN USER", "ADMIN USER GUEST"))
    union_removed = graphql_changes(BASE_SDL, BASE_SDL.replace("User | Error", "User"))
    union_added = graphql_changes(BASE_SDL, BASE_SDL.replace("User | Error", "User | Error | Query"))
    interface_removed = graphql_changes(BASE_SDL, BASE_SDL.replace("User implements Node", "User"))
    interface_added = graphql_changes(BASE_SDL, BASE_SDL.replace("type Error {", "type Error implements Node { id: ID!"))

    assert one(enum_removed, "graphql_enum_value_removed", path="Role", location="USER").severity == "breaking"
    assert one(enum_added, "graphql_enum_value_added", location="GUEST").severity == "warning"  # a client's switch may not know it
    assert one(union_removed, "graphql_union_member_removed", path="Result", location="Error").severity == "breaking"
    assert one(union_added, "graphql_union_member_added", location="Query").severity == "warning"
    assert one(interface_removed, "graphql_interface_removed", path="User", location="Node").severity == "breaking"
    assert one(interface_added, "graphql_interface_added", path="Error", location="Node").severity == "warning"


def test_directives():
    removed = graphql_changes(BASE_SDL, BASE_SDL.replace("directive @cache(ttl: Int) on FIELD_DEFINITION", ""))
    added = graphql_changes(BASE_SDL, BASE_SDL + "\ndirective @log on FIELD_DEFINITION\n")

    assert one(removed, "graphql_directive_removed", path="@cache").severity == "breaking"
    assert one(added, "graphql_directive_added", path="@log").severity == "info"


def test_graphql_changes_are_most_severe_first_and_grouped_by_type():
    changes = graphql_changes(BASE_SDL, BASE_SDL.replace("name: String  role", "email: String  role").replace("ADMIN USER", "ADMIN USER GUEST"))

    severities = [c.severity for c in changes]
    assert severities == sorted(severities, key=["breaking", "warning", "info"].index)
    assert {c.path for c in changes} == {"User", "Role"}
    assert all(c.method is None for c in changes)


# --- Postman ------------------------------------------------------------------------

SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


def pm_request(name, method, path, query=(), headers=(), host="{{baseUrl}}"):
    url = {"raw": f"{host}/{'/'.join(path)}", "host": [host], "path": list(path), "query": [{"key": k, **({"disabled": True} if k.startswith("~") else {})} for k in query]}
    return {"name": name, "request": {"method": method, "url": url, "header": [{"key": h} for h in headers]}}


def pm(*items, **info):
    return parse_spec(json.dumps({"info": {"name": "Pets", "schema": SCHEMA, **info}, "item": list(items)}).encode())


LIST = pm_request("List", "GET", ["pets"], query=["limit"])
GET = pm_request("Get", "GET", ["pets", ":id"])


def test_postman_requests_added_and_removed():
    removed = diff_parsed(pm(LIST, GET, version="1"), pm(LIST, version="1")).changes
    added = diff_parsed(pm(LIST, version="1"), pm(LIST, GET, version="1")).changes

    gone = one(removed, "operation_removed", method="GET", path="/pets/:id")
    assert gone.severity == "breaking"
    assert one(added, "operation_added", method="GET", path="/pets/:id").severity == "info"


def test_postman_query_parameters_and_headers():
    more = pm_request("List", "GET", ["pets"], query=["limit", "offset"], headers=["X-Token"])
    fewer = pm_request("List", "GET", ["pets"], query=[])

    gained = diff_parsed(pm(LIST, version="1"), pm(more, version="1")).changes
    lost = diff_parsed(pm(more, version="1"), pm(fewer, version="1")).changes

    assert {(c.kind, c.location, c.severity) for c in gained} == {
        ("parameter_added", "query:offset", "info"),
        ("parameter_added", "header:X-Token", "info"),
    }
    assert {(c.kind, c.location, c.severity) for c in lost} == {
        ("parameter_removed", "query:limit", "warning"),
        ("parameter_removed", "query:offset", "warning"),
        ("parameter_removed", "header:X-Token", "warning"),
    }


def test_postman_folders_names_hosts_and_disabled_parameters_are_not_changes():
    moved = {"name": "Folder", "item": [pm_request("Renamed", "GET", ["pets"], query=["limit", "~debug"], host="https://staging.example.com")]}

    assert diff_parsed(pm(LIST, version="1"), pm(moved, version="1")).changes == []


# --- AsyncAPI -----------------------------------------------------------------------


def payload(properties: dict, required=()) -> dict:
    return {"type": "object", "properties": properties, "required": list(required)}


def v2(*, subscribe=None, publish=None, components=None, **extra) -> dict:
    channels = {}
    if subscribe is not None:
        channels["user/signedup"] = {"subscribe": {"message": subscribe}}
    if publish is not None:
        channels["user/create"] = {"publish": {"message": publish}}
    document = {"asyncapi": "2.6.0", "info": {"title": "Users", "version": "1.0.0"}, "channels": channels, **extra}
    if components:
        document["components"] = components
    return document


def asyncapi(document: dict):
    return parse_spec(json.dumps(document).encode())


def async_changes(old: dict, new: dict):
    return diff_parsed(asyncapi(old), asyncapi(new)).changes


SIGNED_UP = {"name": "UserSignedUp", "payload": payload({"id": {"type": "string"}, "email": {"type": "string"}}, ["id"])}
CREATE = {"name": "CreateUser", "payload": payload({"name": {"type": "string"}}, ["name"])}


def with_payload(message: dict, schema: dict) -> dict:
    return {**message, "payload": schema}


def test_identical_asyncapi_documents_have_no_changes():
    document = v2(subscribe=SIGNED_UP, publish=CREATE)

    assert async_changes(document, copy.deepcopy(document)) == []


def test_asyncapi_operations_removed_and_added_are_labelled_by_direction_and_channel():
    removed = async_changes(v2(subscribe=SIGNED_UP, publish=CREATE), v2(publish=CREATE))
    added = async_changes(v2(publish=CREATE), v2(subscribe=SIGNED_UP, publish=CREATE))

    gone = one(removed, "operation_removed", method="SUBSCRIBE", path="user/signedup")
    assert gone.severity == "breaking"
    assert one(added, "operation_added", method="SUBSCRIBE", path="user/signedup").severity == "info"


def test_what_a_client_receives_is_judged_like_a_response():
    """2.x subscribe: the client receives the messages."""
    old = v2(subscribe=SIGNED_UP)
    removed_property = v2(subscribe=with_payload(SIGNED_UP, payload({"id": {"type": "string"}}, ["id"])))
    added_property = v2(subscribe=with_payload(SIGNED_UP, payload({"id": {"type": "string"}, "email": {"type": "string"}, "plan": {"type": "string"}}, ["id", "plan"])))
    changed_type = v2(subscribe=with_payload(SIGNED_UP, payload({"id": {"type": "integer"}, "email": {"type": "string"}}, ["id"])))

    gone = one(async_changes(old, removed_property), "property_removed", location="email")
    assert (gone.severity, gone.scope, gone.method, gone.path, gone.media_type) == ("breaking", "message", "SUBSCRIBE", "user/signedup", "UserSignedUp")
    assert one(async_changes(old, added_property), "property_added", location="plan").severity == "info"  # even when required
    assert one(async_changes(old, changed_type), "type_changed", location="id").severity == "breaking"


def test_what_a_client_sends_is_judged_like_a_request():
    """2.x publish: the client sends the messages."""
    old = v2(publish=CREATE)
    required = v2(publish=with_payload(CREATE, payload({"name": {"type": "string"}, "tenant": {"type": "string"}}, ["name", "tenant"])))
    optional = v2(publish=with_payload(CREATE, payload({"name": {"type": "string"}, "note": {"type": "string"}}, ["name"])))
    removed = v2(publish=with_payload(CREATE, payload({}, [])))

    assert one(async_changes(old, required), "property_added", location="tenant").severity == "breaking"
    assert one(async_changes(old, optional), "property_added", location="note").severity == "info"
    assert one(async_changes(old, removed), "property_removed", location="name").severity == "warning"


def test_messages_removed_and_added_depend_on_the_direction():
    other = {"name": "UserDeleted", "payload": payload({"id": {"type": "string"}})}
    sub_two = v2(subscribe={"oneOf": [SIGNED_UP, other]})
    sub_one = v2(subscribe={"oneOf": [SIGNED_UP]})
    pub_two = v2(publish={"oneOf": [CREATE, other]})
    pub_one = v2(publish={"oneOf": [CREATE]})

    assert one(async_changes(sub_two, sub_one), "message_removed", media_type="UserDeleted").severity == "breaking"
    assert one(async_changes(sub_one, sub_two), "message_added", media_type="UserDeleted").severity == "warning"  # a client may not handle it
    assert one(async_changes(pub_one, pub_two), "message_added", media_type="UserDeleted").severity == "info"  # one it may now send
    assert one(async_changes(pub_two, pub_one), "message_removed", media_type="UserDeleted").severity == "breaking"


def test_references_to_messages_and_schemas_are_followed():
    def document(email_type: str) -> dict:
        return v2(
            subscribe={"$ref": "#/components/messages/SignedUp"},
            components={
                "messages": {"SignedUp": {"name": "UserSignedUp", "payload": {"$ref": "#/components/schemas/User"}}},
                "schemas": {"User": payload({"id": {"type": "string"}, "email": {"type": email_type}}, ["id"])},
            },
        )

    change = one(async_changes(document("string"), document("integer")), "type_changed", location="email")

    assert (change.severity, change.media_type, change.detail) == ("breaking", "UserSignedUp", {"from": "string", "to": "integer"})


def test_asyncapi_3_send_is_what_a_client_receives_and_receive_what_it_sends():
    def v3(action: str, schema: dict) -> dict:
        return {
            "asyncapi": "3.0.0",
            "info": {"title": "Users", "version": "1.0.0"},
            "channels": {"users": {"address": "user/events", "messages": {"event": {"payload": schema}}}},
            "operations": {"op": {"action": action, "channel": {"$ref": "#/channels/users"}}},
        }

    base = payload({"id": {"type": "string"}, "email": {"type": "string"}}, ["id"])
    smaller = payload({"id": {"type": "string"}}, ["id"])
    stricter = payload({"id": {"type": "string"}, "email": {"type": "string"}, "tenant": {"type": "string"}}, ["id", "tenant"])

    received = async_changes(v3("send", base), v3("send", smaller))  # the client receives: a property is gone
    sent = async_changes(v3("receive", base), v3("receive", stricter))  # the client sends: a required one appeared

    gone = one(received, "property_removed", method="SEND", path="user/events", location="email")
    assert (gone.severity, gone.media_type) == ("breaking", "event")
    assert one(sent, "property_added", method="RECEIVE", location="tenant").severity == "breaking"


def test_a_deprecated_asyncapi_operation_is_a_warning():
    deprecated = v2(subscribe=SIGNED_UP)
    deprecated["channels"]["user/signedup"]["subscribe"]["deprecated"] = True

    assert one(async_changes(v2(subscribe=SIGNED_UP), deprecated), "operation_deprecated").severity == "warning"


def test_odd_asyncapi_documents_never_raise():
    odd = [{"asyncapi": "2.0.0", "info": {"version": "1"}}, {"asyncapi": "3.0.0", "info": {"version": "1"}, "operations": {"a": None, "b": {"action": "send"}}},
           {"asyncapi": "2.6.0", "info": {"version": "1"}, "channels": {"x": None, "y": {"publish": "no"}, "z": {"subscribe": {"message": {"oneOf": [None, 1]}}}}}]
    for old in odd:
        for new in odd:
            diff_parsed(asyncapi(old), asyncapi(new))  # must not raise


# --- the dispatcher -----------------------------------------------------------------


def test_a_change_of_kind_is_one_breaking_change():
    openapi = parse_spec(json.dumps(pets_spec()).encode())

    diff = diff_parsed(openapi, gql(BASE_SDL))

    (change,) = diff.changes
    assert (change.kind, change.severity, change.detail) == ("spec_type_changed", "breaking", {"from": "openapi", "to": "graphql"})


def test_openapi_still_goes_through_the_openapi_comparison():
    old = parse_spec(json.dumps(pets_spec("1.0.0")).encode())
    new = parse_spec(json.dumps(pets_spec("2.0.0", paths={})).encode())

    assert [c.kind for c in diff_parsed(old, new).changes] == ["operation_removed"]


# --- through the API ----------------------------------------------------------------


@pytest.fixture()
def _signed_in(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


async def test_a_breaking_graphql_change_is_summarised_and_listed(db_session, make_access_token, tmp_path, _signed_in):
    owner = await make_user(db_session, email="owner@example.com")
    team = await make_team(db_session, "Owners", members=(owner,))
    token = token_for(make_access_token, owner)
    settings = docs_settings(tmp_path)
    created = (
        await request(
            db_session, "POST", "/api/api-docs/upload", token=token, settings=settings,
            data={"team_id": str(team.id), "title": "Users"}, files={"file": ("schema.graphql", BASE_SDL.encode(), "text/plain")},
        )
    ).json()
    breaking = BASE_SDL.replace("name: String  role", "role").replace("ADMIN USER", "ADMIN USER GUEST")

    uploaded = (
        await request(
            db_session, "POST", f"/api/api-docs/{created['id']}/upload-version", token=token, settings=settings,
            files={"file": ("schema.graphql", breaking.encode(), "text/plain")},
        )
    ).json()
    version_id = uploaded["current_version"]["id"]
    # `against` is given because inside the test's one transaction every version has the same timestamp
    changes = await request(
        db_session,
        "GET",
        f"/api/api-docs/{created['id']}/versions/{version_id}/changes?against={created['current_version']['id']}",
        token=token,
        settings=settings,
    )

    assert uploaded["new_version_found"] is True
    assert uploaded["current_version"]["change_summary"] == {"breaking": 1, "warning": 1, "info": 0}
    assert changes.status_code == 200, changes.text
    body = changes.json()
    assert (body["base"]["version"], body["target"]["version"]) == (created["current_version"]["version"], uploaded["current_version"]["version"])
    assert [(c["kind"], c["severity"], c["path"], c["location"]) for c in body["changes"]] == [
        ("graphql_field_removed", "breaking", "User", "name"),
        ("graphql_enum_value_added", "warning", "Role", "GUEST"),
    ]
    assert all(c["method"] is None for c in body["changes"])
