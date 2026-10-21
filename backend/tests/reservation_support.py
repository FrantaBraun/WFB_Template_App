# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What the table_reservations tests share: seeding tables and opening hours, a
throwaway app the router is mounted on (whether the module is on the real app
depends on the branch's backend/modules.json, which a test must not assume), a
fixed clock handed to the app through its get_now dependency, and helpers to
reserve over HTTP.

The default seed is a pub open every weekday 10:00-22:00, so no test depends on
which weekday "today" is."""

import socket
from datetime import date, datetime, time, timedelta
from email.utils import parseaddr

import pytest
from fastapi import FastAPI
from fastapi_mail import FastMail
from sqlalchemy import delete, func, select

from app.config import Settings, get_settings
from app.database import get_db
from app.modules.table_reservations import service
from app.modules.table_reservations.config import get_config, load_config
from app.modules.table_reservations.deps import get_now
from app.modules.table_reservations.models import (
    DiningTable,
    OpeningException,
    OpeningHours,
    Reservation,
)
from app.modules.table_reservations.router import router as reservations_router
from app.services.email import _connection_config

BASE = "/api/modules/table_reservations"
NOW = datetime.combine(date.today(), time(9, 0))
TODAY = NOW.date()


def day(offset: int) -> date:
    return TODAY + timedelta(days=offset)


def hhmm(value: int) -> str:
    """Minutes since midnight as "HH:MM"."""
    return f"{value // 60:02d}:{value % 60:02d}"


def reservations_app() -> FastAPI:
    app = FastAPI()
    app.include_router(reservations_router, prefix=BASE)
    return app


def make_settings(**fields) -> Settings:
    """Settings that never send for real, with a notice address."""
    values = {
        "frontend_url": "https://pub.test",
        "mail_username": "u",
        "mail_password": "p",
        "mail_from": "noreply@example.com",
        "mail_server": "smtp.example.com",
        "mail_suppress_send": True,
        "booking_notify_mail": "owner@example.com",
        "contact_mail": "",
    }
    values.update(fields)
    return Settings(**values)


def install_overrides(app: FastAPI, db_session, *, settings: Settings | None = None, now: datetime = NOW) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings or make_settings()
    app.dependency_overrides[get_config] = load_config
    app.dependency_overrides[get_now] = lambda: now


async def clear_tables(db) -> None:
    """Empties everything the module owns, reservations first (the foreign key is
    RESTRICT). The tests run in a transaction that is rolled back, so this never
    outlives a test."""
    for model in (Reservation, DiningTable, OpeningException, OpeningHours):
        await db.execute(delete(model))


async def seed_hours(db, opens: str = "10:00", closes: str = "22:00", *, closed_weekdays: tuple[int, ...] = ()) -> None:
    """The regular hours of the whole week."""
    for weekday in range(7):
        closed = weekday in closed_weekdays
        db.add(
            OpeningHours(
                weekday=weekday,
                is_closed=closed,
                opens=None if closed else time.fromisoformat(opens),
                closes=None if closed else time.fromisoformat(closes),
            )
        )
    await db.commit()


async def make_table(db, name: str, seats: int, *, position: int = 0, is_active: bool = True) -> DiningTable:
    table = DiningTable(name=name, seats=seats, position=position, is_active=is_active)
    db.add(table)
    await db.commit()
    await db.refresh(table)
    return table


async def seed_pub(db, *, seats: tuple[int, ...] = (2, 4, 6), opens: str = "10:00", closes: str = "22:00") -> list[DiningTable]:
    """Open every day from `opens` to `closes`, with one table per entry of `seats` (named T<seats>-<n>)."""
    await seed_hours(db, opens, closes)
    return [await make_table(db, f"T{count}-{n}", count, position=n) for n, count in enumerate(seats)]


async def make_exception(db, on: date, *, closed: bool = True, opens: str | None = None, closes: str | None = None, reason: str | None = None) -> OpeningException:
    row = OpeningException(
        day=on,
        is_closed=closed,
        opens=time.fromisoformat(opens) if opens else None,
        closes=time.fromisoformat(closes) if closes else None,
        reason=reason,
    )
    db.add(row)
    await db.commit()
    return row


def reservation_body(offset: int = 1, start: str = "18:00", *, kind: str = "table", party_size: int = 2, **fields) -> dict:
    """The body of a guest's reservation for the day `offset` days from today."""
    body = {
        "kind": kind,
        "day": day(offset).isoformat(),
        "start_time": start,
        "party_size": party_size,
        "name": "Eva Nováková",
        "email": "eva@example.com",
        "consent": True,
        "language": "cs",
    }
    body.update(fields)
    return body


async def reserve(client, offset: int = 1, start: str = "18:00", **fields):
    """A guest's reservation over HTTP (see reservation_body for the defaults)."""
    return await client.post(f"{BASE}/reservations", json=reservation_body(offset, start, **fields))


async def stored(db, token: str) -> Reservation:
    """The reservation a response's cancel_token belongs to."""
    return await service.get_by_token(db, token)


async def count_rows(db, model=Reservation, *conditions) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*conditions))


@pytest.fixture(autouse=True)
def _fast_fqdn(monkeypatch):
    """Building a message calls socket.getfqdn() (for its Message-ID), which takes
    about a second per call on some machines (a DNS lookup of the host's own name) -
    with two e-mails per reservation that made the suite minutes slower. Nothing here
    depends on the real host name."""
    monkeypatch.setattr(socket, "getfqdn", lambda name="": "pub.test")


@pytest.fixture()
def outbox():
    """Every e-mail the code under test "sends" (nothing leaves the process)."""
    with FastMail(_connection_config(make_settings())).record_messages() as box:
        yield box


def to_of(message) -> str:
    """The recipient address of a message ("name <address>" -> "address")."""
    return parseaddr(message["To"])[1]


def text_of(message) -> str:
    """The plain-text body of a message."""
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
    raise AssertionError("no text part")
