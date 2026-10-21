# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules of reserving the pub, as pure functions: no database, no clock of
their own (the caller passes "now"), no HTTP.

Times of a day are whole minutes since midnight (`int`); the service converts
from and to `datetime.time`. Everything is local (Europe/Prague), without zone
conversion, and a day is one stretch from `opens` to `closes` (closing after
midnight is not supported).

What can be reserved
- A **table** for `party_size` people from `start` to `end`. Guests never choose
  a table: assign_table() takes the smallest active one that seats the party and
  is free. Between two reservations of the SAME table there must be at least
  BUFFER_MINUTES (the new one may neither start before the other's end plus the
  buffer, nor end after the other's start minus it).
- The **whole pub** from `start` to the closing time of the day. During that
  time there may be no table reservation (they must not overlap it) and no
  second whole-pub reservation; and while it is held, no table can be reserved
  that overlaps it. Between a table and the whole pub only an overlap counts, not
  the buffer - the buffer is a rule of one table.

How long a table reservation lasts: the guest may ask for a duration (default
DEFAULT_DURATION), the end is cut at closing time, and what is left must still
be at least MIN_DURATION. Start times are multiples of STEP_MINUTES.

Every refusal is a short code (see the constants below the functions that
return them) which the service turns into an HTTP answer and the frontend into
the visitor's language.
"""

from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time

from app.modules.table_reservations.models import KIND_TABLE, KIND_WHOLE_VENUE

BUFFER_MINUTES = 30
STEP_MINUTES = 15
MIN_DURATION = 30
MAX_DURATION = 480
DEFAULT_DURATION = 120

# Refusal codes
BAD_START = "bad_start"  # not a multiple of STEP_MINUTES
OUTSIDE_HOURS = "outside_hours"  # before opening, or too close to closing for MIN_DURATION
TOO_SOON = "too_soon"  # earlier than now + the lead time
CLOSED = "closed"  # the pub is closed that day
PARTY_TOO_LARGE = "party_too_large"  # no active table seats so many
VENUE_RESERVED = "venue_reserved"  # the whole pub is reserved at that time
NO_TABLE = "no_table"  # every suitable table is taken
TABLES_RESERVED = "tables_reserved"  # a table is reserved during the requested whole-pub time


@dataclass(frozen=True)
class Hours:
    """Opening hours of one day, as minutes since midnight."""

    opens: int
    closes: int


@dataclass(frozen=True)
class DayOverride:
    """A one-off change of one date: closed, or other hours."""

    closed: bool
    hours: Hours | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Seating:
    """A table as far as assigning is concerned."""

    id: Hashable
    seats: int
    position: int = 0
    is_active: bool = True


@dataclass(frozen=True)
class Held:
    """A confirmed reservation of the day being planned (`end` is exclusive)."""

    kind: str
    table_id: Hashable | None
    start: int
    end: int


def minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def at(value: int) -> time:
    """Minutes since midnight as a time of day."""
    if not 0 <= value < 24 * 60:
        raise ValueError(f"{value} minutes is not a time of one day")
    return time(value // 60, value % 60)


def round_up(value: int, step: int = STEP_MINUTES) -> int:
    return -(-value // step) * step


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def hours_problem(opens: int, closes: int) -> str | None:
    """Why these opening hours are not acceptable (a code), or None."""
    if closes <= opens:
        return "closes_before_opens"
    if closes - opens < MIN_DURATION:
        return "too_short"
    return None


def day_hours(day: date, weekly: Mapping[int, Hours | None], overrides: Mapping[date, DayOverride]) -> Hours | None:
    """The hours of a date: a one-off change wins over the weekday's regular
    hours. None = closed."""
    override = overrides.get(day)
    if override is not None:
        return None if override.closed else override.hours
    return weekly.get(day.weekday())


def earliest_start(day: date, now: datetime, lead_minutes: int) -> int | None:
    """The first start time (minutes) a guest may ask for on `day`: None for a
    day already over, 0 for a later day, and for today now plus the lead time."""
    today = now.date()
    if day < today:
        return None
    if day > today:
        return 0
    return round_up(minutes(now.time()) + lead_minutes)


def start_problem(start: int, hours: Hours, earliest: int) -> str | None:
    """Why `start` is not a possible start on a day with `hours` (a code), or None."""
    if start % STEP_MINUTES != 0:
        return BAD_START
    if start < hours.opens or start > hours.closes - MIN_DURATION:
        return OUTSIDE_HOURS
    if start < earliest:
        return TOO_SOON
    return None


def planned_end(start: int, duration: int, hours: Hours) -> int | None:
    """When a table reservation of `duration` minutes from `start` ends: cut at
    closing time. None when what is left is shorter than MIN_DURATION."""
    end = min(start + duration, hours.closes)
    return end if end - start >= MIN_DURATION else None


def _table_clash(start: int, end: int, other: Held) -> bool:
    """Whether [start, end) comes closer to another reservation of the same table than the buffer allows."""
    return start < other.end + BUFFER_MINUTES and other.start < end + BUFFER_MINUTES


def assign_table(tables: Iterable[Seating], held: Sequence[Held], start: int, end: int, party_size: int) -> tuple[Seating | None, str | None]:
    """The table for a party in [start, end): the smallest active one that seats
    them and keeps the buffer to its other reservations (ties: lower position,
    then id). (None, reason) when there is none: PARTY_TOO_LARGE (no table seats so
    many), VENUE_RESERVED (the whole pub is reserved in that time) or NO_TABLE."""
    usable = sorted((table for table in tables if table.is_active and table.seats >= party_size), key=lambda t: (t.seats, t.position, str(t.id)))
    if not usable:
        return None, PARTY_TOO_LARGE
    if any(h.kind == KIND_WHOLE_VENUE and overlaps(start, end, h.start, h.end) for h in held):
        return None, VENUE_RESERVED
    for table in usable:
        if not any(h.kind == KIND_TABLE and h.table_id == table.id and _table_clash(start, end, h) for h in held):
            return table, None
    return None, NO_TABLE


def whole_venue_problem(start: int, hours: Hours, held: Sequence[Held]) -> str | None:
    """Why the whole pub cannot be reserved from `start` to closing (a code), or None:
    another whole-pub reservation overlaps (VENUE_RESERVED) or a table reservation does
    (TABLES_RESERVED)."""
    for h in held:
        if overlaps(start, hours.closes, h.start, h.end):
            return VENUE_RESERVED if h.kind == KIND_WHOLE_VENUE else TABLES_RESERVED
    return None


def whole_venue_from(hours: Hours, held: Sequence[Held], earliest: int) -> tuple[int | None, str | None]:
    """The earliest start from which the whole pub can be reserved (every later
    start, in steps, up to MIN_DURATION before closing, works too) - or (None, reason)
    when it cannot be reserved that day: VENUE_RESERVED, TABLES_RESERVED (the tables'
    reservations run so late that nothing is left) or TOO_SOON (nothing is left today)."""
    if any(h.kind == KIND_WHOLE_VENUE for h in held):
        return None, VENUE_RESERVED
    latest = hours.closes - MIN_DURATION
    base = round_up(max(hours.opens, earliest))
    tables_end = max((h.end for h in held if h.kind == KIND_TABLE and h.start < hours.closes), default=0)
    candidate = max(base, round_up(tables_end))
    if candidate <= latest:
        return candidate, None
    return None, (TABLES_RESERVED if base <= latest else TOO_SOON)


def available_starts(
    hours: Hours, held: Sequence[Held], tables: Sequence[Seating], party_size: int, duration: int, earliest: int
) -> list[int]:
    """Every start time (minutes) at which a party of `party_size` could be seated
    for `duration` minutes (cut at closing time)."""
    starts: list[int] = []
    for start in range(round_up(max(hours.opens, earliest)), hours.closes - MIN_DURATION + 1, STEP_MINUTES):
        end = planned_end(start, duration, hours)
        if end is None:
            continue
        table, _ = assign_table(tables, held, start, end, party_size)
        if table is not None:
            starts.append(start)
    return starts


def fits_hours(start: int, end: int, hours: Hours | None) -> bool:
    """Whether a reservation from `start` to `end` lies within `hours` (None = closed: nothing fits)."""
    return hours is not None and start >= hours.opens and end <= hours.closes
