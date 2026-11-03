# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the kinds of document besides OpenAPI: AsyncAPI, Postman
collections and GraphQL schemas (SDL, or an introspection result) - how each
is recognised, what version it gets (GraphQL schemas and most Postman
collections carry none, so one is derived from the structure: a changed
structure is a new version, a changed description only a content change), and
that they go through uploading, storing and downloading like any other.

Parsing is pure; the last part goes through the API with a real database."""

import json

import pytest
import yaml
from graphql import build_schema, introspection_from_schema

import app.security.jwt as jwt_module
from app.services.openapi_spec import SpecValidationError, parse_spec
from tests.version_support import make_team, make_user, request, token_for

SDL = """
type Query {
  users(limit: Int): [User!]!
}

type User {
  id: ID!
  name: String
}
"""


def sdl(text: str = SDL) -> bytes:
    return text.encode()


def revision(raw: bytes) -> str:
    return parse_spec(raw).version


# --- GraphQL ------------------------------------------------------------------------


def test_sdl_is_a_graphql_schema_with_a_version_made_from_its_structure():
    parsed = parse_spec(sdl())

    assert (parsed.kind, parsed.format, parsed.title) == ("graphql", "graphql", None)
    assert parsed.version.startswith("rev-") and len(parsed.version) == len("rev-") + 8
    assert parsed.content_hash and parsed.schema is not None and parsed.document == {}


def test_the_same_schema_written_differently_has_the_same_version_and_content():
    reordered = """
    # a comment that says nothing about the structure
    type User { name: String   id: ID! }
    type Query { users(limit: Int): [User!]! }
    """

    assert revision(sdl(reordered)) == revision(sdl())
    assert parse_spec(sdl(reordered)).content_hash == parse_spec(sdl()).content_hash


def test_a_reworded_description_keeps_the_version_but_changes_the_content():
    described = SDL.replace("name: String", '"The display name"\n  name: String')

    assert revision(sdl(described)) == revision(sdl())
    assert parse_spec(sdl(described)).content_hash != parse_spec(sdl()).content_hash


@pytest.mark.parametrize(
    "changed",
    [
        SDL.replace("name: String", "name: String\n  email: String"),  # a field added
        SDL.replace("users(limit: Int)", "users(limit: Int!)"),  # an argument became required
        SDL.replace("[User!]!", "[User]!"),  # a type changed
        SDL + "\nenum Role { ADMIN }\n",  # a type added
        SDL.replace("users(limit: Int)", "users(limit: Int = 10)"),  # a default
    ],
)
def test_any_change_of_structure_is_a_new_version(changed):
    assert revision(sdl(changed)) != revision(sdl())


def test_an_introspection_result_is_the_same_schema_as_its_sdl():
    schema = build_schema(SDL)
    introspection = {"data": introspection_from_schema(schema)}

    parsed = parse_spec(json.dumps(introspection).encode())
    bare = parse_spec(json.dumps(introspection["data"]).encode())

    assert (parsed.kind, parsed.format) == ("graphql", "json")
    assert parsed.version == bare.version == revision(sdl())
    assert parsed.content_hash == bare.content_hash == parse_spec(sdl()).content_hash
    assert parsed.document == introspection  # kept as parsed


def test_union_enum_interface_and_directive_changes_are_all_part_of_the_structure():
    rich = """
    directive @cache(ttl: Int) on FIELD_DEFINITION
    interface Node { id: ID! }
    type Dog implements Node { id: ID! }
    type Cat implements Node { id: ID! }
    union Pet = Dog | Cat
    enum Role { ADMIN USER }
    input Filter { role: Role }
    scalar Date
    type Query { pets(filter: Filter): [Pet!]! }
    """
    base = revision(sdl(rich))

    assert revision(sdl(rich.replace("Dog | Cat", "Dog"))) != base
    assert revision(sdl(rich.replace("ADMIN USER", "ADMIN USER GUEST"))) != base
    assert revision(sdl(rich.replace("Dog implements Node", "Dog"))) != base
    assert revision(sdl(rich.replace("ttl: Int", "ttl: Int!"))) != base
    assert revision(sdl(rich.replace("role: Role", "role: Role!"))) != base
    assert revision(sdl(rich.replace("scalar Date", "scalar Date\n    scalar Time"))) != base


@pytest.mark.parametrize(
    "bad",
    [b"type Query {", b"type Query { a: Unknown }", b"just some plain text", b"", b"   \n", b'{"__schema": {"foo": 1}}', b"\xff\xfe\x00"],
)
def test_something_that_is_not_a_graphql_schema_is_refused(bad):
    with pytest.raises(SpecValidationError):
        parse_spec(bad)


# --- AsyncAPI -----------------------------------------------------------------------

ASYNCAPI_V2 = {
    "asyncapi": "2.6.0",
    "info": {"title": "Streetlights", "version": "1.2.0"},
    "channels": {"light/measured": {"publish": {"message": {"payload": {"type": "object"}}}}},
}
ASYNCAPI_V3 = {
    "asyncapi": "3.0.0",
    "info": {"title": "Streetlights", "version": "2.0.0"},
    "channels": {"lights": {"address": "light/measured", "messages": {"measured": {"payload": {"type": "object"}}}}},
    "operations": {"onMeasured": {"action": "receive", "channel": {"$ref": "#/channels/lights"}}},
}


@pytest.mark.parametrize(("document", "version"), [(ASYNCAPI_V2, "1.2.0"), (ASYNCAPI_V3, "2.0.0")])
def test_an_asyncapi_document_is_recognised_with_its_own_version(document, version):
    parsed = parse_spec(json.dumps(document).encode())

    assert (parsed.kind, parsed.format, parsed.version, parsed.title) == ("asyncapi", "json", version, "Streetlights")
    assert parsed.document == document


def test_an_asyncapi_document_can_be_yaml_and_has_the_same_content_hash():
    as_yaml = parse_spec(yaml.safe_dump(ASYNCAPI_V2).encode())

    assert (as_yaml.kind, as_yaml.format) == ("asyncapi", "yaml")
    assert as_yaml.content_hash == parse_spec(json.dumps(ASYNCAPI_V2).encode()).content_hash


def test_an_asyncapi_document_without_a_version_is_refused():
    broken = {"asyncapi": "2.6.0", "info": {"title": "No version"}, "channels": {}}

    with pytest.raises(SpecValidationError, match="info.version"):
        parse_spec(json.dumps(broken).encode())


# --- Postman ------------------------------------------------------------------------

POSTMAN_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


def collection(items: list, **info) -> dict:
    return {"info": {"name": "Pets", "schema": POSTMAN_SCHEMA, **info}, "item": items}


def request_item(name: str, method: str, raw: str, *, path: list[str] | None = None, query: list | None = None, headers: list | None = None, description=None) -> dict:
    url: dict = {"raw": raw, "host": ["{{baseUrl}}"], "path": path if path is not None else []}
    if query is not None:
        url["query"] = query
    request: dict = {"method": method, "url": url, "header": headers or []}
    if description is not None:
        request["description"] = description
    return {"name": name, "request": request}


LIST_PETS = request_item("List pets", "GET", "{{baseUrl}}/pets?limit=10", path=["pets"], query=[{"key": "limit", "value": "10"}])
GET_PET = request_item("Get a pet", "GET", "{{baseUrl}}/pets/:id", path=["pets", ":id"])


def postman(items: list, **info) -> bytes:
    return json.dumps(collection(items, **info)).encode()


def test_a_postman_collection_is_recognised_and_titled_by_its_name():
    parsed = parse_spec(postman([LIST_PETS]))

    assert (parsed.kind, parsed.format, parsed.title) == ("postman", "json", "Pets")


def test_a_declared_version_is_used_as_a_string_or_as_the_object_form():
    assert parse_spec(postman([LIST_PETS], version="3.1")).version == "3.1"
    assert parse_spec(postman([LIST_PETS], version={"major": 1, "minor": 4, "patch": 2})).version == "1.4.2"


def test_without_a_declared_version_it_comes_from_the_requests():
    first = parse_spec(postman([LIST_PETS]))

    assert first.version.startswith("rev-")
    # folders, descriptions and names are not what the API looks like
    foldered = postman([{"name": "Folder", "item": [{**LIST_PETS, "name": "Renamed", "request": {**LIST_PETS["request"], "description": "now described"}}]}])
    assert parse_spec(foldered).version == first.version
    assert parse_spec(foldered).content_hash != first.content_hash  # but it is a content change
    # a server change is not a change of requests
    other_host = request_item("List pets", "GET", "https://staging.example.com/pets?limit=10", path=["pets"], query=[{"key": "limit", "value": "10"}])
    assert parse_spec(postman([other_host])).version == first.version
    # whereas a request, a query parameter or a header is
    assert parse_spec(postman([LIST_PETS, GET_PET])).version != first.version
    with_query = request_item("List pets", "GET", "{{baseUrl}}/pets", path=["pets"], query=[{"key": "limit"}, {"key": "offset"}])
    assert parse_spec(postman([with_query])).version != first.version
    with_header = request_item("List pets", "GET", "{{baseUrl}}/pets", path=["pets"], query=[{"key": "limit"}], headers=[{"key": "X-Token"}])
    assert parse_spec(postman([with_header])).version != first.version


def test_a_disabled_parameter_is_not_part_of_the_request():
    base = request_item("List", "GET", "{{baseUrl}}/pets", path=["pets"], query=[{"key": "limit"}])
    with_disabled = request_item("List", "GET", "{{baseUrl}}/pets", path=["pets"], query=[{"key": "limit"}, {"key": "debug", "disabled": True}])

    assert parse_spec(postman([with_disabled])).version == parse_spec(postman([base])).version


def test_an_older_export_is_recognised_without_the_schema_url():
    older = {"info": {"_postman_id": "abc-123", "name": "Old"}, "item": [LIST_PETS]}

    parsed = parse_spec(json.dumps(older).encode())

    assert (parsed.kind, parsed.title) == ("postman", "Old")


def test_a_document_that_only_looks_a_little_like_one_is_not_a_collection():
    not_one = {"info": {"title": "Pets", "version": "1.0.0"}, "item": [LIST_PETS]}

    assert parse_spec(json.dumps(not_one).encode()).kind == "openapi"


# --- the existing kinds are unchanged -----------------------------------------------


def test_openapi_and_swagger_are_still_openapi_and_anything_with_a_version_is_accepted():
    openapi = {"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "paths": {}}
    swagger = {"swagger": "2.0", "info": {"title": "T", "version": "1"}, "paths": {}}
    other = {"info": {"title": "T", "version": "9"}}

    assert [parse_spec(json.dumps(d).encode()).kind for d in (openapi, swagger, other)] == ["openapi"] * 3


def test_yaml_that_is_a_list_or_a_scalar_is_not_accepted():
    for text in (b"- a\n- b\n", b"42", b"hello there"):
        with pytest.raises(SpecValidationError):
            parse_spec(text)


# --- through the API ----------------------------------------------------------------


@pytest.fixture()
def _signed_in(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


async def _upload(db_session, token, team, raw: bytes, filename: str, settings):
    return await request(
        db_session,
        "POST",
        "/api/api-docs/upload",
        token=token,
        settings=settings,
        data={"team_id": str(team.id), "title": "Uploaded"},
        files={"file": (filename, raw, "application/octet-stream")},
    )


@pytest.mark.parametrize(
    ("raw", "filename", "spec_type", "media_type"),
    [
        (sdl(), "schema.graphql", "graphql", "application/graphql"),
        (json.dumps(ASYNCAPI_V2).encode(), "asyncapi.json", "asyncapi", "application/json"),
        (yaml.safe_dump(ASYNCAPI_V3).encode(), "asyncapi.yaml", "asyncapi", "application/yaml"),
        (postman([LIST_PETS]), "collection.json", "postman", "application/json"),
    ],
)
async def test_each_kind_can_be_uploaded_stored_listed_and_downloaded(
    db_session, make_access_token, tmp_path, _signed_in, raw, filename, spec_type, media_type
):
    from tests.version_support import docs_settings

    owner = await make_user(db_session, email="owner@example.com")
    team = await make_team(db_session, "Owners", members=(owner,))
    token = token_for(make_access_token, owner)
    settings = docs_settings(tmp_path)

    created = await _upload(db_session, token, team, raw, filename, settings)

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["current_version"]["spec_type"] == spec_type
    doc_id, version_id = body["id"], body["current_version"]["id"]
    listing = await request(db_session, "GET", f"/api/api-docs/{doc_id}/versions", token=token)
    assert [row["spec_type"] for row in listing.json()] == [spec_type]
    download = await request(db_session, "GET", f"/api/api-docs/{doc_id}/versions/{version_id}/spec", token=token, settings=settings)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(media_type)
    assert download.content == raw  # exactly as uploaded


async def test_a_graphql_schema_gets_new_versions_as_its_structure_changes(db_session, make_access_token, tmp_path, _signed_in):
    from tests.version_support import docs_settings

    owner = await make_user(db_session, email="owner@example.com")
    team = await make_team(db_session, "Owners", members=(owner,))
    token = token_for(make_access_token, owner)
    settings = docs_settings(tmp_path)
    created = (await _upload(db_session, token, team, sdl(), "schema.graphql", settings)).json()
    path = f"/api/api-docs/{created['id']}/upload-version"
    first_version = created["current_version"]["version"]

    async def upload(text: str):
        return (await request(db_session, "POST", path, token=token, settings=settings, files={"file": ("schema.graphql", sdl(text), "text/plain")})).json()

    same = await upload(SDL.replace("  ", "    "))  # only reformatted
    described = await upload(SDL.replace("name: String", '"The display name"\n  name: String'))
    changed = await upload(SDL.replace("name: String", "name: String\n  email: String"))

    assert (same["new_version_found"], same["content_changed"]) == (False, False)
    assert (described["new_version_found"], described["content_changed"]) == (False, True)
    assert described["current_version"]["version"] == first_version  # same structure, same version
    assert changed["new_version_found"] is True and changed["current_version"]["version"] != first_version
    assert changed["previous_version"] == first_version
