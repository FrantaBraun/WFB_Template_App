# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The pure rules of the table reservations module (rules.py): no database, no
clock, times as minutes since midnight."""

from datetime import date, datetime, time

import pytest

from app.modules.table_reservations import rules
from app.modules.table_reservations.models import KIND_TABLE, KIND_WHOLE_VENUE
from app.modules.table_reservations.rules import DayOverride, Held, Hours, Seating


def m(hours: int, minutes: int = 0) -> int:
    return hours * 60 + minutes


OPEN = Hours(m(10), m(22))  # 10:00 - 22:00

SMALL = Seating(id="small", seats=2, position=1)
MIDDLE = Seating(id="middle", seats=4, position=2)
BIG = Seating(id="big", seats=6, position=3)
TABLES = [BIG, SMALL, MIDDLE]  # deliberately unordered


def on_table(table_id: str, start: int, end: int) -> Held:
    return Held(KIND_TABLE, table_id, start, end)


def whole(start: int, end: int = m(22)) -> Held:
    return Held(KIND_WHOLE_VENUE, None, start, end)


# --- Opening hours ------------------------------------------------------------------------------


def test_closing_must_come_after_opening_and_leave_room_for_a_reservation():
    assert rules.hours_problem(m(10), m(22)) is None
    assert rules.hours_problem(m(22), m(10)) == "closes_before_opens"
    assert rules.hours_problem(m(10), m(10)) == "closes_before_opens"
    assert rules.hours_problem(m(10), m(10, 15)) == "too_short"
    assert rules.hours_problem(m(10), m(10, 30)) is None


def test_a_one_off_change_wins_over_the_regular_hours_of_the_weekday():
    monday = date(2027, 5, 3)
    weekly = {0: OPEN, 1: None}
    assert monday.weekday() == 0

    assert rules.day_hours(monday, weekly, {}) == OPEN
    assert rules.day_hours(monday, weekly, {monday: DayOverride(closed=True, reason="Private party")}) is None
    assert rules.day_hours(monday, weekly, {monday: DayOverride(closed=False, hours=Hours(m(16), m(20)))}) == Hours(m(16), m(20))
    assert rules.day_hours(date(2027, 5, 4), weekly, {}) is None  # Tuesday: closed in the regular hours
    assert rules.day_hours(date(2027, 5, 5), weekly, {}) is None  # Wednesday: not mentioned at all
    assert rules.day_hours(date(2027, 5, 4), weekly, {date(2027, 5, 4): DayOverride(closed=False, hours=OPEN)}) == OPEN


def test_the_exception_of_another_date_changes_nothing():
    weekly = {n: OPEN for n in range(7)}
    assert rules.day_hours(date(2027, 5, 3), weekly, {date(2027, 5, 10): DayOverride(closed=True)}) == OPEN


# --- Starts ---------------------------------------------------------------------------------------------


def test_the_earliest_start_depends_on_the_day():
    now = datetime(2027, 5, 3, 9, 7)

    assert rules.earliest_start(date(2027, 5, 2), now, 30) is None  # a day already over
    assert rules.earliest_start(date(2027, 5, 4), now, 30) == 0  # a later day: any time
    assert rules.earliest_start(date(2027, 5, 3), now, 30) == m(9, 45)  # now + 30 min, up to the next step
    assert rules.earliest_start(date(2027, 5, 3), datetime(2027, 5, 3, 9, 0), 30) == m(9, 30)
    assert rules.earliest_start(date(2027, 5, 3), now, 0) == m(9, 15)


@pytest.mark.parametrize(
    ("start", "earliest", "problem"),
    [
        (m(18), 0, None),
        (m(10), 0, None),  # exactly at opening
        (m(21, 30), 0, None),  # the last start that leaves MIN_DURATION
        (m(21, 45), 0, rules.OUTSIDE_HOURS),
        (m(9, 45), 0, rules.OUTSIDE_HOURS),
        (m(22), 0, rules.OUTSIDE_HOURS),
        (m(18, 10), 0, rules.BAD_START),
        (m(18), m(18, 15), rules.TOO_SOON),
        (m(18, 15), m(18, 15), None),
    ],
)
def test_which_starts_are_possible(start, earliest, problem):
    assert rules.start_problem(start, OPEN, earliest) == problem


def test_a_table_reservation_lasts_the_asked_time_but_not_past_closing():
    assert rules.planned_end(m(18), 120, OPEN) == m(20)
    assert rules.planned_end(m(18), 60, OPEN) == m(19)
    assert rules.planned_end(m(20), 120, OPEN) == m(22)  # exactly until closing
    assert rules.planned_end(m(21), 120, OPEN) == m(22)  # cut at closing time
    assert rules.planned_end(m(21, 30), 120, OPEN) == m(22)  # half an hour is still enough
    assert rules.planned_end(m(21, 45), 120, OPEN) is None  # 15 minutes is not


# --- Assigning a table ---------------------------------------------------------------------------------


def test_the_smallest_table_that_seats_the_party_is_chosen():
    assert rules.assign_table(TABLES, [], m(18), m(20), 1)[0] == SMALL
    assert rules.assign_table(TABLES, [], m(18), m(20), 2)[0] == SMALL
    assert rules.assign_table(TABLES, [], m(18), m(20), 3)[0] == MIDDLE
    assert rules.assign_table(TABLES, [], m(18), m(20), 4)[0] == MIDDLE
    assert rules.assign_table(TABLES, [], m(18), m(20), 5)[0] == BIG
    assert rules.assign_table(TABLES, [], m(18), m(20), 6)[0] == BIG


def test_equally_big_tables_are_taken_by_position_then_id():
    first, second = Seating(id="b", seats=4, position=1), Seating(id="a", seats=4, position=2)
    same_position_b, same_position_a = Seating(id="b", seats=4, position=0), Seating(id="a", seats=4, position=0)

    assert rules.assign_table([second, first], [], m(18), m(20), 3)[0] == first
    assert rules.assign_table([same_position_b, same_position_a], [], m(18), m(20), 3)[0] == same_position_a


def test_a_taken_table_makes_way_for_the_next_bigger_one():
    held = [on_table("small", m(18), m(20))]

    assert rules.assign_table(TABLES, held, m(18), m(20), 2)[0] == MIDDLE
    assert rules.assign_table(TABLES, held, m(18), m(20), 3)[0] == MIDDLE


def test_when_every_suitable_table_is_taken_there_is_none():
    held = [on_table("middle", m(18), m(20)), on_table("big", m(18), m(20))]

    assert rules.assign_table(TABLES, held, m(18), m(20), 3) == (None, rules.NO_TABLE)
    assert rules.assign_table(TABLES, held, m(18), m(20), 2)[0] == SMALL  # a small one is still free


def test_a_party_larger_than_every_table_is_told_so_not_that_it_is_full():
    assert rules.assign_table(TABLES, [], m(18), m(20), 7) == (None, rules.PARTY_TOO_LARGE)
    assert rules.assign_table([], [], m(18), m(20), 1) == (None, rules.PARTY_TOO_LARGE)


def test_an_inactive_table_is_never_assigned():
    tables = [Seating(id="small", seats=2, is_active=False), MIDDLE]

    assert rules.assign_table(tables, [], m(18), m(20), 2)[0] == MIDDLE
    assert rules.assign_table([Seating(id="only", seats=4, is_active=False)], [], m(18), m(20), 2) == (None, rules.PARTY_TOO_LARGE)


# The half an hour between two reservations of one table


@pytest.mark.parametrize(
    ("start", "end", "free"),
    [
        (m(20, 30), m(22), True),  # exactly 30 minutes after the other ends
        (m(20, 15), m(22), False),  # 15 minutes after: too close
        (m(20), m(22), False),  # straight after: too close
        (m(18), m(20), False),  # the very same time
        (m(19), m(21), False),  # overlapping
        (m(16), m(17, 30), True),  # ends exactly 30 minutes before the other starts
        (m(16), m(17, 45), False),  # ends 15 minutes before: too close
        (m(16), m(18), False),  # ends exactly when the other starts
        (m(10), m(12), True),  # far away
    ],
)
def test_two_reservations_of_one_table_keep_half_an_hour_between_them(start, end, free):
    held = [on_table("small", m(18), m(20))]
    only_small = [SMALL]

    table, reason = rules.assign_table(only_small, held, start, end, 2)

    assert (table is not None) is free
    assert reason in (None, rules.NO_TABLE)


def test_the_half_hour_is_a_rule_of_one_table_another_table_may_be_used_at_once():
    held = [on_table("small", m(18), m(20))]

    assert rules.assign_table(TABLES, held, m(20), m(22), 2)[0] == MIDDLE  # small is too close, middle is free


# The whole pub and the tables


def test_no_table_can_be_reserved_while_the_whole_pub_is_reserved():
    held = [whole(m(20))]

    assert rules.assign_table(TABLES, held, m(21), m(22), 2) == (None, rules.VENUE_RESERVED)
    assert rules.assign_table(TABLES, held, m(19), m(20, 30), 2) == (None, rules.VENUE_RESERVED)  # overlaps the start
    assert rules.assign_table(TABLES, held, m(20), m(22), 2) == (None, rules.VENUE_RESERVED)


def test_a_table_may_end_exactly_when_the_whole_pub_starts_there_is_no_buffer_between_them():
    held = [whole(m(20))]

    assert rules.assign_table(TABLES, held, m(18), m(20), 2)[0] == SMALL
    assert rules.assign_table(TABLES, held, m(17), m(19, 45), 2)[0] == SMALL


def test_the_whole_pub_cannot_be_reserved_over_a_table_reservation():
    held = [on_table("small", m(18), m(20))]

    assert rules.whole_venue_problem(m(19, 45), OPEN, held) == rules.TABLES_RESERVED
    assert rules.whole_venue_problem(m(18), OPEN, held) == rules.TABLES_RESERVED
    assert rules.whole_venue_problem(m(16), OPEN, held) == rules.TABLES_RESERVED  # it would run over the table's time
    assert rules.whole_venue_problem(m(20), OPEN, held) is None  # from the moment the table is done
    assert rules.whole_venue_problem(m(20, 15), OPEN, held) is None


def test_the_whole_pub_cannot_be_reserved_twice_in_a_day():
    assert rules.whole_venue_problem(m(21), OPEN, [whole(m(20))]) == rules.VENUE_RESERVED
    assert rules.whole_venue_problem(m(10), OPEN, [whole(m(20))]) == rules.VENUE_RESERVED


def test_a_cancelled_or_other_reservation_does_not_count_only_the_held_ones_do():
    assert rules.whole_venue_problem(m(18), OPEN, []) is None


def test_the_whole_pub_can_be_reserved_from_the_end_of_the_last_table_reservation():
    assert rules.whole_venue_from(OPEN, [], 0) == (m(10), None)
    assert rules.whole_venue_from(OPEN, [], m(14, 15)) == (m(14, 15), None)
    held = [on_table("small", m(12), m(14)), on_table("big", m(18), m(20, 10))]
    assert rules.whole_venue_from(OPEN, held, 0) == (m(20, 15), None)  # up to the next step
    assert rules.whole_venue_from(OPEN, held, m(21)) == (m(21), None)  # the later of the two


def test_when_the_whole_pub_cannot_be_reserved_there_is_a_reason():
    assert rules.whole_venue_from(OPEN, [whole(m(20))], 0) == (None, rules.VENUE_RESERVED)
    assert rules.whole_venue_from(OPEN, [on_table("small", m(18), m(21, 50))], 0) == (None, rules.TABLES_RESERVED)
    assert rules.whole_venue_from(OPEN, [], m(21, 45)) == (None, rules.TOO_SOON)


# --- Which starts a guest is offered ---------------------------------------------------------------


def test_a_free_pub_offers_every_step_from_opening_to_half_an_hour_before_closing():
    starts = rules.available_starts(OPEN, [], TABLES, 2, 120, 0)

    assert starts[0] == m(10)
    assert starts[-1] == m(21, 30)
    assert all(later - earlier == 15 for earlier, later in zip(starts, starts[1:]))


def test_starts_in_the_past_are_not_offered():
    starts = rules.available_starts(OPEN, [], TABLES, 2, 120, m(19, 40))

    assert starts[0] == m(19, 45)


def test_a_start_is_offered_while_some_suitable_table_is_free_for_the_whole_stay():
    held = [on_table("small", m(18), m(20)), on_table("middle", m(18), m(20))]  # the two smaller tables, busy

    starts = rules.available_starts(OPEN, held, TABLES, 2, 120, 0)

    assert m(18) in starts  # the big table is free (it seats 6, they are 2)
    assert rules.available_starts(OPEN, [*held, on_table("big", m(18), m(20))], TABLES, 2, 120, 0).count(m(18)) == 0


def test_the_buffer_and_the_length_decide_which_starts_remain():
    only_small = [SMALL]
    held = [on_table("small", m(18), m(20))]

    starts = rules.available_starts(OPEN, held, only_small, 2, 120, 0)

    assert m(15, 30) in starts and m(15, 45) not in starts  # two hours from 15:30 end at 17:30, 30 min before 18:00
    assert m(20, 15) not in starts and m(20, 30) in starts  # 30 minutes after the other one ends
    assert m(16) not in starts and m(17, 15) not in starts  # these would end at or after 18:00


def test_the_asked_duration_changes_what_fits():
    only_small = [SMALL]
    held = [on_table("small", m(18), m(20))]

    short = rules.available_starts(OPEN, held, only_small, 2, 60, 0)
    long = rules.available_starts(OPEN, held, only_small, 2, 240, 0)

    assert m(16, 30) in short and m(16, 30) not in long  # an hour fits before 18:00 minus the buffer, four do not


def test_late_starts_are_cut_at_closing_not_dropped():
    starts = rules.available_starts(OPEN, [], TABLES, 2, 240, 0)

    assert m(21, 30) in starts  # four hours asked, half an hour is left and it is accepted


def test_nothing_is_offered_when_the_whole_pub_is_reserved_and_party_too_large_gives_none():
    assert rules.available_starts(OPEN, [whole(m(10))], TABLES, 2, 120, 0) == []
    assert rules.available_starts(OPEN, [], TABLES, 9, 120, 0) == []


# --- Hours versus reservations -----------------------------------------------------------------------


def test_a_reservation_must_lie_within_the_hours_of_its_day():
    assert rules.fits_hours(m(18), m(20), OPEN)
    assert rules.fits_hours(m(10), m(22), OPEN)
    assert not rules.fits_hours(m(9, 45), m(12), OPEN)
    assert not rules.fits_hours(m(21), m(22, 15), OPEN)
    assert not rules.fits_hours(m(18), m(20), None)  # a closed day holds nothing


def test_minutes_and_times_convert_both_ways():
    assert rules.minutes(time(18, 45)) == m(18, 45)
    assert rules.at(m(18, 45)) == time(18, 45)
    assert rules.at(0) == time(0, 0)
    with pytest.raises(ValueError):
        rules.at(24 * 60)
    assert rules.round_up(m(10, 1)) == m(10, 15)
    assert rules.round_up(m(10, 15)) == m(10, 15)
