# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Which slots a registration offers, as pure functions: no database, no
clock of their own (the caller passes "now").

A registration's *blocks* say on which days and at which times people can
book. A block has

- days: `dates` (an explicit list of days), `weekdays` (days of the week
  within a range, Monday = 0) or `any_future` (any day from today to the
  horizon);
- times: `all_day` (the whole day is one slot), `manual` (a list of HH:MM)
  or `generated` (slots of `slot_minutes` from `time_from`, the last one
  ending no later than `time_to`);
- an optional capacity of its own (else the registration's).

A registration with no blocks offers any future day, all day. Slots are
never stored: expand_slots() computes them. The same slot in two blocks is
offered once, with the FIRST block's capacity. An all-day slot has one
capacity for the whole day.

All times are local (Europe/Prague, see local_now) with no zone conversion.
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

LOCAL_ZONE = "Europe/Prague"

DAYS_MODES = ("dates", "weekdays", "any_future")
TIME_MODES = ("all_day", "manual", "generated")

MIN_SLOT_MINUTES = 5
MAX_SLOT_MINUTES = 1440
MAX_RANGE_DAYS = 1100
MAX_DATES = 400
MAX_MANUAL_TIMES = 100
MAX_BLOCKS = 50
MAX_CAPACITY = 1000

_zone_warned = False


def _local_zone() -> ZoneInfo | None:
    """The local zone, or None - warning once - where the time zone database is missing."""
    global _zone_warned
    try:
        return ZoneInfo(LOCAL_ZONE)
    except ZoneInfoNotFoundError:
        if not _zone_warned:
            logger.warning("No time zone database for %s (install tzdata) - using the server's local time", LOCAL_ZONE)
            _zone_warned = True
        return None


def local_now() -> datetime:
    """"Now" as a naive local (Europe/Prague) datetime. Falls back to the
    server's own clock where the time zone database is missing."""
    zone = _local_zone()
    return datetime.now(zone).replace(tzinfo=None) if zone else datetime.now()


def to_local(moment: datetime) -> datetime:
    """A timezone-aware moment as a naive local (Europe/Prague) datetime."""
    zone = _local_zone()
    return moment.astimezone(zone).replace(tzinfo=None) if zone else moment.astimezone().replace(tzinfo=None)


@dataclass(frozen=True)
class Block:
    days_mode: str = "any_future"
    dates: tuple[date, ...] = ()
    weekdays: tuple[int, ...] = ()
    range_from: date | None = None
    range_to: date | None = None
    time_mode: str = "all_day"
    times: tuple[time, ...] = ()
    slot_minutes: int | None = None
    time_from: time | None = None
    time_to: time | None = None
    capacity: int | None = None


@dataclass(frozen=True)
class Slot:
    """One bookable slot: a day and a time, or (time None) the whole day."""

    day: date
    time: time | None
    capacity: int = field(default=1)

    @property
    def key(self) -> tuple[date, time | None]:
        return (self.day, self.time)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def block_times(block: Block) -> list[time | None]:
    """The times of day of a block, in order: [None] for all day."""
    if block.time_mode == "all_day":
        return [None]
    if block.time_mode == "manual":
        return sorted(set(block.times))
    if block.time_mode == "generated" and block.slot_minutes and block.time_from and block.time_to:
        step, end = block.slot_minutes, _minutes(block.time_to)
        times: list[time | None] = []
        start = _minutes(block.time_from)
        while start + step <= end:
            times.append(time(start // 60, start % 60))
            start += step
        return times
    return []


def block_days(block: Block, low: date, high: date) -> list[date]:
    """The days of a block that fall in low..high (inclusive), in order."""
    if block.days_mode == "dates":
        return sorted(day for day in set(block.dates) if low <= day <= high)
    if block.days_mode == "weekdays":
        if block.range_from is None or block.range_to is None:
            return []
        first, last = max(low, block.range_from), min(high, block.range_to)
        days = []
        day = first
        while day <= last:
            if day.weekday() in block.weekdays:
                days.append(day)
            day += timedelta(days=1)
        return days
    if block.days_mode == "any_future":
        return [low + timedelta(days=offset) for offset in range((high - low).days + 1)]
    return []


def effective_blocks(blocks: Sequence[Block]) -> list[Block]:
    """The blocks a registration actually offers: with none, any future day, all day."""
    return list(blocks) if blocks else [Block(days_mode="any_future", time_mode="all_day")]


def expand_slots(
    blocks: Sequence[Block],
    default_capacity: int,
    *,
    now: datetime,
    horizon_days: int,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Slot]:
    """Every slot on offer, in order, optionally only within date_from..date_to.

    Never in the past (a timed slot whose start is not after `now`; an all-day
    slot of a day before today - today itself is still offered) and never
    beyond `horizon_days` from today. Deduplicated: the first block that
    offers a slot decides its capacity."""
    today = now.date()
    low = max(today, date_from) if date_from else today
    high = min(today + timedelta(days=horizon_days), date_to) if date_to else today + timedelta(days=horizon_days)
    if low > high:
        return []

    slots: dict[tuple[date, time | None], Slot] = {}
    for block in effective_blocks(blocks):
        times = block_times(block)
        capacity = block.capacity or default_capacity
        for day in block_days(block, low, high):
            for slot_time in times:
                if slot_time is not None and datetime.combine(day, slot_time) <= now:
                    continue
                slots.setdefault((day, slot_time), Slot(day, slot_time, capacity))
    return sorted(slots.values(), key=lambda slot: (slot.day, slot.time or time.min))


def free_places(slot: Slot, taken: dict[tuple[date, time | None], int]) -> int:
    """Places left in a slot, given how many confirmed bookings each slot has."""
    return max(slot.capacity - taken.get(slot.key, 0), 0)


def free_days(offers: Iterable[tuple[Slot, int]]) -> dict[date, int]:
    """Day -> number of slots with room left, for the days that have at least
    one. `offers` pairs each slot with its free places. A day is free when it
    has a slot with room: a timed slot not yet full, or the all-day slot while
    fewer than its capacity have booked the day."""
    free: dict[date, int] = {}
    for slot, places in offers:
        if places > 0:
            free[slot.day] = free.get(slot.day, 0) + 1
    return free


def validate_blocks(blocks: Sequence[Block]) -> list[str]:
    """Why a set of blocks is not acceptable (empty when it is). Checked when a registration is saved."""
    problems: list[str] = []
    if len(blocks) > MAX_BLOCKS:
        problems.append(f"at most {MAX_BLOCKS} blocks")

    for index, block in enumerate(blocks, start=1):
        where = f"block {index}"
        if block.days_mode not in DAYS_MODES:
            problems.append(f"{where}: unknown days_mode")
            continue
        if block.time_mode not in TIME_MODES:
            problems.append(f"{where}: unknown time_mode")
            continue
        if block.capacity is not None and not 1 <= block.capacity <= MAX_CAPACITY:
            problems.append(f"{where}: capacity must be between 1 and {MAX_CAPACITY}")

        if block.days_mode == "dates":
            if not block.dates:
                problems.append(f"{where}: at least one date is needed")
            elif len(set(block.dates)) != len(block.dates):
                problems.append(f"{where}: duplicate dates")
            elif len(block.dates) > MAX_DATES:
                problems.append(f"{where}: at most {MAX_DATES} dates")
        elif block.days_mode == "weekdays":
            if not block.weekdays:
                problems.append(f"{where}: at least one day of the week is needed")
            elif any(not 0 <= weekday <= 6 for weekday in block.weekdays) or len(set(block.weekdays)) != len(block.weekdays):
                problems.append(f"{where}: days of the week must be distinct values 0 (Monday) to 6 (Sunday)")
            if block.range_from is None or block.range_to is None:
                problems.append(f"{where}: both ends of the range are needed")
            elif block.range_from > block.range_to:
                problems.append(f"{where}: the range ends before it starts")
            elif (block.range_to - block.range_from).days > MAX_RANGE_DAYS:
                problems.append(f"{where}: the range is longer than {MAX_RANGE_DAYS} days")
        elif block.days_mode == "any_future":
            if len(blocks) > 1:
                problems.append(f"{where}: 'any future day' must be the only block")
            if block.time_mode != "all_day":
                problems.append(f"{where}: 'any future day' can only be all day")

        if block.time_mode == "manual":
            if not block.times:
                problems.append(f"{where}: at least one time is needed")
            elif len(set(block.times)) != len(block.times):
                problems.append(f"{where}: duplicate times")
            elif len(block.times) > MAX_MANUAL_TIMES:
                problems.append(f"{where}: at most {MAX_MANUAL_TIMES} times")
        elif block.time_mode == "generated":
            if block.slot_minutes is None or not MIN_SLOT_MINUTES <= block.slot_minutes <= MAX_SLOT_MINUTES:
                problems.append(f"{where}: slot_minutes must be between {MIN_SLOT_MINUTES} and {MAX_SLOT_MINUTES}")
            elif block.time_from is None or block.time_to is None:
                problems.append(f"{where}: both time_from and time_to are needed")
            elif block.time_from >= block.time_to:
                problems.append(f"{where}: time_from must be before time_to")
            elif not block_times(block):
                problems.append(f"{where}: not even one slot fits between time_from and time_to")

    if problems:
        return problems

    # An all-day block and a timed one on the same day would book the same day two ways.
    far = date(2100, 1, 1)
    kinds: dict[date, set[bool]] = {}
    for block in blocks:
        if block.days_mode == "any_future":
            continue
        low = block.range_from if block.days_mode == "weekdays" else date.min
        days = block_days(block, low or date.min, block.range_to if block.days_mode == "weekdays" else far)
        for day in days:
            kinds.setdefault(day, set()).add(block.time_mode == "all_day")
    clash = sorted(day for day, which in kinds.items() if len(which) > 1)
    if clash:
        problems.append(f"a day cannot be both all day and timed (for example {clash[0].isoformat()})")
    return problems
