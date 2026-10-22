# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Records of the repository module: creating and editing them with every
kind of value, references, soft delete / restore / permanent delete, and
listing with filters, sorting and paging (the SQL against the real database).
Images are in test_modules_repository_images.py, the isolation of one user's
data from another's in test_modules_repository_structure.py."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.repository.models import Record
from tests.repository_support import (  # noqa: F401  (the fixtures are used by name)
    BASE,
    _overrides,
    add_record,
    alice,
    attribute,
    bob,
    client,
    create_repository,
    create_table,
    make_table,
    make_user,
    post_record,
    put_attributes,
    query,
    records_url,
    set_limits,
)


async def _get(client, headers, repository, table, slug):
    return await client.get(records_url(repository, table, f"/{slug}"), headers=headers)


async def _books(client, headers):
    """A table with one attribute of each kind of value."""
    attrs = {
        "title": attribute("text", "Title", required=True, show_in_list=True),
        "pages": attribute("number", "Pages", show_in_list=True),
        "read": attribute("boolean", "Read"),
        "published": attribute("date", "Published"),
        "added": attribute("datetime", "Added"),
        "tags": attribute("list", "Tags", config={"element_type": "text"}),
        "sizes": attribute("map", "Sizes", config={"element_type": "number"}),
    }
    repository, table, _ = await make_table(client, headers, *attrs.values())
    return repository, table, {key: value["id"] for key, value in attrs.items()}


# --- Creating -------------------------------------------------------------------------


async def test_create_a_record_with_every_kind_of_value(client, alice):
    repository, table, ids = await _books(client, alice)

    created = await post_record(
        client,
        alice,
        repository,
        table,
        name="  Dune  ",
        data={
            ids["title"]: "  Dune  ",
            ids["pages"]: 412,
            ids["read"]: False,
            ids["published"]: "1965-08-01",
            ids["added"]: "2026-10-22T08:30",
            ids["tags"]: ["sci-fi", "classic"],
            ids["sizes"]: {" width ": 13.5, "height": 20},
        },
    )

    assert created["name"] == "Dune"
    assert created["slug"] == "dune"
    assert created["deleted_on"] is None
    assert created["created_on"]
    assert created["refs"] == {}
    assert created["data"] == {
        ids["title"]: "Dune",
        ids["pages"]: 412,
        ids["read"]: False,
        ids["published"]: "1965-08-01",
        ids["added"]: "2026-10-22T08:30",
        ids["tags"]: {"0": "sci-fi", "1": "classic"},
        ids["sizes"]: {"width": 13.5, "height": 20},
    }
    assert (await _get(client, alice, repository, table, "dune")).json() == created


async def test_a_table_without_attributes_has_records_with_just_a_name(client, alice):
    repository, table, _ = await make_table(client, alice)

    created = await post_record(client, alice, repository, table, name="Plain")

    assert (created["data"], created["slug"]) == ({}, "plain")


async def test_values_that_are_not_set_are_not_stored(client, alice):
    repository, table, ids = await _books(client, alice)

    created = await post_record(
        client, alice, repository, table, data={ids["title"]: "x", ids["pages"]: None, ids["tags"]: [], ids["sizes"]: {}}
    )

    assert created["data"] == {ids["title"]: "x"}


@pytest.mark.parametrize(
    ("name", "code"),
    [("", "required"), ("   ", "required"), ("a" * 201, "too_long"), ("a\x00b", "invalid_text")],
)
async def test_the_name_is_required_and_bounded(client, alice, name, code):
    repository, table, _ = await make_table(client, alice)

    resp = await client.post(records_url(repository, table), json={"name": name}, headers=alice)

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {"name": code}}


@pytest.mark.parametrize("body", [{}, {"name": 5}, {"name": "x", "other": 1}, {"name": "x", "data": []}, {"name": "x", "slug": 5}])
async def test_a_malformed_body_is_a_422(client, alice, body):
    repository, table, _ = await make_table(client, alice)

    assert (await client.post(records_url(repository, table), json=body, headers=alice)).status_code == 422


async def test_a_required_attribute_must_have_a_value(client, alice):
    repository, table, ids = await _books(client, alice)

    for data in ({}, {ids["title"]: ""}, {ids["title"]: "  "}, {ids["title"]: None}, {ids["pages"]: 5}):
        resp = await client.post(records_url(repository, table), json={"name": "x", "data": data}, headers=alice)
        assert resp.status_code == 422, data
        assert resp.json()["detail"] == {"errors": {ids["title"]: "required"}}


async def test_invalid_values_are_reported_by_attribute_with_a_code(client, alice):
    repository, table, ids = await _books(client, alice)
    data = {
        ids["title"]: 5,
        ids["pages"]: "many",
        ids["read"]: "yes",
        ids["published"]: "2026-02-30",
        ids["added"]: "2026-10-22",
        ids["tags"]: ["fine", "  ", 7],
        ids["sizes"]: {"": 1, "ok": "wide"},
    }

    resp = await client.post(records_url(repository, table), json={"name": "x", "data": data}, headers=alice)

    assert resp.status_code == 422
    assert resp.json()["detail"] == {
        "errors": {
            ids["title"]: "invalid_type",
            ids["pages"]: "invalid_type",
            ids["read"]: "invalid_type",
            ids["published"]: "invalid_date",
            ids["added"]: "invalid_datetime",
            f"{ids['tags']}.1": "required",
            f"{ids['tags']}.2": "invalid_type",
            f"{ids['sizes']}.": "invalid_key",
            f"{ids['sizes']}.ok": "invalid_type",
        }
    }
    assert (await query(client, alice, repository, table)).json()["total"] == 0  # nothing was stored


async def test_a_value_for_an_attribute_the_table_does_not_have_is_refused(client, alice):
    repository, table, ids = await _books(client, alice)
    other_table_attribute = attribute("text", "Elsewhere")

    resp = await client.post(
        records_url(repository, table),
        json={"name": "x", "data": {ids["title"]: "t", other_table_attribute["id"]: "v"}},
        headers=alice,
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {other_table_attribute["id"]: "unknown_attribute"}}


async def test_records_with_the_same_name_get_numbered_slugs(client, alice):
    repository, table, _ = await make_table(client, alice)

    slugs = [(await post_record(client, alice, repository, table, name="Dune"))["slug"] for _ in range(3)]

    assert slugs == ["dune", "dune-2", "dune-3"]


async def test_a_given_slug_is_kept_taken_ones_are_409_and_bad_ones_422(client, alice):
    repository, table, _ = await make_table(client, alice)
    created = await post_record(client, alice, repository, table, name="Dune", slug="my-dune")
    assert created["slug"] == "my-dune"

    taken = await client.post(records_url(repository, table), json={"name": "Other", "slug": "my-dune"}, headers=alice)
    assert (taken.status_code, taken.json()["detail"]) == (409, {"errors": {"slug": "taken"}})
    for slug, code in (("Bad Slug", "invalid"), ("new", "reserved"), ("edit", "reserved")):
        resp = await client.post(records_url(repository, table), json={"name": "Other", "slug": slug}, headers=alice)
        assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"slug": code}})


async def test_the_same_slug_can_be_used_in_two_tables(client, alice):
    repository, table, _ = await make_table(client, alice)
    other = await create_table(client, alice, repository["slug"], name="Films")

    await post_record(client, alice, repository, table, name="Dune")

    assert (await post_record(client, alice, repository, other, name="Dune"))["slug"] == "dune"


async def test_a_deleted_records_slug_is_still_taken(client, alice):
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="Dune")
    await client.delete(records_url(repository, table, "/dune"), headers=alice)

    assert (await post_record(client, alice, repository, table, name="Dune"))["slug"] == "dune-2"


async def test_the_number_of_records_per_table_is_limited_deleted_ones_included(client, alice):
    set_limits(max_records_per_table=2)
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="One")
    await post_record(client, alice, repository, table, name="Two")
    await client.delete(records_url(repository, table, "/one"), headers=alice)

    resp = await client.post(records_url(repository, table), json={"name": "Three"}, headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"limit": "max_records_per_table", "max": 2}


# --- Reading and editing --------------------------------------------------------------------


async def test_an_unknown_record_is_404(client, alice):
    repository, table, _ = await make_table(client, alice)

    assert (await _get(client, alice, repository, table, "nope")).status_code == 404


async def test_editing_the_name_leaves_the_slug_and_the_values_alone(client, alice):
    repository, table, ids = await _books(client, alice)
    created = await post_record(client, alice, repository, table, name="Dune", data={ids["title"]: "Dune", ids["pages"]: 400})

    resp = await client.patch(records_url(repository, table, "/dune"), json={"name": "Dune Messiah"}, headers=alice)

    assert resp.status_code == 200
    body = resp.json()
    assert (body["name"], body["slug"], body["data"], body["id"]) == ("Dune Messiah", "dune", created["data"], created["id"])


async def test_editing_the_data_replaces_all_the_values(client, alice):
    repository, table, ids = await _books(client, alice)
    await post_record(client, alice, repository, table, name="Dune", data={ids["title"]: "Dune", ids["pages"]: 400, ids["tags"]: ["a", "b"]})

    resp = await client.patch(
        records_url(repository, table, "/dune"),
        json={"data": {ids["title"]: "Dune (2nd)", ids["tags"]: ["b"]}},
        headers=alice,
    )

    assert resp.json()["data"] == {ids["title"]: "Dune (2nd)", ids["tags"]: {"0": "b"}}
    assert (await _get(client, alice, repository, table, "dune")).json()["data"] == resp.json()["data"]


async def test_editing_the_data_checks_it_like_creating_does(client, alice):
    repository, table, ids = await _books(client, alice)
    await post_record(client, alice, repository, table, name="Dune", data={ids["title"]: "Dune"})

    resp = await client.patch(records_url(repository, table, "/dune"), json={"data": {ids["pages"]: 5}}, headers=alice)

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {ids["title"]: "required"}}
    assert (await _get(client, alice, repository, table, "dune")).json()["data"] == {ids["title"]: "Dune"}


async def test_a_required_attribute_added_later_is_enforced_only_when_the_values_are_edited(client, alice):
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="Old")
    note = attribute("text", "Note", required=True)
    assert (await put_attributes(client, alice, repository["slug"], table["slug"], [note])).status_code == 200

    renamed = await client.patch(records_url(repository, table, "/old"), json={"name": "Older"}, headers=alice)
    edited = await client.patch(records_url(repository, table, "/old"), json={"data": {}}, headers=alice)

    assert renamed.status_code == 200
    assert (edited.status_code, edited.json()["detail"]) == (422, {"errors": {note["id"]: "required"}})


async def test_editing_the_slug(client, alice):
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="Dune")
    await post_record(client, alice, repository, table, name="Emma")

    moved = await client.patch(records_url(repository, table, "/dune"), json={"slug": "dune-1965"}, headers=alice)
    same = await client.patch(records_url(repository, table, "/emma"), json={"slug": "emma", "name": "Emma!"}, headers=alice)
    taken = await client.patch(records_url(repository, table, "/emma"), json={"slug": "dune-1965"}, headers=alice)
    bad = await client.patch(records_url(repository, table, "/emma"), json={"slug": "new"}, headers=alice)

    assert (moved.status_code, moved.json()["slug"]) == (200, "dune-1965")
    assert same.status_code == 200
    assert (taken.status_code, taken.json()["detail"]) == (409, {"errors": {"slug": "taken"}})
    assert (bad.status_code, bad.json()["detail"]) == (422, {"errors": {"slug": "reserved"}})
    assert (await _get(client, alice, repository, table, "dune")).status_code == 404


async def test_a_record_cannot_be_edited_with_an_unknown_field(client, alice):
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="Dune")

    assert (await client.patch(records_url(repository, table, "/dune"), json={"deleted_on": None}, headers=alice)).status_code == 422


async def test_a_deleted_record_cannot_be_edited(client, alice):
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="Dune")
    await client.delete(records_url(repository, table, "/dune"), headers=alice)

    resp = await client.patch(records_url(repository, table, "/dune"), json={"name": "Dune 2"}, headers=alice)

    assert (resp.status_code, resp.json()["detail"]) == (409, {"errors": {"record": "deleted"}})


async def test_a_list_is_renumbered_when_its_elements_change(client, alice):
    repository, table, ids = await _books(client, alice)
    await post_record(client, alice, repository, table, name="Dune", data={ids["title"]: "Dune", ids["tags"]: ["a", "b", "c"]})

    resp = await client.patch(
        records_url(repository, table, "/dune"),
        json={"data": {ids["title"]: "Dune", ids["tags"]: {"2": "c", "0": "a"}}},
        headers=alice,
    )

    assert resp.json()["data"][ids["tags"]] == {"0": "a", "1": "c"}


# --- Deleting -------------------------------------------------------------------------------------


async def test_delete_marks_the_record_deleted_and_restore_brings_it_back(client, alice):
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="Dune")

    assert (await client.delete(records_url(repository, table, "/dune"), headers=alice)).status_code == 204

    deleted = (await _get(client, alice, repository, table, "dune")).json()
    assert deleted["deleted_on"] is not None
    assert (await query(client, alice, repository, table)).json()["total"] == 0
    assert (await query(client, alice, repository, table, include_deleted=True)).json()["total"] == 1
    assert (await client.get(f"{BASE}/repositories/{repository['slug']}", headers=alice)).json()["record_count"] == 0

    assert (await client.post(records_url(repository, table, "/dune/restore"), headers=alice)).status_code == 204

    assert (await _get(client, alice, repository, table, "dune")).json()["deleted_on"] is None
    assert (await query(client, alice, repository, table)).json()["total"] == 1


async def test_deleting_twice_and_restoring_a_record_that_is_not_deleted_change_nothing(client, alice):
    repository, table, _ = await make_table(client, alice)
    await post_record(client, alice, repository, table, name="Dune")

    assert (await client.post(records_url(repository, table, "/dune/restore"), headers=alice)).status_code == 204
    await client.delete(records_url(repository, table, "/dune"), headers=alice)
    first = (await _get(client, alice, repository, table, "dune")).json()["deleted_on"]
    assert (await client.delete(records_url(repository, table, "/dune"), headers=alice)).status_code == 204

    assert (await _get(client, alice, repository, table, "dune")).json()["deleted_on"] == first


async def test_only_a_deleted_record_can_be_deleted_for_good(client, db_session, alice):
    repository, table, _ = await make_table(client, alice)
    created = await post_record(client, alice, repository, table, name="Dune")

    refused = await client.delete(records_url(repository, table, "/dune/permanent"), headers=alice)
    assert (refused.status_code, refused.json()["detail"]) == (409, {"errors": {"record": "not_deleted"}})

    await client.delete(records_url(repository, table, "/dune"), headers=alice)
    assert (await client.delete(records_url(repository, table, "/dune/permanent"), headers=alice)).status_code == 204

    assert (await _get(client, alice, repository, table, "dune")).status_code == 404
    assert await db_session.scalar(select(Record).where(Record.id == created["id"])) is None
    assert (await post_record(client, alice, repository, table, name="Dune"))["slug"] == "dune"  # the slug is free again


# --- References ---------------------------------------------------------------------------------------


async def _library(client, headers):
    """Authors, and Books that refer to an author and to co-authors."""
    repository = await create_repository(client, headers, name="Library")
    authors = await create_table(client, headers, repository["slug"], name="Authors")
    books = await create_table(client, headers, repository["slug"], name="Books")
    author = attribute("reference", "Author", config={"table_id": authors["id"]}, show_in_list=True)
    coauthors = attribute("list", "Co-authors", config={"element_type": "reference", "table_id": authors["id"]})
    resp = await put_attributes(client, headers, repository["slug"], books["slug"], [author, coauthors])
    assert resp.status_code == 200, resp.text
    return repository, authors, resp.json(), author["id"], coauthors["id"]


async def test_a_reference_is_stored_and_resolved_with_the_name_of_what_it_points_at(client, alice):
    repository, authors, books, author_id, coauthors_id = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    anderson = await post_record(client, alice, repository, authors, name="Kevin J. Anderson")

    created = await post_record(
        client,
        alice,
        repository,
        books,
        name="Dune: House Atreides",
        data={author_id: herbert["id"], coauthors_id: [anderson["id"], herbert["id"]]},
    )

    assert created["data"] == {author_id: herbert["id"], coauthors_id: {"0": anderson["id"], "1": herbert["id"]}}
    assert created["refs"] == {
        herbert["id"]: {"name": "Frank Herbert", "slug": "frank-herbert", "table_slug": "authors", "table_name": "Authors", "deleted": False},
        anderson["id"]: {"name": "Kevin J. Anderson", "slug": "kevin-j-anderson", "table_slug": "authors", "table_name": "Authors", "deleted": False},
    }


async def test_a_reference_must_be_a_record_of_the_table_it_points_at(client, alice):
    repository, authors, books, author_id, coauthors_id = await _library(client, alice)
    a_book = await post_record(client, alice, repository, books, name="A book")
    nowhere = "00000000-0000-4000-8000-000000000000"

    for value in (a_book["id"], nowhere, "not-a-uuid", 5):
        resp = await client.post(records_url(repository, books), json={"name": "x", "data": {author_id: value}}, headers=alice)
        assert resp.status_code == 422, value
        assert resp.json()["detail"] == {"errors": {author_id: "invalid_reference"}}


async def test_the_bad_element_of_a_list_of_references_is_named(client, alice):
    repository, authors, books, author_id, coauthors_id = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    nowhere = "00000000-0000-4000-8000-000000000000"

    resp = await client.post(
        records_url(repository, books),
        json={"name": "x", "data": {coauthors_id: [herbert["id"], nowhere]}},
        headers=alice,
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {f"{coauthors_id}.1": "invalid_reference"}}


async def test_a_deleted_record_cannot_be_newly_referenced(client, alice):
    repository, authors, books, author_id, _ = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    await client.delete(records_url(repository, authors, "/frank-herbert"), headers=alice)

    resp = await client.post(records_url(repository, books), json={"name": "x", "data": {author_id: herbert["id"]}}, headers=alice)

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {author_id: "invalid_reference"}})


async def test_a_reference_already_on_a_record_survives_the_target_being_deleted(client, alice):
    repository, authors, books, author_id, _ = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    await post_record(client, alice, repository, books, name="Dune", data={author_id: herbert["id"]})
    await client.delete(records_url(repository, authors, "/frank-herbert"), headers=alice)

    shown = (await _get(client, alice, repository, books, "dune")).json()
    assert shown["refs"][herbert["id"]]["deleted"] is True

    kept = await client.patch(
        records_url(repository, books, "/dune"), json={"data": {author_id: herbert["id"]}, "name": "Dune!"}, headers=alice
    )
    assert kept.status_code == 200
    assert kept.json()["data"] == {author_id: herbert["id"]}

    await client.post(records_url(repository, authors, "/frank-herbert/restore"), headers=alice)
    assert (await _get(client, alice, repository, books, "dune")).json()["refs"][herbert["id"]]["deleted"] is False


async def test_a_reference_cannot_point_into_another_repository(client, alice):
    repository, authors, books, author_id, _ = await _library(client, alice)
    elsewhere = await create_repository(client, alice, name="Elsewhere")
    foreign_table = await create_table(client, alice, elsewhere["slug"], name="Authors")
    foreign = await post_record(client, alice, elsewhere, foreign_table, name="Someone")

    resp = await client.post(records_url(repository, books), json={"name": "x", "data": {author_id: foreign["id"]}}, headers=alice)

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {author_id: "invalid_reference"}})


async def test_a_record_can_refer_to_a_record_of_its_own_table(client, alice):
    repository, table, _ = await make_table(client, alice)
    parent = attribute("reference", "Parent", config={"table_id": table["id"]})
    assert (await put_attributes(client, alice, repository["slug"], table["slug"], [parent])).status_code == 200
    root = await post_record(client, alice, repository, table, name="Root")

    child = await post_record(client, alice, repository, table, name="Child", data={parent["id"]: root["id"]})

    assert child["refs"][root["id"]]["name"] == "Root"


async def test_a_record_that_is_referred_to_cannot_be_deleted_for_good(client, alice):
    repository, authors, books, author_id, coauthors_id = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    anderson = await post_record(client, alice, repository, authors, name="Kevin J. Anderson")
    await post_record(client, alice, repository, books, name="Dune", data={author_id: herbert["id"]})
    await post_record(client, alice, repository, books, name="Sandworms", data={coauthors_id: [herbert["id"], anderson["id"]]})
    for slug in ("frank-herbert", "kevin-j-anderson"):
        await client.delete(records_url(repository, authors, f"/{slug}"), headers=alice)

    herbert_refused = await client.delete(records_url(repository, authors, "/frank-herbert/permanent"), headers=alice)
    anderson_refused = await client.delete(records_url(repository, authors, "/kevin-j-anderson/permanent"), headers=alice)

    assert herbert_refused.status_code == anderson_refused.status_code == 409
    detail = herbert_refused.json()["detail"]
    assert detail["count"] == 2
    assert sorted(item["record"] for item in detail["referenced_by"]) == ["Dune", "Sandworms"]
    assert detail["referenced_by"][0]["table"] == "Books"
    assert detail["referenced_by"][0]["table_slug"] == "books"
    assert anderson_refused.json()["detail"]["count"] == 1  # only through the list of co-authors
    assert (await _get(client, alice, repository, authors, "frank-herbert")).status_code == 200


async def test_a_deleted_record_that_refers_still_blocks_and_one_that_is_gone_does_not(client, alice):
    repository, authors, books, author_id, _ = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    await post_record(client, alice, repository, books, name="Dune", data={author_id: herbert["id"]})
    await client.delete(records_url(repository, authors, "/frank-herbert"), headers=alice)
    await client.delete(records_url(repository, books, "/dune"), headers=alice)

    assert (await client.delete(records_url(repository, authors, "/frank-herbert/permanent"), headers=alice)).status_code == 409

    await client.delete(records_url(repository, books, "/dune/permanent"), headers=alice)
    assert (await client.delete(records_url(repository, authors, "/frank-herbert/permanent"), headers=alice)).status_code == 204


async def test_a_record_referring_only_to_itself_can_be_deleted_for_good(client, alice):
    repository, table, _ = await make_table(client, alice)
    parent = attribute("reference", "Parent", config={"table_id": table["id"]})
    await put_attributes(client, alice, repository["slug"], table["slug"], [parent])
    root = await post_record(client, alice, repository, table, name="Root")
    await client.patch(records_url(repository, table, "/root"), json={"data": {parent["id"]: root["id"]}}, headers=alice)
    await client.delete(records_url(repository, table, "/root"), headers=alice)

    assert (await client.delete(records_url(repository, table, "/root/permanent"), headers=alice)).status_code == 204


# --- Listing ---------------------------------------------------------------------------------------------------


async def _items(client, db_session, headers):
    """Five records with known values (one deleted, one with nothing)."""
    attrs = {
        "note": attribute("text", "Note", show_in_list=True),
        "pages": attribute("number", "Pages", show_in_list=True),
        "read": attribute("boolean", "Read"),
        "published": attribute("date", "Published"),
        "added": attribute("datetime", "Added"),
        "cover": attribute("image", "Cover", show_in_list=True),
        "tags": attribute("list", "Tags", config={"element_type": "text"}),
    }
    repository, table, _ = await make_table(client, headers, *attrs.values(), table_name="Items")
    ids = {key: value["id"] for key, value in attrs.items()}
    rows = {
        "alpha": dict(note="Hello World", pages=10, read=True, published="2026-01-10", added="2026-01-10T08:00"),
        "bravo": dict(note="hello there", pages=200, read=False, published="2026-06-15", added="2026-06-15T12:30"),
        "cecil": dict(note="Zebra crossing", pages=35.5, published="2026-12-31"),
        "delta": dict(),
    }
    for index, (name, values) in enumerate(rows.items()):
        await add_record(
            db_session,
            table["id"],
            name=name.capitalize(),
            slug=name,
            data={ids[key]: value for key, value in values.items()},
            created_on=datetime(2026, 3, 1 + index * 10, 23, 30, tzinfo=timezone.utc),
        )
    await add_record(
        db_session, table["id"], name="Echo", slug="echo", data={ids["note"]: "hello deleted", ids["pages"]: 1}, deleted=True,
        created_on=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    return repository, table, ids


async def _names(client, headers, repository, table, **body):
    resp = await query(client, headers, repository, table, **body)
    assert resp.status_code == 200, resp.text
    return [item["slug"] for item in resp.json()["items"]]


async def test_the_default_listing_is_by_name_and_leaves_deleted_records_out(client, db_session, alice):
    repository, table, _ = await _items(client, db_session, alice)

    body = (await query(client, alice, repository, table)).json()

    assert [item["slug"] for item in body["items"]] == ["alpha", "bravo", "cecil", "delta"]
    assert (body["total"], body["page"], body["page_size"]) == (4, 1, 25)
    assert await _names(client, alice, repository, table, include_deleted=True) == ["alpha", "bravo", "cecil", "delta", "echo"]


async def test_an_item_carries_the_system_attributes_and_only_the_values_shown_on_the_content_page(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)

    items = (await query(client, alice, repository, table, q="alpha")).json()["items"]

    assert len(items) == 1
    item = items[0]
    assert (item["name"], item["slug"], item["deleted_on"]) == ("Alpha", "alpha", None)
    assert item["created_on"]
    assert item["values"] == {ids["note"]: "Hello World", ids["pages"]: 10}  # not read, published, added


async def test_a_listing_resolves_the_references_it_shows(client, alice):
    repository, authors, books, author_id, _ = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    await post_record(client, alice, repository, books, name="Dune", data={author_id: herbert["id"]})

    body = (await query(client, alice, repository, books)).json()

    assert body["items"][0]["values"] == {author_id: herbert["id"]}
    assert body["refs"][herbert["id"]]["name"] == "Frank Herbert"


async def test_paging(client, db_session, alice):
    repository, table, _ = await make_table(client, alice)
    for index in range(60):
        await add_record(db_session, table["id"], name=f"Item {index:02d}", slug=f"item-{index:02d}")

    first = (await query(client, alice, repository, table)).json()
    third = (await query(client, alice, repository, table, page=3)).json()
    beyond = (await query(client, alice, repository, table, page=4)).json()
    big = (await query(client, alice, repository, table, page_size=50, page=2)).json()

    assert (first["total"], len(first["items"]), first["items"][0]["slug"], first["items"][-1]["slug"]) == (60, 25, "item-00", "item-24")
    assert (len(third["items"]), third["items"][0]["slug"], third["items"][-1]["slug"]) == (10, "item-50", "item-59")
    assert (beyond["items"], beyond["total"]) == ([], 60)
    assert (len(big["items"]), big["items"][0]["slug"], big["page_size"]) == (10, "item-50", 50)
    for bad in ({"page": 0}, {"page": -1}, {"page_size": 30}, {"page_size": 101}, {"page_size": 0}):
        assert (await query(client, alice, repository, table, **bad)).status_code == 422, bad


async def test_quick_search_looks_in_name_and_slug_and_wildcards_are_literal(client, db_session, alice):
    repository, table, _ = await _items(client, db_session, alice)
    await add_record(db_session, table["id"], name="100% sure", slug="sure")
    await add_record(db_session, table["id"], name="snake_case", slug="snake")

    assert await _names(client, alice, repository, table, q="ALP") == ["alpha"]
    assert await _names(client, alice, repository, table, q="rav") == ["bravo"]
    assert await _names(client, alice, repository, table, q="%") == ["sure"]
    assert await _names(client, alice, repository, table, q="_") == ["snake"]
    assert await _names(client, alice, repository, table, q="nothing like this") == []
    assert await _names(client, alice, repository, table, q="   ") != []


async def test_text_filters(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)
    note = ids["note"]
    await add_record(db_session, table["id"], name="Percent", slug="percent", data={note: "50% done_"})

    def cond(op, value=None):
        return [{"field": note, "op": op, **({} if value is None else {"value": value})}]

    assert await _names(client, alice, repository, table, conditions=cond("contains", "HELLO")) == ["alpha", "bravo"]
    assert await _names(client, alice, repository, table, conditions=cond("contains", "%")) == ["percent"]
    assert await _names(client, alice, repository, table, conditions=cond("contains", "_")) == ["percent"]
    assert await _names(client, alice, repository, table, conditions=cond("contains", "'; DROP TABLE module_repository_records; --")) == []
    assert await _names(client, alice, repository, table, conditions=cond("equals", "HELLO world")) == ["alpha"]
    assert await _names(client, alice, repository, table, conditions=cond("equals", "hello")) == []
    assert await _names(client, alice, repository, table, conditions=cond("empty")) == ["delta"]
    assert await _names(client, alice, repository, table, conditions=cond("not_empty")) == ["alpha", "bravo", "cecil", "percent"]
    assert await _names(client, alice, repository, table, conditions=[{"field": "name", "op": "contains", "value": "AL"}]) == ["alpha"]
    assert await _names(client, alice, repository, table, conditions=[{"field": "slug", "op": "equals", "value": "BRAVO"}]) == ["bravo"]


async def test_number_filters(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)
    pages = ids["pages"]

    def cond(op, **values):
        return [{"field": pages, "op": op, **values}]

    assert await _names(client, alice, repository, table, conditions=cond("eq", value=200)) == ["bravo"]
    assert await _names(client, alice, repository, table, conditions=cond("eq", value=35.5)) == ["cecil"]
    assert await _names(client, alice, repository, table, conditions=cond("ne", value=10)) == ["bravo", "cecil"]  # no value is not "different"
    assert await _names(client, alice, repository, table, conditions=cond("lt", value=35.5)) == ["alpha"]
    assert await _names(client, alice, repository, table, conditions=cond("lte", value=35.5)) == ["alpha", "cecil"]
    assert await _names(client, alice, repository, table, conditions=cond("gt", value=10)) == ["bravo", "cecil"]
    assert await _names(client, alice, repository, table, conditions=cond("gte", value=200)) == ["bravo"]
    assert await _names(client, alice, repository, table, conditions=cond("between", value=10, value2=35.5)) == ["alpha", "cecil"]
    assert await _names(client, alice, repository, table, conditions=cond("empty")) == ["delta"]
    assert await _names(client, alice, repository, table, conditions=cond("not_empty")) == ["alpha", "bravo", "cecil"]


async def test_boolean_filters(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)
    read = ids["read"]

    assert await _names(client, alice, repository, table, conditions=[{"field": read, "op": "equals", "value": True}]) == ["alpha"]
    assert await _names(client, alice, repository, table, conditions=[{"field": read, "op": "equals", "value": False}]) == ["bravo"]
    assert await _names(client, alice, repository, table, conditions=[{"field": read, "op": "empty"}]) == ["cecil", "delta"]


async def test_date_and_datetime_filters(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)
    published, added = ids["published"], ids["added"]

    def day(op, **values):
        return [{"field": published, "op": op, **values}]

    assert await _names(client, alice, repository, table, conditions=day("before", value="2026-06-15")) == ["alpha"]
    assert await _names(client, alice, repository, table, conditions=day("after", value="2026-06-15")) == ["cecil"]
    assert await _names(client, alice, repository, table, conditions=day("eq", value="2026-06-15")) == ["bravo"]
    assert await _names(client, alice, repository, table, conditions=day("between", value="2026-01-10", value2="2026-06-15")) == ["alpha", "bravo"]
    assert await _names(client, alice, repository, table, conditions=day("empty")) == ["delta"]
    after = [{"field": added, "op": "after", "value": "2026-03-01T00:00"}]
    between = [{"field": added, "op": "between", "value": "2026-06-15T12:00", "value2": "2026-06-15T13:00"}]
    assert await _names(client, alice, repository, table, conditions=after) == ["bravo"]
    assert await _names(client, alice, repository, table, conditions=between) == ["bravo"]
    assert await _names(client, alice, repository, table, conditions=[{"field": added, "op": "eq", "value": "2026-01-10T08:00"}]) == ["alpha"]


async def test_created_on_is_compared_by_its_date_in_prague(client, db_session, alice):
    # Created at 23:30 UTC on the 1st, 11th, 21st and 31st of March 2026 (CET, so 00:30 on the NEXT day in Prague).
    repository, table, _ = await _items(client, db_session, alice)

    def created(op, **values):
        return [{"field": "created_on", "op": op, **values}]

    assert await _names(client, alice, repository, table, conditions=created("eq", value="2026-03-02")) == ["alpha"]
    assert await _names(client, alice, repository, table, conditions=created("eq", value="2026-03-01")) == []
    assert await _names(client, alice, repository, table, conditions=created("after", value="2026-03-12")) == ["cecil", "delta"]
    assert await _names(client, alice, repository, table, conditions=created("before", value="2026-03-12")) == ["alpha"]
    assert await _names(client, alice, repository, table, conditions=created("between", value="2026-03-02", value2="2026-03-12")) == ["alpha", "bravo"]


async def test_reference_filters(client, alice):
    repository, authors, books, author_id, _ = await _library(client, alice)
    herbert = await post_record(client, alice, repository, authors, name="Frank Herbert")
    asimov = await post_record(client, alice, repository, authors, name="Isaac Asimov")
    await post_record(client, alice, repository, books, name="Dune", data={author_id: herbert["id"]})
    await post_record(client, alice, repository, books, name="Foundation", data={author_id: asimov["id"]})
    await post_record(client, alice, repository, books, name="Anonymous")

    assert await _names(client, alice, repository, books, conditions=[{"field": author_id, "op": "equals", "value": herbert["id"]}]) == ["dune"]
    assert await _names(client, alice, repository, books, conditions=[{"field": author_id, "op": "empty"}]) == ["anonymous"]
    assert await _names(client, alice, repository, books, conditions=[{"field": author_id, "op": "not_empty"}]) == ["dune", "foundation"]


async def test_conditions_are_combined_with_and(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)

    conditions = [
        {"field": ids["note"], "op": "contains", "value": "hello"},
        {"field": ids["pages"], "op": "gt", "value": 50},
    ]

    assert await _names(client, alice, repository, table, conditions=conditions) == ["bravo"]
    assert await _names(client, alice, repository, table, conditions=conditions, q="alpha") == []
    assert await _names(client, alice, repository, table, conditions=conditions, include_deleted=True) == ["bravo"]


async def test_a_filter_that_is_not_valid_is_a_422_with_the_conditions_named(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)

    resp = await query(
        client,
        alice,
        repository,
        table,
        conditions=[
            {"field": ids["pages"], "op": "contains", "value": "x"},
            {"field": ids["cover"], "op": "empty"},
            {"field": ids["tags"], "op": "empty"},
            {"field": "nope", "op": "empty"},
            {"field": ids["pages"], "op": "between", "value": 5},
            {"field": ids["published"], "op": "eq", "value": "yesterday"},
        ],
        sort={"field": ids["cover"]},
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == {
        "errors": {
            "conditions.0": "invalid_operator",
            "conditions.1": "unknown_field",
            "conditions.2": "unknown_field",
            "conditions.3": "unknown_field",
            "conditions.4": "value_required",
            "conditions.5": "invalid_date",
            "sort": "unknown_field",
        }
    }


async def test_a_field_name_cannot_be_used_to_reach_the_sql(client, db_session, alice):
    repository, table, _ = await _items(client, db_session, alice)

    for field in ("data->>'x'", "name; drop table module_repository_records", "'\" or 1=1 --"):
        resp = await query(client, alice, repository, table, conditions=[{"field": field, "op": "empty"}])
        assert resp.status_code == 422
    assert (await query(client, alice, repository, table)).json()["total"] == 4


async def test_at_most_twenty_conditions(client, db_session, alice):
    repository, table, _ = await _items(client, db_session, alice)
    one = {"field": "name", "op": "not_empty"}

    assert (await query(client, alice, repository, table, conditions=[one] * 20)).status_code == 200
    assert (await query(client, alice, repository, table, conditions=[one] * 21)).status_code == 422
    assert (await query(client, alice, repository, table, conditions=[{"field": "name", "op": "empty", "other": 1}])).status_code == 422


async def test_sorting(client, db_session, alice):
    repository, table, ids = await _items(client, db_session, alice)

    def by(field, direction="asc"):
        return {"field": field, "dir": direction}

    # Empty values come last whichever way it goes.
    assert await _names(client, alice, repository, table, sort=by(ids["pages"])) == ["alpha", "cecil", "bravo", "delta"]
    assert await _names(client, alice, repository, table, sort=by(ids["pages"], "desc")) == ["bravo", "cecil", "alpha", "delta"]
    # Text ignores case: "hello there" < "Hello World" < "Zebra crossing".
    assert await _names(client, alice, repository, table, sort=by(ids["note"])) == ["bravo", "alpha", "cecil", "delta"]
    assert await _names(client, alice, repository, table, sort=by("name", "desc")) == ["delta", "cecil", "bravo", "alpha"]
    assert await _names(client, alice, repository, table, sort=by(ids["published"], "desc")) == ["cecil", "bravo", "alpha", "delta"]
    assert await _names(client, alice, repository, table, sort=by(ids["added"])) == ["alpha", "bravo", "cecil", "delta"]
    assert await _names(client, alice, repository, table, sort=by(ids["read"])) == ["bravo", "alpha", "cecil", "delta"]  # false before true
    assert await _names(client, alice, repository, table, sort=by("created_on", "desc")) == ["delta", "cecil", "bravo", "alpha"]
    assert await _names(client, alice, repository, table, sort=by("slug", "desc")) == ["delta", "cecil", "bravo", "alpha"]


async def test_a_reference_is_sorted_by_the_name_of_what_it_points_at(client, alice):
    repository, authors, books, author_id, _ = await _library(client, alice)
    zed = await post_record(client, alice, repository, authors, name="Zed")
    adam = await post_record(client, alice, repository, authors, name="adam")
    await post_record(client, alice, repository, books, name="First", data={author_id: zed["id"]})
    await post_record(client, alice, repository, books, name="Second", data={author_id: adam["id"]})
    await post_record(client, alice, repository, books, name="Third")

    assert await _names(client, alice, repository, books, sort={"field": author_id}) == ["second", "first", "third"]
    assert await _names(client, alice, repository, books, sort={"field": author_id, "dir": "desc"}) == ["first", "second", "third"]


async def test_records_with_equal_sort_values_keep_a_stable_order(client, db_session, alice):
    repository, table, _ = await make_table(client, alice)
    for index in range(30):
        await add_record(db_session, table["id"], name="Same", slug=f"same-{index:02d}", created_on=datetime(2026, 1, 1, tzinfo=timezone.utc))

    first = await _names(client, alice, repository, table)
    again = await _names(client, alice, repository, table)
    second_page = await _names(client, alice, repository, table, page=2)

    assert first == again
    assert len(set(first) | set(second_page)) == 30


async def test_listing_is_limited_to_the_table(client, db_session, alice):
    repository, table, _ = await _items(client, db_session, alice)
    other = await create_table(client, alice, repository["slug"], name="Other")
    await add_record(db_session, other["id"], name="Elsewhere")

    assert "elsewhere" not in " ".join(await _names(client, alice, repository, table, include_deleted=True)).lower()
    assert [item["name"] for item in (await query(client, alice, repository, other)).json()["items"]] == ["Elsewhere"]


# --- The picker's search ---------------------------------------------------------------------------------------------


async def _search(client, headers, repository, table, **params):
    resp = await client.get(records_url(repository, table, "").replace("/records", "/records-search"), params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_search_finds_records_that_are_not_deleted_by_name_or_slug(client, db_session, alice):
    repository, table, _ = await _items(client, db_session, alice)

    everything = await _search(client, alice, repository, table)
    assert [hit["name"] for hit in everything["items"]] == ["Alpha", "Bravo", "Cecil", "Delta"]
    assert (everything["total"], everything["page"], everything["page_size"]) == (4, 1, 20)
    assert {"id", "name", "slug"} == set(everything["items"][0])
    assert [hit["slug"] for hit in (await _search(client, alice, repository, table, q="ALP"))["items"]] == ["alpha"]
    assert [hit["slug"] for hit in (await _search(client, alice, repository, table, q="echo"))["items"]] == []  # deleted
    assert (await _search(client, alice, repository, table, q="%"))["total"] == 0
    assert (await _search(client, alice, repository, table, q="  "))["total"] == 4


async def test_search_is_paged_by_twenty(client, db_session, alice):
    repository, table, _ = await make_table(client, alice)
    for index in range(25):
        await add_record(db_session, table["id"], name=f"Item {index:02d}", slug=f"item-{index:02d}")

    first = await _search(client, alice, repository, table)
    second = await _search(client, alice, repository, table, page=2)

    assert (first["total"], len(first["items"]), len(second["items"])) == (25, 20, 5)
    assert second["items"][0]["name"] == "Item 20"
    assert (await client.get(records_url(repository, table).replace("/records", "/records-search"), params={"page": 0}, headers=alice)).status_code == 422


# --- Records and removed attributes -----------------------------------------------------------------------------------


async def test_the_values_of_an_attribute_removed_from_the_table_disappear_from_its_records(client, alice):
    repository, table, ids = await _books(client, alice)
    await post_record(client, alice, repository, table, name="Dune", data={ids["title"]: "Dune", ids["pages"]: 400})
    kept = [attribute("text", "Title") | {"id": ids["title"], "required": True, "show_in_list": True}]

    refused = await put_attributes(client, alice, repository["slug"], table["slug"], kept)
    assert refused.status_code == 409
    done = await put_attributes(client, alice, repository["slug"], table["slug"], kept, confirm_purge="true")

    assert done.status_code == 200
    assert (await _get(client, alice, repository, table, "dune")).json()["data"] == {ids["title"]: "Dune"}


async def test_a_record_that_is_too_large_all_together_is_refused(client, alice):
    attrs = [attribute("list", f"Texts {index}", config={"element_type": "text"}) for index in range(8)]
    repository, table, _ = await make_table(client, alice, *attrs)
    big = ["x" * 5000] * 200  # 1 MB of text in one attribute: each is within its own limits

    resp = await client.post(
        records_url(repository, table),
        json={"name": "Huge", "data": {attr["id"]: big for attr in attrs}},
        headers=alice,
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {"data": "record_too_large"}}
    assert (await query(client, alice, repository, table)).json()["total"] == 0
