# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The public side of the table reservations module: the opening hours a visitor
is shown, what is free, how a guest reserves a table or the whole pub (and every
way that is refused), and cancelling by the link in the e-mail.

Mounts just this module's router on a throwaway app (see reservation_support.py),
with the clock fixed (today, 09:00) and the database a rolled-back session. The
pub is open 10:00-22:00 every day unless a test says otherwise. E-mails are
captured through fastapi-mail's recorder (MAIL_SUPPRESS_SEND), so nothing is ever
sent for real."""

import logging
from datetime import datetime, time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.modules.table_reservations import mail as reservation_mail
from app.modules.table_reservations import service
from app.modules.table_reservations.config import get_config, load_config
from app.modules.table_reservations.models import Reservation
from tests.reservation_support import (  # noqa: F401  (outbox and _fast_fqdn are fixtures)
    BASE,
    _fast_fqdn,
    NOW,
    TODAY,
    clear_tables,
    count_rows,
    day,
    install_overrides,
    make_exception,
    make_settings,
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
async def _overrides(db_session):
    await clear_tables(db_session)
    install_overrides(_app, db_session)
    service.reset_purge_throttle()
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


def at_clock(db_session, hour: int, minute: int = 0) -> None:
    """Moves the app's clock to `hour:minute` today."""
    install_overrides(_app, db_session, now=datetime.combine(TODAY, time(hour, minute)))


# --- Opening hours --------------------------------------------------------------------------------------


async def test_info_gives_the_week_the_coming_exceptions_and_the_limits(client, db_session):
    await seed_pub(db_session, seats=(2, 4, 6))
    await make_exception(db_session, day(5), closed=True, reason="Private party")
    await make_exception(db_session, day(-3), closed=True, reason="Long gone")

    resp = await client.get(f"{BASE}/info")

    assert resp.status_code == 200
    body = resp.json()
    assert [entry["weekday"] for entry in body["weekly"]] == list(range(7))
    assert all(entry["is_closed"] is False and entry["opens"] == "10:00:00" and entry["closes"] == "22:00:00" for entry in body["weekly"])
    assert [(e["day"], e["reason"]) for e in body["exceptions"]] == [(day(5).isoformat(), "Private party")]
    assert body["max_party_size"] == 6
    assert body["max_whole_venue_party"] == 200
    assert (body["default_duration"], body["min_duration"], body["step_minutes"]) == (120, 30, 15)
    assert body["duration_options"] == [60, 90, 120, 150, 180, 240]
    assert body["can_reserve"] is True


async def test_info_of_a_pub_not_set_up_yet_says_nothing_can_be_reserved(client, db_session):
    resp = await client.get(f"{BASE}/info")

    body = resp.json()
    assert len(body["weekly"]) == 7 and all(entry["is_closed"] for entry in body["weekly"])
    assert (body["max_party_size"], body["can_reserve"]) == (0, False)


async def test_info_needs_a_table_and_an_open_day(client, db_session):
    await seed_hours(db_session)
    assert (await client.get(f"{BASE}/info")).json()["can_reserve"] is False  # open, but no table

    await clear_tables(db_session)
    await make_table(db_session, "Only", 4)
    assert (await client.get(f"{BASE}/info")).json()["can_reserve"] is False  # a table, but never open


async def test_an_inactive_table_does_not_count_towards_the_largest_party(client, db_session):
    await seed_hours(db_session)
    await make_table(db_session, "Small", 2)
    await make_table(db_session, "Big, out of use", 10, is_active=False)

    assert (await client.get(f"{BASE}/info")).json()["max_party_size"] == 2


async def test_days_show_hours_reasons_and_which_days_can_be_reserved(client, db_session):
    await seed_hours(db_session, closed_weekdays=(day(3).weekday(),))
    await make_table(db_session, "Table", 4)
    await make_exception(db_session, day(1), closed=True, reason="Staff outing")
    await make_exception(db_session, day(2), closed=False, opens="16:00", closes="20:00", reason="Short day")

    resp = await client.get(f"{BASE}/days", params={"month": day(1).strftime("%Y-%m")})

    assert resp.status_code == 200
    days = {entry["day"]: entry for entry in resp.json()["days"]}
    assert days[day(1).isoformat()] == {"day": day(1).isoformat(), "is_open": False, "opens": None, "closes": None, "reason": "Staff outing", "bookable": False}
    assert (days[day(2).isoformat()]["opens"], days[day(2).isoformat()]["closes"], days[day(2).isoformat()]["reason"]) == ("16:00:00", "20:00:00", "Short day")
    assert days[day(2).isoformat()]["bookable"] is True
    assert days[day(3).isoformat()]["is_open"] is False  # a closed weekday, no reason needed
    assert days[day(3).isoformat()]["reason"] is None


async def test_a_day_that_is_over_or_too_far_ahead_cannot_be_reserved(client, db_session):
    await seed_hours(db_session)
    horizon = load_config().max_days_ahead

    for offset, expected in ((-1, False), (0, True), (horizon, True), (horizon + 1, False)):
        resp = await client.get(f"{BASE}/days", params={"month": day(offset).strftime("%Y-%m")})
        entry = next(item for item in resp.json()["days"] if item["day"] == day(offset).isoformat())
        assert entry["bookable"] is expected, offset
        assert entry["is_open"] is True


async def test_days_refuse_a_malformed_month(client):
    assert (await client.get(f"{BASE}/days", params={"month": "2027-13"})).status_code == 422
    assert (await client.get(f"{BASE}/days")).status_code == 422


# --- What is free ---------------------------------------------------------------------------------------------


def starts(resp) -> list[str]:
    return [value[:5] for value in resp.json()["starts"]]


async def test_a_free_pub_offers_every_quarter_hour_for_a_party(client, db_session):
    await seed_pub(db_session)

    resp = await client.get(f"{BASE}/availability", params={"day": day(1).isoformat(), "party_size": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert starts(resp)[:3] == ["10:00", "10:15", "10:30"] and starts(resp)[-1] == "21:30"
    assert body["is_open"] and body["bookable"] and body["table_reason"] is None
    assert (body["opens"], body["closes"]) == ("10:00:00", "22:00:00")
    assert body["whole_venue_from"] == "10:00:00" and body["whole_venue_reason"] is None


async def test_a_reservation_takes_its_start_times_away_with_the_half_hour_buffer(client, db_session):
    await seed_pub(db_session, seats=(4,))
    assert (await reserve(client, 1, "18:00", party_size=3)).status_code == 201

    resp = await client.get(f"{BASE}/availability", params={"day": day(1).isoformat(), "party_size": 3})

    free = starts(resp)
    assert "15:30" in free and "15:45" not in free  # two hours from 15:30 end 30 minutes before 18:00
    assert all(slot not in free for slot in ("16:00", "18:00", "19:45", "20:00", "20:15"))
    assert "20:30" in free
    assert resp.json()["whole_venue_from"] == "20:00:00"  # from the end of the table's time, no buffer needed


async def test_a_shorter_stay_leaves_more_starts(client, db_session):
    await seed_pub(db_session, seats=(4,))
    await reserve(client, 1, "18:00", party_size=3)

    two_hours = starts(await client.get(f"{BASE}/availability", params={"day": day(1).isoformat(), "party_size": 3}))
    one_hour = starts(await client.get(f"{BASE}/availability", params={"day": day(1).isoformat(), "party_size": 3, "duration": 60}))

    assert "16:15" in one_hour and "16:15" not in two_hours  # an hour from 16:15 ends at 17:15, enough before 18:00


async def test_a_party_too_large_for_any_table_is_offered_nothing_and_told_why(client, db_session):
    await seed_pub(db_session, seats=(2, 4))

    resp = await client.get(f"{BASE}/availability", params={"day": day(1).isoformat(), "party_size": 5})

    assert resp.json()["starts"] == [] and resp.json()["table_reason"] == "party_too_large"
    assert resp.json()["whole_venue_from"] == "10:00:00"  # the whole pub still can be reserved


async def test_when_every_table_is_taken_the_reason_is_no_table(client, db_session):
    await seed_pub(db_session, seats=(4,))
    for start in ("10:00", "12:30", "15:00", "17:30", "20:00"):
        assert (await reserve(client, 1, start, party_size=3, email=f"p{start[:2]}@example.com")).status_code == 201

    body = (await client.get(f"{BASE}/availability", params={"day": day(1).isoformat(), "party_size": 3, "duration": 120})).json()

    assert body["starts"] == [] and body["table_reason"] == "no_table"


async def test_a_closed_day_offers_nothing(client, db_session):
    await seed_pub(db_session)
    await make_exception(db_session, day(1), closed=True, reason="Closed for a funeral")

    body = (await client.get(f"{BASE}/availability", params={"day": day(1).isoformat(), "party_size": 2})).json()

    assert (body["is_open"], body["bookable"], body["starts"], body["reason"]) == (False, False, [], "Closed for a funeral")
    assert body["whole_venue_from"] is None


async def test_today_only_offers_starts_after_the_lead_time(client, db_session):
    await seed_pub(db_session)
    at_clock(db_session, 19, 50)  # lead 30 minutes -> 20:20 -> the next quarter is 20:30

    resp = await client.get(f"{BASE}/availability", params={"day": TODAY.isoformat(), "party_size": 2})

    assert starts(resp)[0] == "20:30" and starts(resp)[-1] == "21:30"
    assert resp.json()["whole_venue_from"] == "20:30:00"


async def test_late_in_the_evening_nothing_is_left_today(client, db_session):
    await seed_pub(db_session)
    at_clock(db_session, 21, 30)

    body = (await client.get(f"{BASE}/availability", params={"day": TODAY.isoformat(), "party_size": 2})).json()

    assert body["starts"] == [] and body["table_reason"] == "too_soon"
    assert body["whole_venue_from"] is None and body["whole_venue_reason"] == "too_soon"


async def test_availability_of_a_past_or_too_distant_day_is_empty_and_not_bookable(client, db_session):
    await seed_pub(db_session)
    horizon = load_config().max_days_ahead

    for offset in (-1, horizon + 1):
        body = (await client.get(f"{BASE}/availability", params={"day": day(offset).isoformat(), "party_size": 2})).json()
        assert (body["bookable"], body["starts"]) == (False, [])


async def test_availability_validates_its_parameters(client, db_session):
    await seed_pub(db_session)
    url = f"{BASE}/availability"

    assert (await client.get(url, params={"day": day(1).isoformat()})).status_code == 422
    assert (await client.get(url, params={"day": day(1).isoformat(), "party_size": 0})).status_code == 422
    assert (await client.get(url, params={"day": day(1).isoformat(), "party_size": 201})).status_code == 422
    assert (await client.get(url, params={"day": day(1).isoformat(), "party_size": 2, "duration": 10})).status_code == 422
    assert (await client.get(url, params={"day": "soon", "party_size": 2})).status_code == 422


# --- Reserving a table ---------------------------------------------------------------------------------------------


async def test_a_guest_reserves_a_table_and_the_system_picks_the_smallest_that_fits(client, db_session):
    tables = await seed_pub(db_session, seats=(2, 4, 6))

    resp = await reserve(client, 1, "18:00", party_size=3, phone="  +420 777 123 456 ", note=" window seat, please ")

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["kind"], body["day"], body["start_time"], body["end_time"]) == ("table", day(1).isoformat(), "18:00:00", "20:00:00")
    assert len(body["cancel_token"]) >= 30
    row = await stored(db_session, body["cancel_token"])
    assert row.table_id == tables[1].id  # the table for 4
    assert (row.party_size, row.name, row.email, row.status, row.language) == (3, "Eva Nováková", "eva@example.com", "confirmed", "cs")
    assert (row.phone, row.note) == ("+420 777 123 456", "window seat, please")
    assert row.consent_at is not None and row.cancelled_at is None


async def test_the_response_never_tells_the_guest_which_table_it_is(client, db_session):
    await seed_pub(db_session)

    body = (await reserve(client)).json()

    assert set(body) == {"cancel_token", "kind", "day", "start_time", "end_time"}


async def test_the_default_stay_is_two_hours_and_the_guest_may_ask_for_another(client, db_session):
    await seed_pub(db_session)

    default = (await reserve(client, 1, "12:00", email="a@example.com")).json()
    longer = (await reserve(client, 1, "12:00", email="b@example.com", duration_minutes=180)).json()
    shorter = (await reserve(client, 1, "12:00", email="c@example.com", duration_minutes=60)).json()

    assert (default["end_time"], longer["end_time"], shorter["end_time"]) == ("14:00:00", "15:00:00", "13:00:00")


async def test_the_end_is_cut_at_closing_time(client, db_session):
    await seed_pub(db_session)

    late = (await reserve(client, 1, "21:00", email="a@example.com")).json()
    last = (await reserve(client, 1, "21:30", email="b@example.com", duration_minutes=240)).json()

    assert (late["end_time"], last["end_time"]) == ("22:00:00", "22:00:00")


async def test_a_start_too_close_to_closing_is_refused(client, db_session):
    await seed_pub(db_session)

    resp = await reserve(client, 1, "21:45")

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"start_time": "outside_hours"}}


async def test_a_taken_table_makes_the_next_guest_sit_at_the_next_one(client, db_session):
    tables = await seed_pub(db_session, seats=(2, 4, 6))

    first = await stored(db_session, (await reserve(client, 1, "18:00", party_size=2, email="a@example.com")).json()["cancel_token"])
    second = await stored(db_session, (await reserve(client, 1, "18:00", party_size=2, email="b@example.com")).json()["cancel_token"])
    third = await stored(db_session, (await reserve(client, 1, "18:00", party_size=2, email="c@example.com")).json()["cancel_token"])

    assert [first.table_id, second.table_id, third.table_id] == [tables[0].id, tables[1].id, tables[2].id]
    fourth = await reserve(client, 1, "18:00", party_size=2, email="d@example.com")
    assert fourth.status_code == 409 and fourth.json()["detail"] == {"errors": {"start_time": "no_table"}}
    assert await count_rows(db_session) == 3  # a refusal leaves nothing behind


async def test_a_table_is_free_again_half_an_hour_after_the_last_guest_left(client, db_session):
    await seed_pub(db_session, seats=(4,))
    assert (await reserve(client, 1, "18:00", party_size=3)).status_code == 201  # 18:00-20:00

    too_close = await reserve(client, 1, "20:15", party_size=3, email="b@example.com")
    straight_after = await reserve(client, 1, "20:00", party_size=3, email="c@example.com")
    just_enough = await reserve(client, 1, "20:30", party_size=3, email="d@example.com")

    assert (too_close.status_code, straight_after.status_code, just_enough.status_code) == (409, 409, 201)
    assert too_close.json()["detail"] == {"errors": {"start_time": "no_table"}}


async def test_the_half_hour_counts_before_a_reservation_too(client, db_session):
    await seed_pub(db_session, seats=(4,))
    assert (await reserve(client, 1, "18:00", party_size=3)).status_code == 201

    ends_15_before = await reserve(client, 1, "15:45", party_size=3, email="b@example.com")  # ends 17:45
    ends_30_before = await reserve(client, 1, "15:30", party_size=3, email="c@example.com")  # ends 17:30
    shorter_stay = await reserve(client, 1, "16:30", party_size=3, email="d@example.com", duration_minutes=60)  # ends 17:30

    assert (ends_15_before.status_code, ends_30_before.status_code, shorter_stay.status_code) == (409, 201, 409)  # the 16:30 one overlaps the 15:30 one


async def test_reservations_of_different_days_do_not_disturb_each_other(client, db_session):
    await seed_pub(db_session, seats=(4,))

    assert (await reserve(client, 1, "18:00", party_size=3)).status_code == 201
    assert (await reserve(client, 2, "18:00", party_size=3)).status_code == 201


async def test_a_party_larger_than_any_table_is_refused_at_the_party_field(client, db_session):
    await seed_pub(db_session, seats=(2, 4))

    resp = await reserve(client, 1, "18:00", party_size=5)

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"party_size": "party_too_large"}}


async def test_an_inactive_table_is_not_given_to_anyone(client, db_session):
    await seed_hours(db_session)
    await make_table(db_session, "Out of use", 4, is_active=False)

    resp = await reserve(client, 1, "18:00", party_size=2)

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"party_size": "party_too_large"}}


# --- Days and times that do not exist --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("offset", "start", "field", "code"),
    [
        (-1, "18:00", "day", "out_of_range"),
        (load_config().max_days_ahead + 1, "18:00", "day", "out_of_range"),
        (1, "18:10", "start_time", "bad_start"),
        (1, "09:45", "start_time", "outside_hours"),
        (1, "22:00", "start_time", "outside_hours"),
        (1, "23:00", "start_time", "outside_hours"),
        (1, "18:00:30", "start_time", "bad_start"),
    ],
)
async def test_a_day_or_time_that_cannot_be_reserved_is_refused_with_its_reason(client, db_session, offset, start, field, code):
    await seed_pub(db_session)

    resp = await reserve(client, offset, start)

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {field: code}}
    assert await count_rows(db_session) == 0


async def test_a_closed_weekday_and_a_closed_date_are_refused(client, db_session):
    await seed_hours(db_session, closed_weekdays=(day(2).weekday(),))
    await make_table(db_session, "Table", 4)
    await make_exception(db_session, day(1), closed=True, reason="Water damage")

    exception = await reserve(client, 1)
    weekday = await reserve(client, 2)

    assert (exception.status_code, weekday.status_code) == (422, 422)
    assert exception.json()["detail"] == weekday.json()["detail"] == {"errors": {"day": "closed"}}


async def test_a_one_off_change_of_hours_applies_to_reservations_of_that_day(client, db_session):
    await seed_pub(db_session)
    await make_exception(db_session, day(1), closed=False, opens="16:00", closes="20:00", reason="Short day")

    before_opening = await reserve(client, 1, "15:45")
    first = await reserve(client, 1, "16:00", email="a@example.com")
    last = await reserve(client, 1, "19:30", email="b@example.com")
    too_late = await reserve(client, 1, "19:45", email="c@example.com")

    assert [r.status_code for r in (before_opening, first, last, too_late)] == [422, 201, 201, 422]
    assert last.json()["end_time"] == "20:00:00"  # cut at that day's closing


async def test_a_reservation_for_today_must_respect_the_lead_time(client, db_session):
    await seed_pub(db_session)
    at_clock(db_session, 19, 50)

    too_soon = await reserve(client, 0, "20:15")
    after_lead = await reserve(client, 0, "20:30", email="b@example.com")

    assert too_soon.status_code == 422 and too_soon.json()["detail"] == {"errors": {"start_time": "too_soon"}}
    assert after_lead.status_code == 201


async def test_a_duration_that_is_not_a_step_is_refused(client, db_session):
    await seed_pub(db_session)

    odd = await reserve(client, 1, duration_minutes=100)
    too_short = await reserve(client, 1, duration_minutes=15)
    too_long = await reserve(client, 1, duration_minutes=600)

    assert odd.status_code == 422 and odd.json()["detail"] == {"errors": {"duration_minutes": "bad_duration"}}
    assert too_short.status_code == 422 and too_long.status_code == 422


# --- The whole pub -------------------------------------------------------------------------------------------------------


async def test_a_guest_reserves_the_whole_pub_from_a_time_until_closing(client, db_session):
    await seed_pub(db_session)

    resp = await reserve(client, 1, "19:00", kind="whole_venue", party_size=40, duration_minutes=60)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["kind"], body["start_time"], body["end_time"]) == ("whole_venue", "19:00:00", "22:00:00")  # the duration does not matter
    row = await stored(db_session, body["cancel_token"])
    assert (row.table_id, row.party_size) == (None, 40)


async def test_the_whole_pub_cannot_be_reserved_over_a_table_reservation(client, db_session):
    await seed_pub(db_session)
    assert (await reserve(client, 1, "18:00", party_size=2)).status_code == 201  # 18:00-20:00

    overlapping = await reserve(client, 1, "19:00", kind="whole_venue", party_size=30, email="b@example.com")
    covering = await reserve(client, 1, "16:00", kind="whole_venue", party_size=30, email="c@example.com")
    after = await reserve(client, 1, "20:00", kind="whole_venue", party_size=30, email="d@example.com")

    assert overlapping.status_code == 409 and overlapping.json()["detail"] == {"errors": {"start_time": "tables_reserved"}}
    assert covering.status_code == 409
    assert after.status_code == 201  # from the moment the table is done


async def test_no_table_can_be_reserved_while_the_whole_pub_is_reserved(client, db_session):
    await seed_pub(db_session)
    assert (await reserve(client, 1, "20:00", kind="whole_venue", party_size=30)).status_code == 201  # 20:00-22:00

    inside = await reserve(client, 1, "20:30", email="b@example.com")
    crossing = await reserve(client, 1, "19:00", email="c@example.com")  # 19:00-21:00 runs into it
    ending_as_it_starts = await reserve(client, 1, "18:00", email="d@example.com")  # 18:00-20:00 ends exactly when it starts

    assert inside.status_code == 409 and inside.json()["detail"] == {"errors": {"start_time": "venue_reserved"}}
    assert crossing.status_code == 409
    assert ending_as_it_starts.status_code == 201


async def test_a_second_whole_pub_reservation_in_a_day_is_refused(client, db_session):
    await seed_pub(db_session)
    assert (await reserve(client, 1, "20:00", kind="whole_venue", party_size=30)).status_code == 201

    later = await reserve(client, 1, "21:00", kind="whole_venue", party_size=30, email="b@example.com")
    earlier = await reserve(client, 1, "12:00", kind="whole_venue", party_size=30, email="c@example.com")
    next_day = await reserve(client, 2, "20:00", kind="whole_venue", party_size=30, email="d@example.com")

    assert later.status_code == 409 and later.json()["detail"] == {"errors": {"start_time": "venue_reserved"}}
    assert earlier.status_code == 409
    assert next_day.status_code == 201


async def test_the_whole_pub_follows_the_hours_of_its_day(client, db_session):
    await seed_pub(db_session)
    await make_exception(db_session, day(1), closed=False, opens="16:00", closes="19:00")

    resp = await reserve(client, 1, "17:00", kind="whole_venue", party_size=30)

    assert resp.status_code == 201 and resp.json()["end_time"] == "19:00:00"


async def test_the_whole_pub_needs_a_start_within_the_hours_too(client, db_session):
    await seed_pub(db_session)

    early = await reserve(client, 1, "09:00", kind="whole_venue", party_size=30)
    late = await reserve(client, 1, "21:45", kind="whole_venue", party_size=30, email="b@example.com")

    assert (early.status_code, late.status_code) == (422, 422)


async def test_the_whole_pub_is_for_at_most_the_configured_party(client, db_session):
    await seed_pub(db_session)

    assert (await reserve(client, 1, "19:00", kind="whole_venue", party_size=200)).status_code == 201
    assert (await reserve(client, 2, "19:00", kind="whole_venue", party_size=201)).status_code == 422


async def test_a_cancelled_reservation_gives_its_place_back(client, db_session):
    await seed_pub(db_session, seats=(4,))
    table = (await reserve(client, 1, "18:00", party_size=3)).json()["cancel_token"]
    whole = None
    assert (await reserve(client, 1, "19:00", kind="whole_venue", party_size=30, email="b@example.com")).status_code == 409

    assert (await client.post(f"{BASE}/reservations/{table}/cancel")).status_code == 200
    whole = await reserve(client, 1, "19:00", kind="whole_venue", party_size=30, email="b@example.com")
    assert whole.status_code == 201
    assert (await reserve(client, 1, "20:00", party_size=3, email="c@example.com")).status_code == 409  # the whole pub holds it now

    assert (await client.post(f"{BASE}/reservations/{whole.json()['cancel_token']}/cancel")).status_code == 200
    assert (await reserve(client, 1, "20:00", party_size=3, email="c@example.com")).status_code == 201


# --- What the guest must give and what keeps bots out -----------------------------------------------------------


async def test_the_consent_to_processing_personal_data_is_required(client, db_session):
    await seed_pub(db_session)

    resp = await reserve(client, 1, consent=False)

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"consent": "required"}}
    assert await count_rows(db_session) == 0


@pytest.mark.parametrize(
    "override",
    [{"email": "not-an-address"}, {"name": "   "}, {"party_size": 0}, {"kind": "balcony"}, {"surprise": 1}, {"note": "x" * 501}, {"phone": "1" * 41}],
)
async def test_invalid_details_are_refused_by_validation(client, db_session, override):
    await seed_pub(db_session)

    resp = await client.post(f"{BASE}/reservations", json=reservation_body(1, "18:00") | override)

    assert resp.status_code == 422
    assert await count_rows(db_session) == 0


async def test_the_phone_and_the_note_are_optional(client, db_session):
    await seed_pub(db_session)

    resp = await reserve(client, 1, phone="", note="   ")

    assert resp.status_code == 201
    row = await stored(db_session, resp.json()["cancel_token"])
    assert (row.phone, row.note) == (None, None)


async def test_a_filled_honeypot_is_told_created_and_nothing_is_stored_or_sent(client, db_session, outbox):
    await seed_pub(db_session)

    resp = await reserve(client, 1, fax="http://spam.example")

    assert resp.status_code == 201
    assert await count_rows(db_session) == 0
    assert outbox == []


async def test_one_address_may_hold_only_so_many_upcoming_reservations(client, db_session):
    await seed_pub(db_session, seats=(2, 2, 2, 2, 2))
    limit = load_config().max_active_per_email

    for number in range(limit):
        assert (await reserve(client, number + 1, "18:00", email="Same@Example.com")).status_code == 201
    over = await reserve(client, limit + 1, "18:00", email="same@example.com")  # the same address in another case

    assert over.status_code == 422 and over.json()["detail"] == {"errors": {"email": "too_many"}}
    assert (await reserve(client, limit + 1, "18:00", email="other@example.com")).status_code == 201


async def test_a_cancelled_reservation_does_not_count_towards_the_limit(client, db_session):
    await seed_pub(db_session, seats=(2, 2, 2, 2, 2))
    limit = load_config().max_active_per_email
    tokens = [(await reserve(client, number + 1, "18:00")).json()["cancel_token"] for number in range(limit)]
    assert (await reserve(client, limit + 1, "18:00")).status_code == 422

    await client.post(f"{BASE}/reservations/{tokens[0]}/cancel")

    assert (await reserve(client, limit + 1, "18:00")).status_code == 201


async def test_a_refused_request_does_not_use_up_the_limit_or_send_anything(client, db_session, outbox):
    await seed_pub(db_session, seats=(2,))

    resp = await reserve(client, 1, "18:10")

    assert resp.status_code == 422
    assert await count_rows(db_session) == 0
    assert outbox == []


# --- E-mails ---------------------------------------------------------------------------------------------------------------


async def test_the_guest_gets_a_confirmation_with_the_cancel_link_and_the_pub_a_notice(client, db_session, outbox):
    tables = await seed_pub(db_session, seats=(4,))

    resp = await reserve(client, 2, "18:00", party_size=3, phone="+420 111", note="birthday")

    token = resp.json()["cancel_token"]
    assert [to_of(m) for m in outbox] == ["eva@example.com", "owner@example.com"]
    guest, owner = outbox
    guest_text = text_of(guest)
    assert guest["Subject"] == f"Rezervace potvrzena: {day(2).day}. {day(2).month}. {day(2).year} v 18:00"
    assert "18:00–20:00" in guest_text and "Počet osob: 3" in guest_text and "stůl" in guest_text
    assert f"https://pub.test/reservations/cancel/{token}" in guest_text
    assert tables[0].name not in guest_text  # the guest is not told which table
    owner_text = text_of(owner)
    assert tables[0].name in owner_text and "+420 111" in owner_text and "birthday" in owner_text and "eva@example.com" in owner_text
    assert "cancel" not in owner_text.lower()


async def test_the_confirmation_is_in_the_language_the_guest_reserved_in(client, db_session, outbox):
    await seed_pub(db_session)

    await reserve(client, 2, "18:00", language="en-GB")
    await reserve(client, 3, "18:00", language="de")

    english, _, german, _ = outbox
    assert english["Subject"] == f"Reservation confirmed: {day(2).isoformat()} at 18:00"
    assert "We look forward" in text_of(english)
    assert german["Subject"].startswith("Rezervace potvrzena")  # an unknown language falls back to the default


async def test_the_stored_language_is_the_resolved_one(client, db_session):
    await seed_pub(db_session)

    for offset, (language, expected) in enumerate((("en-US", "en"), ("cs", "cs"), ("fr", "cs"), (None, "cs")), start=1):
        resp = await client.post(f"{BASE}/reservations", json=reservation_body(offset, "18:00", language=language, email=f"guest{offset}@example.com"))
        assert (await stored(db_session, resp.json()["cancel_token"])).language == expected, language


async def test_without_a_notice_address_the_pub_is_only_logged(client, db_session, outbox, caplog):
    await seed_pub(db_session)
    install_overrides(_app, db_session, settings=make_settings(booking_notify_mail="", contact_mail=""))

    with caplog.at_level(logging.WARNING):
        resp = await reserve(client, 1)

    assert resp.status_code == 201
    assert [to_of(m) for m in outbox] == ["eva@example.com"]
    assert any("nobody is notified" in record.getMessage() for record in caplog.records)


async def test_the_contact_mail_is_the_notice_address_when_no_other_is_set(client, db_session, outbox):
    await seed_pub(db_session)
    install_overrides(_app, db_session, settings=make_settings(booking_notify_mail="", contact_mail="contact@example.com"))

    await reserve(client, 1)

    assert [to_of(m) for m in outbox] == ["eva@example.com", "contact@example.com"]


async def test_the_two_mails_can_be_switched_off(client, db_session, outbox):
    await seed_pub(db_session)
    config = load_config()
    config.send_confirmation = False
    config.notify_admin = False
    _app.dependency_overrides[get_config] = lambda: config

    resp = await reserve(client, 1)

    assert resp.status_code == 201
    assert outbox == []


async def test_a_mail_that_cannot_be_sent_does_not_undo_the_reservation(client, db_session, monkeypatch, caplog):
    await seed_pub(db_session)

    async def broken(*args, **kwargs):
        raise OSError("smtp is down")

    monkeypatch.setattr(reservation_mail, "send_email", broken)

    with caplog.at_level(logging.ERROR):
        resp = await reserve(client, 1)

    assert resp.status_code == 201
    assert await count_rows(db_session) == 1
    assert any("Could not send" in record.getMessage() for record in caplog.records)


# --- The guest's own page and cancelling ----------------------------------------------------------------------------------------


async def test_the_guest_sees_their_reservation_without_the_email_or_the_table(client, db_session):
    await seed_pub(db_session)
    token = (await reserve(client, 1, "18:00", party_size=2)).json()["cancel_token"]

    resp = await client.get(f"{BASE}/reservations/{token}")

    assert resp.status_code == 200
    assert resp.json() == {
        "kind": "table",
        "day": day(1).isoformat(),
        "start_time": "18:00:00",
        "end_time": "20:00:00",
        "party_size": 2,
        "name": "Eva Nováková",
        "status": "confirmed",
        "cancelled_at": None,
    }


async def test_an_unknown_token_is_a_404_for_both_looking_and_cancelling(client, db_session):
    assert (await client.get(f"{BASE}/reservations/nope")).status_code == 404
    assert (await client.post(f"{BASE}/reservations/nope/cancel")).status_code == 404


async def test_opening_the_page_cancels_nothing_only_the_post_does(client, db_session, outbox):
    await seed_pub(db_session)
    token = (await reserve(client, 1)).json()["cancel_token"]
    outbox.clear()

    await client.get(f"{BASE}/reservations/{token}")

    assert (await stored(db_session, token)).status == "confirmed"
    assert outbox == []


async def test_cancelling_by_the_link_frees_the_table_and_tells_the_guest(client, db_session, outbox):
    await seed_pub(db_session, seats=(4,))
    token = (await reserve(client, 1, "18:00", party_size=3)).json()["cancel_token"]
    outbox.clear()

    resp = await client.post(f"{BASE}/reservations/{token}/cancel")

    assert resp.status_code == 200 and resp.json()["status"] == "cancelled" and resp.json()["cancelled_at"]
    row = await stored(db_session, token)
    assert (row.status, row.cancelled_by, row.cancel_note) == ("cancelled", "guest", None)
    assert [to_of(m) for m in outbox] == ["eva@example.com"]
    assert outbox[0]["Subject"].startswith("Rezervace zrušena")
    assert (await reserve(client, 1, "18:00", party_size=3, email="b@example.com")).status_code == 201  # the table is free again


async def test_pressing_cancel_again_changes_nothing_and_sends_nothing(client, db_session, outbox):
    await seed_pub(db_session)
    token = (await reserve(client, 1)).json()["cancel_token"]
    await client.post(f"{BASE}/reservations/{token}/cancel")
    cancelled_at = (await stored(db_session, token)).cancelled_at
    outbox.clear()

    again = await client.post(f"{BASE}/reservations/{token}/cancel")

    assert again.status_code == 200 and again.json()["status"] == "cancelled"
    assert (await stored(db_session, token)).cancelled_at == cancelled_at
    assert outbox == []


async def test_an_old_reservation_is_purged_when_a_new_one_is_made(client, db_session):
    tables = await seed_pub(db_session, seats=(4,))
    old = Reservation(
        kind="table",
        table_id=tables[0].id,
        day=day(-400),
        start_time=time(18),
        end_time=time(20),
        party_size=2,
        name="Old",
        email="old@example.com",
        consent_at=datetime(2025, 1, 1),
        language="cs",
    )
    recent = Reservation(
        kind="table",
        table_id=tables[0].id,
        day=day(-30),
        start_time=time(18),
        end_time=time(20),
        party_size=2,
        name="Recent",
        email="recent@example.com",
        consent_at=datetime(2026, 1, 1),
        language="cs",
    )
    db_session.add_all([old, recent])
    await db_session.commit()

    await reserve(client, 1)

    names = {row.name for row in (await db_session.scalars(select(Reservation))).all()}
    assert names == {"Recent", "Eva Nováková"}
