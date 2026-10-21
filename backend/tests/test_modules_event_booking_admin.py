# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The administrators' side of the booking module: the gate on every /manage
route, registrations (create, edit, blocks, link, delete), the list of bookings
with its filters, one booking's detail, the CSV export and the summary of
answers.

An administrator's changes to a single booking (move, edit, cancel) and
retention are in test_modules_event_booking_changes.py and
test_modules_event_booking_retention.py. Same set-up as the public tests: a
throwaway app, a fixed clock, a rolled-back session."""

import csv
import io
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.modules.event_booking import service
from app.modules.event_booking.models import Booking, Registration, RegistrationBlock
from app.modules.forms import service as forms_service
from app.modules.forms.models import Form, FormQuestion
from tests.booking_support import (  # noqa: F401  (outbox is a fixture)
    BASE,
    GOOD_ANSWERS,
    QUESTIONS,
    Q_EXTRA,
    Q_KIND,
    Q_NOTE,
    TODAY,
    book,
    booking_app,
    clear_tables,
    count_rows,
    dates_block,
    day,
    install_overrides,
    make_article,
    make_event,
    outbox,
    seed,
)

_app = booking_app()


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await clear_tables(db_session)
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    install_overrides(_app, db_session)
    service.reset_purge_throttle()
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    """An administrator of this application (local User.is_admin) - with a
    plain auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    """Not an administrator here - even though the auth service calls them
    "admin": role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


# --- The gate -------------------------------------------------------------------------------------


PUBLIC_ROUTES = {
    ("GET", "/by-events"),
    ("GET", "/registrations/{registration_id}"),
    ("GET", "/registrations/{registration_id}/days"),
    ("GET", "/registrations/{registration_id}/slots"),
    ("POST", "/registrations/{registration_id}/bookings"),
    ("GET", "/bookings/{cancel_token}"),
    ("POST", "/bookings/{cancel_token}/cancel"),
}


def _all_routes():
    """Every (method, path) of the module, read from the OpenAPI schema - the
    router is mounted as one object on newer FastAPI."""
    paths = _app.openapi()["paths"]
    return [(method.upper(), path.removeprefix(BASE)) for path, operations in paths.items() for method in operations]


def _manage_routes():
    return [route for route in _all_routes() if route[1].startswith("/manage")]


def test_every_route_is_either_a_known_public_one_or_under_manage():
    routes = _all_routes()

    assert {route for route in routes if not route[1].startswith("/manage")} == PUBLIC_ROUTES
    assert len(_manage_routes()) == 16


async def _call(client, method: str, path: str, headers: dict):
    concrete = path.replace("{registration_id}", str(uuid.uuid4())).replace("{booking_id}", str(uuid.uuid4()))
    return await client.request(method, f"{BASE}{concrete}", headers=headers)


@pytest.mark.parametrize(("method", "path"), _manage_routes())
async def test_anonymous_requests_are_rejected_on_every_manage_route(client, method, path):
    assert (await _call(client, method, path, headers={})).status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _manage_routes())
async def test_non_admins_are_rejected_on_every_manage_route(client, non_admin, method, path):
    resp = await _call(client, method, path, headers=non_admin)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


# --- Creating and reading registrations ---------------------------------------------------------------


async def _event(db_session, slug="tour", **fields):
    article = await make_article(db_session, slug)
    return await make_event(db_session, article, **fields)


async def _create(client, admin, event, **fields):
    return await client.post(f"{BASE}/manage/registrations", json={"event_id": str(event.id), "name": "Tour sign-up", **fields}, headers=admin)


async def test_an_administrator_creates_the_registration_of_an_event_with_its_form(client, db_session, admin):
    event = await _event(db_session, "tour", title="Castle tour")

    resp = await _create(client, admin, event, description="Come along", access="link", capacity=4, blocks=[dates_block(3, 5, times=["10:00"], capacity=2)])

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["name"], body["description"], body["access"], body["capacity"], body["is_open"]) == ("Tour sign-up", "Come along", "link", 4, True)
    assert body["event_id"] == str(event.id) and body["event_title"] == "Castle tour"
    assert body["article_slug"] == "tour" and body["article_id"] == str(event.article_id)
    assert body["link_token"] and len(body["link_token"]) >= 30
    assert (body["confirmed_count"], body["cancelled_count"]) == (0, 0)
    block = body["blocks"][0]
    assert block["days_mode"] == "dates" and block["dates"] == [day(3).isoformat(), day(5).isoformat()]
    assert block["time_mode"] == "manual" and block["times"] == ["10:00:00"] and block["capacity"] == 2 and block["position"] == 0
    form = await forms_service.get_form(db_session, uuid.UUID(body["form_id"]))
    assert form is not None and form.name == "Tour sign-up"


async def test_defaults_are_public_open_capacity_one_and_no_blocks(client, db_session, admin):
    event = await _event(db_session)

    body = (await _create(client, admin, event)).json()

    assert (body["access"], body["capacity"], body["is_open"], body["blocks"], body["description"]) == ("public", 1, True, [], "")


async def test_blocks_of_every_kind_are_stored_and_returned(client, db_session, admin):
    event = await _event(db_session)
    blocks = [
        dates_block(3),
        {"days_mode": "weekdays", "weekdays": [0, 2], "range_from": day(10).isoformat(), "range_to": day(60).isoformat(), "time_mode": "generated", "slot_minutes": 30, "time_from": "09:00", "time_to": "10:30"},
    ]

    body = (await _create(client, admin, event, blocks=blocks)).json()

    assert [block["position"] for block in body["blocks"]] == [0, 1]
    weekly = body["blocks"][1]
    assert weekly["weekdays"] == [0, 2] and weekly["range_from"] == day(10).isoformat()
    assert (weekly["slot_minutes"], weekly["time_from"], weekly["time_to"]) == (30, "09:00:00", "10:30:00")


async def test_an_unknown_event_is_a_422_and_a_second_registration_for_the_same_event_a_409(client, db_session, admin):
    event = await _event(db_session)

    unknown = await client.post(f"{BASE}/manage/registrations", json={"event_id": str(uuid.uuid4()), "name": "X"}, headers=admin)
    first = await _create(client, admin, event)
    second = await _create(client, admin, event, name="Another")

    assert unknown.status_code == 422 and unknown.json()["detail"] == {"errors": {"event_id": "unknown"}}
    assert first.status_code == 201
    assert second.status_code == 409 and second.json()["detail"] == {"errors": {"event_id": "has_registration"}}
    assert await count_rows(db_session, Registration) == 1 and await count_rows(db_session, Form) == 1


async def test_invalid_blocks_are_a_422_listing_the_problems_and_nothing_is_created(client, db_session, admin):
    event = await _event(db_session)
    blocks = [dates_block(3, times=["10:00"]), dates_block(3), {"days_mode": "weekdays", "weekdays": [], "time_mode": "all_day"}]

    resp = await _create(client, admin, event, blocks=blocks)

    assert resp.status_code == 422
    problems = resp.json()["detail"]["errors"]["blocks"]
    assert any("day of the week" in problem for problem in problems) and any("both ends" in problem for problem in problems)
    assert await count_rows(db_session, Registration) == 0 and await count_rows(db_session, Form) == 0


async def test_a_clash_of_an_all_day_and_a_timed_block_is_refused(client, db_session, admin):
    event = await _event(db_session)

    resp = await _create(client, admin, event, blocks=[dates_block(3), dates_block(3, times=["10:00"])])

    assert resp.status_code == 422
    assert "both all day and timed" in resp.json()["detail"]["errors"]["blocks"][0]


@pytest.mark.parametrize(
    "fields",
    [
        {"capacity": 0},
        {"capacity": 1001},
        {"access": "secret"},
        {"name": ""},
        {"is_open": "maybe"},
        {"blocks": [{"days_mode": "sometimes", "time_mode": "all_day"}]},
        {"blocks": [{"days_mode": "dates", "dates": ["soon"], "time_mode": "all_day"}]},
        {"blocks": [{"days_mode": "any_future", "time_mode": "all_day", "capacity": 0}]},
        {"blocks": [{"days_mode": "any_future", "time_mode": "all_day", "bogus": 1}]},
        {"bogus": 1},
    ],
)
async def test_malformed_registrations_are_422(client, db_session, admin, fields):
    event = await _event(db_session)

    assert (await _create(client, admin, event, **fields)).status_code == 422
    assert await count_rows(db_session, Registration) == 0


async def test_a_registration_is_read_back_with_its_booking_counts(client, db_session, admin):
    _, event, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4, 5)], capacity=2)
    await book(client, registration, offset=3)
    cancelled = (await book(client, registration, offset=4)).json()["cancel_token"]
    await client.post(f"{BASE}/bookings/{cancelled}/cancel")

    body = (await client.get(f"{BASE}/manage/registrations/{registration.id}", headers=admin)).json()

    assert (body["confirmed_count"], body["cancelled_count"]) == (1, 1)
    assert body["link_token"] == registration.link_token and body["form_id"] == str(registration.form_id)
    assert (await client.get(f"{BASE}/manage/registrations/{uuid.uuid4()}", headers=admin)).status_code == 404


async def test_the_list_has_counts_and_can_be_limited_to_an_event(client, db_session, admin):
    _, first_event, first = await seed(db_session, article={"slug": "one"}, blocks=[dates_block(3)], event={"start": day(20)})
    _, second_event, second = await seed(db_session, article={"slug": "two"}, blocks=[dates_block(3)], event={"start": day(5)})
    await book(client, first, offset=3, answers={})

    everything = (await client.get(f"{BASE}/manage/registrations", headers=admin)).json()
    only_second = (await client.get(f"{BASE}/manage/registrations", params={"event_id": str(second_event.id)}, headers=admin)).json()

    assert [item["id"] for item in everything] == [str(first.id), str(second.id)]  # latest event first
    assert (everything[0]["confirmed_count"], everything[1]["confirmed_count"]) == (1, 0)
    assert everything[0]["event_title"] == first_event.title and everything[0]["event_start_date"] == day(20).isoformat()
    assert [item["id"] for item in only_second] == [str(second.id)]
    assert (await client.get(f"{BASE}/manage/registrations", params={"event_id": str(uuid.uuid4())}, headers=admin)).json() == []


# --- The editor's live preview ---------------------------------------------------------------------


async def _preview(client, admin, **body):
    resp = await client.post(f"{BASE}/manage/preview-slots", json=body, headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_the_preview_lists_what_the_blocks_would_offer_from_today(client, admin):
    blocks = [
        dates_block(2, times=["10:00", "11:00"], capacity=3),
        {"days_mode": "dates", "dates": [day(0).isoformat(), day(1).isoformat()], "time_mode": "manual", "times": ["08:00", "12:00"]},
    ]

    body = await _preview(client, admin, blocks=blocks, capacity=2)

    assert body["problems"] == [] and body["total"] == 5
    assert [(slot["date"], slot["time"], slot["capacity"]) for slot in body["slots"]] == [
        (day(0).isoformat(), "12:00:00", 2),  # 08:00 today is already past at the fixed 09:00
        (day(1).isoformat(), "08:00:00", 2),
        (day(1).isoformat(), "12:00:00", 2),
        (day(2).isoformat(), "10:00:00", 3),
        (day(2).isoformat(), "11:00:00", 3),
    ]


async def test_the_preview_of_no_blocks_is_every_future_day_all_day_and_is_cut_off(client, admin):
    body = await _preview(client, admin, blocks=[], capacity=1)

    assert body["total"] > 300 and len(body["slots"]) == service.PREVIEW_LIMIT
    assert body["slots"][0] == {"date": TODAY.isoformat(), "time": None, "capacity": 1}


async def test_the_preview_explains_blocks_that_are_not_acceptable_instead_of_failing(client, admin):
    body = await _preview(client, admin, blocks=[dates_block(3), dates_block(3, times=["10:00"])])

    assert body["slots"] == [] and body["total"] == 0
    assert body["problems"] and "both all day and timed" in body["problems"][0]


async def test_the_preview_saves_nothing_and_rejects_malformed_input(client, db_session, admin):
    await _preview(client, admin, blocks=[dates_block(3)])

    assert await count_rows(db_session, RegistrationBlock) == 0 and await count_rows(db_session, Registration) == 0
    for body in ({"blocks": [{"days_mode": "x", "time_mode": "all_day"}]}, {"capacity": 0}, {"bogus": 1}):
        assert (await client.post(f"{BASE}/manage/preview-slots", json=body, headers=admin)).status_code == 422


# --- Editing ----------------------------------------------------------------------------------------


async def test_a_registration_can_be_edited_field_by_field_and_the_form_name_follows(client, db_session, admin):
    _, _, registration = await seed(db_session, blocks=[dates_block(3)])

    resp = await client.patch(
        f"{BASE}/manage/registrations/{registration.id}",
        json={"name": "Renamed", "description": "New text", "access": "authenticated", "capacity": 6, "is_open": False},
        headers=admin,
    )

    body = resp.json()
    assert resp.status_code == 200
    assert (body["name"], body["description"], body["access"], body["capacity"], body["is_open"]) == ("Renamed", "New text", "authenticated", 6, False)
    assert len(body["blocks"]) == 1  # blocks untouched when not sent
    assert body["link_token"] == registration.link_token
    assert (await forms_service.get_form(db_session, registration.form_id)).name == "Renamed"


async def test_sending_blocks_replaces_the_whole_list_in_order(client, db_session, admin):
    _, _, registration = await seed(db_session, blocks=[dates_block(3), dates_block(4)])

    resp = await client.patch(f"{BASE}/manage/registrations/{registration.id}", json={"blocks": [dates_block(9), dates_block(7, times=["10:00"])]}, headers=admin)

    blocks = resp.json()["blocks"]
    assert [block["dates"] for block in blocks] == [[day(9).isoformat()], [day(7).isoformat()]]
    assert [block["position"] for block in blocks] == [0, 1]
    assert await count_rows(db_session, RegistrationBlock, RegistrationBlock.registration_id == registration.id) == 2

    emptied = await client.patch(f"{BASE}/manage/registrations/{registration.id}", json={"blocks": []}, headers=admin)
    assert emptied.json()["blocks"] == []


async def test_invalid_blocks_on_update_change_nothing(client, db_session, admin):
    _, _, registration = await seed(db_session, blocks=[dates_block(3)])

    resp = await client.patch(f"{BASE}/manage/registrations/{registration.id}", json={"name": "Nope", "blocks": [dates_block(3), dates_block(3, times=["10:00"])]}, headers=admin)

    assert resp.status_code == 422
    body = (await client.get(f"{BASE}/manage/registrations/{registration.id}", headers=admin)).json()
    assert body["name"] == "Sign-up" and len(body["blocks"]) == 1


@pytest.mark.parametrize(
    "fields",
    [{"name": None}, {"access": None}, {"capacity": None}, {"is_open": None}, {"capacity": 0}, {"access": "x"}, {"event_id": str(uuid.uuid4())}, {"bogus": 1}],
)
async def test_malformed_updates_are_422(client, db_session, admin, fields):
    _, _, registration = await seed(db_session)

    assert (await client.patch(f"{BASE}/manage/registrations/{registration.id}", json=fields, headers=admin)).status_code == 422
    assert (await client.patch(f"{BASE}/manage/registrations/{uuid.uuid4()}", json={"name": "x"}, headers=admin)).status_code == 404


async def test_existing_bookings_survive_a_change_of_blocks_and_capacity(client, db_session, admin):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])
    await book(client, registration, offset=3)

    await client.patch(f"{BASE}/manage/registrations/{registration.id}", json={"blocks": [dates_block(8)], "capacity": 1}, headers=admin)

    assert await count_rows(db_session, Booking, Booking.status == "confirmed") == 1
    assert (await client.get(f"{BASE}/registrations/{registration.id}/days")).json()["days"][0]["date"] == day(8).isoformat()


async def test_regenerating_the_link_stops_the_old_one_working(client, db_session, admin):
    _, event, registration = await seed(db_session, access="link", blocks=[dates_block(3)])
    old = registration.link_token

    resp = await client.post(f"{BASE}/manage/registrations/{registration.id}/regenerate-link", headers=admin)

    new = resp.json()["link_token"]
    assert resp.status_code == 200 and new != old and len(new) >= 30
    assert (await client.get(f"{BASE}/registrations/{registration.id}", params={"token": old})).status_code == 404
    assert (await client.get(f"{BASE}/registrations/{registration.id}", params={"token": new})).status_code == 200
    assert (await client.get(f"{BASE}/by-events", params={"ids": str(event.id), "token": old})).json() == []
    assert (await client.post(f"{BASE}/manage/registrations/{uuid.uuid4()}/regenerate-link", headers=admin)).status_code == 404


# --- Deleting ------------------------------------------------------------------------------------------


async def test_a_registration_without_bookings_is_deleted_with_its_blocks_and_form(client, db_session, admin):
    _, event, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])
    form_id = registration.form_id

    resp = await client.delete(f"{BASE}/manage/registrations/{registration.id}", headers=admin)

    assert resp.status_code == 204
    assert await count_rows(db_session, Registration) == 0
    assert await count_rows(db_session, RegistrationBlock) == 0
    assert await db_session.get(Form, form_id) is None
    assert await count_rows(db_session, FormQuestion) == 0
    assert (await client.delete(f"{BASE}/manage/registrations/{registration.id}", headers=admin)).status_code == 404
    assert (await _create(client, admin, event)).status_code == 201  # the event is free for a new one


@pytest.mark.parametrize("cancel", [False, True])
async def test_a_registration_with_bookings_cannot_be_deleted_even_cancelled_ones(client, db_session, admin, cancel):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])
    token = (await book(client, registration, offset=3)).json()["cancel_token"]
    if cancel:
        await client.post(f"{BASE}/bookings/{token}/cancel")

    resp = await client.delete(f"{BASE}/manage/registrations/{registration.id}", headers=admin)

    assert resp.status_code == 409 and resp.json()["detail"] == {"errors": {"_form": "has_bookings"}}
    assert await count_rows(db_session, Registration) == 1 and await count_rows(db_session, Booking) == 1


async def test_an_event_with_a_registration_cannot_be_deleted(db_session):
    _, event, _ = await seed(db_session)

    await db_session.delete(event)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# --- The days and times an administrator can move a booking to ---------------------------------------


async def test_the_administrators_pickers_include_the_bookings_own_full_slot(client, db_session, admin):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00", "11:00"]), dates_block(4, times=["10:00"])])
    mine = (await book(client, registration, offset=3, slot_time="10:00")).json()["cancel_token"]
    await book(client, registration, offset=4, slot_time="10:00", email="b@example.com")
    booking = await service.get_booking_by_token(db_session, mine)

    plain = (await client.get(f"{BASE}/manage/registrations/{registration.id}/days", headers=admin)).json()["days"]
    including = (await client.get(f"{BASE}/manage/registrations/{registration.id}/days", params={"booking_id": str(booking.id)}, headers=admin)).json()["days"]
    slots_plain = (await client.get(f"{BASE}/manage/registrations/{registration.id}/slots", params={"date": day(3).isoformat()}, headers=admin)).json()["slots"]
    slots_including = (await client.get(f"{BASE}/manage/registrations/{registration.id}/slots", params={"date": day(3).isoformat(), "booking_id": str(booking.id)}, headers=admin)).json()["slots"]

    assert [item["date"] for item in plain] == [day(3).isoformat()]  # day 4 is full
    assert [(item["date"], item["free_slots"]) for item in including] == [(day(3).isoformat(), 2)]
    assert [slot["time"] for slot in slots_plain] == ["11:00:00"]
    assert [(slot["time"], slot["free"]) for slot in slots_including] == [("10:00:00", 1), ("11:00:00", 1)]


async def test_the_pickers_offer_a_registration_that_is_closed_and_reject_a_foreign_booking(client, db_session, admin):
    _, _, registration = await seed(db_session, blocks=[dates_block(3)], is_open=False)
    _, _, other = await seed(db_session, article={"slug": "other"}, blocks=[dates_block(3)])
    other_booking = Booking(registration_id=other.id, slot_date=day(3), name="X", email="x@example.com", consent_at=datetime.now(timezone.utc), language="cs")
    db_session.add(other_booking)
    await db_session.commit()

    days = (await client.get(f"{BASE}/manage/registrations/{registration.id}/days", headers=admin)).json()["days"]
    foreign = await client.get(f"{BASE}/manage/registrations/{registration.id}/days", params={"booking_id": str(other_booking.id)}, headers=admin)
    unknown = await client.get(f"{BASE}/manage/registrations/{uuid.uuid4()}/days", headers=admin)

    assert [item["date"] for item in days] == [day(3).isoformat()]
    assert foreign.status_code == 404 and unknown.status_code == 404


# --- The list of bookings and one booking ---------------------------------------------------------------


async def _bookings(client, registration, specs):
    """Books (offset, time, name, email) with default answers; returns the cancel tokens."""
    tokens = []
    for offset, slot_time, name, email in specs:
        resp = await book(client, registration, offset=offset, slot_time=slot_time, name=name, email=email)
        assert resp.status_code == 201, resp.text
        tokens.append(resp.json()["cancel_token"])
    return tokens


async def _list(client, admin, registration, **params):
    resp = await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings", params=params, headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _seed_list(client, db_session):
    _, _, registration = await seed(
        db_session,
        questions=QUESTIONS,
        blocks=[dates_block(3, 4, times=["09:30", "10:30"]), dates_block(5)],
        capacity=3,
    )
    tokens = await _bookings(
        client,
        registration,
        [
            (4, "10:30", "Zdeněk Dvořák", "zdenek@example.com"),
            (3, "10:30", "Alena Králová", "alena@example.com"),
            (5, None, "Bohumil Černý", "bohumil@example.org"),
            (3, "09:30", "Cecilie 100%", "cecilie@example.com"),
        ],
    )
    return registration, tokens


async def test_the_bookings_are_listed_by_their_slot_with_a_total(client, db_session, admin):
    registration, _ = await _seed_list(client, db_session)

    page = await _list(client, admin, registration)

    assert page["total"] == 4
    assert [(item["slot_date"], item["slot_time"], item["name"]) for item in page["items"]] == [
        (day(3).isoformat(), "09:30:00", "Cecilie 100%"),
        (day(3).isoformat(), "10:30:00", "Alena Králová"),
        (day(4).isoformat(), "10:30:00", "Zdeněk Dvořák"),
        (day(5).isoformat(), None, "Bohumil Černý"),
    ]
    first = page["items"][0]
    assert first["email"] == "cecilie@example.com" and first["status"] == "confirmed" and first["has_history"] is False and first["created_at"]
    descending = await _list(client, admin, registration, sort="desc")
    assert [item["name"] for item in descending["items"]] == ["Bohumil Černý", "Zdeněk Dvořák", "Alena Králová", "Cecilie 100%"]


async def test_the_list_can_be_filtered_by_status_dates_and_text(client, db_session, admin):
    registration, tokens = await _seed_list(client, db_session)
    await client.post(f"{BASE}/bookings/{tokens[1]}/cancel")  # Alena

    cancelled = await _list(client, admin, registration, status="cancelled")
    confirmed = await _list(client, admin, registration, status="confirmed")
    window = await _list(client, admin, registration, date_from=day(4).isoformat(), date_to=day(4).isoformat())
    from_day = await _list(client, admin, registration, date_from=day(4).isoformat())
    by_name = await _list(client, admin, registration, q="králov")
    by_email = await _list(client, admin, registration, q="EXAMPLE.ORG")
    percent = await _list(client, admin, registration, q="100%")
    wildcard = await _list(client, admin, registration, q="%")
    underscore = await _list(client, admin, registration, q="_")

    assert [item["name"] for item in cancelled["items"]] == ["Alena Králová"] and cancelled["total"] == 1
    assert confirmed["total"] == 3
    assert [item["name"] for item in window["items"]] == ["Zdeněk Dvořák"]
    assert from_day["total"] == 2
    assert [item["name"] for item in by_name["items"]] == ["Alena Králová"]
    assert [item["name"] for item in by_email["items"]] == ["Bohumil Černý"]
    assert [item["name"] for item in percent["items"]] == ["Cecilie 100%"]
    assert [item["name"] for item in wildcard["items"]] == ["Cecilie 100%"]  # a % is not a wildcard
    assert underscore["total"] == 0  # nor is an underscore
    assert (await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings", params={"status": "weird"}, headers=admin)).status_code == 422


async def test_the_list_is_paged(client, db_session, admin):
    registration, _ = await _seed_list(client, db_session)

    first = await _list(client, admin, registration, limit=3)
    second = await _list(client, admin, registration, limit=3, offset=3)

    assert (len(first["items"]), len(second["items"]), first["total"], second["total"]) == (3, 1, 4, 4)
    assert {item["id"] for item in first["items"]}.isdisjoint(item["id"] for item in second["items"])
    for params in ({"limit": 0}, {"limit": 201}, {"offset": -1}):
        assert (await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings", params=params, headers=admin)).status_code == 422


async def test_the_list_belongs_to_one_registration_and_an_unknown_one_is_a_404(client, db_session, admin):
    registration, _ = await _seed_list(client, db_session)
    _, _, other = await seed(db_session, article={"slug": "other"}, blocks=[dates_block(3)])

    assert (await _list(client, admin, other))["total"] == 0
    assert (await _list(client, admin, registration))["total"] == 4
    assert (await client.get(f"{BASE}/manage/registrations/{uuid.uuid4()}/bookings", headers=admin)).status_code == 404


async def test_a_booking_is_shown_with_every_field_its_answers_and_no_history_yet(client, db_session, admin):
    _, event, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00"])], name="Tour sign-up", event={"title": "Castle tour"})
    token = (await book(client, registration, offset=3, slot_time="10:00", answers={Q_NOTE: "Hi", Q_KIND: "b", Q_EXTRA: "More"}, language="en")).json()["cancel_token"]
    booking = await service.get_booking_by_token(db_session, token)

    resp = await client.get(f"{BASE}/manage/bookings/{booking.id}", headers=admin)

    body = resp.json()
    assert resp.status_code == 200
    assert body["id"] == str(booking.id) and body["registration_id"] == str(registration.id)
    assert (body["event_title"], body["registration_name"]) == ("Castle tour", "Tour sign-up")
    assert (body["slot_date"], body["slot_time"], body["name"], body["email"]) == (day(3).isoformat(), "10:00:00", "Eva Nováková", "eva@example.com")
    assert (body["language"], body["status"], body["user_sub"], body["cancelled_at"]) == ("en", "confirmed", None, None)
    assert body["consent_at"] and body["created_at"] and body["updated_at"]
    assert {entry["question_id"]: entry["display"] for entry in body["answers"] if entry["shown"]} == {Q_NOTE: "Hi", Q_KIND: "Beta", Q_EXTRA: "More"}
    assert body["history"] == []
    assert "cancel_token" not in body
    assert (await client.get(f"{BASE}/manage/bookings/{uuid.uuid4()}", headers=admin)).status_code == 404


# --- CSV ------------------------------------------------------------------------------------------------


def _csv_rows(resp) -> list[list[str]]:
    text = resp.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";"))


async def test_the_csv_is_utf8_with_a_bom_semicolons_one_column_per_question_and_every_booking(client, db_session, admin):
    registration, tokens = await _seed_list(client, db_session)
    await client.post(f"{BASE}/bookings/{tokens[1]}/cancel")

    resp = await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings.csv", headers=admin)

    assert resp.status_code == 200
    assert resp.content.startswith(b"\xef\xbb\xbf")
    assert resp.headers["content-type"] == "text/csv; charset=utf-8"
    assert resp.headers["content-disposition"].startswith('attachment; filename="bookings-') and resp.headers["cache-control"] == "no-store"
    rows = _csv_rows(resp)
    assert rows[0] == ["Datum", "Čas", "Jméno", "E-mail", "Stav", "Vytvořeno", "Souhlas udělen", "Note", "Kind", "Extra"]
    assert len(rows) == 5
    assert rows[1][:5] == [f"{day(3).day}. {day(3).month}. {day(3).year}", "09:30", "Cecilie 100%", "cecilie@example.com", "potvrzená"]
    assert rows[2][4] == "zrušená" and rows[2][2] == "Alena Králová"
    assert rows[4][1] == "celý den"
    assert rows[1][7:] == ["hello", "Alpha", ""]  # the hidden question's cell is empty


async def test_cells_that_could_run_as_a_formula_are_neutralised(client, db_session, admin):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4, 5, 6)], capacity=5)
    dangerous = ["=HYPERLINK(\"http://evil\")", "+1+1", "-2+3", "@SUM(A1)"]
    for index, text in enumerate(dangerous):
        resp = await book(client, registration, offset=3 + index, name=text, answers={Q_NOTE: text, Q_KIND: "a"}, email=f"p{index}@example.com")
        assert resp.status_code == 201

    rows = _csv_rows(await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings.csv", headers=admin))

    for row, text in zip(rows[1:], dangerous, strict=True):
        assert row[2] == "'" + text  # the name
        assert row[7] == "'" + text  # an answer
    assert rows[1][3] == "p0@example.com" and not any(cell.startswith(("=", "+", "-", "@")) for row in rows for cell in row)


async def test_csv_neutralisation_leaves_ordinary_cells_alone():
    assert service.csv_cell("Eva") == "Eva" and service.csv_cell(None) == "" and service.csv_cell(5) == "5"
    for text in ("=1", "+1", "-1", "@a", "\tcmd", "\rcmd"):
        assert service.csv_cell(text) == "'" + text
    assert service.csv_cell("a=b") == "a=b"


async def test_a_question_that_is_gone_from_the_form_still_has_its_column(client, db_session, admin):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4)], capacity=2)
    await book(client, registration, offset=3)
    from app.modules.forms.schemas import QuestionsReplace

    kept = QuestionsReplace.model_validate({"questions": [QUESTIONS[0]]})
    await forms_service.replace_questions(db_session, registration.form_id, kept.questions)
    await db_session.commit()

    rows = _csv_rows(await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings.csv", headers=admin))

    assert rows[0][7:] == ["Note", "Kind", "Extra"]
    assert rows[1][7:] == ["hello", "Alpha", ""]


async def test_the_csv_of_a_registration_without_bookings_is_just_the_header(client, db_session, admin):
    _, _, registration = await seed(db_session, questions=QUESTIONS)

    rows = _csv_rows(await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings.csv", headers=admin))

    assert len(rows) == 1 and rows[0][7:] == ["Note", "Kind", "Extra"]
    assert (await client.get(f"{BASE}/manage/registrations/{uuid.uuid4()}/bookings.csv", headers=admin)).status_code == 404


# --- The summary of the answers ------------------------------------------------------------------------


async def test_the_summary_counts_only_confirmed_bookings(client, db_session, admin):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)], capacity=5)
    await book(client, registration, offset=3, email="a@example.com", answers={Q_NOTE: "x", Q_KIND: "a"})
    await book(client, registration, offset=3, email="b@example.com", answers={Q_NOTE: "y", Q_KIND: "a"})
    gone = (await book(client, registration, offset=3, email="c@example.com", answers={Q_NOTE: "z", Q_KIND: "b", Q_EXTRA: "e"})).json()["cancel_token"]

    before = (await client.get(f"{BASE}/manage/registrations/{registration.id}/answers/stats", headers=admin)).json()
    await client.post(f"{BASE}/bookings/{gone}/cancel")
    after = (await client.get(f"{BASE}/manage/registrations/{registration.id}/answers/stats", headers=admin)).json()

    def kind(stats):
        return next(question for question in stats["questions"] if question["question_id"] == Q_KIND)

    assert before["submission_count"] == 3 and after["submission_count"] == 2
    assert {option["label"]: option["count"] for option in kind(before)["options"]} == {"Alpha": 2, "Beta": 1}
    assert {option["label"]: option["count"] for option in kind(after)["options"] if option["count"]} == {"Alpha": 2}
    assert (await client.get(f"{BASE}/manage/registrations/{uuid.uuid4()}/answers/stats", headers=admin)).status_code == 404


async def test_the_summary_of_a_registration_without_confirmed_bookings_is_empty(client, db_session, admin):
    _, _, registration = await seed(db_session, questions=QUESTIONS)

    stats = (await client.get(f"{BASE}/manage/registrations/{registration.id}/answers/stats", headers=admin)).json()

    assert stats["submission_count"] == 0 and stats["questions"] == []


async def test_registrations_in_a_forms_own_listing_are_not_mixed_up(client, db_session, admin):
    """Two registrations have two forms: the summary of one never sees the other's answers."""
    _, _, first = await seed(db_session, article={"slug": "one"}, questions=QUESTIONS, blocks=[dates_block(3)])
    _, _, second = await seed(db_session, article={"slug": "two"}, blocks=[dates_block(3)])
    await book(client, first, offset=3)
    await book(client, second, offset=3, answers={})

    first_stats = (await client.get(f"{BASE}/manage/registrations/{first.id}/answers/stats", headers=admin)).json()
    second_stats = (await client.get(f"{BASE}/manage/registrations/{second.id}/answers/stats", headers=admin)).json()

    assert first_stats["submission_count"] == 1 and second_stats["submission_count"] == 1
    assert len(first_stats["questions"]) == 3 and second_stats["questions"] == []
    assert first.form_id != second.form_id
    assert (await db_session.scalars(select(Booking.submission_id))).all()
