# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The administrators' side of the table reservations module: the gate on every
/manage route, the calendar of reservations, cancelling a reservation with a
message to the guest, opening hours and one-off changes of a day (which cannot
close or shorten a day that has reservations until the pub has resolved them one
by one), tables, and retention.

Same set-up as the public tests: a throwaway app, a fixed clock (today, 09:00), a
rolled-back session, a pub open 10:00-22:00 every day."""

import logging
import uuid
from datetime import date, datetime, time

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.user import User
from app.modules.table_reservations import mail as reservation_mail
from app.modules.table_reservations import service
from app.modules.table_reservations.models import OpeningException, Reservation
from tests.reservation_support import (  # noqa: F401  (outbox and _fast_fqdn are fixtures)
    BASE,
    NOW,
    TODAY,
    _fast_fqdn,
    clear_tables,
    count_rows,
    day,
    install_overrides,
    make_exception,
    make_table,
    outbox,
    reservation_body,
    reservations_app,
    reserve,
    seed_hours,
    seed_pub,
    stored,
    text_of,
    to_of,
)

_app = reservations_app()


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
    """An administrator of this application (local User.is_admin) - with a plain
    auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    """Not an administrator here - even though the auth service calls them "admin":
    role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


def at_clock(db_session, hour: int, minute: int = 0) -> None:
    install_overrides(_app, db_session, now=datetime.combine(TODAY, time(hour, minute)))


# --- The gate -----------------------------------------------------------------------------------------


PUBLIC_ROUTES = {
    ("GET", "/info"),
    ("GET", "/days"),
    ("GET", "/availability"),
    ("POST", "/reservations"),
    ("GET", "/reservations/{cancel_token}"),
    ("POST", "/reservations/{cancel_token}/cancel"),
}


def _all_routes():
    """Every (method, path) of the module, read from the OpenAPI schema - the router
    is mounted as one object on newer FastAPI."""
    paths = _app.openapi()["paths"]
    return [(method.upper(), path.removeprefix(BASE)) for path, operations in paths.items() for method in operations]


def _manage_routes():
    return [route for route in _all_routes() if route[1].startswith("/manage")]


def test_every_route_is_either_a_known_public_one_or_under_manage():
    routes = _all_routes()

    assert {route for route in routes if not route[1].startswith("/manage")} == PUBLIC_ROUTES
    assert len(_manage_routes()) == 13


async def _call(client, method: str, path: str, headers: dict):
    concrete = (
        path.replace("{reservation_id}", str(uuid.uuid4()))
        .replace("{table_id}", str(uuid.uuid4()))
        .replace("{day}", day(1).isoformat())
    )
    return await client.request(method, f"{BASE}{concrete}", headers=headers)


@pytest.mark.parametrize(("method", "path"), _manage_routes())
async def test_anonymous_requests_are_rejected_on_every_manage_route(client, method, path):
    assert (await _call(client, method, path, headers={})).status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _manage_routes())
async def test_non_admins_are_rejected_on_every_manage_route(client, non_admin, method, path):
    resp = await _call(client, method, path, headers=non_admin)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


# --- The calendar of reservations -------------------------------------------------------------------------


def list_params(first: int = 0, last: int = 7, **extra) -> dict:
    return {"date_from": day(first).isoformat(), "date_to": day(last).isoformat(), **extra}


async def test_the_list_gives_the_reservations_of_a_range_by_day_and_start_with_the_table(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(2, 4))
    await reserve(client, 3, "19:00", party_size=2, email="c@example.com", name="Third")
    await reserve(client, 1, "20:00", party_size=3, email="a@example.com", name="First", phone="+420 1", note="quiet corner")
    await reserve(client, 1, "12:00", party_size=2, email="b@example.com", name="Earlier")
    await reserve(client, 2, "19:00", kind="whole_venue", party_size=30, email="w@example.com", name="Everyone")
    await reserve(client, 20, "19:00", party_size=2, email="far@example.com", name="Out of range")

    resp = await client.get(f"{BASE}/manage/reservations", params=list_params(), headers=admin)

    assert resp.status_code == 200
    rows = resp.json()
    assert [row["name"] for row in rows] == ["Earlier", "First", "Everyone", "Third"]  # by day, then start
    assert [(row["table_name"], row["kind"]) for row in rows] == [(tables[0].name, "table"), (tables[1].name, "table"), (None, "whole_venue"), (tables[0].name, "table")]
    first = rows[1]
    assert (first["email"], first["phone"], first["note"], first["party_size"], first["status"]) == ("a@example.com", "+420 1", "quiet corner", 3, "confirmed")
    assert (first["day"], first["start_time"], first["end_time"], first["language"]) == (day(1).isoformat(), "20:00:00", "22:00:00", "cs")
    assert first["consent_at"] and first["created_at"] and first["cancelled_at"] is None


async def test_the_list_can_show_only_confirmed_or_only_cancelled_reservations(client, admin, db_session):
    await seed_pub(db_session)
    kept = (await reserve(client, 1, "18:00", email="a@example.com", name="Kept")).json()["cancel_token"]
    gone = (await reserve(client, 1, "18:00", email="b@example.com", name="Gone")).json()["cancel_token"]
    await client.post(f"{BASE}/reservations/{gone}/cancel")

    both = (await client.get(f"{BASE}/manage/reservations", params=list_params(), headers=admin)).json()
    confirmed = (await client.get(f"{BASE}/manage/reservations", params=list_params(status="confirmed"), headers=admin)).json()
    cancelled = (await client.get(f"{BASE}/manage/reservations", params=list_params(status="cancelled"), headers=admin)).json()

    assert sorted(row["name"] for row in both) == ["Gone", "Kept"]
    assert [row["name"] for row in confirmed] == ["Kept"]
    assert [(row["name"], row["cancelled_by"]) for row in cancelled] == [("Gone", "guest")]
    assert kept != gone


async def test_a_bad_range_or_status_is_refused(client, admin, db_session):
    backwards = await client.get(f"{BASE}/manage/reservations", params={"date_from": day(5).isoformat(), "date_to": day(1).isoformat()}, headers=admin)
    too_wide = await client.get(f"{BASE}/manage/reservations", params=list_params(0, 62), headers=admin)
    widest = await client.get(f"{BASE}/manage/reservations", params=list_params(0, 61), headers=admin)
    bad_status = await client.get(f"{BASE}/manage/reservations", params=list_params(status="maybe"), headers=admin)
    missing = await client.get(f"{BASE}/manage/reservations", headers=admin)

    assert backwards.status_code == 422 and backwards.json()["detail"] == {"errors": {"date_to": "bad_range"}}
    assert too_wide.status_code == 422
    assert widest.status_code == 200  # 62 days
    assert bad_status.status_code == 422 and missing.status_code == 422


async def test_one_reservation_can_be_read_with_everything_known_about_it(client, admin, db_session):
    await seed_pub(db_session)
    token = (await reserve(client, 1, "18:00", phone="+420 1", note="n")).json()["cancel_token"]
    row = await stored(db_session, token)

    resp = await client.get(f"{BASE}/manage/reservations/{row.id}", headers=admin)

    assert resp.status_code == 200
    assert resp.json()["id"] == str(row.id) and resp.json()["email"] == "eva@example.com" and resp.json()["notified"] is None
    assert (await client.get(f"{BASE}/manage/reservations/{uuid.uuid4()}", headers=admin)).status_code == 404


# --- The pub cancels a reservation -----------------------------------------------------------------------------


async def test_the_pub_cancels_with_a_message_and_the_guest_is_told(client, admin, db_session, outbox):
    await seed_pub(db_session, seats=(4,))
    token = (await reserve(client, 2, "18:00", party_size=3)).json()["cancel_token"]
    row = await stored(db_session, token)
    outbox.clear()

    resp = await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "  The kitchen is closed that evening. "}, headers=admin)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email_sent"] is True
    assert (body["reservation"]["status"], body["reservation"]["cancelled_by"], body["reservation"]["cancel_note"], body["reservation"]["notified"]) == (
        "cancelled",
        "admin",
        "The kitchen is closed that evening.",
        True,
    )
    assert body["reservation"]["cancelled_at"] and body["reservation"]["email_error"] is None
    assert [to_of(m) for m in outbox] == ["eva@example.com"]
    text = text_of(outbox[0])
    assert outbox[0]["Subject"] == f"Zrušení Vaší rezervace: {day(2).day}. {day(2).month}. {day(2).year} v 18:00"
    assert "Vzkaz od hospůdky:\nThe kitchen is closed that evening." in text
    assert "18:00–20:00" in text and "Eva Nováková" in text
    assert "/reservations/cancel/" not in text  # a cancelled reservation has nothing left to cancel
    refreshed = await stored(db_session, token)
    assert refreshed.cancelled_by_sub is not None


async def test_the_message_is_optional_and_then_the_mail_has_no_heading(client, admin, db_session, outbox):
    await seed_pub(db_session)
    row = await stored(db_session, (await reserve(client, 1)).json()["cancel_token"])
    outbox.clear()

    resp = await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={}, headers=admin)

    assert resp.status_code == 200 and resp.json()["email_sent"] is True
    assert resp.json()["reservation"]["cancel_note"] is None
    assert "Vzkaz od hospůdky" not in text_of(outbox[0])
    assert "Za nepříjemnosti se omlouváme" in text_of(outbox[0])


async def test_the_mail_to_the_guest_is_in_the_language_they_reserved_in(client, admin, db_session, outbox):
    await seed_pub(db_session)
    row = await stored(db_session, (await reserve(client, 1, language="en")).json()["cancel_token"])
    outbox.clear()

    await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "Sorry!"}, headers=admin)

    assert outbox[0]["Subject"].startswith("Your reservation has been cancelled")
    assert "A message from the pub:\nSorry!" in text_of(outbox[0])


async def test_cancelling_without_notifying_sends_nothing(client, admin, db_session, outbox):
    await seed_pub(db_session)
    row = await stored(db_session, (await reserve(client, 1)).json()["cancel_token"])
    outbox.clear()

    resp = await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "Not sent", "notify": False}, headers=admin)

    assert resp.status_code == 200 and resp.json()["email_sent"] is None
    assert resp.json()["reservation"]["status"] == "cancelled" and resp.json()["reservation"]["notified"] is None
    assert resp.json()["reservation"]["cancel_note"] == "Not sent"  # kept with the reservation anyway
    assert outbox == []


async def test_a_mail_that_cannot_be_sent_is_reported_and_the_cancellation_stands(client, admin, db_session, monkeypatch, caplog):
    await seed_pub(db_session, seats=(4,))
    row = await stored(db_session, (await reserve(client, 1, "18:00", party_size=3)).json()["cancel_token"])

    async def broken(*args, **kwargs):
        raise OSError("smtp is down")

    monkeypatch.setattr(reservation_mail, "send_email", broken)

    with caplog.at_level(logging.ERROR):
        resp = await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "Sorry"}, headers=admin)

    assert resp.status_code == 200 and resp.json()["email_sent"] is False
    body = resp.json()["reservation"]
    assert (body["status"], body["notified"], body["email_error"]) == ("cancelled", False, "smtp is down")
    assert (await reserve(client, 1, "18:00", party_size=3, email="b@example.com")).status_code == 201  # the table is free


async def test_cancelling_again_changes_and_sends_nothing(client, admin, db_session, outbox):
    await seed_pub(db_session)
    row = await stored(db_session, (await reserve(client, 1)).json()["cancel_token"])
    first = await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "First"}, headers=admin)
    outbox.clear()

    again = await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "Second"}, headers=admin)

    assert again.status_code == 200 and again.json()["email_sent"] is None
    assert again.json()["reservation"]["cancel_note"] == "First"
    assert again.json()["reservation"]["cancelled_at"] == first.json()["reservation"]["cancelled_at"]
    assert outbox == []


async def test_a_reservation_the_guest_cancelled_stays_theirs(client, admin, db_session, outbox):
    await seed_pub(db_session)
    token = (await reserve(client, 1)).json()["cancel_token"]
    await client.post(f"{BASE}/reservations/{token}/cancel")
    row = await stored(db_session, token)
    outbox.clear()

    resp = await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "Late"}, headers=admin)

    assert resp.status_code == 200 and resp.json()["email_sent"] is None
    assert resp.json()["reservation"]["cancelled_by"] == "guest" and resp.json()["reservation"]["cancel_note"] is None
    assert outbox == []


async def test_cancelling_validates_the_body_and_the_id(client, admin, db_session):
    await seed_pub(db_session)
    row = await stored(db_session, (await reserve(client, 1)).json()["cancel_token"])

    assert (await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "x" * 1001}, headers=admin)).status_code == 422
    assert (await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"surprise": 1}, headers=admin)).status_code == 422
    assert (await client.post(f"{BASE}/manage/reservations/{uuid.uuid4()}/cancel", json={}, headers=admin)).status_code == 404
    assert (await stored(db_session, row.cancel_token)).status == "confirmed"


# --- Opening hours -------------------------------------------------------------------------------------------------


def week(opens: str = "10:00", closes: str = "22:00", overrides: dict | None = None) -> dict:
    """The body of PUT /manage/opening-hours: every weekday open `opens`-`closes`,
    `overrides` keyed by weekday (e.g. {6: {"is_closed": True}})."""
    days = []
    for weekday in range(7):
        entry = {"weekday": weekday, "is_closed": False, "opens": opens, "closes": closes}
        entry.update((overrides or {}).get(weekday, {}))
        days.append(entry)
    return {"days": days}


async def test_the_regular_hours_of_a_pub_not_set_up_yet_are_closed_every_day(client, admin, db_session):
    resp = await client.get(f"{BASE}/manage/opening-hours", headers=admin)

    assert resp.status_code == 200
    assert resp.json() == [{"weekday": n, "is_closed": True, "opens": None, "closes": None} for n in range(7)]


async def test_the_pub_sets_the_hours_of_the_whole_week_and_changes_them(client, admin, db_session):
    first = await client.put(f"{BASE}/manage/opening-hours", json=week("11:00", "23:00", {5: {"opens": "12:00", "closes": "23:30"}, 6: {"is_closed": True}}), headers=admin)

    assert first.status_code == 200, first.text
    by_day = {entry["weekday"]: entry for entry in first.json()}
    assert (by_day[0]["opens"], by_day[0]["closes"]) == ("11:00:00", "23:00:00")
    assert (by_day[5]["opens"], by_day[5]["closes"]) == ("12:00:00", "23:30:00")
    assert by_day[6] == {"weekday": 6, "is_closed": True, "opens": None, "closes": None}

    second = await client.put(f"{BASE}/manage/opening-hours", json=week("10:00", "22:00"), headers=admin)
    stored_week = (await client.get(f"{BASE}/manage/opening-hours", headers=admin)).json()

    assert second.status_code == 200 and stored_week == second.json()
    assert all((entry["is_closed"], entry["opens"], entry["closes"]) == (False, "10:00:00", "22:00:00") for entry in stored_week)


async def test_hours_that_make_no_sense_are_refused_at_their_weekday(client, admin, db_session):
    backwards = await client.put(f"{BASE}/manage/opening-hours", json=week(overrides={2: {"opens": "22:00", "closes": "10:00"}}), headers=admin)
    too_short = await client.put(f"{BASE}/manage/opening-hours", json=week(overrides={3: {"opens": "10:00", "closes": "10:15"}}), headers=admin)
    missing = await client.put(f"{BASE}/manage/opening-hours", json=week(overrides={4: {"opens": None}}), headers=admin)

    assert backwards.status_code == 422 and backwards.json()["detail"] == {"errors": {"weekday_2_closes": "closes_before_opens"}}
    assert too_short.status_code == 422 and too_short.json()["detail"] == {"errors": {"weekday_3_closes": "too_short"}}
    assert missing.status_code == 422 and missing.json()["detail"] == {"errors": {"weekday_4_opens": "required"}}
    assert (await client.get(f"{BASE}/manage/opening-hours", headers=admin)).json()[0]["is_closed"] is True  # nothing was saved


async def test_every_weekday_must_be_given_exactly_once(client, admin, db_session):
    twice = week()
    twice["days"][6]["weekday"] = 5
    short = {"days": week()["days"][:6]}

    assert (await client.put(f"{BASE}/manage/opening-hours", json=twice, headers=admin)).status_code == 422
    assert (await client.put(f"{BASE}/manage/opening-hours", json=short, headers=admin)).status_code == 422
    assert (await client.put(f"{BASE}/manage/opening-hours", json=week(overrides={1: {"weekday": 9}}), headers=admin)).status_code == 422


async def test_shortening_the_hours_is_refused_while_a_reservation_would_fall_outside_them(client, admin, db_session):
    await seed_pub(db_session)
    token = (await reserve(client, 2, "20:00", party_size=2)).json()["cancel_token"]  # 20:00-22:00
    weekday = day(2).weekday()
    shorter = week("10:00", "21:00")

    refused = await client.put(f"{BASE}/manage/opening-hours", json=shorter, headers=admin)

    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["errors"] == {"_form": "has_reservations"} and detail["total"] == 1
    assert [(r["name"], r["day"], r["start_time"], r["end_time"]) for r in detail["reservations"]] == [("Eva Nováková", day(2).isoformat(), "20:00:00", "22:00:00")]
    assert (await client.get(f"{BASE}/manage/opening-hours", headers=admin)).json()[weekday]["closes"] == "22:00:00"  # unchanged

    row = await stored(db_session, token)
    await client.post(f"{BASE}/manage/reservations/{row.id}/cancel", json={"note": "Hours change"}, headers=admin)
    assert (await client.put(f"{BASE}/manage/opening-hours", json=shorter, headers=admin)).status_code == 200


async def test_the_pub_may_close_a_weekday_that_has_no_reservations_but_not_one_that_has(client, admin, db_session):
    await seed_pub(db_session)
    await reserve(client, 2, "18:00")
    busy_weekday = day(2).weekday()
    free_weekday = (busy_weekday + 3) % 7  # the only reservation is on the busy weekday

    free = await client.put(f"{BASE}/manage/opening-hours", json=week(overrides={free_weekday: {"is_closed": True}}), headers=admin)
    busy = await client.put(f"{BASE}/manage/opening-hours", json=week(overrides={busy_weekday: {"is_closed": True}}), headers=admin)

    assert free.status_code == 200
    assert busy.status_code == 409


async def test_a_reservation_that_is_over_or_cancelled_never_blocks_a_change_of_hours(client, admin, db_session):
    await seed_pub(db_session)
    at_clock(db_session, 9)
    await reserve(client, 0, "10:30", email="today@example.com")  # today, 10:30-12:30
    cancelled = (await reserve(client, 3, "20:00", email="gone@example.com")).json()["cancel_token"]
    await client.post(f"{BASE}/reservations/{cancelled}/cancel")
    at_clock(db_session, 15)  # the lunch reservation is over by now

    resp = await client.put(f"{BASE}/manage/opening-hours", json=week("13:00", "20:00"), headers=admin)

    assert resp.status_code == 200, resp.text


async def test_a_reservation_that_has_not_ended_yet_still_blocks(client, admin, db_session):
    await seed_pub(db_session)
    await reserve(client, 0, "10:30")  # today, 10:30-12:30
    at_clock(db_session, 12)  # half an hour left

    resp = await client.put(f"{BASE}/manage/opening-hours", json=week("13:00", "20:00"), headers=admin)

    assert resp.status_code == 409


async def test_a_one_off_change_of_a_day_keeps_a_reservation_valid_whatever_the_regular_hours_say(client, admin, db_session):
    await seed_pub(db_session)
    await make_exception(db_session, day(2), closed=False, opens="10:00", closes="23:00")
    await reserve(client, 2, "21:30", email="late@example.com")  # 21:30-23:00, only possible because of the exception

    on_that_weekday = await client.put(f"{BASE}/manage/opening-hours", json=week("10:00", "20:00"), headers=admin)

    assert on_that_weekday.status_code == 200  # that date has its own hours, the regular ones do not apply to it


# --- One-off changes of a day ----------------------------------------------------------------------------------------


async def test_the_pub_closes_a_day_with_a_reason_visitors_can_see(client, admin, db_session):
    await seed_pub(db_session)

    resp = await client.put(f"{BASE}/manage/exceptions/{day(3).isoformat()}", json={"is_closed": True, "reason": "  Burst pipe, sorry  "}, headers=admin)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"day": day(3).isoformat(), "is_closed": True, "opens": None, "closes": None, "reason": "Burst pipe, sorry"}
    listed = await client.get(f"{BASE}/manage/exceptions", headers=admin)
    assert [entry["day"] for entry in listed.json()] == [day(3).isoformat()]
    public = (await client.get(f"{BASE}/info")).json()
    assert [(e["day"], e["reason"]) for e in public["exceptions"]] == [(day(3).isoformat(), "Burst pipe, sorry")]
    availability = (await client.get(f"{BASE}/availability", params={"day": day(3).isoformat(), "party_size": 2})).json()
    assert (availability["is_open"], availability["reason"]) == (False, "Burst pipe, sorry")
    assert (await reserve(client, 3)).json()["detail"] == {"errors": {"day": "closed"}}


async def test_a_blank_reason_is_no_reason(client, admin, db_session):
    await seed_pub(db_session)

    resp = await client.put(f"{BASE}/manage/exceptions/{day(3).isoformat()}", json={"is_closed": True, "reason": "   "}, headers=admin)

    assert resp.json()["reason"] is None


async def test_the_pub_sets_other_hours_for_one_day(client, admin, db_session):
    await seed_pub(db_session)

    resp = await client.put(f"{BASE}/manage/exceptions/{day(3).isoformat()}", json={"is_closed": False, "opens": "16:00", "closes": "20:00", "reason": "Match day"}, headers=admin)

    assert resp.status_code == 200 and (resp.json()["opens"], resp.json()["closes"]) == ("16:00:00", "20:00:00")
    assert (await reserve(client, 3, "19:30")).status_code == 201
    assert (await reserve(client, 3, "20:00", email="b@example.com")).status_code == 422


async def test_changing_an_exception_that_already_exists_updates_it(client, admin, db_session):
    await seed_pub(db_session)
    url = f"{BASE}/manage/exceptions/{day(3).isoformat()}"
    await client.put(url, json={"is_closed": True, "reason": "First"}, headers=admin)

    await client.put(url, json={"is_closed": False, "opens": "12:00", "closes": "18:00", "reason": "Second"}, headers=admin)

    rows = (await client.get(f"{BASE}/manage/exceptions", headers=admin)).json()
    assert [(r["is_closed"], r["opens"], r["reason"]) for r in rows] == [(False, "12:00:00", "Second")]


async def test_exception_hours_that_make_no_sense_or_a_date_in_the_past_are_refused(client, admin, db_session):
    await seed_pub(db_session)
    url = f"{BASE}/manage/exceptions/{day(3).isoformat()}"

    backwards = await client.put(url, json={"is_closed": False, "opens": "20:00", "closes": "12:00"}, headers=admin)
    missing = await client.put(url, json={"is_closed": False, "opens": "12:00"}, headers=admin)
    past = await client.put(f"{BASE}/manage/exceptions/{day(-1).isoformat()}", json={"is_closed": True}, headers=admin)
    today = await client.put(f"{BASE}/manage/exceptions/{TODAY.isoformat()}", json={"is_closed": True}, headers=admin)
    long_reason = await client.put(url, json={"is_closed": True, "reason": "x" * 201}, headers=admin)

    assert backwards.json()["detail"] == {"errors": {"closes": "closes_before_opens"}}
    assert missing.json()["detail"] == {"errors": {"closes": "required"}}
    assert past.status_code == 422 and past.json()["detail"] == {"errors": {"day": "in_past"}}
    assert today.status_code == 200
    assert long_reason.status_code == 422
    assert (await client.put(f"{BASE}/manage/exceptions/not-a-day", json={"is_closed": True}, headers=admin)).status_code == 422


async def test_a_day_with_reservations_cannot_be_closed_until_each_is_cancelled_by_the_pub(client, admin, db_session, outbox):
    await seed_pub(db_session)
    table_token = (await reserve(client, 2, "18:00", party_size=2, email="table@example.com", name="Table guest")).json()["cancel_token"]
    whole_token = (await reserve(client, 2, "21:00", kind="whole_venue", party_size=40, email="party@example.com", name="Party guest", language="en")).json()["cancel_token"]
    other_day = (await reserve(client, 3, "18:00", email="other@example.com", name="Other day")).json()["cancel_token"]
    table_row, whole_row = await stored(db_session, table_token), await stored(db_session, whole_token)
    url = f"{BASE}/manage/exceptions/{day(2).isoformat()}"
    close = {"is_closed": True, "reason": "Private event"}

    refused = await client.put(url, json=close, headers=admin)

    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["errors"] == {"_form": "has_reservations"} and detail["total"] == 2
    assert [r["name"] for r in detail["reservations"]] == ["Table guest", "Party guest"]  # by start time
    assert [r["id"] for r in detail["reservations"]] == [str(table_row.id), str(whole_row.id)]
    assert detail["reservations"][0]["table_name"] and detail["reservations"][1]["table_name"] is None
    assert (await client.get(f"{BASE}/manage/exceptions", headers=admin)).json() == []  # nothing was saved
    outbox.clear()

    first = await client.post(f"{BASE}/manage/reservations/{table_row.id}/cancel", json={"note": "We are closed for a private event."}, headers=admin)
    still_refused = await client.put(url, json=close, headers=admin)
    second = await client.post(f"{BASE}/manage/reservations/{whole_row.id}/cancel", json={"note": "Closed that day, sorry."}, headers=admin)
    closed = await client.put(url, json=close, headers=admin)

    assert (first.status_code, second.status_code) == (200, 200)
    assert still_refused.status_code == 409 and still_refused.json()["detail"]["total"] == 1  # only the party is left
    assert closed.status_code == 200 and closed.json()["is_closed"] is True
    assert [to_of(m) for m in outbox] == ["table@example.com", "party@example.com"]  # each guest was told, in their language
    assert "We are closed for a private event." in text_of(outbox[0]) and "Closed that day, sorry." in text_of(outbox[1])
    assert outbox[1]["Subject"].startswith("Your reservation has been cancelled")
    assert (await stored(db_session, other_day)).status == "confirmed"  # another day is untouched


async def test_a_day_can_be_shortened_only_if_every_reservation_still_fits(client, admin, db_session):
    await seed_pub(db_session)
    await reserve(client, 2, "12:00", email="a@example.com")  # 12:00-14:00
    await reserve(client, 2, "19:00", email="b@example.com")  # 19:00-21:00
    url = f"{BASE}/manage/exceptions/{day(2).isoformat()}"

    cuts_the_evening = await client.put(url, json={"is_closed": False, "opens": "10:00", "closes": "18:00"}, headers=admin)
    starts_after_lunch = await client.put(url, json={"is_closed": False, "opens": "13:00", "closes": "22:00"}, headers=admin)
    fits = await client.put(url, json={"is_closed": False, "opens": "12:00", "closes": "21:00"}, headers=admin)

    assert cuts_the_evening.status_code == 409 and [r["start_time"] for r in cuts_the_evening.json()["detail"]["reservations"]] == ["19:00:00"]
    assert starts_after_lunch.status_code == 409 and [r["start_time"] for r in starts_after_lunch.json()["detail"]["reservations"]] == ["12:00:00"]
    assert fits.status_code == 200  # exactly the span of the two reservations


async def test_a_cancelled_reservation_does_not_stand_in_the_way_of_closing(client, admin, db_session):
    await seed_pub(db_session)
    token = (await reserve(client, 2, "18:00")).json()["cancel_token"]
    await client.post(f"{BASE}/reservations/{token}/cancel")

    resp = await client.put(f"{BASE}/manage/exceptions/{day(2).isoformat()}", json={"is_closed": True}, headers=admin)

    assert resp.status_code == 200


async def test_removing_an_exception_restores_the_regular_hours(client, admin, db_session):
    await seed_pub(db_session)
    url = f"{BASE}/manage/exceptions/{day(3).isoformat()}"
    await client.put(url, json={"is_closed": True, "reason": "Oops"}, headers=admin)

    resp = await client.delete(url, headers=admin)

    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/manage/exceptions", headers=admin)).json() == []
    assert (await reserve(client, 3)).status_code == 201
    assert (await client.delete(url, headers=admin)).status_code == 404


async def test_removing_an_exception_is_refused_while_a_reservation_only_fits_because_of_it(client, admin, db_session):
    await seed_pub(db_session)
    await make_exception(db_session, day(3), closed=False, opens="10:00", closes="23:30")
    await reserve(client, 3, "22:30")  # 22:30-23:30, possible only with the longer evening

    resp = await client.delete(f"{BASE}/manage/exceptions/{day(3).isoformat()}", headers=admin)

    assert resp.status_code == 409 and resp.json()["detail"]["total"] == 1
    assert await db_session.get(OpeningException, day(3)) is not None


async def test_the_list_of_exceptions_starts_today_unless_asked_otherwise(client, admin, db_session):
    await seed_pub(db_session)
    await make_exception(db_session, day(-5), closed=True)
    await make_exception(db_session, day(4), closed=True)
    await make_exception(db_session, day(2), closed=True)

    default = (await client.get(f"{BASE}/manage/exceptions", headers=admin)).json()
    from_earlier = (await client.get(f"{BASE}/manage/exceptions", params={"date_from": day(-10).isoformat()}, headers=admin)).json()

    assert [e["day"] for e in default] == [day(2).isoformat(), day(4).isoformat()]
    assert [e["day"] for e in from_earlier] == [day(-5).isoformat(), day(2).isoformat(), day(4).isoformat()]


# --- Tables ----------------------------------------------------------------------------------------------------------------


async def test_the_pub_adds_lists_and_changes_tables(client, admin, db_session):
    created = await client.post(f"{BASE}/manage/tables", json={"name": "  Window  ", "seats": 4, "position": 2}, headers=admin)
    await client.post(f"{BASE}/manage/tables", json={"name": "Bar", "seats": 2, "position": 1}, headers=admin)

    assert created.status_code == 201, created.text
    assert (created.json()["name"], created.json()["seats"], created.json()["is_active"], created.json()["upcoming_count"]) == ("Window", 4, True, 0)
    listed = (await client.get(f"{BASE}/manage/tables", headers=admin)).json()
    assert [t["name"] for t in listed] == ["Bar", "Window"]  # by position

    changed = await client.patch(f"{BASE}/manage/tables/{created.json()['id']}", json={"name": "Big window", "seats": 6, "position": 0}, headers=admin)

    assert changed.status_code == 200 and (changed.json()["name"], changed.json()["seats"]) == ("Big window", 6)
    assert [t["name"] for t in (await client.get(f"{BASE}/manage/tables", headers=admin)).json()] == ["Big window", "Bar"]


@pytest.mark.parametrize("body", [{"name": "", "seats": 4}, {"name": "T", "seats": 0}, {"name": "T", "seats": 51}, {"name": "T"}, {"seats": 4}, {"name": "T", "seats": 4, "extra": 1}])
async def test_a_table_needs_a_name_and_a_sensible_number_of_seats(client, admin, db_session, body):
    assert (await client.post(f"{BASE}/manage/tables", json=body, headers=admin)).status_code == 422


async def test_a_change_cannot_set_a_field_to_null_and_an_unknown_table_is_404(client, admin, db_session):
    table = await make_table(db_session, "T", 4)

    assert (await client.patch(f"{BASE}/manage/tables/{table.id}", json={"seats": None}, headers=admin)).status_code == 422
    assert (await client.patch(f"{BASE}/manage/tables/{uuid.uuid4()}", json={"seats": 2}, headers=admin)).status_code == 404
    assert (await client.delete(f"{BASE}/manage/tables/{uuid.uuid4()}", headers=admin)).status_code == 404


async def test_the_list_counts_each_tables_upcoming_reservations(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(2, 4))
    await reserve(client, 1, "18:00", party_size=2, email="a@example.com")
    await reserve(client, 2, "18:00", party_size=2, email="b@example.com")
    gone = (await reserve(client, 3, "18:00", party_size=2, email="c@example.com")).json()["cancel_token"]
    await client.post(f"{BASE}/reservations/{gone}/cancel")

    listed = {t["id"]: t["upcoming_count"] for t in (await client.get(f"{BASE}/manage/tables", headers=admin)).json()}

    assert listed == {str(tables[0].id): 2, str(tables[1].id): 0}


async def test_a_table_with_upcoming_reservations_cannot_be_taken_out_of_use_until_they_are_cancelled(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(4,))
    token = (await reserve(client, 1, "18:00", party_size=3)).json()["cancel_token"]
    url = f"{BASE}/manage/tables/{tables[0].id}"

    refused = await client.patch(url, json={"is_active": False}, headers=admin)

    assert refused.status_code == 409
    assert refused.json()["detail"]["errors"] == {"_form": "has_reservations"} and refused.json()["detail"]["total"] == 1
    assert refused.json()["detail"]["reservations"][0]["table_name"] == tables[0].name
    await client.post(f"{BASE}/manage/reservations/{(await stored(db_session, token)).id}/cancel", json={}, headers=admin)
    assert (await client.patch(url, json={"is_active": False}, headers=admin)).status_code == 200
    assert (await reserve(client, 1, "18:00", party_size=2, email="b@example.com")).status_code == 422  # no table left


async def test_seating_fewer_people_is_refused_only_when_a_reservation_no_longer_fits(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(4,))
    await reserve(client, 1, "18:00", party_size=3)
    url = f"{BASE}/manage/tables/{tables[0].id}"

    too_few = await client.patch(url, json={"seats": 2}, headers=admin)
    still_enough = await client.patch(url, json={"seats": 3}, headers=admin)
    more = await client.patch(url, json={"seats": 8}, headers=admin)

    assert (too_few.status_code, still_enough.status_code, more.status_code) == (409, 200, 200)


async def test_a_table_may_be_renamed_or_put_back_into_use_whatever_is_reserved(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(4,))
    await reserve(client, 1, "18:00", party_size=3)
    url = f"{BASE}/manage/tables/{tables[0].id}"

    assert (await client.patch(url, json={"name": "Renamed", "position": 5}, headers=admin)).status_code == 200
    assert (await client.patch(url, json={"is_active": True}, headers=admin)).status_code == 200


async def test_an_unused_table_is_deleted_but_one_with_reservations_is_not(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(2, 4, 6))
    upcoming = (await reserve(client, 1, "18:00", party_size=3)).json()["cancel_token"]  # the table for 4
    cancelled = (await reserve(client, 1, "18:00", party_size=2, email="b@example.com")).json()["cancel_token"]  # the table for 2
    await client.post(f"{BASE}/reservations/{cancelled}/cancel")

    unused = await client.delete(f"{BASE}/manage/tables/{tables[2].id}", headers=admin)
    with_upcoming = await client.delete(f"{BASE}/manage/tables/{tables[1].id}", headers=admin)
    with_history = await client.delete(f"{BASE}/manage/tables/{tables[0].id}", headers=admin)

    assert unused.status_code == 204
    assert with_upcoming.status_code == 409 and with_upcoming.json()["detail"]["errors"] == {"_form": "has_reservations"}
    assert with_history.status_code == 409 and with_history.json()["detail"] == {"errors": {"_form": "in_use"}}  # deactivate it instead
    assert upcoming and (await stored(db_session, upcoming)).table_id == tables[1].id


# --- Retention (GDPR) ------------------------------------------------------------------------------------------------------


def old_reservation(table_id, on: date, name: str) -> Reservation:
    return Reservation(
        kind="table",
        table_id=table_id,
        day=on,
        start_time=time(18),
        end_time=time(20),
        party_size=2,
        name=name,
        email=f"{name.lower()}@example.com",
        phone="+420 123",
        note="personal",
        consent_at=datetime(2025, 1, 1),
        language="cs",
    )


async def test_the_pub_can_purge_the_reservations_older_than_the_retention_on_demand(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(4,))
    db_session.add_all(
        [
            old_reservation(tables[0].id, day(-400), "Old"),
            old_reservation(tables[0].id, day(-364), "Within"),
            old_reservation(tables[0].id, day(-30), "Recent"),
            old_reservation(tables[0].id, day(5), "Future"),
        ]
    )
    await db_session.commit()

    resp = await client.post(f"{BASE}/manage/purge", headers=admin)

    assert resp.status_code == 200 and resp.json() == {"deleted_reservations": 1}
    from sqlalchemy import select

    names = {row.name for row in (await db_session.scalars(select(Reservation))).all()}
    assert names == {"Within", "Recent", "Future"}


async def test_the_purge_runs_by_itself_at_most_once_a_day_when_the_list_is_opened(client, admin, db_session):
    tables = await seed_pub(db_session, seats=(4,))
    db_session.add(old_reservation(tables[0].id, day(-400), "Old"))
    await db_session.commit()

    await client.get(f"{BASE}/manage/reservations", params=list_params(), headers=admin)
    assert await count_rows(db_session) == 0

    db_session.add(old_reservation(tables[0].id, day(-401), "Older"))
    await db_session.commit()
    await client.get(f"{BASE}/manage/reservations", params=list_params(), headers=admin)
    assert await count_rows(db_session) == 1  # not again the same day


def test_months_ago_clamps_the_day_to_the_length_of_the_month():
    assert service.months_ago(date(2027, 3, 31), 1) == date(2027, 2, 28)
    assert service.months_ago(date(2028, 3, 31), 1) == date(2028, 2, 29)
    assert service.months_ago(date(2027, 1, 15), 12) == date(2026, 1, 15)
    assert service.months_ago(date(2027, 1, 15), 13) == date(2025, 12, 15)
