# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Fills the database of the demo pub (Hostinec U Zlatého chmele) with made-up
data, so a fresh installation has something to show: the tables, the opening
hours, a standing menu of a Czech inn with eight draught beers, the lunch menu of
this week and the next, and the two notes under the menus.

Run it once from backend/ after the migrations:

    .venv/Scripts/python.exe seed_demo.py            (what exists is left alone)
    .venv/Scripts/python.exe seed_demo.py --replace  (the standing menu and notes are made again)

It never touches reservations, and never replaces tables or opening hours that
already exist - an administrator's own setup is not overwritten. The lunch menus of
the two weeks are always written afresh (they are the part that goes stale)."""

import asyncio
import sys
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pub_menu.models import DailyMenu, DailyMenuItem, MenuCategory, MenuItem, MenuPrice, MenuSettings
from app.modules.table_reservations.models import DiningTable, OpeningHours

TABLES = [
    ("U okna 1", 2),
    ("U okna 2", 2),
    ("U pípy", 2),
    ("U kamen", 4),
    ("Zadní stůl", 4),
    ("Rodinný stůl", 6),
    ("Kulatý stůl", 6),
    ("Štamgast", 8),
]

# Monday to Thursday 11-22, Friday to Sunday 11-23 (Monday = 0).
HOURS = {weekday: (time(11), time(22) if weekday < 4 else time(23)) for weekday in range(7)}

DAILY_NOTE = "Polední menu podáváme Po–Pá 11:00–14:00. Polévka je v ceně hlavního jídla."
OFFER_NOTE = "Informace o alergenech Vám rádi sdělíme u obsluhy. Ceny jsou včetně DPH."

# (category, kind, description, [(name, description, allergens, [(portion, price)])])
MENU = [
    (
        "Studená kuchyně",
        "food",
        "K pivu i na začátek",
        [
            ("Utopenec", "Špekáček v octovém nálevu s cibulí", [1, 10, 12], [("1 ks", 59)]),
            ("Nakládaný hermelín", "S cibulí, chilli a pečivem", [1, 7], [("", 89)]),
            ("Škvarková pomazánka", "Domácí, s cibulkou a chlebem", [1, 7], [("", 79)]),
            ("Tlačenka s cibulí", "Octová, s chlebem", [1, 10, 12], [("", 85)]),
            ("Pivní sýr", "S cibulí a hořčicí", [1, 7, 10], [("", 95)]),
        ],
    ),
    (
        "Polévky",
        "food",
        "",
        [
            ("Kulajda", "S houbami, vejcem a koprem", [1, 3, 7, 9], [("0,33 l", 79)]),
            ("Česnečka se sýrem", "S opečeným chlebem", [1, 7], [("0,33 l", 65)]),
            ("Hovězí vývar", "S masem a nudlemi", [1, 3, 9], [("0,33 l", 69)]),
        ],
    ),
    (
        "Hlavní jídla",
        "food",
        "Staročeská kuchyně",
        [
            ("Svíčková na smetaně", "Houskový knedlík, brusinky, šlehačka", [1, 3, 7, 9, 10], [("150 g", 189), ("250 g", 239)]),
            ("Vepřo knedlo zelo", "Pečené vepřové, bramborovo-houskový knedlík, dušené zelí", [1, 3, 7], [("200 g", 169)]),
            ("Hovězí guláš", "Houskový knedlík, cibule", [1, 3, 7, 9], [("200 g", 179)]),
            ("Smažený sýr", "Hranolky, tatarská omáčka", [1, 3, 7, 10], [("2 ks", 159)]),
            ("Kachna pečená", "Červené a bílé zelí, lokše", [1, 3, 7], [("1/4 ks", 249)]),
            ("Vepřový řízek", "Bramborový salát", [1, 3, 7, 9, 10], [("150 g", 175)]),
        ],
    ),
    (
        "Sladké",
        "food",
        "",
        [
            ("Palačinky s povidly", "Se šlehačkou a mletým perníkem", [1, 3, 7], [("2 ks", 85)]),
            ("Jablečný závin", "Teplý, se šlehačkou", [1, 3, 7], [("", 79)]),
        ],
    ),
    (
        "Výčepní piva",
        "drink",
        "Čepujeme z tanků, vždy čerstvé a vychlazené",
        [
            ("Plzeň 12°", "Světlý ležák", [1], [("0,3 l", 42), ("0,5 l", 58)]),
            ("Kozel 11°", "Světlý ležák", [1], [("0,3 l", 36), ("0,5 l", 49)]),
            ("Kozel Černý 10°", "Tmavý ležák", [1], [("0,3 l", 36), ("0,5 l", 49)]),
            ("Budvar 12°", "Světlý ležák", [1], [("0,3 l", 40), ("0,5 l", 55)]),
            ("Bernard Jantarový 12°", "Polotmavý ležák", [1], [("0,3 l", 40), ("0,5 l", 55)]),
            ("Svijany Kněžna 11°", "Polotmavý ležák z Českého ráje", [1], [("0,5 l", 59)]),
            ("Sezónní kohout I", "Střídáme podle sezóny", [1], [("0,3 l", 46), ("0,5 l", 64)]),
            ("Sezónní kohout II", "Střídáme podle sezóny", [1], [("0,3 l", 46), ("0,5 l", 64)]),
        ],
    ),
    (
        "Nealkoholické nápoje",
        "drink",
        "",
        [
            ("Domácí limonáda", "Citron, máta", [], [("0,4 l", 49)]),
            ("Kofola", "Čepovaná", [], [("0,3 l", 39), ("0,5 l", 52)]),
            ("Minerální voda", "Perlivá nebo jemně perlivá", [], [("0,33 l", 39)]),
            ("Káva", "Espresso nebo filtrovaná", [7], [("", 55)]),
        ],
    ),
]

# One lunch menu per weekday, Monday to Friday; the second week repeats them in another order.
# (soup, [(main, portion, price, description, allergens)], dessert or None)
DAILY = [
    (("Kulajda", [1, 3, 7, 9]), [("Kuřecí řízek, bramborový salát", "150 g", 149, "", [1, 3, 7, 9, 10]), ("Hovězí guláš, houskový knedlík", "200 g", 159, "", [1, 3, 7, 9]), ("Rizoto se zeleninou a sýrem", "300 g", 139, "Vegetariánské", [7, 9])], None),
    (("Zelňačka", [1]), [("Pečená kachní stehna, červené zelí, lokše", "1/2 ks", 189, "", [1, 3]), ("Vepřová pečeně, houskový knedlík, zelí", "150 g", 155, "", [1, 3, 7]), ("Špagety s rajčatovou omáčkou", "300 g", 129, "Vegetariánské", [1, 3])], "Palačinka s marmeládou"),
    (("Dršťková polévka", [1, 9]), [("Svíčková na smetaně, knedlík", "150 g", 169, "", [1, 3, 7, 9, 10]), ("Smažený sýr, hranolky, tatarka", "2 ks", 145, "", [1, 3, 7, 10]), ("Kuře na paprice, těstoviny", "200 g", 149, "", [1, 3, 7])], None),
    (("Bramboračka", [1, 7, 9]), [("Vepřo knedlo zelo", "200 g", 155, "", [1, 3, 7]), ("Pečený hřbet s bylinkovým máslem, brambory", "180 g", 179, "", [7]), ("Pečená zelenina s kozím sýrem", "300 g", 139, "Vegetariánské", [7])], "Jablečný závin"),
    (("Hovězí vývar s nudlemi", [1, 3, 9]), [("Smažená ryba, bramborový salát", "180 g", 165, "", [1, 3, 4, 7, 10]), ("Špikovaná pečeně na smetaně", "150 g", 175, "", [1, 3, 7, 9]), ("Kroketky se špenátem", "250 g", 135, "Vegetariánské", [1, 3, 7])], None),
]


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def seed(db: AsyncSession, today: date, *, replace: bool = False) -> dict[str, int]:
    """Writes the demo data (flushes, does not commit) and returns how much of
    each kind it created: tables, hours, categories, items, daily_menus."""
    made = {"tables": 0, "hours": 0, "categories": 0, "items": 0, "daily_menus": 0}

    if not await db.scalar(select(func.count()).select_from(DiningTable)):
        db.add_all(DiningTable(name=name, seats=seats, position=position) for position, (name, seats) in enumerate(TABLES))
        made["tables"] = len(TABLES)

    if not await db.scalar(select(func.count()).select_from(OpeningHours)):
        db.add_all(OpeningHours(weekday=weekday, is_closed=False, opens=opens, closes=closes) for weekday, (opens, closes) in HOURS.items())
        made["hours"] = len(HOURS)

    if replace:
        await db.execute(delete(MenuCategory))  # the items and their prices go with them
    if not await db.scalar(select(func.count()).select_from(MenuCategory)):
        for category_position, (name, kind, description, items) in enumerate(MENU):
            category = MenuCategory(name=name, kind=kind, description=description, position=category_position)
            db.add(category)
            await db.flush()
            for item_position, (item_name, item_description, allergens, prices) in enumerate(items):
                item = MenuItem(category_id=category.id, name=item_name, description=item_description, allergens=allergens, position=item_position)
                db.add(item)
                await db.flush()
                db.add_all(MenuPrice(item_id=item.id, label=label, price=Decimal(price), position=price_position) for price_position, (label, price) in enumerate(prices))
                made["items"] += 1
            made["categories"] += 1

    settings = await db.get(MenuSettings, 1)
    if settings is None:
        settings = MenuSettings(id=1, daily_note="", offer_note="")
        db.add(settings)
    if replace or not (settings.daily_note or settings.offer_note):
        settings.daily_note, settings.offer_note = DAILY_NOTE, OFFER_NOTE

    first_monday = monday_of(today)
    for week in range(2):
        for offset, (soup, mains, dessert) in enumerate(DAILY[week:] + DAILY[:week]):
            day = first_monday + timedelta(weeks=week, days=offset)
            await db.execute(delete(DailyMenu).where(DailyMenu.day == day))
            db.add(DailyMenu(day=day, is_published=True))
            await db.flush()
            position = 0
            db.add(DailyMenuItem(day=day, kind="soup", name=soup[0], amount="0,33 l", allergens=soup[1], position=position))
            for name, amount, price, description, allergens in mains:
                position += 1
                db.add(DailyMenuItem(day=day, kind="main", name=name, amount=amount, description=description, allergens=allergens, price=Decimal(price), position=position))
            if dessert:
                position += 1
                db.add(DailyMenuItem(day=day, kind="dessert", name=dessert, allergens=[1, 3, 7], price=Decimal(59), position=position))
            made["daily_menus"] += 1

    await db.flush()
    return made


async def main(replace: bool) -> None:
    from app.database import AsyncSessionLocal, engine
    from app.modules.pub_menu.deps import local_today

    async with AsyncSessionLocal() as db:
        made = await seed(db, local_today(), replace=replace)
        await db.commit()
    await engine.dispose()
    print("Created:", ", ".join(f"{count} {kind}" for kind, count in made.items()))


if __name__ == "__main__":
    asyncio.run(main("--replace" in sys.argv[1:]))
