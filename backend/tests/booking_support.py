# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What the event_booking tests share: seeding articles, events and
registrations, a form of questions, and the throwaway app the router is mounted
on (whether the module is on the real app depends on the branch's
backend/modules.json, which a test must not assume - see
test_modules_notifications_router.py).

Rows are seeded the way the module itself creates them: a registration through
service.create_registration (which makes its form), questions through the forms
service. The clock is fixed (NOW) and handed to the app through its get_now
dependency, so slots, "today" and the end of an event are deterministic."""

import uuid
from datetime import date, datetime, time, timedelta
from email.utils import parseaddr

import pytest
from fastapi import FastAPI
from fastapi_mail import FastMail
from sqlalchemy import delete, func, select

from app.config import Settings, get_settings
from app.database import get_db
from app.modules.articles.models import Article, ArticleType
from app.modules.articles.search import build_search_text, normalize_text
from app.modules.event_booking import service
from app.modules.event_booking.config import get_config, load_config
from app.modules.event_booking.deps import get_now
from app.modules.event_booking.models import Booking, BookingChange, Registration, RegistrationBlock
from app.modules.event_booking.router import router as booking_router
from app.modules.event_booking.schemas import RegistrationCreate
from app.modules.event_calendar.models import Event
from app.modules.forms import service as forms_service
from app.modules.forms.models import Form, FormQuestion, FormSubmission
from app.modules.forms.schemas import QuestionsReplace
from app.services.email import _connection_config

BASE = "/api/modules/event_booking"
NOW = datetime.combine(date.today(), time(9, 0))
TODAY = NOW.date()

Q_NOTE, Q_KIND, Q_EXTRA = (str(uuid.UUID(int=i)) for i in (901, 902, 903))
QUESTIONS = [
    {"id": Q_NOTE, "type": "text", "label": "Note", "required": True, "config": {}},
    {
        "id": Q_KIND,
        "type": "radio",
        "label": "Kind",
        "config": {"options": [{"id": "a", "label": "Alpha"}, {"id": "b", "label": "Beta"}]},
    },
    {
        "id": Q_EXTRA,
        "type": "text",
        "label": "Extra",
        "required": True,
        "config": {},
        "conditions": [{"question_id": Q_KIND, "operator": "equals", "value": "b"}],
    },
]
GOOD_ANSWERS = {Q_NOTE: "hello", Q_KIND: "a"}


def day(offset: int) -> date:
    return TODAY + timedelta(days=offset)


def booking_app() -> FastAPI:
    app = FastAPI()
    app.include_router(booking_router, prefix=BASE)
    return app


def make_settings(**fields) -> Settings:
    """Settings that never send for real, with a notice address."""
    values = {
        "frontend_url": "https://app.test",
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
    """Empties everything the module touches, dependants first (the foreign
    keys are RESTRICT), so a database that holds data does not matter."""
    for model in (
        BookingChange,
        Booking,
        RegistrationBlock,
        Registration,
        FormSubmission,
        FormQuestion,
        Form,
        Event,
        Article,
        ArticleType,
    ):
        await db.execute(delete(model))


async def make_article(db, slug: str = "article", **fields) -> Article:
    fields.setdefault("status", "published")
    title = fields.setdefault("title", slug)
    article = Article(slug=slug, search_text=build_search_text(title, fields.get("perex", ""), fields.get("content", "")), **fields)
    db.add(article)
    await db.commit()
    return article


async def make_event(db, article: Article, start: date | None = None, **fields) -> Event:
    title = fields.pop("title", f"{article.slug} term")
    event = Event(
        article_id=article.id,
        title=title,
        start_date=start or day(10),
        search_text=normalize_text(title),
        **fields,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def make_registration(db, event: Event, *, questions: list[dict] | None = None, blocks: list[dict] | None = None, **fields) -> Registration:
    """A registration of `event` made through the service (its form with it)."""
    body = RegistrationCreate.model_validate(
        {"event_id": event.id, "name": fields.pop("name", "Sign-up"), "blocks": blocks or [], **fields}
    )
    registration = await service.create_registration(db, body)
    if questions:
        parsed = QuestionsReplace.model_validate({"questions": questions})
        await forms_service.replace_questions(db, registration.form_id, parsed.questions)
    await db.commit()
    await db.refresh(registration)
    return registration


async def seed(db, *, questions: list[dict] | None = None, blocks: list[dict] | None = None, article: dict | None = None, event: dict | None = None, **registration):
    """A published article with one event and a registration: (article, event, registration)."""
    article_row = await make_article(db, **(article or {}))
    event_row = await make_event(db, article_row, **(event or {}))
    registration_row = await make_registration(db, event_row, questions=questions, blocks=blocks, **registration)
    return article_row, event_row, registration_row


def dates_block(*offsets: int, times: list[str] | None = None, capacity: int | None = None) -> dict:
    """A block of explicit days (offsets from today), all day or at the given times."""
    block: dict = {"days_mode": "dates", "dates": [day(offset).isoformat() for offset in offsets], "time_mode": "all_day"}
    if times:
        block.update(time_mode="manual", times=times)
    if capacity is not None:
        block["capacity"] = capacity
    return block


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


async def count_rows(db, model=Booking, *conditions) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*conditions))


async def book(client, registration, *, headers=None, token=None, **body):
    """A visitor's booking over HTTP (see booking_body for the defaults)."""
    url = f"{BASE}/registrations/{registration.id}/bookings" + (f"?token={token}" if token else "")
    return await client.post(url, json=booking_body(**body), headers=headers or {})


def booking_body(offset: int = 1, *, slot_time: str | None = None, **fields) -> dict:
    """The body of a visitor's booking for the day `offset` days from today."""
    body = {
        "slot_date": day(offset).isoformat(),
        "slot_time": slot_time,
        "name": "Eva Nováková",
        "email": "eva@example.com",
        "consent": True,
        "answers": dict(GOOD_ANSWERS),
        "language": "cs",
    }
    body.update(fields)
    return body
