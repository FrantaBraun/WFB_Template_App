# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""backend/seed_demo.py - the made-up data of the demo pub: that it fills an empty
database with a coherent set (what the public pages then show), that running it
again changes only what it should, and that it never touches reservations or an
administrator's own tables and hours."""

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import func, select

import seed_demo
from app.modules.pub_menu import service as menu_service
from app.modules.pub_menu.config import load_config
from app.modules.pub_menu.models import ALLERGEN_NUMBERS, DailyMenu, DailyMenuItem, MenuCategory, MenuItem, MenuPrice, MenuSettings
from app.modules.table_reservations.models import DiningTable, OpeningHours, Reservation
from tests.menu_support import MONDAY, TODAY, clear_tables as clear_menu_tables
from tests.reservation_support import clear_tables as clear_reservation_tables


@pytest.fixture(autouse=True)
async def _empty(db_session):
    await clear_reservation_tables(db_session)
    await clear_menu_tables(db_session)
    await db_session.commit()


async def count(db, model, *conditions) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*conditions))


async def test_an_empty_database_gets_tables_hours_a_menu_and_two_weeks_of_lunches(db_session):
    made = await seed_demo.seed(db_session, TODAY)

    assert made == {"tables": 8, "hours": 7, "categories": 6, "items": 28, "daily_menus": 10}
    assert await count(db_session, DiningTable) == 8 and await count(db_session, OpeningHours) == 7
    assert await count(db_session, MenuCategory) == 6 and await count(db_session, MenuItem) == 28
    seats = sorted((await db_session.scalars(select(DiningTable.seats))).all())
    assert seats == [2, 2, 2, 4, 4, 6, 6, 8]  # parties up to eight sit at a table, bigger ones take the whole inn


async def test_the_pub_is_open_every_day_and_closes_later_at_the_weekend(db_session):
    await seed_demo.seed(db_session, TODAY)

    rows = {row.weekday: row for row in (await db_session.scalars(select(OpeningHours))).all()}

    assert sorted(rows) == list(range(7)) and not any(row.is_closed for row in rows.values())
    assert [rows[d].closes for d in range(7)] == [time(22)] * 4 + [time(23)] * 3
    assert all(row.opens == time(11) for row in rows.values())


async def test_the_standing_menu_has_eight_draught_beers_each_with_a_price_and_valid_allergens(db_session):
    await seed_demo.seed(db_session, TODAY)

    categories = {c.name: c for c in (await db_session.scalars(select(MenuCategory))).all()}
    beers = (await db_session.scalars(select(MenuItem).where(MenuItem.category_id == categories["Výčepní piva"].id))).all()

    assert len(beers) == 8 and categories["Výčepní piva"].kind == "drink"
    for item in (await db_session.scalars(select(MenuItem))).all():
        assert item.is_active and item.is_available
        assert set(item.allergens) <= set(ALLERGEN_NUMBERS)
        assert await count(db_session, MenuPrice, MenuPrice.item_id == item.id) >= 1, item.name
    assert all(price.price >= 0 for price in (await db_session.scalars(select(MenuPrice))).all())


async def test_the_lunch_menus_are_for_the_working_days_of_this_week_and_the_next_and_published(db_session):
    await seed_demo.seed(db_session, TODAY)

    days = sorted((await db_session.scalars(select(DailyMenu))).all(), key=lambda menu: menu.day)

    assert [menu.day for menu in days] == [MONDAY + timedelta(weeks=w, days=d) for w in range(2) for d in range(5)]
    assert all(menu.is_published for menu in days)
    for menu in days:
        kinds = [item.kind for item in (await db_session.scalars(select(DailyMenuItem).where(DailyMenuItem.day == menu.day).order_by(DailyMenuItem.position))).all()]
        assert kinds[0] == "soup" and kinds.count("main") == 3, menu.day


async def test_what_the_visitors_get_is_filled_from_the_first_request(db_session):
    await seed_demo.seed(db_session, TODAY)
    config = load_config()

    offer = await menu_service.public_offer(db_session, config)
    week = await menu_service.public_week(db_session, TODAY, TODAY, config)
    next_week = await menu_service.public_week(db_session, TODAY + timedelta(weeks=1), TODAY, config)

    assert [c.name for c in offer.categories][:2] == ["Studená kuchyně", "Polévky"]
    assert offer.note and week.note
    assert [len(day.items) > 0 for day in week.days] == [True] * 5 + [False] * 2  # no lunch at the weekend
    assert [len(day.items) > 0 for day in next_week.days] == [True] * 5 + [False] * 2
    assert week.days[0].items[0].kind == "soup" and week.days[0].items[0].price is None


async def test_the_second_week_serves_the_same_dishes_in_another_order(db_session):
    await seed_demo.seed(db_session, TODAY)
    config = load_config()

    first = await menu_service.public_week(db_session, TODAY, TODAY, config)
    second = await menu_service.public_week(db_session, TODAY + timedelta(weeks=1), TODAY, config)

    assert first.days[0].items[0].name != second.days[0].items[0].name
    assert {d.items[0].name for d in first.days[:5]} == {d.items[0].name for d in second.days[:5]}


async def test_running_it_again_creates_no_second_set_of_tables_hours_or_menu(db_session):
    await seed_demo.seed(db_session, TODAY)

    again = await seed_demo.seed(db_session, TODAY)

    assert (again["tables"], again["hours"], again["categories"], again["items"]) == (0, 0, 0, 0)
    assert again["daily_menus"] == 10  # the lunch menus are written afresh
    assert await count(db_session, DiningTable) == 8 and await count(db_session, MenuCategory) == 6
    assert await count(db_session, DailyMenu) == 10


async def test_the_lunch_menus_are_replaced_not_added_to(db_session):
    await seed_demo.seed(db_session, TODAY)
    before = await count(db_session, DailyMenuItem)

    await seed_demo.seed(db_session, TODAY)

    assert await count(db_session, DailyMenuItem) == before


async def test_replace_makes_the_standing_menu_and_notes_again_but_keeps_the_pubs_own_setup(db_session):
    await seed_demo.seed(db_session, TODAY)
    own_table = DiningTable(name="Own table", seats=3, position=99)
    db_session.add(own_table)
    category = (await db_session.scalars(select(MenuCategory).limit(1))).first()
    category.name = "Renamed by the pub"
    (await db_session.get(MenuSettings, 1)).offer_note = "Mine"
    await db_session.flush()

    again = await seed_demo.seed(db_session, TODAY, replace=True)

    assert again["categories"] == 6 and again["tables"] == 0
    assert "Renamed by the pub" not in [c.name for c in (await db_session.scalars(select(MenuCategory))).all()]
    assert (await db_session.get(MenuSettings, 1)).offer_note == seed_demo.OFFER_NOTE
    assert await count(db_session, DiningTable, DiningTable.name == "Own table") == 1  # tables are never replaced


async def test_it_leaves_notes_and_setup_the_pub_has_already_written(db_session):
    db_session.add(MenuSettings(id=1, daily_note="Our own note", offer_note=""))
    db_session.add(DiningTable(name="Only table", seats=2, position=0))
    db_session.add(OpeningHours(weekday=0, is_closed=True))
    await db_session.flush()

    made = await seed_demo.seed(db_session, TODAY)

    assert (made["tables"], made["hours"]) == (0, 0)
    assert (await db_session.get(MenuSettings, 1)).daily_note == "Our own note"
    assert await count(db_session, DiningTable) == 1 and await count(db_session, OpeningHours) == 1


async def test_it_never_touches_reservations(db_session):
    await seed_demo.seed(db_session, TODAY)
    table = (await db_session.scalars(select(DiningTable).limit(1))).first()
    db_session.add(
        Reservation(
            kind="table",
            table_id=table.id,
            day=date(2030, 1, 1),
            start_time=time(18),
            end_time=time(20),
            party_size=2,
            name="Guest",
            email="guest@example.com",
            consent_at=datetime(2030, 1, 1),
            language="cs",
        )
    )
    await db_session.flush()

    await seed_demo.seed(db_session, TODAY, replace=True)

    assert await count(db_session, Reservation) == 1
