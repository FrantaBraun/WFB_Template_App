# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The pure slot logic of the booking module (app.modules.event_booking.slots):
how blocks expand into slots, what never gets offered (the past, beyond the
horizon), how duplicates merge, which days are free, and which sets of blocks
are refused. No database and no real clock - "now" is always passed in."""

import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfoNotFoundError

import pytest

from app.modules.event_booking import slots
from app.modules.event_booking.slots import Block, Slot, expand_slots, validate_blocks

NOW = datetime(2026, 6, 10, 10, 0)  # a Wednesday
TODAY = NOW.date()


def _days(start: date, count: int) -> tuple[date, ...]:
    return tuple(start + timedelta(days=offset) for offset in range(count))


def _expand(blocks, capacity=1, *, now=NOW, horizon=365, **kwargs):
    return expand_slots(blocks, capacity, now=now, horizon_days=horizon, **kwargs)


# --- Times of one block ----------------------------------------------------------------------------


def test_all_day_is_one_slot_without_time():
    assert slots.block_times(Block(time_mode="all_day")) == [None]


def test_manual_times_are_sorted_and_unique():
    block = Block(time_mode="manual", times=(time(11), time(9, 30), time(11)))

    assert slots.block_times(block) == [time(9, 30), time(11)]


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (60, [time(9), time(10), time(11)]),
        (45, [time(9), time(9, 45), time(10, 30), time(11, 15)]),  # the last one ends exactly at 12:00
        (50, [time(9), time(9, 50), time(10, 40)]),  # 11:30 + 50 would run past 12:00
        (180, [time(9)]),
    ],
)
def test_generated_times_step_from_the_start_and_must_end_by_the_end(minutes, expected):
    block = Block(time_mode="generated", slot_minutes=minutes, time_from=time(9), time_to=time(12))

    assert slots.block_times(block) == expected


def test_generated_times_with_nothing_fitting_or_incomplete_are_empty():
    assert slots.block_times(Block(time_mode="generated", slot_minutes=120, time_from=time(9), time_to=time(10))) == []
    assert slots.block_times(Block(time_mode="generated", slot_minutes=30)) == []


# --- Days of one block --------------------------------------------------------------------------------


def test_dates_mode_keeps_only_the_listed_days_within_the_window():
    days = _days(TODAY, 5)
    block = Block(days_mode="dates", dates=(days[3], days[1], days[1], TODAY - timedelta(days=3)))

    assert slots.block_days(block, TODAY, days[4]) == [days[1], days[3]]
    assert slots.block_days(block, days[2], days[4]) == [days[3]]


def test_weekdays_mode_picks_those_weekdays_inside_the_range_and_window():
    # 2026-06-10 is a Wednesday (2); ask for Mondays (0) and Wednesdays.
    block = Block(days_mode="weekdays", weekdays=(0, 2), range_from=date(2026, 6, 1), range_to=date(2026, 6, 21))

    assert slots.block_days(block, date(2026, 6, 10), date(2026, 6, 30)) == [
        date(2026, 6, 10),
        date(2026, 6, 15),
        date(2026, 6, 17),
    ]


def test_weekdays_mode_without_a_range_has_no_days():
    assert slots.block_days(Block(days_mode="weekdays", weekdays=(0,)), TODAY, TODAY + timedelta(days=30)) == []


def test_any_future_mode_is_every_day_of_the_window():
    assert slots.block_days(Block(days_mode="any_future"), TODAY, TODAY + timedelta(days=2)) == list(_days(TODAY, 3))


def test_unknown_days_mode_has_no_days():
    assert slots.block_days(Block(days_mode="nonsense"), TODAY, TODAY + timedelta(days=2)) == []


# --- Expanding blocks into slots ---------------------------------------------------------------------


def test_no_blocks_offers_every_future_day_all_day():
    result = _expand([], horizon=3)

    assert [(slot.day, slot.time) for slot in result] == [(day, None) for day in _days(TODAY, 4)]


@pytest.mark.parametrize("days_mode", ["dates", "weekdays", "any_future"])
@pytest.mark.parametrize("time_mode", ["all_day", "manual", "generated"])
def test_every_combination_of_days_and_times_expands(days_mode, time_mode):
    first, second = TODAY + timedelta(days=1), TODAY + timedelta(days=8)  # Thursdays
    block = Block(
        days_mode=days_mode,
        dates=(first, second),
        weekdays=(3,),
        range_from=first,
        range_to=second,
        time_mode=time_mode,
        times=(time(14), time(15)),  # later than NOW, so today's are offered too
        slot_minutes=60,
        time_from=time(16),
        time_to=time(18),
    )
    per_day = {"all_day": 1, "manual": 2, "generated": 2}[time_mode]
    days = {"dates": 2, "weekdays": 2, "any_future": 11}[days_mode]  # any_future: today + 10 days of horizon

    result = _expand([block], horizon=10)

    assert len(result) == days * per_day
    assert result == sorted(result, key=lambda slot: (slot.day, slot.time or time.min))
    if days_mode != "any_future":
        assert {slot.day for slot in result} == {first, second}


def test_timed_slots_of_today_are_offered_only_while_they_are_still_ahead():
    block = Block(days_mode="dates", dates=(TODAY,), time_mode="manual", times=(time(9, 59), time(10, 0), time(10, 1)))

    assert [slot.time for slot in _expand([block])] == [time(10, 1)]


def test_an_all_day_slot_of_today_is_still_offered_but_yesterday_is_not():
    block = Block(days_mode="dates", dates=(TODAY - timedelta(days=1), TODAY), time_mode="all_day")

    assert [slot.day for slot in _expand([block])] == [TODAY]


def test_nothing_is_offered_beyond_the_horizon():
    block = Block(days_mode="any_future", time_mode="all_day")

    result = _expand([block], horizon=30)

    assert result[0].day == TODAY
    assert result[-1].day == TODAY + timedelta(days=30)
    assert len(result) == 31


def test_a_listed_day_beyond_the_horizon_is_dropped():
    block = Block(days_mode="dates", dates=(TODAY + timedelta(days=30), TODAY + timedelta(days=31)), time_mode="all_day")

    assert [slot.day for slot in _expand([block], horizon=30)] == [TODAY + timedelta(days=30)]


def test_the_window_can_be_narrowed_with_date_from_and_date_to():
    block = Block(days_mode="any_future", time_mode="all_day")

    result = _expand([block], date_from=TODAY + timedelta(days=5), date_to=TODAY + timedelta(days=7))

    assert [slot.day for slot in result] == [TODAY + timedelta(days=offset) for offset in (5, 6, 7)]


def test_a_window_entirely_in_the_past_or_reversed_offers_nothing():
    block = Block(days_mode="any_future", time_mode="all_day")

    assert _expand([block], date_from=TODAY - timedelta(days=9), date_to=TODAY - timedelta(days=2)) == []
    assert _expand([block], date_from=TODAY + timedelta(days=5), date_to=TODAY + timedelta(days=2)) == []


def test_capacity_is_the_blocks_own_or_the_registrations():
    own = Block(days_mode="dates", dates=(TODAY + timedelta(days=1),), time_mode="all_day", capacity=5)
    default = Block(days_mode="dates", dates=(TODAY + timedelta(days=2),), time_mode="all_day")

    result = _expand([own, default], capacity=2)

    assert [(slot.day, slot.capacity) for slot in result] == [
        (TODAY + timedelta(days=1), 5),
        (TODAY + timedelta(days=2), 2),
    ]


def test_the_same_slot_in_two_blocks_is_offered_once_with_the_first_blocks_capacity():
    day = TODAY + timedelta(days=3)
    first = Block(days_mode="dates", dates=(day,), time_mode="manual", times=(time(9), time(10)), capacity=4)
    second = Block(days_mode="dates", dates=(day,), time_mode="manual", times=(time(10), time(11)), capacity=9)

    result = _expand([first, second])

    assert [(slot.time, slot.capacity) for slot in result] == [(time(9), 4), (time(10), 4), (time(11), 9)]


def test_the_merge_does_not_depend_on_which_block_covers_more():
    day = TODAY + timedelta(days=3)
    narrow = Block(days_mode="dates", dates=(day,), time_mode="manual", times=(time(9),), capacity=7)
    wide = Block(days_mode="dates", dates=(day,), time_mode="generated", slot_minutes=60, time_from=time(9), time_to=time(11), capacity=2)

    assert [(slot.time, slot.capacity) for slot in _expand([narrow, wide])] == [(time(9), 7), (time(10), 2)]
    assert [(slot.time, slot.capacity) for slot in _expand([wide, narrow])] == [(time(9), 2), (time(10), 2)]


def test_slots_have_a_key_of_day_and_time():
    assert Slot(TODAY, time(9), 3).key == (TODAY, time(9))
    assert Slot(TODAY, None, 3).key == (TODAY, None)


# --- Which days are free ------------------------------------------------------------------------------


def test_a_day_is_free_when_a_time_has_room_and_counts_its_free_slots():
    monday, tuesday = TODAY + timedelta(days=5), TODAY + timedelta(days=6)
    offers = [
        (Slot(monday, time(9), 1), 0),
        (Slot(monday, time(10), 1), 1),
        (Slot(monday, time(11), 2), 2),
        (Slot(tuesday, time(9), 1), 0),
    ]

    assert slots.free_days(offers) == {monday: 2}


def test_a_whole_day_slot_is_free_until_its_capacity_is_used():
    day = TODAY + timedelta(days=2)
    slot = Slot(day, None, 3)

    assert slots.free_days([(slot, slots.free_places(slot, {(day, None): 2}))]) == {day: 1}
    assert slots.free_days([(slot, slots.free_places(slot, {(day, None): 3}))]) == {}


def test_free_places_never_go_negative():
    slot = Slot(TODAY, time(9), 2)

    assert slots.free_places(slot, {slot.key: 5}) == 0
    assert slots.free_places(slot, {}) == 2


# --- Which sets of blocks are refused -----------------------------------------------------------------


def _valid_dates_block(**changes):
    return Block(**{"days_mode": "dates", "dates": (TODAY + timedelta(days=1),), "time_mode": "all_day", **changes})


def test_an_empty_set_and_ordinary_blocks_are_valid():
    blocks = [
        _valid_dates_block(),
        Block(days_mode="weekdays", weekdays=(0, 4), range_from=TODAY, range_to=TODAY + timedelta(days=60), time_mode="manual", times=(time(9),)),
        Block(
            days_mode="dates",
            dates=(TODAY + timedelta(days=100),),
            time_mode="generated",
            slot_minutes=30,
            time_from=time(8),
            time_to=time(9),
            capacity=3,
        ),
    ]

    assert validate_blocks([]) == []
    assert validate_blocks(blocks) == []


def test_any_future_may_be_the_only_block_and_only_all_day():
    assert validate_blocks([Block(days_mode="any_future", time_mode="all_day")]) == []
    assert any("only block" in problem for problem in validate_blocks([Block(days_mode="any_future"), _valid_dates_block()]))
    assert any("all day" in problem for problem in validate_blocks([Block(days_mode="any_future", time_mode="manual", times=(time(9),))]))


@pytest.mark.parametrize(
    ("block", "fragment"),
    [
        (Block(days_mode="nonsense"), "days_mode"),
        (_valid_dates_block(time_mode="nonsense"), "time_mode"),
        (_valid_dates_block(capacity=0), "capacity"),
        (_valid_dates_block(capacity=slots.MAX_CAPACITY + 1), "capacity"),
        (_valid_dates_block(dates=()), "at least one date"),
        (_valid_dates_block(dates=(TODAY, TODAY)), "duplicate dates"),
        (_valid_dates_block(dates=_days(TODAY, slots.MAX_DATES + 1)), "at most"),
        (Block(days_mode="weekdays", range_from=TODAY, range_to=TODAY + timedelta(days=7)), "day of the week"),
        (Block(days_mode="weekdays", weekdays=(7,), range_from=TODAY, range_to=TODAY + timedelta(days=7)), "0 (Monday) to 6"),
        (Block(days_mode="weekdays", weekdays=(1, 1), range_from=TODAY, range_to=TODAY + timedelta(days=7)), "distinct"),
        (Block(days_mode="weekdays", weekdays=(1,), range_from=TODAY), "both ends"),
        (Block(days_mode="weekdays", weekdays=(1,), range_to=TODAY), "both ends"),
        (Block(days_mode="weekdays", weekdays=(1,), range_from=TODAY, range_to=TODAY - timedelta(days=1)), "ends before"),
        (Block(days_mode="weekdays", weekdays=(1,), range_from=TODAY, range_to=TODAY + timedelta(days=slots.MAX_RANGE_DAYS + 1)), "longer than"),
        (_valid_dates_block(time_mode="manual"), "at least one time"),
        (_valid_dates_block(time_mode="manual", times=(time(9), time(9))), "duplicate times"),
        (
            _valid_dates_block(time_mode="manual", times=tuple(time(h, m) for h in range(24) for m in (0, 10, 20, 30, 40, 50))),
            "at most",
        ),
        (_valid_dates_block(time_mode="generated", time_from=time(9), time_to=time(12)), "slot_minutes"),
        (_valid_dates_block(time_mode="generated", slot_minutes=4, time_from=time(9), time_to=time(12)), "slot_minutes"),
        (_valid_dates_block(time_mode="generated", slot_minutes=1441, time_from=time(9), time_to=time(12)), "slot_minutes"),
        (_valid_dates_block(time_mode="generated", slot_minutes=30, time_to=time(12)), "time_from and time_to"),
        (_valid_dates_block(time_mode="generated", slot_minutes=30, time_from=time(12), time_to=time(12)), "before time_to"),
        (_valid_dates_block(time_mode="generated", slot_minutes=30, time_from=time(13), time_to=time(12)), "before time_to"),
        (_valid_dates_block(time_mode="generated", slot_minutes=120, time_from=time(9), time_to=time(10)), "not even one slot"),
    ],
)
def test_invalid_blocks_are_refused_with_a_reason(block, fragment):
    problems = validate_blocks([block])

    assert problems
    assert any(fragment in problem for problem in problems), problems
    assert problems[0].startswith("block 1")


def test_slot_minutes_at_the_limits_are_accepted():
    for minutes, time_to in ((5, time(9, 5)), (1440, time(23, 59))):
        block = _valid_dates_block(time_mode="generated", slot_minutes=minutes, time_from=time(0) if minutes == 1440 else time(9), time_to=time_to)
        if minutes == 1440:
            assert any("not even one slot" in problem for problem in validate_blocks([block]))  # 24 h cannot fit before 23:59
        else:
            assert validate_blocks([block]) == []


def test_too_many_blocks_are_refused():
    blocks = [_valid_dates_block(dates=(TODAY + timedelta(days=offset),)) for offset in range(slots.MAX_BLOCKS + 1)]

    assert any("at most" in problem for problem in validate_blocks(blocks))


def test_problems_name_the_block_they_are_in():
    problems = validate_blocks([_valid_dates_block(), _valid_dates_block(dates=(), capacity=0)])

    assert problems and all(problem.startswith("block 2") for problem in problems)


def test_an_all_day_and_a_timed_block_may_not_share_a_day():
    day = TODAY + timedelta(days=4)
    all_day = _valid_dates_block(dates=(day,))
    timed = _valid_dates_block(dates=(day, day + timedelta(days=1)), time_mode="manual", times=(time(9),))

    problems = validate_blocks([all_day, timed])

    assert problems == [f"a day cannot be both all day and timed (for example {day.isoformat()})"]


def test_the_clash_is_found_between_a_weekday_range_and_a_day_list():
    friday = date(2026, 6, 12)
    weekly = Block(days_mode="weekdays", weekdays=(4,), range_from=date(2026, 6, 1), range_to=date(2026, 6, 30), time_mode="manual", times=(time(9),))
    single = _valid_dates_block(dates=(friday,))

    assert validate_blocks([weekly, single])
    assert validate_blocks([single, weekly])
    assert validate_blocks([weekly, _valid_dates_block(dates=(date(2026, 6, 11),))]) == []  # a Thursday


def test_all_day_and_timed_blocks_on_different_days_are_fine():
    all_day = _valid_dates_block(dates=(TODAY + timedelta(days=1),))
    timed = _valid_dates_block(dates=(TODAY + timedelta(days=2),), time_mode="manual", times=(time(9),))

    assert validate_blocks([all_day, timed]) == []


# --- The local clock ------------------------------------------------------------------------------------


def test_local_now_is_naive_and_close_to_the_real_time():
    now = slots.local_now()

    assert now.tzinfo is None
    assert abs((now - datetime.now()).total_seconds()) < 3 * 3600


def test_to_local_converts_a_moment_to_prague_time():
    assert slots.to_local(datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)) == datetime(2026, 7, 1, 12, 0)  # summer: UTC+2
    assert slots.to_local(datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)) == datetime(2026, 1, 1, 11, 0)  # winter: UTC+1


def test_without_a_time_zone_database_the_servers_own_time_is_used_and_warned_about_once(monkeypatch, caplog):
    def _missing(name):
        raise ZoneInfoNotFoundError(name)

    monkeypatch.setattr(slots, "ZoneInfo", _missing)
    monkeypatch.setattr(slots, "_zone_warned", False)

    with caplog.at_level(logging.WARNING, logger=slots.__name__):
        first = slots.local_now()
        second = slots.local_now()
        converted = slots.to_local(datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc))

    assert first.tzinfo is None and second.tzinfo is None and converted.tzinfo is None
    assert len([record for record in caplog.records if "tzdata" in record.getMessage()]) == 1
