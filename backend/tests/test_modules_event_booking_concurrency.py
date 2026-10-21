# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Capacity under concurrency: a slot may hold more than one person, so no
unique constraint can guard it - everything that adds a confirmed booking to a
slot first locks the registration row (SELECT ... FOR UPDATE), counts, and only
then writes. These tests fire requests at the same slot at the same time
(asyncio.gather), each with a session of its own, and check that exactly as
many succeed as there are places.

That needs real commits, so unlike the other booking tests the rows here are
committed and removed again by id at the end - nothing else in the database is
touched. Each request gets its own session from the real get_db dependency."""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.user import User
from app.modules.articles.models import Article
from app.modules.event_booking import service
from app.modules.event_booking.config import get_config, load_config
from app.modules.event_booking.deps import get_now
from app.modules.event_booking.models import Booking, Registration
from app.modules.event_calendar.models import Event
from app.modules.forms.models import Form, FormQuestion, FormSubmission
from tests.booking_support import BASE, NOW, booking_app, booking_body, dates_block, day, make_article, make_event, make_registration, make_settings

_app = booking_app()


@pytest.fixture(autouse=True)
async def _overrides(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    # get_db is NOT overridden: every request opens its own session on the real engine.
    _app.dependency_overrides[get_settings] = lambda: make_settings()
    _app.dependency_overrides[get_config] = load_config
    _app.dependency_overrides[get_now] = lambda: NOW
    service.reset_purge_throttle()
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


class Rows:
    """Ids of what a test committed, so exactly those rows can be removed."""

    def __init__(self):
        self.article_ids: list[uuid.UUID] = []
        self.event_ids: list[uuid.UUID] = []
        self.registration_ids: list[uuid.UUID] = []
        self.form_ids: list[uuid.UUID] = []
        self.user_subs: list[uuid.UUID] = []

    async def registration(self, *, blocks, capacity=1):
        async with AsyncSessionLocal() as db:
            article = await make_article(db, f"race-{uuid.uuid4().hex[:10]}")
            event = await make_event(db, article)
            registration = await make_registration(db, event, blocks=blocks, capacity=capacity)
        self.article_ids.append(article.id)
        self.event_ids.append(event.id)
        self.registration_ids.append(registration.id)
        self.form_ids.append(registration.form_id)
        return registration

    async def clean(self):
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Booking).where(Booking.registration_id.in_(self.registration_ids)))
            await db.execute(delete(FormSubmission).where(FormSubmission.form_id.in_(self.form_ids)))
            await db.execute(delete(Registration).where(Registration.id.in_(self.registration_ids)))
            await db.execute(delete(FormQuestion).where(FormQuestion.form_id.in_(self.form_ids)))
            await db.execute(delete(Form).where(Form.id.in_(self.form_ids)))
            await db.execute(delete(Event).where(Event.id.in_(self.event_ids)))
            await db.execute(delete(Article).where(Article.id.in_(self.article_ids)))
            await db.execute(delete(User).where(User.auth_sub.in_(self.user_subs)))
            await db.commit()


@pytest.fixture()
async def rows():
    rows = Rows()
    yield rows
    await rows.clean()


@pytest.fixture()
async def admin_headers(rows, make_access_token):
    sub = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(User(auth_sub=sub, is_admin=True))
        await db.commit()
    rows.user_subs.append(sub)
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


def _book(client, registration, *, offset=3, slot_time=None, email="a@example.com"):
    return client.post(
        f"{BASE}/registrations/{registration.id}/bookings",
        json=booking_body(offset, slot_time=slot_time, email=email, answers={}),
    )


async def _bookings(registration, status="confirmed") -> list[Booking]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(Booking).where(Booking.registration_id == registration.id, Booking.status == status))).all())


async def test_simultaneous_requests_for_the_last_place_one_wins(client, rows):
    registration = await rows.registration(blocks=[dates_block(3, times=["10:00"])])

    results = await asyncio.gather(*[_book(client, registration, slot_time="10:00", email=f"p{n}@example.com") for n in range(4)])

    assert sorted(response.status_code for response in results) == [201, 409, 409, 409]
    assert len(await _bookings(registration)) == 1


async def test_many_simultaneous_requests_never_exceed_the_capacity(client, rows):
    registration = await rows.registration(blocks=[dates_block(3, times=["10:00"])], capacity=3)

    results = await asyncio.gather(*[_book(client, registration, slot_time="10:00", email=f"p{n}@example.com") for n in range(8)])

    statuses = sorted(response.status_code for response in results)
    assert statuses == [201] * 3 + [409] * 5
    assert len(await _bookings(registration)) == 3


async def test_a_whole_day_slot_holds_up_to_its_capacity_under_a_race_too(client, rows):
    registration = await rows.registration(blocks=[dates_block(3)], capacity=2)

    results = await asyncio.gather(*[_book(client, registration, email=f"p{n}@example.com") for n in range(5)])

    assert sorted(response.status_code for response in results) == [201, 201, 409, 409, 409]


async def test_slots_do_not_block_each_other(client, rows):
    registration = await rows.registration(blocks=[dates_block(3, times=["10:00", "11:00", "12:00"])])

    results = await asyncio.gather(*[_book(client, registration, slot_time=slot, email=f"p{n}@example.com") for n, slot in enumerate(["10:00", "11:00", "12:00"])])

    assert [response.status_code for response in results] == [201, 201, 201]


async def test_a_visitor_and_an_administrators_move_race_for_the_last_place(client, rows, admin_headers):
    registration = await rows.registration(blocks=[dates_block(3, 4, times=["10:00"])])
    token = (await _book(client, registration, offset=3, slot_time="10:00", email="mover@example.com")).json()["cancel_token"]
    async with AsyncSessionLocal() as db:
        mover = await service.get_booking_by_token(db, token)
    move = client.patch(f"{BASE}/manage/bookings/{mover.id}", json={"slot_date": day(4).isoformat(), "notify": False}, headers=admin_headers)

    moved, booked = await asyncio.gather(move, _book(client, registration, offset=4, slot_time="10:00", email="visitor@example.com"))

    assert sorted([moved.status_code, booked.status_code]) in ([201, 409], [200, 409])
    in_slot = [booking for booking in await _bookings(registration) if booking.slot_date == day(4)]
    assert len(in_slot) == 1


async def test_two_administrators_moving_into_the_same_last_place_one_wins(client, rows, admin_headers):
    registration = await rows.registration(blocks=[dates_block(3, 4, times=["10:00"]), dates_block(5)], capacity=1)
    first = (await _book(client, registration, offset=3, slot_time="10:00", email="a@example.com")).json()["cancel_token"]
    second = (await _book(client, registration, offset=5, email="b@example.com")).json()["cancel_token"]
    async with AsyncSessionLocal() as db:
        first_booking = await service.get_booking_by_token(db, first)
        second_booking = await service.get_booking_by_token(db, second)
    body = {"slot_date": day(4).isoformat(), "slot_time": "10:00", "notify": False}

    results = await asyncio.gather(
        client.patch(f"{BASE}/manage/bookings/{first_booking.id}", json=body, headers=admin_headers),
        client.patch(f"{BASE}/manage/bookings/{second_booking.id}", json=body, headers=admin_headers),
    )

    assert sorted(response.status_code for response in results) == [200, 409]
    assert len([booking for booking in await _bookings(registration) if booking.slot_date == day(4)]) == 1


async def test_a_visitor_and_an_administrator_cancelling_the_same_booking_leave_one_cancellation(client, rows, admin_headers):
    registration = await rows.registration(blocks=[dates_block(3)])
    token = (await _book(client, registration, email="a@example.com")).json()["cancel_token"]
    async with AsyncSessionLocal() as db:
        booking = await service.get_booking_by_token(db, token)

    results = await asyncio.gather(
        client.post(f"{BASE}/bookings/{token}/cancel"),
        client.post(f"{BASE}/manage/bookings/{booking.id}/cancel", json={"notify": False}, headers=admin_headers),
        client.post(f"{BASE}/bookings/{token}/cancel"),
    )

    assert [response.status_code for response in results] == [200, 200, 200]
    cancelled = await _bookings(registration, "cancelled")
    assert len(cancelled) == 1 and cancelled[0].cancelled_at is not None
    assert await _bookings(registration) == []
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Booking).where(Booking.registration_id == registration.id)) == 1


async def test_the_place_a_cancellation_frees_is_taken_by_exactly_one_of_two_waiting_visitors(client, rows):
    registration = await rows.registration(blocks=[dates_block(3, times=["10:00"])])
    token = (await _book(client, registration, slot_time="10:00", email="holder@example.com")).json()["cancel_token"]

    results = await asyncio.gather(
        client.post(f"{BASE}/bookings/{token}/cancel"),
        _book(client, registration, slot_time="10:00", email="b@example.com"),
        _book(client, registration, slot_time="10:00", email="c@example.com"),
    )

    booked = [response.status_code for response in results[1:]]
    assert results[0].status_code == 200
    assert booked.count(201) <= 1  # never both
    assert len(await _bookings(registration)) == booked.count(201)
