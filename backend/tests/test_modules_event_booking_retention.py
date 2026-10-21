# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Retention (GDPR): bookings, their answers and the history of changes are
deleted a configured number of months after their slot. There is no scheduler,
so the purge also runs - at most once a day - when a booking is made or the
administrators' list is opened, and on demand.

purge_expired takes the date as an argument, so these tests insert rows with
dates relative to a fixed "today" and call it directly."""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.modules.event_booking import service
from app.modules.event_booking.models import Booking, BookingChange
from app.modules.forms import service as forms_service
from app.modules.forms.models import FormSubmission
from tests.booking_support import (
    BASE,
    GOOD_ANSWERS,
    QUESTIONS,
    TODAY,
    book,
    booking_app,
    clear_tables,
    count_rows,
    dates_block,
    day,
    install_overrides,
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
    service.reset_purge_throttle()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


async def _insert(db, registration, slot_date: date, *, status: str = "confirmed", email: str = "old@example.com") -> Booking:
    """A booking with answers and a history entry, put straight into the database."""
    questions = forms_service.to_logic_questions(await forms_service.get_questions(db, registration.form_id))
    submission = await forms_service.store_submission(db, registration.form_id, forms_service.validate_answers(questions, GOOD_ANSWERS))
    booking = Booking(
        registration_id=registration.id,
        slot_date=slot_date,
        name="Old Booking",
        email=email,
        consent_at=datetime.now(timezone.utc),
        submission_id=submission.id,
        language="cs",
        status=status,
    )
    db.add(booking)
    await db.flush()
    db.add(BookingChange(booking_id=booking.id, kind="updated", changes={"name": {"from": "a", "to": "b"}}))
    await db.commit()
    return booking


async def _registration(db_session, slug="r"):
    _, _, registration = await seed(db_session, article={"slug": slug}, questions=QUESTIONS if slug == "r" else None, blocks=[dates_block(3, 4)], capacity=5)
    return registration


# --- Counting months -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("today", "months", "expected"),
    [
        (date(2026, 10, 21), 12, date(2025, 10, 21)),
        (date(2026, 10, 21), 1, date(2026, 9, 21)),
        (date(2026, 1, 15), 1, date(2025, 12, 15)),
        (date(2026, 3, 31), 1, date(2026, 2, 28)),  # the day is clamped to the month's length
        (date(2024, 3, 31), 1, date(2024, 2, 29)),  # a leap year
        (date(2024, 2, 29), 12, date(2023, 2, 28)),
        (date(2026, 5, 31), 3, date(2026, 2, 28)),
        (date(2026, 10, 21), 120, date(2016, 10, 21)),
        (date(2026, 10, 21), 0, date(2026, 10, 21)),
    ],
)
def test_months_ago(today, months, expected):
    assert service.months_ago(today, months) == expected


# --- The purge itself -----------------------------------------------------------------------------


async def test_old_bookings_go_with_their_answers_and_history_and_recent_ones_stay(db_session):
    registration = await _registration(db_session)
    cutoff = service.months_ago(TODAY, 12)
    await _insert(db_session, registration, cutoff - timedelta(days=366))
    await _insert(db_session, registration, cutoff - timedelta(days=1))  # a day before the limit: gone
    on_the_day = await _insert(db_session, registration, cutoff)  # exactly twelve months ago: still kept
    recent = await _insert(db_session, registration, day(-30))
    upcoming = await _insert(db_session, registration, day(3))

    deleted = await service.purge_expired(db_session, TODAY)
    await db_session.commit()

    assert deleted == 2
    assert set((await db_session.scalars(select(Booking.id))).all()) == {on_the_day.id, recent.id, upcoming.id}
    assert await count_rows(db_session, BookingChange) == 3
    assert await count_rows(db_session, FormSubmission) == 3


async def test_cancelled_bookings_expire_like_the_others(db_session):
    registration = await _registration(db_session)
    await _insert(db_session, registration, day(-400), status="cancelled")
    await _insert(db_session, registration, day(-10), status="cancelled")

    assert await service.purge_expired(db_session, TODAY) == 1
    assert await count_rows(db_session, Booking) == 1


async def test_the_retention_period_is_the_one_given_or_the_configured(db_session):
    registration = await _registration(db_session)
    await _insert(db_session, registration, day(-100))
    await _insert(db_session, registration, day(-40))
    await _insert(db_session, registration, day(-5))

    assert await service.purge_expired(db_session, TODAY, retention_months=1) == 2  # older than a month
    assert await service.purge_expired(db_session, TODAY) == 0  # twelve months: nothing else is that old
    assert await service.purge_expired(db_session, TODAY, retention_months=1) == 0


async def test_purging_only_touches_expired_bookings_of_every_registration(db_session):
    first = await _registration(db_session, "r")
    second = await _registration(db_session, "other")  # a form of its own, no questions
    await _insert(db_session, first, day(-500))
    db_session.add(Booking(registration_id=second.id, slot_date=day(-500), name="n", email="e@example.com", consent_at=datetime.now(timezone.utc), language="cs"))
    db_session.add(Booking(registration_id=second.id, slot_date=day(5), name="n", email="f@example.com", consent_at=datetime.now(timezone.utc), language="cs"))
    await db_session.commit()

    assert await service.purge_expired(db_session, TODAY) == 2
    assert [booking.slot_date for booking in (await db_session.scalars(select(Booking))).all()] == [day(5)]
    assert await count_rows(db_session, FormSubmission) == 0  # the first one's answers went with it


async def test_a_booking_without_answers_is_purged_too(db_session):
    registration = await _registration(db_session)
    db_session.add(Booking(registration_id=registration.id, slot_date=day(-500), name="n", email="e@example.com", consent_at=datetime.now(timezone.utc), language="cs"))
    await db_session.commit()

    assert await service.purge_expired(db_session, TODAY) == 1


# --- When it runs by itself --------------------------------------------------------------------------


async def test_a_new_booking_triggers_the_purge_once_a_day(client, db_session):
    registration = await _registration(db_session)
    await _insert(db_session, registration, day(-500), email="first@example.com")

    created = await book(client, registration, offset=3, email="a@example.com")
    assert created.status_code == 201
    assert await count_rows(db_session, Booking) == 1  # the old one went

    await _insert(db_session, registration, day(-500), email="second@example.com")
    again = await book(client, registration, offset=4, email="b@example.com")

    assert again.status_code == 201
    assert await count_rows(db_session, Booking) == 3  # today's purge already ran: the second old one stays until tomorrow


async def test_the_purge_runs_again_the_next_day(db_session):
    registration = await _registration(db_session)
    config = service.get_config()
    await _insert(db_session, registration, day(-500))

    await service.maybe_purge(db_session, TODAY, config)
    assert await count_rows(db_session, Booking) == 0
    await _insert(db_session, registration, day(-500))
    await service.maybe_purge(db_session, TODAY, config)
    assert await count_rows(db_session, Booking) == 1  # same day: skipped

    await service.maybe_purge(db_session, day(1), config)

    assert await count_rows(db_session, Booking) == 0


async def test_the_admin_list_triggers_the_purge_as_well(client, db_session, admin):
    registration = await _registration(db_session)
    await _insert(db_session, registration, day(-500))
    await _insert(db_session, registration, day(-2))

    resp = await client.get(f"{BASE}/manage/registrations/{registration.id}/bookings", headers=admin)

    assert resp.json()["total"] == 1


async def test_a_failing_purge_never_breaks_a_booking_and_is_retried_later(client, db_session, monkeypatch, caplog):
    registration = await _registration(db_session)
    calls = []

    async def _broken(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(service, "purge_expired", _broken)
    with caplog.at_level(logging.ERROR, logger=service.__name__):
        first = await book(client, registration, offset=3, email="a@example.com")
        second = await book(client, registration, offset=4, email="b@example.com")

    assert first.status_code == second.status_code == 201
    assert len(calls) == 2  # not marked as done, so it tries again
    assert any("Purging expired bookings failed" in record.getMessage() for record in caplog.records)


# --- On demand ------------------------------------------------------------------------------------------


async def test_the_purge_endpoint_deletes_now_and_says_how_many(client, db_session, admin):
    registration = await _registration(db_session)
    await _insert(db_session, registration, day(-500))
    await _insert(db_session, registration, day(-600), status="cancelled")
    await _insert(db_session, registration, day(-1))

    resp = await client.post(f"{BASE}/manage/purge", headers=admin)

    assert resp.status_code == 200 and resp.json() == {"deleted_bookings": 2}
    assert await count_rows(db_session, Booking) == 1
    assert (await client.post(f"{BASE}/manage/purge", headers=admin)).json() == {"deleted_bookings": 0}
