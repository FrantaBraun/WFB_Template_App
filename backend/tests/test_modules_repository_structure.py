# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The repository module's repositories, tables and attributes (records:
test_modules_repository_records.py) - and that every route of the module is
closed to anonymous callers and to anyone but the owner.

The throwaway app, the users and the helpers are in repository_support.py."""

import uuid
from typing import get_args

import pytest
from sqlalchemy import select

from app.modules.repository import logic, manifest
from app.modules.repository.models import Attribute, Record, RepositoryTable
from app.modules.repository.router import router as repository_router
from app.modules.repository.schemas import ColorScheme
from tests.repository_support import (  # noqa: F401  (the fixtures are used by name)
    BASE,
    _overrides,
    alice,
    attribute as _attribute,
    add_record as _add_record,
    bob,
    client,
    create_repository as _repo,
    create_table as _table,
    make_user,
    put_attributes as _put_attributes,
    repository_app as _repository_app,
    set_limits as _limits,
)


def test_manifest_key_matches_its_folder():
    assert manifest.key == "repository"
    assert manifest.router is repository_router


def test_the_colour_schemes_of_the_schema_match_the_logic():
    assert get_args(ColorScheme) == logic.COLOR_SCHEMES


# --- Everyone is signed in, and everyone sees only their own -----------------------

# One valid request per route (path parameters are filled in): a new route that
# is not listed here fails test_every_route_is_covered, so it cannot escape
# the two checks below.
_STATISTIC = {"name": "Count", "group_by": [{"field": "created_on", "bucket": "month"}], "aggregation": {"fn": "count"}}
_BODIES: dict[tuple[str, str], dict | None] = {
    ("get", "/repositories"): None,
    ("post", "/repositories"): {"name": "Another"},
    ("get", "/slug-check"): None,
    ("get", "/repositories/{repository_slug}"): None,
    ("patch", "/repositories/{repository_slug}"): {"name": "Renamed"},
    ("delete", "/repositories/{repository_slug}"): None,
    ("get", "/repositories/{repository_slug}/tables"): None,
    ("post", "/repositories/{repository_slug}/tables"): {"name": "Another table"},
    ("put", "/repositories/{repository_slug}/table-order"): {"ids": []},
    ("get", "/repositories/{repository_slug}/tables/{table_slug}"): None,
    ("patch", "/repositories/{repository_slug}/tables/{table_slug}"): {"name": "Renamed"},
    ("put", "/repositories/{repository_slug}/tables/{table_slug}/attributes"): {"attributes": []},
    ("delete", "/repositories/{repository_slug}/tables/{table_slug}"): None,
    ("post", "/repositories/{repository_slug}/tables/{table_slug}/records-query"): {},
    ("get", "/repositories/{repository_slug}/tables/{table_slug}/records-search"): None,
    ("post", "/repositories/{repository_slug}/tables/{table_slug}/records"): {"name": "Another record"},
    ("get", "/repositories/{repository_slug}/tables/{table_slug}/records/{record_slug}"): None,
    ("patch", "/repositories/{repository_slug}/tables/{table_slug}/records/{record_slug}"): {"name": "Renamed"},
    ("delete", "/repositories/{repository_slug}/tables/{table_slug}/records/{record_slug}"): None,
    ("post", "/repositories/{repository_slug}/tables/{table_slug}/records/{record_slug}/restore"): None,
    ("delete", "/repositories/{repository_slug}/tables/{table_slug}/records/{record_slug}/permanent"): None,
    ("get", "/repositories/{repository_slug}/tables/{table_slug}/filters"): None,
    ("post", "/repositories/{repository_slug}/tables/{table_slug}/filters"): {"name": "Another filter"},
    ("put", "/repositories/{repository_slug}/tables/{table_slug}/filters-order"): {"ids": []},
    ("put", "/repositories/{repository_slug}/tables/{table_slug}/filters/{filter_id}"): {"name": "Renamed"},
    ("delete", "/repositories/{repository_slug}/tables/{table_slug}/filters/{filter_id}"): None,
    ("get", "/repositories/{repository_slug}/tables/{table_slug}/statistics"): None,
    ("post", "/repositories/{repository_slug}/tables/{table_slug}/statistics"): _STATISTIC,
    ("put", "/repositories/{repository_slug}/tables/{table_slug}/statistics-order"): {"ids": []},
    ("post", "/repositories/{repository_slug}/tables/{table_slug}/statistics-preview"): _STATISTIC,
    ("get", "/repositories/{repository_slug}/tables/{table_slug}/statistics-results"): None,
    ("put", "/repositories/{repository_slug}/tables/{table_slug}/statistics/{statistic_id}"): _STATISTIC,
    ("delete", "/repositories/{repository_slug}/tables/{table_slug}/statistics/{statistic_id}"): None,
    ("get", "/repositories/{repository_slug}/tables/{table_slug}/statistics/{statistic_id}/result"): None,
    ("post", "/images"): None,
    ("post", "/images/import-url"): {"url": "https://example.com/a.png"},
    ("get", "/images/{image_id}"): None,
}


def _route_table() -> list[tuple[str, str]]:
    # FastAPI keeps include_router() lazy, so router.routes does not list the
    # included sub-routers' routes - the OpenAPI schema does.
    paths = _repository_app.openapi()["paths"]
    return [
        (method, path.removeprefix(BASE))
        for path, operations in paths.items()
        for method in operations
        if method in ("get", "post", "put", "patch", "delete")
    ]


def test_every_route_is_covered():
    assert sorted(_route_table()) == sorted(_BODIES)


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


def _request_for(method: str, template: str, repository: dict, table: dict, record_slug: str = "any", image_id: str | None = None):
    path = (
        template.replace("{repository_slug}", repository["slug"])
        .replace("{table_slug}", table["slug"])
        .replace("{record_slug}", record_slug)
        .replace("{image_id}", image_id or str(uuid.uuid4()))
        .replace("{filter_id}", str(uuid.uuid4()))
        .replace("{statistic_id}", str(uuid.uuid4()))
    )
    params = None
    if template == "/slug-check":
        params = {"scope": "table", "slug": "free", "repository": repository["slug"]}
    if method == "delete" and "/records/" not in template:
        params = {"confirm_name": table["name"] if "{table_slug}" in template else repository["name"]}
    return f"{BASE}{path}", _BODIES[(method, template)], params


# Scoped to the caller by construction: they list or create the caller's OWN
# repositories and images.
_OWN = {("get", "/repositories"), ("post", "/repositories"), ("post", "/images"), ("post", "/images/import-url")}


@pytest.mark.parametrize(("method", "template"), sorted(_BODIES))
async def test_anonymous_requests_are_rejected_on_every_route(client, method, template):
    url, body, params = _request_for(method, template, {"slug": "any", "name": "any"}, {"slug": "any", "name": "any"})

    resp = await client.request(method, url, json=body, params=params)

    assert resp.status_code in (401, 403)


@pytest.mark.parametrize(("method", "template"), sorted(set(_BODIES) - _OWN))
async def test_someone_elses_data_answers_404_on_every_route(client, alice, bob, method, template):
    """Alice's repository, table, record and image exist; Bob asks for them by their real names."""
    repo = await _repo(client, alice, name="Alice's")
    table = await _table(client, alice, repo["slug"])
    record = (
        await client.post(f"{BASE}/repositories/{repo['slug']}/tables/{table['slug']}/records", json={"name": "Dune"}, headers=alice)
    ).json()
    image = (await client.post(f"{BASE}/images", files={"file": ("a.png", PNG, "image/png")}, headers=alice)).json()
    url, body, params = _request_for(method, template, repo, table, record["slug"], image["id"])

    resp = await client.request(method, url, json=body, params=params, headers=bob)

    assert resp.status_code == 404, resp.text
    # ... and nothing of Alice's changed.
    after = (await client.get(f"{BASE}/repositories/{repo['slug']}", headers=alice)).json()
    assert after["name"] == "Alice's"
    assert [t["slug"] for t in after["tables"]] == [table["slug"]]
    kept = (await client.get(f"{BASE}/repositories/{repo['slug']}/tables/{table['slug']}/records/{record['slug']}", headers=alice)).json()
    assert (kept["name"], kept["deleted_on"]) == ("Dune", None)
    assert (await client.get(f"{BASE}/images/{image['id']}", headers=alice)).status_code == 200


async def test_a_users_list_never_contains_someone_elses_repositories(client, alice, bob):
    await _repo(client, alice, name="Alice's")

    assert (await client.get(f"{BASE}/repositories", headers=bob)).json() == []


# --- Repositories ---------------------------------------------------------------------


async def test_create_repository_makes_the_slug_from_the_name(client, alice):
    created = await _repo(client, alice, name="Moje knihovna", description="  Všechny knihy  ")

    assert created["slug"] == "moje-knihovna"
    assert created["name"] == "Moje knihovna"
    assert created["description"] == "Všechny knihy"
    assert created["color_scheme"] == "blue"
    assert created["table_count"] == 0
    assert created["record_count"] == 0
    assert created["tables"] == []
    uuid.UUID(created["id"])


async def test_a_second_repository_with_the_same_name_gets_a_numbered_slug(client, alice):
    first = await _repo(client, alice, name="Knihy")
    second = await _repo(client, alice, name="Knihy")
    third = await _repo(client, alice, name="Knihy")

    assert [first["slug"], second["slug"], third["slug"]] == ["knihy", "knihy-2", "knihy-3"]


async def test_a_given_slug_is_kept(client, alice):
    created = await _repo(client, alice, name="Knihy", slug="my-books")

    assert created["slug"] == "my-books"


async def test_a_given_slug_that_is_taken_is_a_409(client, alice):
    await _repo(client, alice, slug="knihy")

    resp = await client.post(f"{BASE}/repositories", json={"name": "Other", "slug": "knihy"}, headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"errors": {"slug": "taken"}}


@pytest.mark.parametrize(("slug", "code"), [("Bad Slug", "invalid"), ("-x", "invalid"), ("a" * 81, "invalid"), ("new", "reserved"), ("tables", "reserved")])
async def test_a_given_slug_that_is_invalid_or_reserved_is_a_422(client, alice, slug, code):
    resp = await client.post(f"{BASE}/repositories", json={"name": "Other", "slug": slug}, headers=alice)

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {"slug": code}}


async def test_the_same_slug_can_be_used_by_two_users(client, alice, bob):
    await _repo(client, alice, slug="knihy")

    assert (await _repo(client, bob, slug="knihy"))["slug"] == "knihy"


async def test_a_name_made_of_reserved_words_still_gets_a_usable_slug(client, alice):
    assert (await _repo(client, alice, name="New"))["slug"] == "new-2"


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "   "}, {"name": "x" * 121}, {"name": "x", "color_scheme": "purple"}, {"name": "x", "other": 1}])
async def test_invalid_repository_bodies_are_422(client, alice, body):
    resp = await client.post(f"{BASE}/repositories", json=body, headers=alice)

    assert resp.status_code == 422


async def test_every_colour_scheme_can_be_chosen(client, alice):
    for scheme in logic.COLOR_SCHEMES:
        assert (await _repo(client, alice, name=f"R {scheme}", color_scheme=scheme))["color_scheme"] == scheme


async def test_list_repositories_are_the_callers_own_by_name_with_counts(client, db_session, alice, bob):
    zeta = await _repo(client, alice, name="zeta")
    alpha = await _repo(client, alice, name="Alpha")
    await _repo(client, bob, name="Bobs")
    table_a = await _table(client, alice, alpha["slug"], name="A1")
    await _table(client, alice, alpha["slug"], name="A2")
    await _add_record(db_session, table_a["id"], "one")
    await _add_record(db_session, table_a["id"], "two")
    await _add_record(db_session, table_a["id"], "gone", deleted=True)

    listed = (await client.get(f"{BASE}/repositories", headers=alice)).json()

    assert [r["slug"] for r in listed] == [alpha["slug"], zeta["slug"]]
    assert (listed[0]["table_count"], listed[0]["record_count"]) == (2, 2)
    assert (listed[1]["table_count"], listed[1]["record_count"]) == (0, 0)


async def test_get_repository_lists_its_tables_with_record_counts(client, db_session, alice):
    repo = await _repo(client, alice)
    novels = await _table(client, alice, repo["slug"], name="Novels")
    await _table(client, alice, repo["slug"], name="Authors", view_type="grid")
    await _add_record(db_session, novels["id"], "Dune")

    detail = (await client.get(f"{BASE}/repositories/{repo['slug']}", headers=alice)).json()

    assert [(t["slug"], t["view_type"], t["record_count"]) for t in detail["tables"]] == [("novels", "table", 1), ("authors", "grid", 0)]
    assert (detail["table_count"], detail["record_count"]) == (2, 1)


async def test_an_unknown_repository_is_404(client, alice):
    assert (await client.get(f"{BASE}/repositories/nope", headers=alice)).status_code == 404


async def test_update_repository(client, alice):
    repo = await _repo(client, alice, name="Knihy", description="old")

    resp = await client.patch(
        f"{BASE}/repositories/{repo['slug']}",
        json={"name": "Books", "description": "new", "color_scheme": "teal", "slug": "books"},
        headers=alice,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert (body["name"], body["description"], body["color_scheme"], body["slug"]) == ("Books", "new", "teal", "books")
    assert (await client.get(f"{BASE}/repositories/books", headers=alice)).status_code == 200
    assert (await client.get(f"{BASE}/repositories/knihy", headers=alice)).status_code == 404


async def test_renaming_a_repository_leaves_its_slug_alone(client, alice):
    repo = await _repo(client, alice, name="Knihy")

    body = (await client.patch(f"{BASE}/repositories/{repo['slug']}", json={"name": "Books"}, headers=alice)).json()

    assert body["slug"] == "knihy"


async def test_updating_with_nothing_changes_nothing(client, alice):
    repo = await _repo(client, alice, name="Knihy", description="d", color_scheme="red")

    body = (await client.patch(f"{BASE}/repositories/{repo['slug']}", json={}, headers=alice)).json()

    assert (body["name"], body["description"], body["color_scheme"], body["slug"]) == ("Knihy", "d", "red", "knihy")


async def test_a_repository_can_keep_its_own_slug_on_update(client, alice):
    repo = await _repo(client, alice, name="Knihy")

    resp = await client.patch(f"{BASE}/repositories/knihy", json={"slug": "knihy", "name": "Books"}, headers=alice)

    assert resp.status_code == 200


async def test_changing_to_a_slug_of_another_repository_is_a_409(client, alice):
    await _repo(client, alice, name="Knihy")
    other = await _repo(client, alice, name="Filmy")

    resp = await client.patch(f"{BASE}/repositories/{other['slug']}", json={"slug": "knihy"}, headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"errors": {"slug": "taken"}}


async def test_changing_to_an_invalid_slug_is_a_422_and_changes_nothing(client, alice):
    repo = await _repo(client, alice, name="Knihy")

    resp = await client.patch(f"{BASE}/repositories/knihy", json={"slug": "new", "name": "Books"}, headers=alice)

    assert resp.status_code == 422
    assert (await client.get(f"{BASE}/repositories/{repo['slug']}", headers=alice)).json()["name"] == "Knihy"


async def test_deleting_a_repository_needs_its_name_and_removes_everything_in_it(client, db_session, alice):
    repo = await _repo(client, alice, name="Knihy")
    table = await _table(client, alice, repo["slug"])
    await _put_attributes(client, alice, repo["slug"], table["slug"], [_attribute()])
    record_id = (await _add_record(db_session, table["id"])).id

    wrong = await client.delete(f"{BASE}/repositories/knihy", params={"confirm_name": "knihy"}, headers=alice)
    missing = await client.delete(f"{BASE}/repositories/knihy", headers=alice)
    assert wrong.status_code == missing.status_code == 422
    assert wrong.json()["detail"] == {"errors": {"confirm_name": "mismatch"}}
    assert (await client.get(f"{BASE}/repositories/knihy", headers=alice)).status_code == 200

    done = await client.delete(f"{BASE}/repositories/knihy", params={"confirm_name": "Knihy"}, headers=alice)

    assert done.status_code == 204
    assert (await client.get(f"{BASE}/repositories/knihy", headers=alice)).status_code == 404
    db_session.expire_all()
    assert await db_session.scalar(select(Record).where(Record.id == record_id)) is None
    assert await db_session.scalar(select(RepositoryTable).where(RepositoryTable.id == uuid.UUID(table["id"]))) is None
    assert (await db_session.scalars(select(Attribute).where(Attribute.table_id == uuid.UUID(table["id"])))).all() == []


async def test_the_number_of_repositories_per_user_is_limited(client, alice, bob):
    _limits(max_repositories_per_user=2)
    await _repo(client, alice, name="One")
    await _repo(client, alice, name="Two")

    resp = await client.post(f"{BASE}/repositories", json={"name": "Three"}, headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"limit": "max_repositories_per_user", "max": 2}
    assert (await client.post(f"{BASE}/repositories", json={"name": "Bobs"}, headers=bob)).status_code == 201


# --- The live slug check -------------------------------------------------------------


async def _check(client, headers, **params):
    resp = await client.get(f"{BASE}/slug-check", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_slug_check_for_repositories(client, alice, bob):
    await _repo(client, alice, slug="knihy")
    await _repo(client, bob, slug="bobs")

    assert await _check(client, alice, scope="repository", slug="filmy") == {"slug": "filmy", "available": True, "reason": None, "suggestion": None}
    taken = await _check(client, alice, scope="repository", slug="knihy")
    assert (taken["available"], taken["reason"], taken["suggestion"]) == (False, "taken", "knihy-2")
    assert (await _check(client, alice, scope="repository", slug="bobs"))["available"] is True  # Bob's is not Alice's business
    assert (await _check(client, alice, scope="repository", slug="Bad Slug"))["reason"] == "invalid"
    assert (await _check(client, alice, scope="repository", slug="new"))["reason"] == "reserved"


async def test_slug_check_treats_the_slug_being_edited_as_free(client, alice):
    await _repo(client, alice, slug="knihy")

    assert (await _check(client, alice, scope="repository", slug="knihy", exclude="knihy"))["available"] is True


async def test_slug_check_for_tables_is_per_repository(client, alice):
    one = await _repo(client, alice, name="One")
    two = await _repo(client, alice, name="Two")
    await _table(client, alice, one["slug"], name="Novels")

    assert (await _check(client, alice, scope="table", repository=one["slug"], slug="novels"))["reason"] == "taken"
    assert (await _check(client, alice, scope="table", repository=two["slug"], slug="novels"))["available"] is True


async def test_slug_check_for_records_counts_deleted_ones(client, db_session, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    record = await _add_record(db_session, table["id"], "Dune", deleted=True)

    result = await _check(client, alice, scope="record", repository=repo["slug"], table=table["slug"], slug=record.slug)

    assert (result["available"], result["reason"]) == (False, "taken")


async def test_slug_check_needs_the_parent_slugs(client, alice):
    repo = await _repo(client, alice)

    assert (await client.get(f"{BASE}/slug-check", params={"scope": "table", "slug": "x"}, headers=alice)).status_code == 422
    assert (await client.get(f"{BASE}/slug-check", params={"scope": "record", "slug": "x", "repository": repo["slug"]}, headers=alice)).status_code == 422
    assert (await client.get(f"{BASE}/slug-check", params={"scope": "table", "slug": "x", "repository": "nope"}, headers=alice)).status_code == 404
    assert (await client.get(f"{BASE}/slug-check", params={"scope": "other", "slug": "x"}, headers=alice)).status_code == 422


# --- Tables ----------------------------------------------------------------------------


async def test_create_table(client, alice):
    repo = await _repo(client, alice)

    created = await _table(client, alice, repo["slug"], name="Příběhy", description="  Short  ")

    assert (created["slug"], created["name"], created["description"]) == ("pribehy", "Příběhy", "Short")
    assert (created["view_type"], created["position"], created["record_count"], created["attributes"]) == ("table", 0, 0, [])


async def test_tables_get_increasing_positions_and_slugs_are_unique_in_the_repository(client, alice):
    one = await _repo(client, alice, name="One")
    two = await _repo(client, alice, name="Two")

    first = await _table(client, alice, one["slug"], name="Novels")
    second = await _table(client, alice, one["slug"], name="Novels")
    elsewhere = await _table(client, alice, two["slug"], name="Novels")

    assert (first["slug"], second["slug"], elsewhere["slug"]) == ("novels", "novels-2", "novels")
    assert (first["position"], second["position"], elsewhere["position"]) == (0, 1, 0)


async def test_a_table_slug_given_twice_is_a_409(client, alice):
    repo = await _repo(client, alice)
    await _table(client, alice, repo["slug"], slug="novels")

    resp = await client.post(f"{BASE}/repositories/{repo['slug']}/tables", json={"name": "x", "slug": "novels"}, headers=alice)

    assert resp.status_code == 409


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "x", "view_type": "list"}, {"name": "x", "other": 1}])
async def test_invalid_table_bodies_are_422(client, alice, body):
    repo = await _repo(client, alice)

    resp = await client.post(f"{BASE}/repositories/{repo['slug']}/tables", json=body, headers=alice)

    assert resp.status_code == 422


async def test_list_tables_follows_the_order(client, alice):
    repo = await _repo(client, alice)
    for name in ("C", "A", "B"):
        await _table(client, alice, repo["slug"], name=name)

    listed = (await client.get(f"{BASE}/repositories/{repo['slug']}/tables", headers=alice)).json()

    assert [t["name"] for t in listed] == ["C", "A", "B"]


async def test_reorder_tables(client, alice):
    repo = await _repo(client, alice)
    tables = [await _table(client, alice, repo["slug"], name=name) for name in ("C", "A", "B")]
    by_name = {t["name"]: t["id"] for t in tables}

    resp = await client.put(
        f"{BASE}/repositories/{repo['slug']}/table-order",
        json={"ids": [by_name["A"], by_name["B"], by_name["C"]]},
        headers=alice,
    )

    assert resp.status_code == 204
    listed = (await client.get(f"{BASE}/repositories/{repo['slug']}/tables", headers=alice)).json()
    assert [t["name"] for t in listed] == ["A", "B", "C"]


async def test_reorder_must_list_every_table_exactly_once(client, alice):
    repo = await _repo(client, alice)
    first = await _table(client, alice, repo["slug"], name="A")
    second = await _table(client, alice, repo["slug"], name="B")
    url = f"{BASE}/repositories/{repo['slug']}/table-order"

    for ids in ([first["id"]], [first["id"], first["id"]], [first["id"], second["id"], str(uuid.uuid4())], []):
        resp = await client.put(url, json={"ids": ids}, headers=alice)
        assert resp.status_code == 422, ids
        assert resp.json()["detail"] == {"errors": {"ids": "must_list_every_table_once"}}


async def test_get_table_and_update_table(client, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"], name="Novels")
    url = f"{BASE}/repositories/{repo['slug']}/tables/{table['slug']}"

    updated = (
        await client.patch(
            url, json={"name": "Books", "description": "d", "view_type": "grid", "slug": "books"}, headers=alice
        )
    ).json()

    assert (updated["name"], updated["description"], updated["view_type"], updated["slug"]) == ("Books", "d", "grid", "books")
    assert (await client.get(url, headers=alice)).status_code == 404
    assert (await client.get(f"{BASE}/repositories/{repo['slug']}/tables/books", headers=alice)).status_code == 200


async def test_a_table_slug_cannot_move_onto_another_tables(client, alice):
    repo = await _repo(client, alice)
    await _table(client, alice, repo["slug"], name="Novels")
    other = await _table(client, alice, repo["slug"], name="Authors")

    resp = await client.patch(
        f"{BASE}/repositories/{repo['slug']}/tables/{other['slug']}", json={"slug": "novels"}, headers=alice
    )

    assert resp.status_code == 409


async def test_an_unknown_table_is_404(client, alice):
    repo = await _repo(client, alice)

    assert (await client.get(f"{BASE}/repositories/{repo['slug']}/tables/nope", headers=alice)).status_code == 404


async def test_the_number_of_tables_per_repository_is_limited(client, alice):
    _limits(max_tables_per_repository=1)
    repo = await _repo(client, alice)
    await _table(client, alice, repo["slug"], name="One")

    resp = await client.post(f"{BASE}/repositories/{repo['slug']}/tables", json={"name": "Two"}, headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"limit": "max_tables_per_repository", "max": 1}


async def test_deleting_a_table_needs_its_name_and_removes_its_records(client, db_session, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"], name="Novels")
    record_id = (await _add_record(db_session, table["id"])).id
    url = f"{BASE}/repositories/{repo['slug']}/tables/{table['slug']}"

    wrong = await client.delete(url, params={"confirm_name": "novels"}, headers=alice)
    assert wrong.status_code == 422
    assert wrong.json()["detail"] == {"errors": {"confirm_name": "mismatch"}}
    assert (await client.get(url, headers=alice)).status_code == 200

    assert (await client.delete(url, params={"confirm_name": "Novels"}, headers=alice)).status_code == 204

    assert (await client.get(url, headers=alice)).status_code == 404
    db_session.expire_all()
    assert await db_session.scalar(select(Record).where(Record.id == record_id)) is None


async def test_a_table_that_another_table_refers_to_cannot_be_deleted(client, alice):
    repo = await _repo(client, alice)
    authors = await _table(client, alice, repo["slug"], name="Authors")
    books = await _table(client, alice, repo["slug"], name="Books")
    reference = _attribute("reference", "Author", config={"table_id": authors["id"]})
    listing = _attribute("list", "Co-authors", config={"element_type": "reference", "table_id": authors["id"]})
    assert (await _put_attributes(client, alice, repo["slug"], books["slug"], [reference, listing])).status_code == 200
    url = f"{BASE}/repositories/{repo['slug']}/tables/{authors['slug']}"

    resp = await client.delete(url, params={"confirm_name": "Authors"}, headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {
        "referenced_by": [
            {"table": "Books", "table_slug": "books", "attribute": "Author"},
            {"table": "Books", "table_slug": "books", "attribute": "Co-authors"},
        ]
    }
    assert (await client.get(url, headers=alice)).status_code == 200

    # Once nothing points at it, it goes - and the table that pointed can go too.
    assert (await _put_attributes(client, alice, repo["slug"], books["slug"], [])).status_code == 200
    assert (await client.delete(url, params={"confirm_name": "Authors"}, headers=alice)).status_code == 204


async def test_a_table_that_refers_to_itself_can_be_deleted(client, alice):
    repo = await _repo(client, alice)
    people = await _table(client, alice, repo["slug"], name="People")
    parent = _attribute("reference", "Parent", config={"table_id": people["id"]})
    assert (await _put_attributes(client, alice, repo["slug"], people["slug"], [parent])).status_code == 200

    resp = await client.delete(
        f"{BASE}/repositories/{repo['slug']}/tables/{people['slug']}", params={"confirm_name": "People"}, headers=alice
    )

    assert resp.status_code == 204


# --- Attributes ------------------------------------------------------------------------


async def test_attributes_are_saved_in_order_with_their_settings(client, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    title = _attribute("text", "Title", description="  The title ", required=True, show_in_list=True)
    pages = _attribute("number", "Pages")
    tags = _attribute("list", "Tags", config={"element_type": "text"})

    resp = await _put_attributes(client, alice, repo["slug"], table["slug"], [title, pages, tags])

    assert resp.status_code == 200
    saved = resp.json()["attributes"]
    assert [a["name"] for a in saved] == ["Title", "Pages", "Tags"]
    assert [a["position"] for a in saved] == [0, 1, 2]
    assert saved[0] == {
        "id": title["id"],
        "name": "Title",
        "description": "The title",
        "type": "text",
        "required": True,
        "show_in_list": True,
        "config": {},
        "position": 0,
    }
    assert saved[2]["config"] == {"element_type": "text"}
    got = (await client.get(f"{BASE}/repositories/{repo['slug']}/tables/{table['slug']}", headers=alice)).json()
    assert got["attributes"] == saved


async def test_saved_attributes_can_be_renamed_reordered_and_changed_without_losing_their_id(client, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    first = _attribute("text", "First")
    second = _attribute("number", "Second")
    await _put_attributes(client, alice, repo["slug"], table["slug"], [first, second])

    second = {**second, "name": "Renamed", "required": True, "show_in_list": True}
    resp = await _put_attributes(client, alice, repo["slug"], table["slug"], [second, first])

    saved = resp.json()["attributes"]
    assert [(a["id"], a["name"], a["required"], a["show_in_list"]) for a in saved] == [
        (second["id"], "Renamed", True, True),
        (first["id"], "First", False, False),
    ]


async def test_attribute_names_must_be_unique_ignoring_case_and_ids_too(client, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    one = _attribute("text", "Title")

    same_name = await _put_attributes(client, alice, repo["slug"], table["slug"], [one, _attribute("text", "title")])
    same_id = await _put_attributes(client, alice, repo["slug"], table["slug"], [one, {**_attribute("text", "Other"), "id": one["id"]}])

    assert same_name.status_code == same_id.status_code == 422


@pytest.mark.parametrize(
    "attribute",
    [
        {"type": "reference"},
        {"type": "reference", "config": {"table_id": "nope"}},
        {"type": "list"},
        {"type": "list", "config": {"element_type": "list"}},
        {"type": "map", "config": {"element_type": "reference"}},
        {"type": "text", "config": {"x": 1}},
        {"type": "boolean", "required": True},
        {"type": "blob"},
        {"type": "text", "name": ""},
    ],
)
async def test_invalid_attributes_are_422(client, alice, attribute):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])

    resp = await _put_attributes(client, alice, repo["slug"], table["slug"], [_attribute(**{"name": "A", **attribute})])

    assert resp.status_code == 422


async def test_a_table_can_have_at_most_the_configured_number_of_attributes(client, alice):
    _limits(max_attributes_per_table=2)
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])

    fine = await _put_attributes(client, alice, repo["slug"], table["slug"], [_attribute(name="A"), _attribute(name="B")])
    too_many = await _put_attributes(client, alice, repo["slug"], table["slug"], [_attribute(name=n) for n in "ABC"])

    assert fine.status_code == 200
    assert too_many.status_code == 409
    assert too_many.json()["detail"] == {"limit": "max_attributes_per_table", "max": 2}


async def test_the_type_of_a_saved_attribute_cannot_change(client, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    attribute = _attribute("text", "Title")
    await _put_attributes(client, alice, repo["slug"], table["slug"], [attribute])

    resp = await _put_attributes(client, alice, repo["slug"], table["slug"], [{**attribute, "type": "number"}])

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {attribute["id"]: "type_immutable"}}


async def test_what_a_saved_reference_points_at_cannot_change(client, alice):
    repo = await _repo(client, alice)
    authors = await _table(client, alice, repo["slug"], name="Authors")
    publishers = await _table(client, alice, repo["slug"], name="Publishers")
    books = await _table(client, alice, repo["slug"], name="Books")
    reference = _attribute("reference", "Author", config={"table_id": authors["id"]})
    listing = _attribute("list", "Tags", config={"element_type": "text"})
    await _put_attributes(client, alice, repo["slug"], books["slug"], [reference, listing])

    moved = await _put_attributes(
        client, alice, repo["slug"], books["slug"], [{**reference, "config": {"table_id": publishers["id"]}}, listing]
    )
    element = await _put_attributes(
        client, alice, repo["slug"], books["slug"], [reference, {**listing, "config": {"element_type": "number"}}]
    )

    assert moved.status_code == element.status_code == 422
    assert moved.json()["detail"] == {"errors": {reference["id"]: "config_immutable"}}
    assert element.json()["detail"] == {"errors": {listing["id"]: "config_immutable"}}


async def test_a_reference_can_only_point_into_the_same_repository(client, alice):
    mine = await _repo(client, alice, name="Mine")
    elsewhere = await _repo(client, alice, name="Elsewhere")
    foreign = await _table(client, alice, elsewhere["slug"], name="Foreign")
    books = await _table(client, alice, mine["slug"], name="Books")
    unknown = str(uuid.uuid4())

    for target in (foreign["id"], unknown):
        attribute = _attribute("reference", "Ref", config={"table_id": target})
        resp = await _put_attributes(client, alice, mine["slug"], books["slug"], [attribute])
        assert resp.status_code == 422
        assert resp.json()["detail"] == {"errors": {attribute["id"]: "invalid_table"}}
    listing = _attribute("map", "Refs", config={"element_type": "reference", "table_id": foreign["id"]})
    assert (await _put_attributes(client, alice, mine["slug"], books["slug"], [listing])).status_code == 422


async def test_a_reference_to_someone_elses_table_is_refused_too(client, alice, bob):
    theirs = await _repo(client, bob, name="Theirs")
    foreign = await _table(client, bob, theirs["slug"], name="Foreign")
    mine = await _repo(client, alice, name="Mine")
    books = await _table(client, alice, mine["slug"], name="Books")

    resp = await _put_attributes(
        client, alice, mine["slug"], books["slug"], [_attribute("reference", "Ref", config={"table_id": foreign["id"]})]
    )

    assert resp.status_code == 422


async def test_an_attribute_id_cannot_be_shared_between_tables(client, alice):
    repo = await _repo(client, alice)
    one = await _table(client, alice, repo["slug"], name="One")
    two = await _table(client, alice, repo["slug"], name="Two")
    attribute = _attribute("text", "Title")
    await _put_attributes(client, alice, repo["slug"], one["slug"], [attribute])

    resp = await _put_attributes(client, alice, repo["slug"], two["slug"], [attribute])

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {attribute["id"]: "id_in_use"}}


async def test_removing_an_attribute_nobody_has_a_value_for_just_removes_it(client, db_session, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    keep = _attribute("text", "Keep")
    drop = _attribute("text", "Drop")
    await _put_attributes(client, alice, repo["slug"], table["slug"], [keep, drop])
    await _add_record(db_session, table["id"], data={keep["id"]: "x"})

    resp = await _put_attributes(client, alice, repo["slug"], table["slug"], [keep])

    assert resp.status_code == 200
    assert [a["name"] for a in resp.json()["attributes"]] == ["Keep"]


async def test_removing_an_attribute_with_values_asks_for_confirmation_and_then_purges_them(client, db_session, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    keep = _attribute("text", "Keep")
    drop = _attribute("number", "Drop")
    await _put_attributes(client, alice, repo["slug"], table["slug"], [keep, drop])
    first = await _add_record(db_session, table["id"], "one", data={keep["id"]: "a", drop["id"]: 1})
    second = await _add_record(db_session, table["id"], "two", data={drop["id"]: 2})
    third = await _add_record(db_session, table["id"], "three", data={keep["id"]: "c"})

    refused = await _put_attributes(client, alice, repo["slug"], table["slug"], [keep])

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"purge_required": [{"id": drop["id"], "name": "Drop", "record_count": 2}]}
    assert (await client.get(f"{BASE}/repositories/{repo['slug']}/tables/{table['slug']}", headers=alice)).json()["attributes"][1]["name"] == "Drop"

    done = await _put_attributes(client, alice, repo["slug"], table["slug"], [keep], confirm_purge="true")

    assert done.status_code == 200
    assert [a["name"] for a in done.json()["attributes"]] == ["Keep"]
    db_session.expire_all()
    stored = {r.id: r.data for r in (await db_session.scalars(select(Record).where(Record.table_id == uuid.UUID(table["id"])))).all()}
    assert stored == {first.id: {keep["id"]: "a"}, second.id: {}, third.id: {keep["id"]: "c"}}


async def test_values_of_a_removed_attribute_do_not_come_back_when_its_id_is_reused_in_the_same_table(client, db_session, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])
    attribute = _attribute("text", "Note")
    await _put_attributes(client, alice, repo["slug"], table["slug"], [attribute])
    record_id = (await _add_record(db_session, table["id"], data={attribute["id"]: "secret"})).id

    await _put_attributes(client, alice, repo["slug"], table["slug"], [], confirm_purge="true")
    await _put_attributes(client, alice, repo["slug"], table["slug"], [attribute])

    db_session.expire_all()
    assert (await db_session.get(Record, record_id)).data == {}


async def test_more_than_the_request_cap_of_attributes_is_a_422(client, alice):
    repo = await _repo(client, alice)
    table = await _table(client, alice, repo["slug"])

    resp = await _put_attributes(client, alice, repo["slug"], table["slug"], [_attribute(name=f"A{i}") for i in range(201)])

    assert resp.status_code == 422


async def test_a_table_can_refer_to_itself_with_a_reference_and_with_a_list_of_references(client, alice):
    repo = await _repo(client, alice)
    people = await _table(client, alice, repo["slug"], name="People")
    parent = _attribute("reference", "Parent", config={"table_id": people["id"]})
    friends = _attribute("list", "Friends", config={"element_type": "reference", "table_id": people["id"]})

    resp = await _put_attributes(client, alice, repo["slug"], people["slug"], [parent, friends])

    assert resp.status_code == 200
    assert resp.json()["attributes"][0]["config"] == {"table_id": people["id"]}
