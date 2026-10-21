# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Reserving under concurrency. Whether a reservation is acceptable depends on the
OTHER reservations of its day (the half hour between two of one table, a table
against the whole pub, a reservation against the day's hours), so no unique
constraint can guard it - everything that decides on the strength of the existing
reservations first takes one advisory lock (service.lock_reservations), reads,
decides and writes. These tests fire requests at the same time (asyncio.gather),
each with a session of its own, and check that the outcome is one a serial
execution could have produced and that the invariants of the rules hold.

That needs real commits, so unlike the other tests of the module the rows here are
committed and removed again - by the ids and addresses they were created with:
nothing else in the database is touched. The days are far enough ahead not to meet
real data, and each day has hours of its own (a one-off change), so the weekly hours
need not exist; the tables seat more people than the application lets an administrator
give a table, so only the tables made here can be assigned to these parties."""

import asyncio
import itertools
import uuid
from datetime import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.user import User
from app.modules.table_reservations import rules, service
from app.modules.table_reservations.config import get_config, load_config
from app.modules.table_reservations.deps import get_now
from app.modules.table_reservations.models import DiningTable, OpeningException, Reservation
from tests.reservation_support import (  # noqa: F401  (_fast_fqdn is a fixture)
    BASE,
    NOW,
    _fast_fqdn,
    day,
    make_settings,
    reservation_body,
    reservations_app,
)

_app = reservations_app()

BIG_PARTY = 60  # more than any table an administrator can create (50 seats)
EMAIL_DOMAIN = "race.example"


@pytest.fixture(autouse=True)
async def _overrides(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    monkeypatch.setattr(service, "_last_purge", NOW.date())  # the purge would touch other data
    # get_db is NOT overridden: every request opens its own session on the real engine.
    _app.dependency_overrides[get_settings] = lambda: make_settings()
    _app.dependency_overrides[get_config] = load_config
    _app.dependency_overrides[get_now] = lambda: NOW
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


class Rows:
    """What a test committed, so exactly that can be removed again."""

    def __init__(self):
        self.table_ids: list[uuid.UUID] = []
        self.days: list = []
        self.user_subs: list[uuid.UUID] = []
        self._numbers = itertools.count(1)

    async def tables(self, count: int) -> list[DiningTable]:
        async with AsyncSessionLocal() as db:
            made = [DiningTable(name=f"race-{uuid.uuid4().hex[:8]}", seats=BIG_PARTY, position=n) for n in range(count)]
            db.add_all(made)
            await db.commit()
            for table in made:
                await db.refresh(table)
        self.table_ids += [table.id for table in made]
        return made

    async def open_day(self, offset: int, opens: str = "10:00", closes: str = "22:00"):
        async with AsyncSessionLocal() as db:
            db.add(OpeningException(day=day(offset), is_closed=False, opens=time.fromisoformat(opens), closes=time.fromisoformat(closes)))
            await db.commit()
        self.days.append(day(offset))

    def email(self) -> str:
        return f"guest{next(self._numbers)}@{EMAIL_DOMAIN}"

    async def clean(self):
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Reservation).where(Reservation.email.like(f"%@{EMAIL_DOMAIN}")))
            await db.execute(delete(Reservation).where(Reservation.table_id.in_(self.table_ids)))
            await db.execute(delete(DiningTable).where(DiningTable.id.in_(self.table_ids)))
            await db.execute(delete(OpeningException).where(OpeningException.day.in_(self.days)))
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


def _reserve(client, rows, offset, start, *, kind="table", party_size=BIG_PARTY, **fields):
    return client.post(
        f"{BASE}/reservations",
        json=reservation_body(offset, start, kind=kind, party_size=party_size, email=rows.email(), **fields),
    )


async def _confirmed(offset: int) -> list[Reservation]:
    async with AsyncSessionLocal() as db:
        return list(
            (
                await db.scalars(
                    select(Reservation).where(Reservation.day == day(offset), Reservation.email.like(f"%@{EMAIL_DOMAIN}"), Reservation.status == "confirmed")
                )
            ).all()
        )


def _held(rows_: list[Reservation]) -> list[rules.Held]:
    return [rules.Held(r.kind, r.table_id, rules.minutes(r.start_time), rules.minutes(r.end_time)) for r in rows_]


def assert_invariants(reservations: list[Reservation]) -> None:
    """What the rules promise about the confirmed reservations of one day."""
    held = _held(reservations)
    wholes = [h for h in held if h.kind == "whole_venue"]
    assert len(wholes) <= 1, "two whole-pub reservations in one day"
    for whole in wholes:
        for other in held:
            if other is not whole:
                assert not rules.overlaps(whole.start, whole.end, other.start, other.end), "a reservation overlaps the whole pub"
    tables = [h for h in held if h.kind == "table"]
    for first, second in itertools.combinations(tables, 2):
        if first.table_id == second.table_id:
            assert not (first.start < second.end + rules.BUFFER_MINUTES and second.start < first.end + rules.BUFFER_MINUTES), "two reservations of one table too close"


# --- Tables -------------------------------------------------------------------------------------------------


async def test_simultaneous_requests_for_the_last_table_one_wins(client, rows):
    await rows.tables(1)
    await rows.open_day(40)

    results = await asyncio.gather(*[_reserve(client, rows, 40, "18:00") for _ in range(6)])

    assert sorted(response.status_code for response in results) == [201, 409, 409, 409, 409, 409]
    assert len(await _confirmed(40)) == 1


async def test_many_simultaneous_requests_fill_the_tables_exactly_with_a_table_each(client, rows):
    tables = await rows.tables(3)
    await rows.open_day(40)

    results = await asyncio.gather(*[_reserve(client, rows, 40, "18:00") for _ in range(8)])

    assert sorted(response.status_code for response in results) == [201] * 3 + [409] * 5
    taken = [reservation.table_id for reservation in await _confirmed(40)]
    assert sorted(map(str, taken)) == sorted(str(table.id) for table in tables)  # three different tables


async def test_starts_that_clash_through_the_buffer_do_not_slip_through_together(client, rows):
    await rows.tables(1)
    await rows.open_day(40)
    starts = ["18:00", "18:15", "19:00", "19:45", "20:00", "20:15", "20:30", "21:00"]

    results = await asyncio.gather(*[_reserve(client, rows, 40, start, duration_minutes=60) for start in starts])

    assert any(response.status_code == 201 for response in results)
    assert all(response.status_code in (201, 409) for response in results)
    assert_invariants(await _confirmed(40))


async def test_a_mix_of_starts_and_lengths_over_several_tables_keeps_every_invariant(client, rows):
    await rows.tables(2)
    await rows.open_day(40)
    plan = [(start, duration) for start in ("10:00", "10:30", "11:00", "12:15", "12:30", "13:00", "14:00", "15:15", "16:00") for duration in (60, 120)]

    results = await asyncio.gather(*[_reserve(client, rows, 40, start, duration_minutes=duration) for start, duration in plan])

    assert all(response.status_code in (201, 409) for response in results)
    confirmed = await _confirmed(40)
    assert len(confirmed) == sum(response.status_code == 201 for response in results)
    assert_invariants(confirmed)


# --- The whole pub against the tables -----------------------------------------------------------------------------


async def test_the_whole_pub_and_a_table_over_the_same_time_cannot_both_be_reserved(client, rows):
    await rows.tables(2)
    await rows.open_day(40)

    results = await asyncio.gather(
        _reserve(client, rows, 40, "18:00", kind="whole_venue", party_size=30),
        _reserve(client, rows, 40, "19:00"),
    )

    assert sorted(response.status_code for response in results) == [201, 409]
    assert_invariants(await _confirmed(40))


async def test_a_crowd_of_both_kinds_leaves_a_consistent_day(client, rows):
    await rows.tables(3)
    await rows.open_day(40)
    requests = [
        *[_reserve(client, rows, 40, start, kind="whole_venue", party_size=30) for start in ("17:00", "18:00", "19:00", "20:00", "21:00")],
        *[_reserve(client, rows, 40, start) for start in ("10:00", "13:00", "16:00", "17:30", "18:30", "19:30", "20:30", "21:30")],
    ]

    results = await asyncio.gather(*requests)

    assert all(response.status_code in (201, 409) for response in results)
    confirmed = await _confirmed(40)
    assert len(confirmed) == sum(response.status_code == 201 for response in results)
    assert len([r for r in confirmed if r.kind == "whole_venue"]) <= 1
    assert_invariants(confirmed)


async def test_two_whole_pub_requests_at_once_one_wins(client, rows):
    await rows.open_day(40)
    await rows.tables(1)

    results = await asyncio.gather(*[_reserve(client, rows, 40, start, kind="whole_venue", party_size=30) for start in ("18:00", "19:00", "20:00")])

    assert sorted(response.status_code for response in results) == [201, 409, 409]


# --- Changes of the pub against reservations -----------------------------------------------------------------------


async def test_closing_a_day_and_reserving_on_it_at_once_never_leave_a_reservation_on_a_closed_day(client, rows, admin_headers):
    for attempt in range(5):  # the order the two get the lock in varies; try it several times
        offset = 41 + attempt
        await rows.tables(1)
        await rows.open_day(offset)

        closed, reserved = await asyncio.gather(
            client.put(f"{BASE}/manage/exceptions/{day(offset).isoformat()}", json={"is_closed": True, "reason": "Race"}, headers=admin_headers),
            _reserve(client, rows, offset, "18:00"),
        )

        confirmed = await _confirmed(offset)
        if closed.status_code == 200:  # closed first: the reservation was refused
            assert reserved.status_code == 422 and reserved.json()["detail"] == {"errors": {"day": "closed"}}
            assert confirmed == []
        else:  # reserved first: closing waited for it and found it
            assert (closed.status_code, reserved.status_code) == (409, 201)
            assert len(confirmed) == 1


async def test_taking_a_table_out_of_use_and_reserving_it_at_once_leave_no_reservation_on_an_unused_table(client, rows, admin_headers):
    for attempt in range(5):  # the order the two get the lock in varies; try it several times
        offset = 46 + attempt
        (table,) = await rows.tables(1)
        await rows.open_day(offset)

        deactivated, reserved = await asyncio.gather(
            client.patch(f"{BASE}/manage/tables/{table.id}", json={"is_active": False}, headers=admin_headers),
            _reserve(client, rows, offset, "18:00"),
        )

        async with AsyncSessionLocal() as db:
            on_table = (await db.scalars(select(Reservation).where(Reservation.table_id == table.id, Reservation.status == "confirmed"))).all()
            active = (await db.get(DiningTable, table.id)).is_active
        if deactivated.status_code == 200:
            assert active is False and on_table == [] and reserved.status_code == 422
        else:
            assert (deactivated.status_code, reserved.status_code) == (409, 201) and len(on_table) == 1
        async with AsyncSessionLocal() as db:  # the next round starts with a table of its own
            await db.execute(delete(Reservation).where(Reservation.table_id == table.id))
            await db.execute(delete(DiningTable).where(DiningTable.id == table.id))
            await db.commit()


async def test_a_guest_and_the_pub_cancelling_the_same_reservation_leave_one_cancellation(client, rows, admin_headers):
    await rows.tables(1)
    await rows.open_day(40)
    token = (await _reserve(client, rows, 40, "18:00")).json()["cancel_token"]
    async with AsyncSessionLocal() as db:
        reservation = await service.get_by_token(db, token)

    results = await asyncio.gather(
        client.post(f"{BASE}/reservations/{token}/cancel"),
        client.post(f"{BASE}/manage/reservations/{reservation.id}/cancel", json={"notify": False}, headers=admin_headers),
        client.post(f"{BASE}/reservations/{token}/cancel"),
    )

    assert [response.status_code for response in results] == [200, 200, 200]
    async with AsyncSessionLocal() as db:
        row = await service.get_by_token(db, token)
    assert row.status == "cancelled" and row.cancelled_at is not None and row.cancelled_by in ("guest", "admin")
    assert await _confirmed(40) == []


async def test_the_place_a_cancellation_frees_is_taken_by_exactly_one_of_two_waiting_guests(client, rows):
    await rows.tables(1)
    await rows.open_day(40)
    token = (await _reserve(client, rows, 40, "18:00")).json()["cancel_token"]

    results = await asyncio.gather(
        client.post(f"{BASE}/reservations/{token}/cancel"),
        _reserve(client, rows, 40, "18:00"),
        _reserve(client, rows, 40, "18:00"),
    )

    booked = [response.status_code for response in results[1:]]
    assert results[0].status_code == 200
    assert booked.count(201) <= 1  # never both
    assert len(await _confirmed(40)) == booked.count(201)
