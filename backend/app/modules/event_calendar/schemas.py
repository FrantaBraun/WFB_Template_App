# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.articles.schemas import ArticleTeaser, ArticleTypeOut, Status as ArticleStatus
from app.modules.event_calendar.models import SHORT_DESCRIPTION_MAX


class EventArticle(BaseModel):
    """The article an event belongs to, as much of it as a calendar needs:
    enough to link to it, colour the event by its type and mark it pinned."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    slug: str
    title: str
    image_url: str | None
    pinned: bool
    status: ArticleStatus
    type: ArticleTypeOut | None = Field(default=None, validation_alias="article_type")


class EventTeaser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    short_description: str
    start_date: date
    end_date: date | None
    start_time: time | None
    end_time: time | None
    article: EventArticle


class EventAdminOut(EventTeaser):
    article_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EventPage(BaseModel):
    items: list[EventTeaser]
    has_more: bool


class ArchiveMonth(BaseModel):
    month: int
    count: int


class ArchiveYear(BaseModel):
    year: int
    months: list[ArchiveMonth]


class DatedArticle(ArticleTeaser):
    """An article on the wall or in search results, with the date it is sorted
    by: the nearest upcoming event (or, once none is left, its last one) -
    `date_kind` "event" - or, for an article without events, the day it was
    created - "created"."""

    date: date
    date_kind: Literal["event", "created"]


class DashboardOut(BaseModel):
    upcoming: DatedArticle | None
    pinned: list[DatedArticle]
    recent_past: list[DatedArticle]


class EditorStatus(BaseModel):
    is_editor: bool


class _TermCheck(BaseModel):
    """end_date not before start_date; end_time only with a start_time and,
    within one day, not before it. Only on EventCreate, which holds the whole
    term: EventUpdate sends just some of the fields, so the router checks the
    term that results from merging them into the stored event."""

    @model_validator(mode="after")
    def _term_is_consistent(self):
        check_term(self.start_date, self.end_date, self.start_time, self.end_time)  # type: ignore[attr-defined]
        return self


def check_term(start_date: date | None, end_date: date | None, start_time: time | None, end_time: time | None) -> None:
    """Raises ValueError for an inconsistent term; ignores whatever is None
    where that makes the check impossible."""
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    if end_time is not None and start_time is None:
        raise ValueError("end_time needs a start_time")
    one_day = end_date is None or start_date is None or end_date == start_date
    if one_day and start_time is not None and end_time is not None and end_time < start_time:
        raise ValueError("end_time must not be before start_time on a single day")


class EventCreate(_TermCheck):
    article_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    short_description: str = Field(default="", max_length=SHORT_DESCRIPTION_MAX)
    start_date: date
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None


class EventUpdate(BaseModel):
    """All optional, applied with exclude_unset. Sending end_date / start_time /
    end_time as null (not omitting them) clears them."""

    article_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    short_description: str | None = Field(default=None, max_length=SHORT_DESCRIPTION_MAX)
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
