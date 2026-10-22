# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Images of the repository module: uploading and reading them back, what is
accepted (by content, never by what the client says), the quotas, how a record
claims and loses them, and importing by address (the downloading itself is
test_modules_repository_fetch.py)."""

import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.repository import fetch, images
from app.modules.repository.config import RepositoryConfig
from app.modules.repository.models import Image, Record
from tests.repository_support import (  # noqa: F401  (the fixtures are used by name)
    BASE,
    _overrides,
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
    records_url,
    set_limits,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"j" * 32
GIF = b"GIF89a" + b"g" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBP" + b"w" * 32
SAMPLES = {"image/png": PNG, "image/jpeg": JPEG, "image/gif": GIF, "image/webp": WEBP}


async def _upload(client, headers, contents=PNG, content_type="image/png", filename="picture.png"):
    return await client.post(f"{BASE}/images", files={"file": (filename, contents, content_type)}, headers=headers)


async def _image_id(client, headers, contents=PNG) -> str:
    resp = await _upload(client, headers, contents)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _album(client, headers):
    """A table with a cover (image) and photos (a map of images)."""
    cover = attribute("image", "Cover")
    photos = attribute("map", "Photos", config={"element_type": "image"})
    repository, table, _ = await make_table(client, headers, cover, photos, table_name="Albums")
    return repository, table, cover["id"], photos["id"]


async def _image_rows(db_session, *ids) -> set[str]:
    db_session.expire_all()
    rows = await db_session.scalars(select(Image.id).where(Image.id.in_([uuid.UUID(i) for i in ids])))
    return {str(i) for i in rows.all()}


# --- Uploading and reading -----------------------------------------------------------------


@pytest.mark.parametrize("mime", sorted(SAMPLES))
async def test_an_image_is_stored_and_read_back_byte_for_byte(client, alice, mime):
    resp = await _upload(client, alice, SAMPLES[mime], content_type="application/octet-stream", filename="whatever.bin")

    assert resp.status_code == 201
    body = resp.json()
    assert (body["mime"], body["size_bytes"]) == (mime, len(SAMPLES[mime]))
    uuid.UUID(body["id"])
    read = await client.get(f"{BASE}/images/{body['id']}", headers=alice)
    assert read.status_code == 200
    assert read.content == SAMPLES[mime]
    assert read.headers["content-type"] == mime
    assert read.headers["x-content-type-options"] == "nosniff"
    assert "private" in read.headers["cache-control"]


async def test_the_image_is_stored_as_base64_text(client, db_session, alice):
    image_id = await _image_id(client, alice)

    row = await db_session.get(Image, uuid.UUID(image_id))

    assert row.data.startswith("iVBORw0KGgp")  # the PNG signature, base64
    assert base64.b64decode(row.data) == PNG
    assert row.record_id is None
    assert row.size_bytes == len(PNG)


@pytest.mark.parametrize(
    "contents",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>',
        b"<!DOCTYPE html><html><script>alert(1)</script></html>",
        b"just some text",
        b"%PDF-1.7 not an image",
        b"PK\x03\x04 a zip",
        b"RIFF\x00\x00\x00\x00WAVEfmt ",
        b"\x89PNG",
        b"GIF8",
    ],
)
async def test_what_is_not_an_accepted_image_is_refused_whatever_it_is_called(client, alice, contents):
    resp = await _upload(client, alice, contents, content_type="image/png", filename="picture.png")

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {"file": "unsupported_type"}}


async def test_an_empty_file_is_refused(client, alice):
    resp = await _upload(client, alice, b"")

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"file": "empty"}})


async def test_a_file_over_the_limit_is_refused_and_one_at_the_limit_is_fine(client, alice):
    set_limits(max_image_bytes=2048)

    at_limit = await _upload(client, alice, PNG + b"x" * (2048 - len(PNG)))
    over = await _upload(client, alice, PNG + b"x" * (2049 - len(PNG)))

    assert at_limit.status_code == 201
    assert (over.status_code, over.json()["detail"]) == (422, {"errors": {"file": "too_large"}})


async def test_a_person_s_images_together_are_limited(client, alice, bob):
    set_limits(max_image_bytes=2048, max_image_bytes_per_user=3000)
    big = PNG + b"x" * (2000 - len(PNG))

    first = await _upload(client, alice, big)
    second = await _upload(client, alice, big)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == {"limit": "max_image_bytes_per_user", "max": 3000}
    assert (await _upload(client, bob, big)).status_code == 201  # Bob has his own quota


async def test_an_upload_needs_a_file(client, alice):
    assert (await client.post(f"{BASE}/images", headers=alice)).status_code == 422


async def test_an_unknown_image_is_404_and_a_malformed_id_is_422(client, alice):
    assert (await client.get(f"{BASE}/images/{uuid.uuid4()}", headers=alice)).status_code == 404
    assert (await client.get(f"{BASE}/images/not-a-uuid", headers=alice)).status_code == 422


async def test_someone_elses_image_is_not_readable(client, alice, bob):
    image_id = await _image_id(client, alice)

    assert (await client.get(f"{BASE}/images/{image_id}", headers=bob)).status_code == 404


# --- Records claim images -----------------------------------------------------------------------


async def test_a_record_claims_the_images_it_holds(client, db_session, alice):
    repository, table, cover, photos = await _album(client, alice)
    cover_id, front_id, back_id = [await _image_id(client, alice, contents) for contents in (PNG, JPEG, GIF)]

    created = await post_record(
        client, alice, repository, table, name="Trip", data={cover: cover_id, photos: {"front": front_id, "back": back_id}}
    )

    assert created["data"] == {cover: cover_id, photos: {"front": front_id, "back": back_id}}
    db_session.expire_all()
    rows = (await db_session.scalars(select(Image).where(Image.id.in_([uuid.UUID(i) for i in (cover_id, front_id, back_id)])))).all()
    assert {str(row.record_id) for row in rows} == {created["id"]}
    assert (await client.get(f"{BASE}/images/{cover_id}", headers=alice)).content == PNG


async def test_an_image_that_does_not_exist_or_is_not_the_callers_cannot_be_used(client, alice, bob):
    repository, table, cover, photos = await _album(client, alice)
    bobs = await _image_id(client, bob)
    nowhere = str(uuid.uuid4())

    for value in (bobs, nowhere):
        resp = await client.post(records_url(repository, table), json={"name": "x", "data": {cover: value}}, headers=alice)
        assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {cover: "invalid_image"}})
    resp = await client.post(records_url(repository, table), json={"name": "x", "data": {photos: {"a": bobs}}}, headers=alice)
    assert resp.json()["detail"] == {"errors": {f"{photos}.a": "invalid_image"}}
    assert (await client.get(f"{BASE}/images/{bobs}", headers=bob)).status_code == 200  # still Bob's, untouched


async def test_an_image_on_one_record_cannot_be_put_on_another(client, alice):
    repository, table, cover, _ = await _album(client, alice)
    image_id = await _image_id(client, alice)
    await post_record(client, alice, repository, table, name="First", data={cover: image_id})

    resp = await client.post(records_url(repository, table), json={"name": "Second", "data": {cover: image_id}}, headers=alice)

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {cover: "invalid_image"}})


async def test_a_record_may_hold_one_image_in_two_places_and_keep_it_when_edited(client, db_session, alice):
    repository, table, cover, photos = await _album(client, alice)
    image_id = await _image_id(client, alice)
    created = await post_record(client, alice, repository, table, name="Trip", data={cover: image_id, photos: {"again": image_id}})

    edited = await client.patch(
        records_url(repository, table, "/trip"), json={"data": {cover: image_id}, "name": "Trip!"}, headers=alice
    )

    assert edited.status_code == 200
    assert await _image_rows(db_session, image_id) == {image_id}
    assert (await client.get(f"{BASE}/images/{image_id}", headers=alice)).status_code == 200
    assert created["data"][photos] == {"again": image_id}


async def test_an_image_the_record_no_longer_holds_is_deleted(client, db_session, alice):
    repository, table, cover, photos = await _album(client, alice)
    old, extra = await _image_id(client, alice), await _image_id(client, alice, JPEG)
    await post_record(client, alice, repository, table, name="Trip", data={cover: old, photos: {"x": extra}})
    new = await _image_id(client, alice, GIF)

    resp = await client.patch(records_url(repository, table, "/trip"), json={"data": {cover: new}}, headers=alice)

    assert resp.status_code == 200
    assert await _image_rows(db_session, old, extra, new) == {new}
    assert (await client.get(f"{BASE}/images/{old}", headers=alice)).status_code == 404
    assert (await client.get(f"{BASE}/images/{new}", headers=alice)).status_code == 200


async def test_editing_only_the_name_keeps_the_images(client, db_session, alice):
    repository, table, cover, _ = await _album(client, alice)
    image_id = await _image_id(client, alice)
    await post_record(client, alice, repository, table, name="Trip", data={cover: image_id})

    await client.patch(records_url(repository, table, "/trip"), json={"name": "Trip!"}, headers=alice)

    assert await _image_rows(db_session, image_id) == {image_id}


async def test_a_failed_save_does_not_claim_or_lose_images(client, db_session, alice):
    repository, table, cover, _ = await _album(client, alice)
    mine = await _image_id(client, alice)

    resp = await client.post(
        records_url(repository, table), json={"name": "x", "data": {cover: mine, "nope": 1}}, headers=alice
    )

    assert resp.status_code == 422
    db_session.expire_all()
    assert (await db_session.get(Image, uuid.UUID(mine))).record_id is None


async def test_deleting_a_record_for_good_deletes_its_images_and_a_soft_delete_keeps_them(client, db_session, alice):
    repository, table, cover, _ = await _album(client, alice)
    image_id = await _image_id(client, alice)
    await post_record(client, alice, repository, table, name="Trip", data={cover: image_id})

    await client.delete(records_url(repository, table, "/trip"), headers=alice)
    assert await _image_rows(db_session, image_id) == {image_id}
    assert (await client.get(f"{BASE}/images/{image_id}", headers=alice)).status_code == 200

    await client.delete(records_url(repository, table, "/trip/permanent"), headers=alice)
    assert await _image_rows(db_session, image_id) == set()


async def test_deleting_a_table_or_a_repository_deletes_the_images_of_its_records(client, db_session, alice):
    repository, table, cover, _ = await _album(client, alice)
    other_repository, other_table, other_cover, _ = await _album(client, alice)
    first, second = await _image_id(client, alice), await _image_id(client, alice, JPEG)
    await post_record(client, alice, repository, table, name="Trip", data={cover: first})
    await post_record(client, alice, other_repository, other_table, name="Trip", data={other_cover: second})

    await client.delete(f"{BASE}/repositories/{repository['slug']}/tables/{table['slug']}", params={"confirm_name": "Albums"}, headers=alice)
    assert await _image_rows(db_session, first, second) == {second}

    await client.delete(f"{BASE}/repositories/{other_repository['slug']}", params={"confirm_name": other_repository["name"]}, headers=alice)
    assert await _image_rows(db_session, first, second) == set()


async def test_removing_an_image_attribute_deletes_the_images_only_it_held(client, db_session, alice):
    repository, table, cover, photos = await _album(client, alice)
    only_cover, shared, only_photo = [await _image_id(client, alice, c) for c in (PNG, JPEG, GIF)]
    await post_record(client, alice, repository, table, name="Trip", data={cover: only_cover, photos: {"a": shared, "b": only_photo}})
    await post_record(client, alice, repository, table, name="Cover too", data={cover: await _image_id(client, alice, WEBP)})
    keep_photos = [attribute("map", "Photos", config={"element_type": "image"}) | {"id": photos}]

    refused = await put_attributes(client, alice, repository["slug"], table["slug"], keep_photos)
    assert refused.status_code == 409
    assert await _image_rows(db_session, only_cover, shared, only_photo) == {only_cover, shared, only_photo}

    done = await put_attributes(client, alice, repository["slug"], table["slug"], keep_photos, confirm_purge="true")

    assert done.status_code == 200
    assert await _image_rows(db_session, only_cover, shared, only_photo) == {shared, only_photo}


async def test_an_image_still_held_by_a_remaining_attribute_survives_the_removal_of_another(client, db_session, alice):
    repository, table, cover, photos = await _album(client, alice)
    image_id = await _image_id(client, alice)
    await post_record(client, alice, repository, table, name="Trip", data={cover: image_id, photos: {"same": image_id}})
    keep_photos = [attribute("map", "Photos", config={"element_type": "image"}) | {"id": photos}]

    done = await put_attributes(client, alice, repository["slug"], table["slug"], keep_photos, confirm_purge="true")

    assert done.status_code == 200
    assert await _image_rows(db_session, image_id) == {image_id}


# --- Uploads nobody claims --------------------------------------------------------------------------


async def test_an_unclaimed_upload_is_deleted_after_the_configured_time_and_a_claimed_one_never(client, db_session, alice):
    repository, table, cover, _ = await _album(client, alice)
    lonely, claimed = await _image_id(client, alice), await _image_id(client, alice, JPEG)
    await post_record(client, alice, repository, table, name="Trip", data={cover: claimed})
    limits = RepositoryConfig(unattached_image_hours=24)
    now = datetime.now(timezone.utc)

    assert await images.purge_unattached(db_session, limits, now + timedelta(hours=23)) == 0
    assert await images.purge_unattached(db_session, limits, now + timedelta(hours=25)) == 1

    assert await _image_rows(db_session, lonely, claimed) == {claimed}
    assert (await client.get(f"{BASE}/images/{lonely}", headers=alice)).status_code == 404


async def test_the_purge_runs_at_most_once_an_hour_when_an_upload_is_made(client, db_session, alice, monkeypatch):
    images.reset_purge_throttle()
    calls = []

    async def counting(db, limits, now=None):
        calls.append(now)
        return 0

    monkeypatch.setattr(images, "purge_unattached", counting)

    await _upload(client, alice)
    await _upload(client, alice, JPEG)

    assert len(calls) == 1
    images.reset_purge_throttle()
    await _upload(client, alice)
    assert len(calls) == 2
    images.reset_purge_throttle()


async def test_a_failing_purge_never_breaks_an_upload(client, alice, monkeypatch):
    images.reset_purge_throttle()

    async def broken(db, limits, now=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(images, "purge_unattached", broken)

    assert (await _upload(client, alice)).status_code == 201
    images.reset_purge_throttle()


# --- Importing by address --------------------------------------------------------------------------------


async def _import(client, headers, url="https://example.com/a.png"):
    return await client.post(f"{BASE}/images/import-url", json={"url": url}, headers=headers)


async def test_an_image_is_imported_from_an_address(client, db_session, alice, monkeypatch):
    seen = {}

    async def fake(url, *, max_bytes, **kwargs):
        seen.update(url=url, max_bytes=max_bytes)
        return JPEG

    monkeypatch.setattr(fetch, "fetch_image_bytes", fake)

    resp = await _import(client, alice, "https://example.com/photo.jpg?size=big")

    assert resp.status_code == 201
    assert (resp.json()["mime"], resp.json()["size_bytes"]) == ("image/jpeg", len(JPEG))
    assert seen == {"url": "https://example.com/photo.jpg?size=big", "max_bytes": RepositoryConfig().max_image_bytes}
    assert (await client.get(f"{BASE}/images/{resp.json()['id']}", headers=alice)).content == JPEG


@pytest.mark.parametrize("code", ["invalid_url", "blocked_port", "unresolvable", "blocked_address", "too_many_redirects", "bad_status", "too_large", "timeout", "network_error"])
async def test_a_failed_download_is_a_422_naming_why(client, alice, monkeypatch, code):
    async def failing(url, **kwargs):
        raise fetch.FetchError(code)

    monkeypatch.setattr(fetch, "fetch_image_bytes", failing)

    resp = await _import(client, alice)

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"url": code}})


async def test_something_downloaded_that_is_not_an_image_is_refused_like_an_upload(client, alice, monkeypatch):
    async def html(url, **kwargs):
        return b"<html>not an image</html>"

    monkeypatch.setattr(fetch, "fetch_image_bytes", html)

    resp = await _import(client, alice)

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"file": "unsupported_type"}})


async def test_an_imported_image_counts_against_the_quota(client, alice, monkeypatch):
    set_limits(max_image_bytes=2048, max_image_bytes_per_user=2048)

    async def big(url, **kwargs):
        return PNG + b"x" * (2000 - len(PNG))

    monkeypatch.setattr(fetch, "fetch_image_bytes", big)

    assert (await _import(client, alice)).status_code == 201
    assert (await _import(client, alice)).status_code == 409


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("http://127.0.0.1/a.png", "blocked_address"),
        ("http://localhost/a.png", "blocked_address"),
        ("http://[::1]/a.png", "blocked_address"),
        ("http://169.254.169.254/latest/meta-data/", "blocked_address"),
        ("http://10.0.0.1/a.png", "blocked_address"),
        ("http://192.168.1.1/a.png", "blocked_address"),
        ("http://example.com:8080/a.png", "blocked_port"),
        ("ftp://example.com/a.png", "invalid_url"),
        ("file:///etc/passwd", "invalid_url"),
        ("http://user:pass@example.com/a.png", "invalid_url"),
        ("not a url", "invalid_url"),
    ],
)
async def test_the_real_downloader_refuses_internal_and_odd_addresses_through_the_api(client, alice, url, code):
    resp = await _import(client, alice, url)

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"url": code}})


async def test_an_address_that_is_far_too_long_is_a_422(client, alice):
    assert (await _import(client, alice, "https://example.com/" + "a" * 2000)).status_code == 422


async def test_images_belong_to_their_users_records_in_the_database(client, db_session, alice):
    repository, table, cover, _ = await _album(client, alice)
    image_id = await _image_id(client, alice)
    created = await post_record(client, alice, repository, table, name="Trip", data={cover: image_id})

    db_session.expire_all()
    image = await db_session.get(Image, uuid.UUID(image_id))
    record = await db_session.get(Record, uuid.UUID(created["id"]))

    assert image.record_id == record.id
    assert image.owner_id is not None
