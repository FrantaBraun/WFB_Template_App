# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What an administrator can do to ONE booking: move it to another slot,
correct the name, the e-mail and the answers, or cancel it - each with an
optional note for the person, a history entry and (unless switched off) an
e-mail in the language the person booked in.

Same set-up as the other booking tests: a throwaway app, a fixed clock, a
rolled-back session; e-mails are captured, never sent. The races between two
requests are in test_modules_event_booking_concurrency.py."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.modules.event_booking import mail as booking_mail
from app.modules.event_booking import service
from app.modules.event_booking.models import Booking, BookingChange
from app.modules.event_booking.schemas import RegistrationUpdate
from app.modules.forms.models import FormSubmission
from tests.booking_support import (  # noqa: F401  (outbox is a fixture)
    BASE,
    GOOD_ANSWERS,
    QUESTIONS,
    Q_EXTRA,
    Q_KIND,
    Q_NOTE,
    book,
    booking_app,
    clear_tables,
    count_rows,
    dates_block,
    day,
    install_overrides,
    outbox,
    seed,
    text_of,
    to_of,
)

_app = booking_app()
CASTLE = {"title": "Castle tour"}


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
def admin_sub():
    return uuid.uuid4()


@pytest.fixture()
async def admin(db_session, make_access_token, admin_sub):
    db_session.add(User(auth_sub=admin_sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(admin_sub), role_name='user')}"}


@pytest.fixture()
async def world(client, db_session):
    """A registration with timed days (3: 10:00 and 11:00, 4: 10:00), an all-day
    day (6) and the three questions; capacity 1. The booking under test is
    Eva's, for day 3 at 10:00, made in Czech."""
    _, event, registration = await seed(
        db_session,
        questions=QUESTIONS,
        blocks=[dates_block(3, times=["10:00", "11:00"]), dates_block(4, times=["10:00"]), dates_block(6)],
        name="Tour sign-up",
        event=CASTLE,
    )
    token = (await book(client, registration, offset=3, slot_time="10:00")).json()["cancel_token"]
    booking = await service.get_booking_by_token(db_session, token)
    return type("World", (), {"registration": registration, "event": event, "token": token, "booking": booking})()


async def _patch(client, admin, booking, **body):
    return await client.patch(f"{BASE}/manage/bookings/{booking.id}", json=body, headers=admin)


async def _cancel(client, admin, booking, **body):
    return await client.post(f"{BASE}/manage/bookings/{booking.id}/cancel", json=body, headers=admin)


async def _reload(db_session, booking) -> Booking:
    await db_session.refresh(booking)
    return booking


async def _history(db_session, booking) -> list[BookingChange]:
    return list((await db_session.scalars(select(BookingChange).where(BookingChange.booking_id == booking.id).order_by(BookingChange.created_at))).all())


# --- Moving a booking ---------------------------------------------------------------------------------


async def test_a_booking_is_moved_to_a_free_slot_and_the_person_is_told(client, db_session, admin, admin_sub, world, outbox):
    outbox.clear()

    resp = await _patch(client, admin, world.booking, slot_date=day(4).isoformat(), slot_time="10:00", note="The castle is closed that morning.")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email_sent"] is True
    assert (body["booking"]["slot_date"], body["booking"]["slot_time"]) == (day(4).isoformat(), "10:00:00")
    moved = await _reload(db_session, world.booking)
    assert (moved.slot_date, moved.slot_time.strftime("%H:%M")) == (day(4), "10:00")
    assert moved.cancel_token == world.token and moved.status == "confirmed"
    change = body["booking"]["history"][0]
    assert change["kind"] == "updated" and change["note"] == "The castle is closed that morning."
    assert change["changes"] == {"slot_date": {"from": day(3).isoformat(), "to": day(4).isoformat()}}  # the time did not change
    assert change["notified"] is True and change["email_error"] is None and change["user_sub"] == str(admin_sub)
    assert len(outbox) == 1
    message = outbox[0]
    assert to_of(message) == "eva@example.com" and message["Subject"] == "Změna Vaší přihlášky: Castle tour"
    text = text_of(message)
    assert f"{day(3).day}. {day(3).month}. {day(3).year}" in text and f"{day(4).day}. {day(4).month}. {day(4).year}" in text
    assert "Poznámka pořadatele:\nThe castle is closed that morning." in text
    assert f"https://app.test/bookings/cancel/{world.token}" in text


async def test_the_old_slot_is_freed_and_the_new_one_taken(client, db_session, admin, world):
    await _patch(client, admin, world.booking, slot_date=day(4).isoformat(), slot_time="10:00")

    old = (await client.get(f"{BASE}/registrations/{world.registration.id}/slots", params={"date": day(3).isoformat()})).json()["slots"]
    new = (await client.get(f"{BASE}/registrations/{world.registration.id}/slots", params={"date": day(4).isoformat()})).json()["slots"]

    assert [slot["time"] for slot in old] == ["10:00:00", "11:00:00"] and new == []


async def test_only_the_time_can_change_within_the_same_day(client, db_session, admin, world):
    resp = await _patch(client, admin, world.booking, slot_time="11:00")

    assert resp.status_code == 200
    assert resp.json()["booking"]["history"][0]["changes"] == {"slot_time": {"from": "10:00", "to": "11:00"}}
    assert (await _reload(db_session, world.booking)).slot_date == day(3)


async def test_a_booking_can_be_moved_to_a_whole_day_slot(client, db_session, admin, world):
    resp = await _patch(client, admin, world.booking, slot_date=day(6).isoformat(), slot_time=None)

    assert resp.status_code == 200
    moved = await _reload(db_session, world.booking)
    assert (moved.slot_date, moved.slot_time) == (day(6), None)
    assert resp.json()["booking"]["history"][0]["changes"] == {
        "slot_date": {"from": day(3).isoformat(), "to": day(6).isoformat()},
        "slot_time": {"from": "10:00", "to": None},
    }


async def test_a_full_slot_is_a_409_and_nothing_changes(client, db_session, admin, world, outbox):
    await book(client, world.registration, offset=4, slot_time="10:00", email="b@example.com")
    outbox.clear()

    resp = await _patch(client, admin, world.booking, slot_date=day(4).isoformat(), slot_time="10:00", note="x")

    assert resp.status_code == 409 and resp.json()["detail"] == {"errors": {"slot": "full"}}
    unchanged = await _reload(db_session, world.booking)
    assert unchanged.slot_date == day(3)
    assert await _history(db_session, world.booking) == [] and len(outbox) == 0


async def test_the_administrator_does_not_override_the_capacity_of_a_bigger_slot(client, db_session, admin):
    _, _, registration = await seed(db_session, article={"slug": "big"}, questions=QUESTIONS, blocks=[dates_block(3, 4, times=["10:00"])], capacity=2)
    tokens = [(await book(client, registration, offset=3, slot_time="10:00", email=f"p{n}@example.com")).json()["cancel_token"] for n in range(2)]
    other = (await book(client, registration, offset=4, slot_time="10:00", email="o@example.com")).json()["cancel_token"]
    mover = await service.get_booking_by_token(db_session, other)

    full = await _patch(client, admin, mover, slot_date=day(3).isoformat())
    await client.post(f"{BASE}/bookings/{tokens[0]}/cancel")
    freed = await _patch(client, admin, mover, slot_date=day(3).isoformat())

    assert full.status_code == 409 and freed.status_code == 200


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"slot_date": 5}, "not_offered"),  # a day nobody offered
        ({"slot_date": 3, "slot_time": "10:30"}, "not_offered"),  # a time that is not on offer
        ({"slot_date": 3, "slot_time": None}, "not_offered"),  # the whole day on a timed day
        ({"slot_date": 6, "slot_time": "10:00"}, "not_offered"),  # a time on a whole-day day
        ({"slot_date": -1}, "not_offered"),  # the past
        ({"slot_date": 500}, "not_offered"),  # beyond the horizon
    ],
)
async def test_a_slot_that_does_not_exist_is_a_422(client, db_session, admin, world, fields, code):
    body = {"slot_date": day(fields["slot_date"]).isoformat(), **({"slot_time": fields["slot_time"]} if "slot_time" in fields else {})}

    resp = await _patch(client, admin, world.booking, **body)

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"slot": code}}
    assert (await _reload(db_session, world.booking)).slot_date == day(3)


async def test_moving_works_on_a_closed_registration_but_still_only_to_a_real_slot(client, db_session, admin, world):
    world.registration.is_open = False
    await db_session.commit()

    assert (await _patch(client, admin, world.booking, slot_time="11:00")).status_code == 200
    assert (await _patch(client, admin, world.booking, slot_time="12:00")).status_code == 422


async def test_a_slot_is_not_checked_again_when_it_is_the_one_the_booking_already_has(client, db_session, admin, world):
    # The offer changes after the booking was made: its day 3 at 10:00 is no longer on offer.
    await service.update_registration(db_session, world.registration.id, RegistrationUpdate.model_validate({"blocks": [dates_block(8)]}))
    await db_session.commit()

    resp = await _patch(client, admin, world.booking, name="Jana Nová", slot_date=day(3).isoformat(), slot_time="10:00")

    assert resp.status_code == 200 and resp.json()["booking"]["name"] == "Jana Nová"


async def test_nothing_actually_changing_is_a_422(client, db_session, admin, world, outbox):
    outbox.clear()

    for body in (
        {},
        {"note": "just saying"},
        {"notify": False},
        {"name": "Eva Nováková"},
        {"name": "  Eva Nováková  "},
        {"email": "eva@example.com"},
        {"slot_date": day(3).isoformat(), "slot_time": "10:00"},
        {"slot_date": day(3).isoformat()},
        {"answers": dict(GOOD_ANSWERS)},
    ):
        resp = await _patch(client, admin, world.booking, **body)
        assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"_form": "no_change"}}, body

    assert await _history(db_session, world.booking) == [] and len(outbox) == 0


# --- Name, e-mail, answers ----------------------------------------------------------------------------


async def test_the_name_is_corrected_and_only_it_is_recorded(client, db_session, admin, world, outbox):
    outbox.clear()

    resp = await _patch(client, admin, world.booking, name="  Eva Novotná ")

    assert resp.status_code == 200
    assert resp.json()["booking"]["name"] == "Eva Novotná"
    assert resp.json()["booking"]["history"][0]["changes"] == {"name": {"from": "Eva Nováková", "to": "Eva Novotná"}}
    assert "Eva Novotná" in text_of(outbox[0])


async def test_the_email_is_changed_and_the_notice_goes_to_the_new_address(client, db_session, admin, world, outbox):
    outbox.clear()

    resp = await _patch(client, admin, world.booking, email="new.address@example.com")

    assert resp.status_code == 200
    assert resp.json()["booking"]["history"][0]["changes"] == {"email": {"from": "eva@example.com", "to": "new.address@example.com"}}
    assert [to_of(message) for message in outbox] == ["new.address@example.com"]
    assert (await _reload(db_session, world.booking)).email == "new.address@example.com"


@pytest.mark.parametrize("fields", [{"name": ""}, {"name": "   "}, {"email": "nope"}, {"email": ""}, {"note": "x" * 1001}, {"cancel_token": "mine"}, {"status": "cancelled"}, {"slot_date": "soon"}, {"slot_time": "noon"}])
async def test_malformed_changes_are_a_422(client, db_session, admin, world, fields):
    assert (await _patch(client, admin, world.booking, **fields)).status_code == 422
    assert await _history(db_session, world.booking) == []


async def test_answers_are_replaced_by_a_new_snapshot_and_the_changed_questions_are_listed(client, db_session, admin, world):
    old_submission = world.booking.submission_id

    resp = await _patch(client, admin, world.booking, answers={Q_NOTE: "Changed", Q_KIND: "a"})

    assert resp.status_code == 200, resp.text
    body = resp.json()["booking"]
    assert {entry["question_id"]: entry["display"] for entry in body["answers"] if entry["shown"]} == {Q_NOTE: "Changed", Q_KIND: "Alpha"}
    assert body["history"][0]["changes"] == {"answers": {"questions": [{"id": Q_NOTE, "label": "Note"}]}}
    moved = await _reload(db_session, world.booking)
    assert moved.submission_id != old_submission
    assert await db_session.get(FormSubmission, old_submission) is None  # the old snapshot is gone
    assert await count_rows(db_session, FormSubmission) == 1


async def test_answers_are_validated_against_the_form_and_a_bad_edit_changes_nothing(client, db_session, admin, world):
    for answers, expected in (
        ({Q_KIND: "a"}, {Q_NOTE: "required"}),
        ({}, {Q_NOTE: "required"}),
        ({Q_NOTE: "x", Q_KIND: "b"}, {Q_EXTRA: "required"}),  # b makes the extra question appear
        ({Q_NOTE: "x", Q_KIND: "zzz"}, None),
        ({Q_NOTE: "x", str(uuid.uuid4()): "?"}, None),
    ):
        resp = await _patch(client, admin, world.booking, answers=answers)
        assert resp.status_code == 422, answers
        if expected:
            assert resp.json()["detail"]["errors"] == expected

    assert await _history(db_session, world.booking) == []
    assert await count_rows(db_session, FormSubmission) == 1


async def test_a_question_that_appears_or_disappears_counts_as_changed(client, db_session, admin, world):
    appears = await _patch(client, admin, world.booking, answers={Q_NOTE: "hello", Q_KIND: "b", Q_EXTRA: "More"})
    disappears = await _patch(client, admin, world.booking, answers={Q_NOTE: "hello", Q_KIND: "a", Q_EXTRA: "ignored now"})

    assert [item["id"] for item in appears.json()["booking"]["history"][0]["changes"]["answers"]["questions"]] == [Q_KIND, Q_EXTRA]
    assert [item["id"] for item in disappears.json()["booking"]["history"][0]["changes"]["answers"]["questions"]] == [Q_KIND, Q_EXTRA]
    submission = await db_session.get(FormSubmission, (await _reload(db_session, world.booking)).submission_id)
    assert next(entry for entry in submission.answers if entry["question_id"] == Q_EXTRA)["shown"] is False


async def test_an_answer_to_a_hidden_question_is_not_a_change(client, db_session, admin, world):
    resp = await _patch(client, admin, world.booking, answers={Q_NOTE: "hello", Q_KIND: "a", Q_EXTRA: "nobody sees this"})

    assert resp.status_code == 422 and resp.json()["detail"] == {"errors": {"_form": "no_change"}}


async def test_several_things_at_once_are_one_change_and_one_mail(client, db_session, admin, world, outbox):
    outbox.clear()

    resp = await _patch(client, admin, world.booking, name="Jana", email="jana@example.com", slot_date=day(4).isoformat(), slot_time="10:00", answers={Q_NOTE: "new", Q_KIND: "a"})

    assert resp.status_code == 200
    changes = resp.json()["booking"]["history"][0]["changes"]
    assert set(changes) == {"name", "email", "slot_date", "answers"}
    assert len(await _history(db_session, world.booking)) == 1 and len(outbox) == 1


async def test_every_change_adds_to_the_history_newest_first(client, db_session, admin, world):
    await _patch(client, admin, world.booking, name="First")
    await _patch(client, admin, world.booking, name="Second")

    detail = (await client.get(f"{BASE}/manage/bookings/{world.booking.id}", headers=admin)).json()
    listed = (await client.get(f"{BASE}/manage/registrations/{world.registration.id}/bookings", headers=admin)).json()["items"][0]

    assert [entry["changes"]["name"]["to"] for entry in detail["history"]] == ["Second", "First"]
    assert listed["has_history"] is True


# --- The note and the e-mail ----------------------------------------------------------------------------


async def test_without_a_note_the_mail_has_no_note_heading(client, db_session, admin, world, outbox):
    outbox.clear()

    await _patch(client, admin, world.booking, slot_time="11:00")
    await _patch(client, admin, world.booking, slot_time="10:00", note="   ")

    assert len(outbox) == 2
    for message in outbox:
        assert "Poznámka pořadatele" not in text_of(message) and "{" not in text_of(message)
    assert [change.note for change in await _history(db_session, world.booking)] == [None, None]


async def test_a_note_of_exactly_the_maximum_length_is_accepted(client, db_session, admin, world):
    assert (await _patch(client, admin, world.booking, slot_time="11:00", note="n" * 1000)).status_code == 200


async def test_the_mail_follows_the_language_the_person_booked_in(client, db_session, admin, outbox):
    _, _, registration = await seed(db_session, article={"slug": "english"}, questions=QUESTIONS, blocks=[dates_block(3, times=["10:00", "11:00"])], event=CASTLE)
    token = (await book(client, registration, offset=3, slot_time="10:00", language="en-GB")).json()["cancel_token"]
    booking = await service.get_booking_by_token(db_session, token)
    outbox.clear()

    await _patch(client, admin, booking, slot_time="11:00", note="Sorry.")
    await _cancel(client, admin, booking, note="Gone.")

    changed, cancelled = outbox
    assert changed["Subject"] == "Your booking has been changed: Castle tour"
    assert f"Previous date: {day(3).isoformat()}, 10:00" in text_of(changed) and "Note from the organiser:\nSorry." in text_of(changed)
    assert cancelled["Subject"] == "Your booking has been cancelled: Castle tour"
    assert "Note from the organiser:\nGone." in text_of(cancelled)


async def test_with_notify_off_nothing_is_sent_and_the_history_says_so(client, db_session, admin, world, outbox):
    outbox.clear()

    resp = await _patch(client, admin, world.booking, name="Silently fixed", notify=False)

    assert resp.status_code == 200 and resp.json()["email_sent"] is None
    change = resp.json()["booking"]["history"][0]
    assert change["notified"] is False and change["email_error"] is None
    assert len(outbox) == 0


async def test_a_failing_mail_is_reported_but_the_change_stands(client, db_session, admin, world, monkeypatch, caplog):
    async def _broken(*args, **kwargs):
        raise ConnectionError("smtp is down")

    monkeypatch.setattr(booking_mail, "send_email", _broken)

    resp = await _patch(client, admin, world.booking, slot_time="11:00", note="Moved.")

    assert resp.status_code == 200
    assert resp.json()["email_sent"] is False
    change = resp.json()["booking"]["history"][0]
    assert change["notified"] is False and "smtp is down" in change["email_error"] and change["note"] == "Moved."
    assert (await _reload(db_session, world.booking)).slot_time.strftime("%H:%M") == "11:00"
    assert any("Could not send" in record.getMessage() for record in caplog.records)
    detail = (await client.get(f"{BASE}/manage/bookings/{world.booking.id}", headers=admin)).json()
    assert detail["history"][0]["email_error"] == change["email_error"]  # still visible later


async def test_a_cancelled_booking_cannot_be_changed(client, db_session, admin, world, outbox):
    await _cancel(client, admin, world.booking)
    outbox.clear()

    resp = await _patch(client, admin, world.booking, name="Too late")

    assert resp.status_code == 409 and resp.json()["detail"] == {"errors": {"_form": "cancelled"}}
    assert len(outbox) == 0 and len(await _history(db_session, world.booking)) == 1  # just the cancellation


async def test_an_unknown_booking_is_a_404(client, admin):
    ghost = type("Ghost", (), {"id": uuid.uuid4()})()

    assert (await _patch(client, admin, ghost, name="x")).status_code == 404
    assert (await _cancel(client, admin, ghost)).status_code == 404


# --- Cancelling ------------------------------------------------------------------------------------------


async def test_an_administrator_cancels_a_booking_with_a_note_and_the_person_is_told(client, db_session, admin, admin_sub, world, outbox):
    outbox.clear()

    resp = await _cancel(client, admin, world.booking, note="The tour is off.")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email_sent"] is True and body["booking"]["status"] == "cancelled" and body["booking"]["cancelled_at"]
    change = body["booking"]["history"][0]
    assert change["kind"] == "cancelled" and change["note"] == "The tour is off." and change["notified"] is True
    assert change["changes"] == {"status": {"from": "confirmed", "to": "cancelled"}} and change["user_sub"] == str(admin_sub)
    message = outbox[0]
    assert to_of(message) == "eva@example.com" and message["Subject"] == "Zrušení Vaší přihlášky: Castle tour"
    text = text_of(message)
    assert f"Zrušený termín: {day(3).day}. {day(3).month}. {day(3).year}, 10:00" in text
    assert "Poznámka pořadatele:\nThe tour is off." in text
    public = (await client.get(f"{BASE}/bookings/{world.token}")).json()
    assert public["status"] == "cancelled" and "The tour is off." not in str(public)


async def test_cancelling_frees_the_place(client, db_session, admin, world):
    assert (await book(client, world.registration, offset=3, slot_time="10:00", email="b@example.com")).status_code == 409

    await _cancel(client, admin, world.booking)

    assert (await book(client, world.registration, offset=3, slot_time="10:00", email="b@example.com")).status_code == 201


async def test_cancelling_twice_changes_and_sends_nothing_more(client, db_session, admin, world, outbox):
    first = await _cancel(client, admin, world.booking, note="first")
    outbox.clear()

    again = await _cancel(client, admin, world.booking, note="second")

    assert again.status_code == 200 and again.json()["email_sent"] is None
    assert again.json()["booking"]["cancelled_at"] == first.json()["booking"]["cancelled_at"]
    assert [change.note for change in await _history(db_session, world.booking)] == ["first"]
    assert len(outbox) == 0


async def test_a_booking_the_visitor_already_cancelled_is_idempotent_for_the_administrator(client, db_session, admin, world, outbox):
    await client.post(f"{BASE}/bookings/{world.token}/cancel")
    outbox.clear()

    resp = await _cancel(client, admin, world.booking, note="late")

    assert resp.status_code == 200 and resp.json()["email_sent"] is None
    assert await _history(db_session, world.booking) == [] and len(outbox) == 0


async def test_cancelling_without_notifying_or_without_a_body(client, db_session, admin, world, outbox):
    outbox.clear()

    resp = await _cancel(client, admin, world.booking, notify=False)

    assert resp.status_code == 200 and resp.json()["email_sent"] is None
    assert resp.json()["booking"]["history"][0]["notified"] is False and len(outbox) == 0
    _, _, other = await seed(db_session, article={"slug": "x"}, blocks=[dates_block(3)])
    token = (await book(client, other, offset=3, answers={})).json()["cancel_token"]
    bare = await client.post(f"{BASE}/manage/bookings/{(await service.get_booking_by_token(db_session, token)).id}/cancel", json={}, headers=admin)
    assert bare.status_code == 200 and bare.json()["email_sent"] is True


async def test_a_failing_mail_on_cancel_is_reported_and_the_cancellation_stands(client, db_session, admin, world, monkeypatch):
    async def _broken(*args, **kwargs):
        raise ConnectionError("smtp is down")

    monkeypatch.setattr(booking_mail, "send_email", _broken)

    resp = await _cancel(client, admin, world.booking, note="x")

    assert resp.status_code == 200 and resp.json()["email_sent"] is False
    assert resp.json()["booking"]["status"] == "cancelled" and "smtp is down" in resp.json()["booking"]["history"][0]["email_error"]


@pytest.mark.parametrize("fields", [{"note": "x" * 1001}, {"notify": "sometimes"}, {"reason": "?"}])
async def test_a_malformed_cancellation_is_a_422(client, db_session, admin, world, fields):
    assert (await _cancel(client, admin, world.booking, **fields)).status_code == 422
    assert (await _reload(db_session, world.booking)).status == "confirmed"
