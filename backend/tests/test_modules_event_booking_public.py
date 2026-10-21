# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The public side of the booking module: what a visitor is shown, how they
book, and cancelling by the link in the e-mail.

Mounts just this module's router on a throwaway app (see booking_support.py),
with the clock fixed and the database a rolled-back session. E-mails are
captured through fastapi-mail's recorder (MAIL_SUPPRESS_SEND), so nothing is
ever sent for real."""

import logging
import time as time_module
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.modules.event_booking import mail as booking_mail
from app.modules.event_booking import service
from app.modules.event_booking.config import get_config, load_config
from app.modules.event_booking.models import STATUS_CANCELLED, Booking
from app.modules.forms.models import FormSubmission
from tests.booking_support import (  # noqa: F401  (outbox is a fixture)
    BASE,
    GOOD_ANSWERS,
    NOW,
    QUESTIONS,
    Q_EXTRA,
    Q_KIND,
    Q_NOTE,
    TODAY,
    book,
    booking_app,
    booking_body,
    clear_tables,
    count_rows,
    dates_block,
    day,
    install_overrides,
    make_settings,
    outbox,
    seed,
    text_of,
    to_of,
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


_count = count_rows
_book = book


# --- What the event list is told ---------------------------------------------------------------------


async def test_by_events_lists_the_registration_of_a_listed_event(client, db_session):
    _, event, registration = await seed(db_session, blocks=[dates_block(3)], description="Come along")

    resp = await client.get(f"{BASE}/by-events", params={"ids": f"{event.id},{uuid.uuid4()}"})

    assert resp.status_code == 200
    assert resp.json() == [
        {
            "event_id": str(event.id),
            "registration_id": str(registration.id),
            "name": "Sign-up",
            "description": "Come along",
            "access": "public",
            "is_open": True,
            "requires_login": False,
        }
    ]


async def test_by_events_marks_an_authenticated_registration_as_needing_login(client, db_session):
    _, event, _ = await seed(db_session, access="authenticated")

    brief = (await client.get(f"{BASE}/by-events", params={"ids": str(event.id)})).json()[0]

    assert brief["requires_login"] is True and brief["access"] == "authenticated"


async def test_by_events_does_not_mention_a_link_registration_without_its_token(client, db_session):
    _, event, registration = await seed(db_session, access="link")

    def ask(**params):
        return client.get(f"{BASE}/by-events", params={"ids": str(event.id), **params})

    assert (await ask()).json() == []
    assert (await ask(token="wrong")).json() == []
    assert (await ask(token=registration.link_token[:-1])).json() == []
    shown = (await ask(token=registration.link_token)).json()
    assert [item["registration_id"] for item in shown] == [str(registration.id)]


async def test_by_events_reports_whether_registering_is_possible_right_now(client, db_session):
    _, open_event, open_registration = await seed(db_session, article={"slug": "open"})
    _, closed_event, _ = await seed(db_session, article={"slug": "closed"}, is_open=False)
    _, over_event, _ = await seed(db_session, article={"slug": "over"}, event={"start": day(-3), "end_date": day(-1)})
    _, today_event, _ = await seed(db_session, article={"slug": "today"}, event={"start": TODAY})
    _, archived_event, _ = await seed(db_session, article={"slug": "archived", "status": "archived"})
    ids = ",".join(str(event.id) for event in (open_event, closed_event, over_event, today_event, archived_event))

    shown = {item["event_id"]: item["is_open"] for item in (await client.get(f"{BASE}/by-events", params={"ids": ids})).json()}

    assert shown == {
        str(open_event.id): True,
        str(closed_event.id): False,
        str(over_event.id): False,
        str(today_event.id): True,  # an event today is not over yet
        str(archived_event.id): False,  # still shown, but nothing new may be booked
    }


async def test_by_events_hides_registrations_of_drafts_and_out_of_window_articles(client, db_session):
    _, draft, _ = await seed(db_session, article={"slug": "draft", "status": "draft"})
    _, expired, _ = await seed(db_session, article={"slug": "expired", "display_to": day(-1)})
    _, embargoed, _ = await seed(db_session, article={"slug": "embargoed", "display_from": day(1)})

    resp = await client.get(f"{BASE}/by-events", params={"ids": ",".join(str(event.id) for event in (draft, expired, embargoed))})

    assert resp.json() == []


async def test_by_events_rejects_malformed_and_too_many_ids(client):
    assert (await client.get(f"{BASE}/by-events", params={"ids": "nope"})).status_code == 422
    assert (await client.get(f"{BASE}/by-events", params={"ids": ",".join(str(uuid.uuid4()) for _ in range(101))})).status_code == 422
    assert (await client.get(f"{BASE}/by-events", params={"ids": ",".join(str(uuid.uuid4()) for _ in range(100))})).status_code == 200
    assert (await client.get(f"{BASE}/by-events")).status_code == 422


# --- The definition of a registration -----------------------------------------------------------------


async def test_a_registration_is_returned_with_its_questions_and_how_to_pick_a_day(client, db_session):
    _, event, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 5)])

    resp = await client.get(f"{BASE}/registrations/{registration.id}")

    body = resp.json()
    assert resp.status_code == 200
    assert body["id"] == str(registration.id) and body["event_id"] == str(event.id)
    assert body["event_title"] == event.title and body["is_open"] is True
    assert body["finite_days"] is True
    assert body["max_days_ahead"] == load_config().max_days_ahead
    assert body["privacy_url"] == load_config().privacy_url
    assert [question["id"] for question in body["questions"]] == [Q_NOTE, Q_KIND, Q_EXTRA]
    assert body["questions"][2]["conditions"] == [{"question_id": Q_KIND, "operator": "equals", "value": "b"}]
    assert "link_token" not in body


@pytest.mark.parametrize(
    ("blocks", "finite"),
    [
        ([], False),
        ([dates_block(3)], True),
        ([dates_block(3), dates_block(5, times=["10:00"])], True),
        ([{"days_mode": "weekdays", "weekdays": [0], "range_from": day(0).isoformat(), "range_to": day(60).isoformat(), "time_mode": "all_day"}], False),
        ([{"days_mode": "any_future", "time_mode": "all_day"}], False),
    ],
)
async def test_finite_days_means_every_block_is_a_list_of_days(client, db_session, blocks, finite):
    _, _, registration = await seed(db_session, blocks=blocks)

    assert (await client.get(f"{BASE}/registrations/{registration.id}")).json()["finite_days"] is finite


async def test_a_link_registration_is_a_404_without_its_token_and_looks_like_one_that_does_not_exist(client, db_session):
    _, _, registration = await seed(db_session, access="link")

    hidden = await client.get(f"{BASE}/registrations/{registration.id}")
    missing = await client.get(f"{BASE}/registrations/{uuid.uuid4()}")
    shown = await client.get(f"{BASE}/registrations/{registration.id}", params={"token": registration.link_token})

    assert hidden.status_code == 404 and hidden.json() == missing.json()
    assert shown.status_code == 200
    for path in ("days", "slots?date=" + day(1).isoformat()):
        assert (await client.get(f"{BASE}/registrations/{registration.id}/{path}")).status_code == 404


async def test_a_registration_of_a_draft_or_an_out_of_window_article_is_a_404(client, db_session):
    _, _, draft = await seed(db_session, article={"slug": "draft", "status": "draft"})
    _, _, expired = await seed(db_session, article={"slug": "expired", "display_to": day(-1)})

    for registration in (draft, expired):
        assert (await client.get(f"{BASE}/registrations/{registration.id}")).status_code == 404


async def test_an_archived_article_keeps_its_registration_visible_but_closed(client, db_session):
    _, _, registration = await seed(db_session, article={"slug": "old", "status": "archived"}, blocks=[dates_block(3)])

    shown = await client.get(f"{BASE}/registrations/{registration.id}")
    days = await client.get(f"{BASE}/registrations/{registration.id}/days")
    booked = await _book(client, registration, offset=3, answers=GOOD_ANSWERS)

    assert shown.status_code == 200 and shown.json()["is_open"] is False
    assert days.json() == {"days": []}
    assert booked.status_code == 409
    assert booked.json()["detail"] == {"errors": {"_form": "closed"}}


# --- Days and times on offer -----------------------------------------------------------------------------


async def test_days_lists_the_days_with_a_free_place_and_how_many_slots_are_free(client, db_session):
    _, _, registration = await seed(
        db_session,
        questions=QUESTIONS,
        blocks=[dates_block(2, 4, 6, times=["10:00", "11:00"]), dates_block(8)],
        capacity=1,
    )
    await _book(client, registration, offset=4, slot_time="10:00")  # day 4: one of two slots gone
    await _book(client, registration, offset=6, slot_time="10:00", email="b@example.com")
    await _book(client, registration, offset=6, slot_time="11:00", email="c@example.com")  # day 6: full
    await _book(client, registration, offset=8, email="d@example.com")  # day 8 (all day, capacity 1): full

    days = (await client.get(f"{BASE}/registrations/{registration.id}/days")).json()["days"]

    assert days == [{"date": day(2).isoformat(), "free_slots": 2}, {"date": day(4).isoformat(), "free_slots": 1}]


async def test_days_can_be_limited_to_a_month_and_never_include_the_past_or_the_horizon(client, db_session):
    first_of_next_month = (TODAY.replace(day=1) + timedelta(days=32)).replace(day=1)
    _, _, registration = await seed(
        db_session,
        blocks=[
            {
                "days_mode": "dates",
                "dates": [day(-5).isoformat(), TODAY.isoformat(), first_of_next_month.isoformat(), day(400).isoformat()],
                "time_mode": "all_day",
            }
        ],
    )

    everything = (await client.get(f"{BASE}/registrations/{registration.id}/days")).json()["days"]
    next_month = (await client.get(f"{BASE}/registrations/{registration.id}/days", params={"month": first_of_next_month.strftime("%Y-%m")})).json()["days"]

    assert [item["date"] for item in everything] == [TODAY.isoformat(), first_of_next_month.isoformat()]
    assert [item["date"] for item in next_month] == [first_of_next_month.isoformat()]
    assert (await client.get(f"{BASE}/registrations/{registration.id}/days", params={"month": "2026-13"})).status_code == 422
    assert (await client.get(f"{BASE}/registrations/{registration.id}/days", params={"month": "soon"})).status_code == 422


async def test_without_any_blocks_every_future_day_up_to_the_horizon_is_offered_all_day(client, db_session):
    _, _, registration = await seed(db_session)

    days = (await client.get(f"{BASE}/registrations/{registration.id}/days")).json()["days"]

    assert days[0]["date"] == TODAY.isoformat()
    assert days[-1]["date"] == day(load_config().max_days_ahead).isoformat()
    assert len(days) == load_config().max_days_ahead + 1


async def test_slots_of_a_day_show_only_the_times_with_room_and_how_much(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(2, times=["09:00", "10:00", "11:00"], capacity=2)])
    await _book(client, registration, offset=2, slot_time="09:00")
    await _book(client, registration, offset=2, slot_time="09:00", email="b@example.com")  # 09:00 full
    await _book(client, registration, offset=2, slot_time="10:00", email="c@example.com")

    slots = (await client.get(f"{BASE}/registrations/{registration.id}/slots", params={"date": day(2).isoformat()})).json()

    assert slots == {
        "date": day(2).isoformat(),
        "slots": [{"time": "10:00:00", "capacity": 2, "free": 1}, {"time": "11:00:00", "capacity": 2, "free": 2}],
    }


async def test_a_whole_day_slot_has_no_time_and_a_capacity_per_day(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(2, capacity=3)])
    await _book(client, registration, offset=2)

    slots = (await client.get(f"{BASE}/registrations/{registration.id}/slots", params={"date": day(2).isoformat()})).json()

    assert slots["slots"] == [{"time": None, "capacity": 3, "free": 2}]


async def test_slots_never_include_times_already_gone_today(client, db_session):
    _, _, registration = await seed(db_session, blocks=[dates_block(0, times=["08:00", "09:00", "09:01", "18:00"])])

    slots = (await client.get(f"{BASE}/registrations/{registration.id}/slots", params={"date": TODAY.isoformat()})).json()["slots"]

    assert [slot["time"] for slot in slots] == ["09:01:00", "18:00:00"]


async def test_slots_of_a_day_that_is_not_offered_are_empty(client, db_session):
    _, _, registration = await seed(db_session, blocks=[dates_block(2)])

    other = (await client.get(f"{BASE}/registrations/{registration.id}/slots", params={"date": day(3).isoformat()})).json()

    assert other["slots"] == []
    assert (await client.get(f"{BASE}/registrations/{registration.id}/slots")).status_code == 422


async def test_a_closed_registration_offers_nothing(client, db_session):
    _, _, registration = await seed(db_session, blocks=[dates_block(2)], is_open=False)

    days = await client.get(f"{BASE}/registrations/{registration.id}/days")
    slots = await client.get(f"{BASE}/registrations/{registration.id}/slots", params={"date": day(2).isoformat()})

    assert days.json() == {"days": []} and slots.json()["slots"] == []


# --- Booking --------------------------------------------------------------------------------------------


async def test_a_visitor_books_an_all_day_slot_and_answers_are_stored_with_it(client, db_session, outbox):
    _, event, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    resp = await _book(client, registration, offset=3, name="  Eva Nováková ", email="Eva@Example.com", answers={Q_NOTE: "Hi", Q_KIND: "b", Q_EXTRA: "More"})

    assert resp.status_code == 201
    created = resp.json()
    assert (created["slot_date"], created["slot_time"]) == (day(3).isoformat(), None)
    booking = (await db_session.scalars(select(Booking))).one()
    assert created["cancel_token"] == booking.cancel_token and len(booking.cancel_token) >= 30
    assert (booking.name, booking.email, booking.status) == ("Eva Nováková", "Eva@example.com", "confirmed")
    assert booking.user_sub is None and booking.language == "cs"
    assert booking.consent_at is not None and booking.registration_id == registration.id
    submission = await db_session.get(FormSubmission, booking.submission_id)
    assert {entry["question_id"]: entry["display"] for entry in submission.answers if entry["shown"]} == {Q_NOTE: "Hi", Q_KIND: "Beta", Q_EXTRA: "More"}


async def test_a_visitor_books_a_timed_slot(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00", "11:00"])])

    resp = await _book(client, registration, offset=3, slot_time="11:00")

    assert resp.status_code == 201 and resp.json()["slot_time"] == "11:00:00"
    booking = (await db_session.scalars(select(Booking))).one()
    assert booking.slot_time.strftime("%H:%M") == "11:00"


async def test_booking_sends_the_confirmation_with_a_cancel_link_and_notifies_the_administrator(client, db_session, outbox):
    _, event, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00"])], name="Tour sign-up", article={"slug": "tour"}, event={"title": "Castle tour"})

    resp = await _book(client, registration, offset=3, slot_time="10:00")

    token = resp.json()["cancel_token"]
    assert len(outbox) == 2
    confirmation = next(message for message in outbox if "eva@example.com" in message["To"])
    notice = next(message for message in outbox if "owner@example.com" in message["To"])
    assert confirmation["Subject"] == "Potvrzení přihlášky: Castle tour"
    body = text_of(confirmation)
    assert "Eva Nováková" in body and "Tour sign-up" in body and "10:00" in body
    assert f"{day(3).day}. {day(3).month}. {day(3).year}" in body
    assert f"https://app.test/bookings/cancel/{token}" in body
    assert notice["Subject"].startswith("Nová přihláška: Castle tour")
    assert "eva@example.com" in text_of(notice) and "cancel" not in text_of(notice).lower()


async def test_the_confirmation_comes_in_the_language_of_the_request(client, db_session, outbox):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)], event={"title": "Tour"})

    await _book(client, registration, offset=3, language="en-US")

    confirmation = next(message for message in outbox if "eva@example.com" in message["To"])
    assert confirmation["Subject"] == "Booking confirmation: Tour"
    assert "all day" in text_of(confirmation) and f"{day(3).isoformat()}" in text_of(confirmation)
    assert (await db_session.scalars(select(Booking.language))).one() == "en"


@pytest.mark.parametrize(("sent", "stored"), [("de", "cs"), (None, "cs"), ("EN_gb", "en"), ("cs-CZ", "cs")])
async def test_an_unsupported_language_falls_back_to_the_default(client, db_session, outbox, sent, stored):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    resp = await _book(client, registration, offset=3, language=sent)

    assert resp.status_code == 201
    assert (await db_session.scalars(select(Booking.language))).one() == stored


async def test_the_switches_in_the_config_turn_the_mails_off(client, db_session, outbox):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4)])
    config = load_config().model_copy(update={"send_confirmation": False, "notify_admin": False})
    _app.dependency_overrides[get_config] = lambda: config

    assert (await _book(client, registration, offset=3)).status_code == 201

    assert len(outbox) == 0

    only_notice = load_config().model_copy(update={"send_confirmation": False})
    _app.dependency_overrides[get_config] = lambda: only_notice
    assert (await _book(client, registration, offset=4)).status_code == 201
    assert [to_of(message) for message in outbox] == ["owner@example.com"]


async def test_the_notice_falls_back_to_the_contact_address_and_without_any_address_is_only_logged(client, db_session, outbox, caplog):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4)])
    install_overrides(_app, db_session, settings=make_settings(booking_notify_mail="", contact_mail="contact@example.com"))

    await _book(client, registration, offset=3)

    assert sorted(to_of(message) for message in outbox) == ["contact@example.com", "eva@example.com"]

    outbox.clear()
    install_overrides(_app, db_session, settings=make_settings(booking_notify_mail="", contact_mail=""))
    with caplog.at_level(logging.WARNING, logger=service.__name__):
        resp = await _book(client, registration, offset=4)

    assert resp.status_code == 201
    assert [to_of(message) for message in outbox] == ["eva@example.com"]
    assert any("nobody is notified" in record.getMessage() for record in caplog.records)


async def test_a_failing_mail_never_breaks_the_booking(client, db_session, monkeypatch, caplog):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    async def _broken(*args, **kwargs):
        raise ConnectionError("smtp is down")

    monkeypatch.setattr(booking_mail, "send_email", _broken)

    with caplog.at_level(logging.ERROR, logger=booking_mail.__name__):
        resp = await _book(client, registration, offset=3)

    assert resp.status_code == 201
    assert await _count(db_session) == 1
    assert sum("Could not send" in record.getMessage() for record in caplog.records) == 2  # the confirmation and the notice


async def test_consent_is_required(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    resp = await _book(client, registration, offset=3, consent=False)

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {"consent": "required"}}
    assert await _count(db_session) == 0


async def test_every_form_problem_is_reported_at_once_and_nothing_is_stored(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    resp = await _book(client, registration, offset=3, consent=False, answers={Q_KIND: "b"})

    assert resp.status_code == 422
    assert resp.json()["detail"]["errors"] == {"consent": "required", Q_NOTE: "required", Q_EXTRA: "required"}
    assert await _count(db_session) == 0 and await _count(db_session, FormSubmission) == 0


async def test_answers_to_hidden_questions_are_not_kept_and_a_conditional_one_is_required_when_shown(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    resp = await _book(client, registration, offset=3, answers={Q_NOTE: "x", Q_KIND: "a", Q_EXTRA: "should be dropped"})

    assert resp.status_code == 201
    submission = (await db_session.scalars(select(FormSubmission))).one()
    extra = next(entry for entry in submission.answers if entry["question_id"] == Q_EXTRA)
    assert extra["shown"] is False and extra["value"] is None


async def test_an_answer_to_an_unknown_question_is_refused(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    resp = await _book(client, registration, offset=3, answers={**GOOD_ANSWERS, str(uuid.uuid4()): "?"})

    assert resp.status_code == 422


@pytest.mark.parametrize(
    "fields",
    [{"name": ""}, {"name": "   "}, {"email": "not-an-address"}, {"email": ""}, {"slot_date": "soon"}, {"unexpected": 1}],
)
async def test_malformed_bodies_are_422(client, db_session, fields):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    assert (await _book(client, registration, offset=3, **fields)).status_code == 422
    assert await _count(db_session) == 0


@pytest.mark.parametrize(
    ("blocks", "offset", "slot_time"),
    [
        ([dates_block(3)], 4, None),  # a day nobody offered
        ([dates_block(3)], 3, "10:00"),  # a time on an all-day slot
        ([dates_block(3, times=["10:00"])], 3, None),  # all day on a timed day
        ([dates_block(3, times=["10:00"])], 3, "10:30"),  # a time that is not on offer
        ([dates_block(3, times=["10:00"])], 3, "10:00:30"),
        ([dates_block(-1)], -1, None),  # yesterday
        ([dates_block(0, times=["08:00"])], 0, "08:00"),  # earlier today
        ([dates_block(0, times=["09:00"])], 0, "09:00"),  # right now
        ([dates_block(400)], 400, None),  # beyond the horizon
    ],
)
async def test_a_slot_that_is_not_on_offer_is_refused(client, db_session, blocks, offset, slot_time):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=blocks)

    resp = await _book(client, registration, offset=offset, slot_time=slot_time)

    assert resp.status_code == 422
    assert resp.json()["detail"] == {"errors": {"slot": "not_offered"}}
    assert await _count(db_session) == 0


async def test_a_later_time_today_and_today_all_day_can_still_be_booked(client, db_session):
    # No questions here: a question id belongs to one form, so two registrations cannot share QUESTIONS.
    _, _, timed = await seed(db_session, article={"slug": "timed"}, blocks=[dates_block(0, times=["09:01"])])
    _, _, all_day = await seed(db_session, article={"slug": "all-day"}, blocks=[dates_block(0)])

    assert (await _book(client, timed, offset=0, slot_time="09:01", answers={})).status_code == 201
    assert (await _book(client, all_day, offset=0, answers={})).status_code == 201


async def test_without_blocks_any_future_day_all_day_can_be_booked(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS)

    assert (await _book(client, registration, offset=40)).status_code == 201
    assert (await _book(client, registration, offset=40, email="other@example.com")).status_code == 409  # capacity 1


async def test_a_full_slot_is_a_409_and_the_next_one_still_works(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00", "11:00"])])

    first = await _book(client, registration, offset=3, slot_time="10:00")
    second = await _book(client, registration, offset=3, slot_time="10:00", email="b@example.com")
    other = await _book(client, registration, offset=3, slot_time="11:00", email="b@example.com")

    assert (first.status_code, second.status_code, other.status_code) == (201, 409, 201)
    assert second.json()["detail"] == {"errors": {"slot": "full"}}
    assert await _count(db_session) == 2


async def test_a_slot_takes_as_many_people_as_its_capacity(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00"])], capacity=3)

    statuses = [(await _book(client, registration, offset=3, slot_time="10:00", email=f"p{n}@example.com")).status_code for n in range(4)]

    assert statuses == [201, 201, 201, 409]


async def test_a_blocks_own_capacity_beats_the_registrations(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, capacity=1), dates_block(4, capacity=2)], capacity=5)

    one_day = [(await _book(client, registration, offset=3, email=f"p{n}@example.com")).status_code for n in range(2)]
    other_day = [(await _book(client, registration, offset=4, email=f"p{n}@example.com")).status_code for n in range(3)]

    assert one_day == [201, 409] and other_day == [201, 201, 409]


async def test_the_whole_day_capacity_is_per_day_not_per_person(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4)], capacity=2)

    assert [(await _book(client, registration, offset=3, email=f"p{n}@example.com")).status_code for n in range(3)] == [201, 201, 409]
    assert (await _book(client, registration, offset=4)).status_code == 201


async def test_a_cancelled_booking_frees_its_place(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])
    token = (await _book(client, registration, offset=3)).json()["cancel_token"]
    assert (await _book(client, registration, offset=3, email="b@example.com")).status_code == 409

    assert (await client.post(f"{BASE}/bookings/{token}/cancel")).status_code == 200

    assert (await _book(client, registration, offset=3, email="b@example.com")).status_code == 201
    assert await _count(db_session, Booking, Booking.status == "confirmed") == 1


# --- When registering is possible ----------------------------------------------------------------------


async def test_a_closed_registration_cannot_be_booked(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)], is_open=False)

    resp = await _book(client, registration, offset=3)

    assert resp.status_code == 409 and resp.json()["detail"] == {"errors": {"_form": "closed"}}


async def test_an_event_that_is_over_cannot_be_booked_but_one_still_running_can(client, db_session):
    _, _, over = await seed(db_session, article={"slug": "over"}, blocks=[dates_block(3)], event={"start": day(-4), "end_date": day(-1)})
    _, _, running = await seed(db_session, article={"slug": "running"}, blocks=[dates_block(3)], event={"start": day(-4), "end_date": TODAY})
    _, _, single = await seed(db_session, article={"slug": "single"}, blocks=[dates_block(3)], event={"start": day(-1)})

    assert (await _book(client, over, offset=3, answers={})).status_code == 409
    assert (await _book(client, running, offset=3, answers={})).status_code == 201
    assert (await _book(client, single, offset=3, answers={})).status_code == 409


@pytest.mark.parametrize(
    ("article", "status"),
    [
        ({"status": "draft"}, 404),
        ({"status": "archived"}, 409),
        ({"display_to": -1}, 404),
        ({"display_from": 1}, 404),
        ({"display_from": -2, "display_to": 2}, 201),
    ],
)
async def test_the_articles_visibility_decides_whether_a_booking_is_possible(client, db_session, article, status):
    fields = {key: day(value) if key.startswith("display_") else value for key, value in article.items()}
    _, _, registration = await seed(db_session, article={"slug": "a", **fields}, questions=QUESTIONS, blocks=[dates_block(3)])

    assert (await _book(client, registration, offset=3)).status_code == status


async def test_booking_an_unknown_registration_is_a_404(client):
    resp = await client.post(f"{BASE}/registrations/{uuid.uuid4()}/bookings", json=booking_body())

    assert resp.status_code == 404


# --- Who may book --------------------------------------------------------------------------------------


async def test_an_authenticated_registration_needs_a_signed_in_user(client, db_session, make_access_token):
    _, _, registration = await seed(db_session, access="authenticated", questions=QUESTIONS, blocks=[dates_block(3, 4)])
    sub = uuid.uuid4()

    anonymous = await _book(client, registration, offset=3)
    garbage = await _book(client, registration, offset=3, headers={"Authorization": "Bearer nonsense"})
    expired = await _book(client, registration, offset=3, headers={"Authorization": f"Bearer {make_access_token(exp=int(time_module.time()) - 60)}"})
    signed_in = await _book(client, registration, offset=3, headers={"Authorization": f"Bearer {make_access_token(sub=str(sub))}"})

    assert (anonymous.status_code, garbage.status_code, expired.status_code) == (401, 401, 401)
    assert anonymous.headers["www-authenticate"] == "Bearer"
    assert signed_in.status_code == 201
    booking = (await db_session.scalars(select(Booking))).one()
    assert booking.user_sub == sub


async def test_an_authenticated_registration_can_be_read_by_anyone_but_booked_only_by_a_user(client, db_session):
    _, _, registration = await seed(db_session, access="authenticated", blocks=[dates_block(3)])

    assert (await client.get(f"{BASE}/registrations/{registration.id}")).json()["requires_login"] is True
    assert (await client.get(f"{BASE}/registrations/{registration.id}/days")).json()["days"]


async def test_a_public_registration_can_be_booked_with_or_without_signing_in(client, db_session, make_access_token):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4, 5)])
    sub = uuid.uuid4()

    anonymous = await _book(client, registration, offset=3)
    signed_in = await _book(client, registration, offset=4, headers={"Authorization": f"Bearer {make_access_token(sub=str(sub))}"})
    stale = await _book(client, registration, offset=5, headers={"Authorization": "Bearer stale"})

    assert (anonymous.status_code, signed_in.status_code, stale.status_code) == (201, 201, 201)
    subs = {booking.slot_date: booking.user_sub for booking in (await db_session.scalars(select(Booking))).all()}
    assert subs == {day(3): None, day(4): sub, day(5): None}


async def test_a_link_registration_can_only_be_booked_with_its_token(client, db_session):
    _, _, registration = await seed(db_session, access="link", questions=QUESTIONS, blocks=[dates_block(3, 4)])

    without = await _book(client, registration, offset=3)
    wrong = await _book(client, registration, offset=3, token="nope")
    right = await _book(client, registration, offset=3, token=registration.link_token)

    assert (without.status_code, wrong.status_code, right.status_code) == (404, 404, 201)
    assert await _count(db_session) == 1


# --- Spam brakes ----------------------------------------------------------------------------------------


async def test_a_filled_honeypot_is_told_it_worked_but_nothing_is_stored_or_sent(client, db_session, outbox):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])

    resp = await _book(client, registration, offset=3, fax="+420 123 456 789")

    assert resp.status_code == 201 and resp.json()["cancel_token"]
    assert await _count(db_session) == 0 and await _count(db_session, FormSubmission) == 0
    assert len(outbox) == 0
    assert (await client.get(f"{BASE}/bookings/{resp.json()['cancel_token']}")).status_code == 404


async def test_an_empty_or_blank_honeypot_is_an_ordinary_booking(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4)])

    assert (await _book(client, registration, offset=3, fax="")).status_code == 201
    assert (await _book(client, registration, offset=4, fax="   ")).status_code == 201
    assert await _count(db_session) == 2


async def test_one_address_may_hold_only_a_few_active_bookings_in_a_registration(client, db_session):
    limit = load_config().max_active_per_email
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(*range(1, limit + 4))], capacity=5)

    statuses = [(await _book(client, registration, offset=n, email="Same@Example.com" if n % 2 else "same@example.com")).status_code for n in range(1, limit + 2)]
    other = await _book(client, registration, offset=limit + 2, email="someone.else@example.com")

    assert statuses == [201] * limit + [422]
    assert other.status_code == 201
    refused = await _book(client, registration, offset=limit + 3, email="SAME@example.com")
    assert refused.json()["detail"] == {"errors": {"email": "too_many"}}


async def test_cancelled_and_past_bookings_do_not_count_towards_the_limit(client, db_session):
    limit = load_config().max_active_per_email
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(*range(1, limit + 3))], capacity=5)
    tokens = [(await _book(client, registration, offset=n)).json()["cancel_token"] for n in range(1, limit + 1)]
    assert (await _book(client, registration, offset=limit + 1)).status_code == 422

    await client.post(f"{BASE}/bookings/{tokens[0]}/cancel")
    assert (await _book(client, registration, offset=limit + 1)).status_code == 201

    booking = await service.get_booking_by_token(db_session, tokens[1])
    booking.slot_date = day(-3)  # a booking whose day has passed
    await db_session.commit()
    assert (await _book(client, registration, offset=limit + 2)).status_code == 201


async def test_the_limit_is_per_registration(client, db_session):
    limit = load_config().max_active_per_email
    _, _, first = await seed(db_session, article={"slug": "one"}, blocks=[dates_block(*range(1, limit + 2))], capacity=5)
    _, _, second = await seed(db_session, article={"slug": "two"}, blocks=[dates_block(1)], capacity=5)
    for offset in range(1, limit + 1):
        await _book(client, first, offset=offset, answers={})

    assert (await _book(client, first, offset=limit + 1, answers={})).status_code == 422
    assert (await _book(client, second, offset=1, answers={})).status_code == 201


# --- Cancelling by the link --------------------------------------------------------------------------------


async def test_the_cancel_page_shows_the_booking_without_the_address_and_cancels_nothing(client, db_session):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00"])], name="Tour sign-up", event={"title": "Castle tour"})
    token = (await _book(client, registration, offset=3, slot_time="10:00")).json()["cancel_token"]

    resp = await client.get(f"{BASE}/bookings/{token}")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_title": "Castle tour",
        "registration_name": "Tour sign-up",
        "slot_date": day(3).isoformat(),
        "slot_time": "10:00:00",
        "name": "Eva Nováková",
        "status": "confirmed",
        "cancelled_at": None,
    }
    assert "eva@example.com" not in resp.text
    assert (await client.get(f"{BASE}/bookings/{token}")).json()["status"] == "confirmed"  # a GET (a bot opening the link) cancels nothing


async def test_cancelling_is_a_post_and_idempotent(client, db_session, outbox):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)], event={"title": "Tour"})
    token = (await _book(client, registration, offset=3)).json()["cancel_token"]
    outbox.clear()

    first = await client.post(f"{BASE}/bookings/{token}/cancel")
    again = await client.post(f"{BASE}/bookings/{token}/cancel")

    assert first.status_code == again.status_code == 200
    assert first.json()["status"] == "cancelled" and first.json()["cancelled_at"]
    assert again.json()["cancelled_at"] == first.json()["cancelled_at"]
    assert len(outbox) == 1  # the cancellation is confirmed once
    assert outbox[0]["Subject"] == "Zrušení přihlášky: Tour" and "eva@example.com" in outbox[0]["To"]
    booking = (await db_session.scalars(select(Booking))).one()
    assert booking.status == STATUS_CANCELLED and booking.cancelled_at is not None
    assert (await client.request("DELETE", f"{BASE}/bookings/{token}")).status_code == 405


async def test_the_cancellation_mail_is_in_the_language_of_the_booking_and_can_be_switched_off(client, db_session, outbox):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3, 4)], event={"title": "Tour"})
    english = (await _book(client, registration, offset=3, language="en")).json()["cancel_token"]
    quiet = (await _book(client, registration, offset=4, language="en", email="b@example.com")).json()["cancel_token"]
    outbox.clear()

    await client.post(f"{BASE}/bookings/{english}/cancel")

    assert outbox[0]["Subject"] == "Booking cancelled: Tour"
    outbox.clear()
    quiet_config = load_config().model_copy(update={"send_confirmation": False})
    _app.dependency_overrides[get_config] = lambda: quiet_config
    await client.post(f"{BASE}/bookings/{quiet}/cancel")
    assert len(outbox) == 0


async def test_an_unknown_token_is_a_404_on_both_pages(client):
    assert (await client.get(f"{BASE}/bookings/{uuid.uuid4().hex}")).status_code == 404
    assert (await client.post(f"{BASE}/bookings/{uuid.uuid4().hex}/cancel")).status_code == 404


async def test_a_failing_cancellation_mail_does_not_undo_the_cancellation(client, db_session, monkeypatch):
    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])
    token = (await _book(client, registration, offset=3)).json()["cancel_token"]

    async def _broken(*args, **kwargs):
        raise ConnectionError("smtp is down")

    monkeypatch.setattr(booking_mail, "send_email", _broken)

    resp = await client.post(f"{BASE}/bookings/{token}/cancel")

    assert resp.status_code == 200 and resp.json()["status"] == "cancelled"


async def test_the_cancel_page_never_shows_an_administrators_note(client, db_session):
    from app.modules.event_booking.models import BookingChange

    _, _, registration = await seed(db_session, questions=QUESTIONS, blocks=[dates_block(3)])
    token = (await _book(client, registration, offset=3)).json()["cancel_token"]
    booking = await service.get_booking_by_token(db_session, token)
    db_session.add(BookingChange(booking_id=booking.id, kind="updated", note="secret internal remark", changes={}))
    await db_session.commit()

    resp = await client.get(f"{BASE}/bookings/{token}")

    assert "secret internal remark" not in resp.text
    assert set(resp.json()) == {"event_title", "registration_name", "slot_date", "slot_time", "name", "status", "cancelled_at"}


def test_the_fixed_clock_is_what_the_expectations_assume():
    assert NOW.date() == TODAY and NOW.hour == 9
