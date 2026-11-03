# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the list of endpoints of a document of any kind
(app/services/spec_outline.py) and GET .../versions/{id}/outline, the readable
form of the kinds that have no rendered documentation."""

import json

import pytest

import app.security.jwt as jwt_module
from app.services import spec_outline
from app.services.openapi_spec import parse_spec
from app.services.spec_outline import extract_endpoints
from tests.format_support import BASE_SDL, SCHEMA, pm, pm_request
from tests.version_support import docs_settings, make_document, make_user, pets_spec, record, request, token_for


def endpoints(document) -> list:
    raw = document if isinstance(document, bytes) else json.dumps(document).encode()
    return extract_endpoints(parse_spec(raw))


def test_openapi_operations_with_their_texts_in_document_order():
    spec = pets_spec(
        paths={
            "/pets": {
                "parameters": [{"name": "x", "in": "query"}],
                "get": {"summary": "List pets", "description": "All of them.", "tags": ["pets", 3], "operationId": "listPets"},
                "post": {"deprecated": True},
                "x-internal": {"get": {}},
            },
            "/pets/{id}": {"delete": {}, "trace": None, "get": "nonsense"},
            "/odd": "nonsense",
        }
    )

    found = endpoints(spec)

    assert [(e.method, e.path) for e in found] == [("GET", "/pets"), ("POST", "/pets"), ("DELETE", "/pets/{id}")]
    listed = found[0]
    assert (listed.name, listed.description, listed.tags, listed.operation_id, listed.deprecated) == (
        "List pets", "All of them.", ("pets",), "listPets", False,
    )
    assert found[1].deprecated is True


def test_swagger_2_and_a_document_without_paths():
    swagger = {"swagger": "2.0", "info": {"title": "Old", "version": "1"}, "paths": {"/a": {"get": {"summary": "A"}}}}

    assert [(e.method, e.path, e.name) for e in endpoints(swagger)] == [("GET", "/a", "A")]
    assert endpoints({"openapi": "3.0.0", "info": {"title": "x", "version": "1"}}) == []


def test_postman_requests_flattened_from_folders():
    folder = {"name": "Admin", "item": [pm_request("Remove", "DELETE", ["pets", ":id"])]}
    request_with_text = pm_request("List", "GET", ["pets"])
    request_with_text["request"]["description"] = "Every pet."

    found = extract_endpoints(pm(request_with_text, folder, version="1"))

    assert [(e.method, e.path, e.name, e.description) for e in found] == [
        ("GET", "/pets", "List", "Every pet."),
        ("DELETE", "/pets/:id", "Remove", None),
    ]


def test_asyncapi_2_directions_channels_and_message_names():
    document = {
        "asyncapi": "2.6.0",
        "info": {"title": "Users", "version": "1"},
        "channels": {
            "user/signedup": {"subscribe": {"message": {"name": "UserSignedUp", "payload": {"type": "object"}}, "deprecated": True}},
            "user/create": {"publish": {"message": {"oneOf": [{"name": "CreateUser"}, {"name": "CreateAdmin"}]}}},
        },
    }

    found = endpoints(document)

    assert [(e.method, e.path, e.name, e.deprecated) for e in found] == [
        ("PUBLISH", "user/create", "CreateUser, CreateAdmin", False),
        ("SUBSCRIBE", "user/signedup", "UserSignedUp", True),
    ]


def test_asyncapi_3_operations_use_the_channel_address():
    document = {
        "asyncapi": "3.0.0",
        "info": {"title": "Users", "version": "1"},
        "channels": {"users": {"address": "user/events", "messages": {"event": {"payload": {"type": "object"}}}}},
        "operations": {"announce": {"action": "send", "channel": {"$ref": "#/channels/users"}}},
    }

    assert [(e.method, e.path, e.name) for e in endpoints(document)] == [("SEND", "user/events", "event")]


def test_graphql_root_fields_with_their_signatures():
    schema = (
        BASE_SDL
        + '\nextend type Query { "All of them" legacy: [User] @deprecated(reason: "no") }'
        + "\ntype Mutation { createUser(name: String!, role: Role = USER): User }"
        + "\nschema { query: Query mutation: Mutation }\n"
    )

    found = endpoints(schema.encode())

    by_path = {(e.method, e.path): e for e in found}
    assert set(by_path) == {("QUERY", "users"), ("QUERY", "user"), ("QUERY", "legacy"), ("MUTATION", "createUser")}
    assert by_path[("QUERY", "users")].name == "users(limit: Int, filter: UserFilter): [User!]!"
    assert by_path[("MUTATION", "createUser")].name == "createUser(name: String!, role: Role): User"
    assert (by_path[("QUERY", "legacy")].description, by_path[("QUERY", "legacy")].deprecated) == ("All of them", True)
    assert by_path[("QUERY", "user")].deprecated is False


def test_the_list_is_capped(monkeypatch):
    monkeypatch.setattr(spec_outline, "MAX_ENDPOINTS", 2)
    paths = {f"/p{i}": {"get": {}} for i in range(5)}

    assert [e.path for e in endpoints(pets_spec(paths=paths))] == ["/p0", "/p1"]


def test_a_long_description_is_cut():
    spec = pets_spec(paths={"/a": {"get": {"description": "x" * 5000}}})

    (found,) = endpoints(spec)

    assert len(found.description) == spec_outline.MAX_TEXT


def test_odd_documents_give_an_empty_list_instead_of_raising():
    assert endpoints({"asyncapi": "3.0.0", "info": {"version": "1"}, "operations": {"a": None}}) == []
    assert endpoints({"info": {"name": "x", "schema": SCHEMA, "version": "1"}, "item": [None, {"request": "x"}]}) == []
    assert endpoints({"info": {"title": "x", "version": "1"}, "paths": [1]}) == []


# --- GET .../versions/{id}/outline ----------------------------------------------------


@pytest.fixture()
def _signed_in(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


async def test_the_outline_of_a_public_openapi_version_is_open_to_anyone(db_session, tmp_path):
    doc = await make_document(db_session, is_public=True)
    version = await record(db_session, doc, pets_spec(paths={"/pets": {"get": {"summary": "List"}}}), tmp_path)

    resp = await request(db_session, "GET", f"/api/api-docs/{doc.id}/versions/{version.id}/outline", settings=docs_settings(tmp_path))

    assert resp.status_code == 200
    assert resp.json() == {
        "spec_type": "openapi",
        "title": "Pets",
        "version": "1.0.0",
        "endpoints": [{"method": "GET", "path": "/pets", "name": "List", "description": None, "tags": [], "deprecated": False, "operation_id": None}],
    }


async def test_the_outline_of_a_private_document_needs_membership(db_session, make_access_token, tmp_path, _signed_in):
    member = await make_user(db_session, email="member@example.com")
    outsider = await make_user(db_session, email="outsider@example.com")
    doc = await make_document(db_session, members=(member,))
    version = await record(db_session, doc, pets_spec(), tmp_path)
    url = f"/api/api-docs/{doc.id}/versions/{version.id}/outline"
    settings = docs_settings(tmp_path)

    anonymous = await request(db_session, "GET", url, settings=settings)
    stranger = await request(db_session, "GET", url, token=token_for(make_access_token, outsider), settings=settings)
    allowed = await request(db_session, "GET", url, token=token_for(make_access_token, member), settings=settings)

    assert (anonymous.status_code, stranger.status_code, allowed.status_code) == (404, 404, 200)


async def test_the_outline_of_a_graphql_schema_lists_its_root_fields(db_session, tmp_path):
    from app.services.api_document_versions import process_new_spec

    doc = await make_document(db_session, is_public=True)
    version = await process_new_spec(
        doc, BASE_SDL.encode(), source="manual_upload", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )

    resp = await request(db_session, "GET", f"/api/api-docs/{doc.id}/versions/{version.id}/outline", settings=docs_settings(tmp_path))

    body = resp.json()
    assert (body["spec_type"], body["version"].startswith("rev-")) == ("graphql", True)
    assert [(e["method"], e["path"]) for e in body["endpoints"]] == [("QUERY", "users"), ("QUERY", "user")]


async def test_outline_errors_for_a_foreign_version_a_missing_file_and_a_broken_file(db_session, tmp_path):
    doc = await make_document(db_session, is_public=True)
    other = await make_document(db_session, is_public=True)
    version = await record(db_session, doc, pets_spec(), tmp_path)
    foreign = await record(db_session, other, pets_spec(), tmp_path)
    settings = docs_settings(tmp_path)
    base = f"/api/api-docs/{doc.id}/versions"

    not_this_documents = await request(db_session, "GET", f"{base}/{foreign.id}/outline", settings=settings)
    stored = tmp_path / version.storage_path
    stored.write_bytes(b"this: is: not: a spec: [")
    broken = await request(db_session, "GET", f"{base}/{version.id}/outline", settings=settings)
    stored.unlink()
    gone = await request(db_session, "GET", f"{base}/{version.id}/outline", settings=settings)

    assert (not_this_documents.status_code, broken.status_code, gone.status_code) == (404, 422, 404)
