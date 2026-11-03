# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for searching the endpoints of every document: the index kept for the
current version of each (app/services/endpoint_index.py - rebuilt on a new
version, never failing a check, filled in for documents that predate it) and
GET /api/endpoint-search (who sees what, what a query matches, ranking,
filters, paging)."""

import json
import uuid

import pytest
from sqlalchemy import delete, func, select, update

import app.security.jwt as jwt_module
from app.models.api_document import ApiDocument, ApiDocumentEndpoint, ApiDocumentVersion
from app.services import endpoint_index
from app.services.api_document_versions import process_new_spec
from tests.format_support import BASE_SDL, pm, pm_request
from tests.version_support import docs_settings, make_document, make_user, pets_spec, record, request, token_for

SEARCH = "/api/endpoint-search"


def marker() -> str:
    """A word nothing else in the database contains, so a query for it finds
    only what the test itself recorded."""
    return "m" + uuid.uuid4().hex[:10]


def spec_with(paths: dict, version: str = "1.0.0") -> dict:
    return pets_spec(version, paths={path: {"get": operation} for path, operation in paths.items()})


async def endpoints_of(db_session, doc) -> list[ApiDocumentEndpoint]:
    result = await db_session.execute(
        select(ApiDocumentEndpoint).where(ApiDocumentEndpoint.documentation_id == doc.id).order_by(ApiDocumentEndpoint.path)
    )
    return list(result.scalars().all())


async def search(db_session, tmp_path, token=None, **params):
    resp = await request(db_session, "GET", SEARCH, token=token, settings=docs_settings(tmp_path), params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def paths_of(body) -> list[str]:
    return [item["path"] for item in body["items"]]


class _UseExistingSession:
    """Stands in for AsyncSessionLocal() so the backfill works on the test's own
    (rolled-back) transaction and never closes the session that owns it."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture()
def _signed_in(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


# --- the index ----------------------------------------------------------------------


async def test_a_new_current_version_is_indexed_with_folded_search_text(db_session, tmp_path):
    doc = await make_document(db_session)
    version = await record(
        db_session, doc, spec_with({"/zakaznici": {"summary": "Zákaznický seznam", "tags": ["Účty"], "operationId": "listZakaznici"}}), tmp_path
    )

    (row,) = await endpoints_of(db_session, doc)

    assert (row.method, row.path, row.name, row.tags, row.version_id) == ("GET", "/zakaznici", "Zákaznický seznam", ["Účty"], version.id)
    assert row.search_text == "get /zakaznici zakaznicky seznam ucty listzakaznici"
    assert version.endpoint_count == 1


async def test_a_new_version_replaces_the_rows_of_its_document_only(db_session, tmp_path):
    doc = await make_document(db_session)
    other = await make_document(db_session)
    await record(db_session, other, spec_with({"/other": {}}), tmp_path)
    await record(db_session, doc, spec_with({"/old": {}, "/stays": {}}, "1.0.0"), tmp_path)

    second = await record(db_session, doc, spec_with({"/stays": {}, "/new": {}}, "2.0.0"), tmp_path)

    assert [(e.path, e.version_id) for e in await endpoints_of(db_session, doc)] == [("/new", second.id), ("/stays", second.id)]
    assert [e.path for e in await endpoints_of(db_session, other)] == ["/other"]
    assert second.endpoint_count == 2


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (BASE_SDL.encode(), {("QUERY", "users"), ("QUERY", "user")}),
        (
            json.dumps(
                {
                    "asyncapi": "2.6.0",
                    "info": {"title": "Users", "version": "1"},
                    "channels": {"user/signedup": {"subscribe": {"message": {"name": "UserSignedUp"}}}},
                }
            ).encode(),
            {("SUBSCRIBE", "user/signedup")},
        ),
    ],
)
async def test_graphql_and_asyncapi_documents_are_indexed_too(db_session, tmp_path, raw, expected):
    doc = await make_document(db_session)

    await process_new_spec(doc, raw, source="manual_upload", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000)

    assert {(e.method, e.path) for e in await endpoints_of(db_session, doc)} == expected


async def test_a_postman_collection_is_indexed_too(db_session, tmp_path):
    doc = await make_document(db_session)
    raw = json.dumps({"info": {"name": "Pets", "schema": pm().document["info"]["schema"], "version": "1"}, "item": [pm_request("List", "GET", ["pets"])]})

    await process_new_spec(doc, raw.encode(), source="manual_upload", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000)

    assert [(e.method, e.path, e.name) for e in await endpoints_of(db_session, doc)] == [("GET", "/pets", "List")]


async def test_a_failing_index_never_fails_the_check_and_is_left_for_the_backfill(db_session, tmp_path, monkeypatch):
    doc = await make_document(db_session)

    def boom(parsed):
        raise RuntimeError("cannot extract")

    monkeypatch.setattr(endpoint_index, "extract_endpoints", boom)
    version = await record(db_session, doc, spec_with({"/pets": {}}), tmp_path)

    assert (version.version, version.endpoint_count) == ("1.0.0", None)  # still usable, not indexed
    assert await endpoints_of(db_session, doc) == []

    monkeypatch.undo()
    monkeypatch.setattr(endpoint_index, "AsyncSessionLocal", lambda: _UseExistingSession(db_session))
    await endpoint_index.backfill_missing(str(tmp_path))

    assert [e.path for e in await endpoints_of(db_session, doc)] == ["/pets"]
    assert await db_session.scalar(select(ApiDocumentVersion.endpoint_count).where(ApiDocumentVersion.id == version.id)) == 1


async def test_a_failure_while_writing_the_index_undoes_only_the_index(db_session, tmp_path, monkeypatch):
    doc = await make_document(db_session, title="Pets API")
    await record(db_session, doc, spec_with({"/old": {}}, "1.0.0"), tmp_path)
    real_replace = endpoint_index.replace_index

    async def delete_then_fail(db, documentation_id, version_id, endpoints):
        await real_replace(db, documentation_id, version_id, [])  # the old rows are gone ...
        raise RuntimeError("the insert failed")  # ... when this happens

    monkeypatch.setattr(endpoint_index, "replace_index", delete_then_fail)
    second = await record(db_session, doc, spec_with({"/new": {}}, "2.0.0"), tmp_path)

    # The savepoint took the half-done index back; the document and the version are still usable
    # (reading an expired attribute would raise) and the second version is recorded, unindexed.
    assert (doc.title, second.version, second.endpoint_count) == ("Pets API", "2.0.0", None)
    assert [e.path for e in await endpoints_of(db_session, doc)] == ["/old"]


async def test_the_backfill_indexes_current_versions_only_and_skips_what_it_cannot_read(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(endpoint_index, "AsyncSessionLocal", lambda: _UseExistingSession(db_session))
    good = await make_document(db_session)
    lost = await make_document(db_session)
    done = await make_document(db_session)
    archived = await record(db_session, good, spec_with({"/good": {}}, "1.0.0"), tmp_path)
    current = await record(db_session, good, spec_with({"/good": {}}, "2.0.0"), tmp_path)  # archives the first
    lost_version = await record(db_session, lost, spec_with({"/lost": {}}), tmp_path)
    await record(db_session, done, spec_with({"/done": {}}), tmp_path)
    # What a database from before the index existed looks like: nothing indexed.
    archived_id, current_id, lost_id, lost_file = archived.id, current.id, lost_version.id, lost_version.storage_path
    await db_session.execute(delete(ApiDocumentEndpoint).where(ApiDocumentEndpoint.documentation_id.in_([good.id, lost.id])))
    await db_session.execute(
        update(ApiDocumentVersion).where(ApiDocumentVersion.documentation_id.in_([good.id, lost.id])).values(endpoint_count=None)
    )
    (tmp_path / lost_file).unlink()
    await db_session.commit()

    await endpoint_index.backfill_missing(str(tmp_path))

    async def count_of(version_id):
        return await db_session.scalar(select(ApiDocumentVersion.endpoint_count).where(ApiDocumentVersion.id == version_id))

    assert [(e.path, e.version_id) for e in await endpoints_of(db_session, good)] == [("/good", current_id)]
    assert (await count_of(current_id), await count_of(archived_id)) == (1, None)  # the archived version is not indexed
    assert await endpoints_of(db_session, lost) == [] and await count_of(lost_id) is None  # its file is gone: skipped, tried again later
    assert [e.path for e in await endpoints_of(db_session, done)] == ["/done"]  # was indexed all along: left alone


async def test_deleting_a_document_removes_its_rows(db_session, tmp_path):
    doc = await make_document(db_session)
    await record(db_session, doc, spec_with({"/a": {}, "/b": {}}), tmp_path)
    doc_id = doc.id

    await db_session.delete(doc)
    await db_session.flush()

    count = await db_session.scalar(select(func.count()).select_from(ApiDocumentEndpoint).where(ApiDocumentEndpoint.documentation_id == doc_id))
    assert count == 0
    assert await db_session.get(ApiDocument, doc_id) is None


# --- who sees what ------------------------------------------------------------------


async def test_anonymous_callers_find_public_documents_only(db_session, tmp_path):
    m = marker()
    public = await make_document(db_session, is_public=True)
    private = await make_document(db_session)
    await record(db_session, public, spec_with({f"/{m}/public": {}}), tmp_path)
    await record(db_session, private, spec_with({f"/{m}/private": {}}), tmp_path)

    body = await search(db_session, tmp_path, q=m)

    assert paths_of(body) == [f"/{m}/public"]
    assert body["total"] == 1


async def test_a_signed_in_user_also_finds_the_documents_of_their_teams(db_session, make_access_token, tmp_path, _signed_in):
    m = marker()
    member = await make_user(db_session, email="member@example.com")
    outsider = await make_user(db_session, email="outsider@example.com")
    mine = await make_document(db_session, members=(member,))
    public = await make_document(db_session, is_public=True)
    foreign = await make_document(db_session)
    for doc, name in ((mine, "mine"), (public, "public"), (foreign, "foreign")):
        await record(db_session, doc, spec_with({f"/{m}/{name}": {}}), tmp_path)

    seen_by_member = await search(db_session, tmp_path, token_for(make_access_token, member), q=m)
    seen_by_outsider = await search(db_session, tmp_path, token_for(make_access_token, outsider), q=m)

    assert paths_of(seen_by_member) == [f"/{m}/mine", f"/{m}/public"]
    assert paths_of(seen_by_outsider) == [f"/{m}/public"]
    assert {hit["document_title"] for hit in seen_by_member["items"]} == {"Pets API"}


async def test_making_a_document_private_takes_effect_at_once(db_session, tmp_path):
    m = marker()
    doc = await make_document(db_session, is_public=True)
    await record(db_session, doc, spec_with({f"/{m}": {}}), tmp_path)
    before = await search(db_session, tmp_path, q=m)

    doc.is_public = False
    await db_session.flush()
    after = await search(db_session, tmp_path, q=m)

    assert (before["total"], after["total"]) == (1, 0)


async def test_only_the_current_version_is_found(db_session, tmp_path):
    m = marker()
    doc = await make_document(db_session, is_public=True)
    await record(db_session, doc, spec_with({f"/{m}/old": {}}, "1.0.0"), tmp_path)
    second = await record(db_session, doc, spec_with({f"/{m}/new": {}}, "2.0.0"), tmp_path)

    body = await search(db_session, tmp_path, q=m)

    assert [(hit["path"], hit["version"], hit["version_id"]) for hit in body["items"]] == [(f"/{m}/new", "2.0.0", str(second.id))]


# --- what a query matches -----------------------------------------------------------


async def test_every_word_must_match_and_case_and_diacritics_do_not(db_session, tmp_path):
    m = marker()
    doc = await make_document(db_session, is_public=True, title=f"Účetní {m}")
    await record(
        db_session,
        doc,
        spec_with(
            {
                "/faktury": {"summary": "Seznam zákazníků", "description": "Vrací všechny FAKTURY zákazníka", "tags": ["Fakturace"]},
                "/sklad": {"summary": "Skladové zásoby"},
            }
        ),
        tmp_path,
    )

    both = await search(db_session, tmp_path, q="zakazniku faktury")
    in_tag = await search(db_session, tmp_path, q=f"fakturace {m}")
    in_title = await search(db_session, tmp_path, q=f"ucetni sklad")
    missing_word = await search(db_session, tmp_path, q="faktury neexistuje")

    assert paths_of(both) == ["/faktury"]
    assert paths_of(in_tag) == ["/faktury"]
    assert paths_of(in_title) == ["/sklad"]
    assert missing_word["total"] == 0


async def test_like_wildcards_in_the_query_are_literal(db_session, tmp_path):
    m = marker()
    doc = await make_document(db_session, is_public=True)
    await record(db_session, doc, spec_with({f"/{m}/rate": {"summary": "50% discount"}, f"/{m}/other": {"summary": "500 items"}}), tmp_path)

    body = await search(db_session, tmp_path, q=f"{m} 50%")

    assert paths_of(body) == [f"/{m}/rate"]


async def test_a_match_in_the_path_ranks_before_the_name_before_the_rest(db_session, tmp_path):
    doc = await make_document(db_session, is_public=True)
    await record(
        db_session,
        doc,
        spec_with(
            {
                "/a-description": {"description": "talks about invoices"},
                "/b-name": {"summary": "List invoices"},
                "/z-invoices": {},
                "/c-id": {"operationId": "invoicesList"},
            }
        ),
        tmp_path,
    )

    body = await search(db_session, tmp_path, q="invoices", document_id=str(doc.id))

    assert paths_of(body) == ["/z-invoices", "/b-name", "/c-id", "/a-description"]


async def test_without_a_query_everything_visible_is_listed_by_document_and_path(db_session, tmp_path):
    first = await make_document(db_session, is_public=True, title="Alpha " + marker())
    second = await make_document(db_session, is_public=True, title="Beta " + marker())
    await record(db_session, second, spec_with({"/x": {}}), tmp_path)
    await record(db_session, first, spec_with({"/z": {}, "/y": {}}), tmp_path)

    items = []
    for doc in (first, second):
        items += (await search(db_session, tmp_path, document_id=str(doc.id)))["items"]

    assert [(hit["document_title"].split()[0], hit["path"]) for hit in items] == [("Alpha", "/y"), ("Alpha", "/z"), ("Beta", "/x")]


# --- filters, paging and the shape of a hit -----------------------------------------


async def test_filters_by_method_document_and_kind(db_session, tmp_path):
    m = marker()
    rest = await make_document(db_session, is_public=True)
    graphql = await make_document(db_session, is_public=True, title=f"Graph {m}")
    await record(
        db_session,
        rest,
        pets_spec(paths={f"/{m}/pets": {"get": {}, "post": {}}, f"/{m}/owners": {"delete": {}}}),
        tmp_path,
    )
    await process_new_spec(graphql, BASE_SDL.encode(), source="manual_upload", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000)

    posts = await search(db_session, tmp_path, q=m, method="post")
    queries = await search(db_session, tmp_path, q=m, method="QUERY")
    one_doc = await search(db_session, tmp_path, q=m, document_id=str(rest.id))
    kind = await search(db_session, tmp_path, q=m, spec_type="graphql")

    assert [(h["method"], h["path"]) for h in posts["items"]] == [("POST", f"/{m}/pets")]
    assert [(h["method"], h["path"]) for h in queries["items"]] == [("QUERY", "user"), ("QUERY", "users")]
    assert {h["document_id"] for h in one_doc["items"]} == {str(rest.id)}
    assert {(h["spec_type"], h["method"]) for h in kind["items"]} == {("graphql", "QUERY")}


async def test_results_are_paged_and_the_total_counts_all_pages(db_session, tmp_path):
    m = marker()
    doc = await make_document(db_session, is_public=True)
    await record(db_session, doc, spec_with({f"/{m}/{i}": {} for i in range(5)}), tmp_path)

    first = await search(db_session, tmp_path, q=m, page_size=2)
    last = await search(db_session, tmp_path, q=m, page_size=2, page=3)
    beyond = await search(db_session, tmp_path, q=m, page_size=2, page=9)

    assert (first["total"], first["page"], first["page_size"], paths_of(first)) == (5, 1, 2, [f"/{m}/0", f"/{m}/1"])
    assert paths_of(last) == [f"/{m}/4"]
    assert (beyond["total"], beyond["items"]) == (5, [])


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"document_id": "nope"}])
async def test_bad_paging_or_filters_are_rejected(db_session, tmp_path, params):
    resp = await request(db_session, "GET", SEARCH, settings=docs_settings(tmp_path), params=params)

    assert resp.status_code == 422


async def test_a_hit_carries_its_document_version_and_a_short_description(db_session, tmp_path):
    m = marker()
    doc = await make_document(db_session, is_public=True, title=f"Pets {m}")
    version = await record(
        db_session,
        doc,
        spec_with({f"/{m}": {"summary": "List", "description": "x" * 1000, "tags": ["pets"], "deprecated": True}}),
        tmp_path,
    )

    (hit,) = (await search(db_session, tmp_path, q=m))["items"]

    assert hit.pop("description").endswith("…") and len(hit["name"]) == 4
    assert hit == {
        "document_id": str(doc.id),
        "document_title": f"Pets {m}",
        "team_id": str(doc.team_id),
        "is_public": True,
        "version_id": str(version.id),
        "version": "1.0.0",
        "spec_type": "openapi",
        "method": "GET",
        "path": f"/{m}",
        "name": "List",
        "tags": ["pets"],
        "deprecated": True,
    }
