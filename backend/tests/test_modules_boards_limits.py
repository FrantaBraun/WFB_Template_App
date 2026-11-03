# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The early warning about the sales limits that change a provider's tax
position (app/modules/boards/limits.py): the two Czech limits for becoming a
VAT payer (counted per calendar year since 2025) and the EU limit for sales
to consumers in other member states per calendar year, measured from the
confirmed boost payments.

The figures use a fixed `now` in 2031, so no payment that already exists in a
development database can fall inside the periods measured."""

import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.database import get_db
from app.models.user import User
from app.modules.boards import limits
from app.modules.boards.config import BoardsConfig, ProviderConfig, InvoicingConfig, TaxLimitsConfig, get_config, load_config
from app.modules.boards.router import router as boards_router
from app.modules.stripe_payment_gate.models import StripePayment

BASE = "/api/modules/boards"
PRAGUE = ZoneInfo("Europe/Prague")
NOW = datetime(2031, 3, 15, 10, 0, tzinfo=timezone.utc)


async def _pay(db_session, *, paid_at, usd=10, country=None, purpose="post_boost", status="paid", currency="usd"):
    db_session.add(
        StripePayment(
            id=uuid.uuid4(),
            user_id=None,
            purpose=purpose,
            amount=usd * 100,
            currency=currency,
            description="test",
            extra={"customer_country": country} if country else {},
            status=status,
            paid_at=paid_at,
        )
    )
    await db_session.commit()


# --- The pure parts --------------------------------------------------------------


def test_a_level_starts_at_the_warning_share_and_the_limit_itself_is_exceeded():
    assert [limits.level_for(p, 80) for p in (0, 79.9, 80, 99.9, 100, 250)] == ["ok", "ok", "warn", "warn", "exceeded", "exceeded"]


def test_the_eu_list_is_the_other_26_member_states():
    assert len(limits.EU_OTHER_COUNTRIES) == 26
    assert {"DE", "SK", "AT", "GR", "IE", "PL"} <= limits.EU_OTHER_COUNTRIES  # Greece is GR in ISO, not the VAT prefix EL
    assert not {"CZ", "GB", "US", "CH", "NO", "EL"} & limits.EU_OTHER_COUNTRIES


def test_the_committed_limits_are_the_legal_ones():
    committed = load_config().tax_limits
    assert committed.vat_registration_czk == 2_000_000  # payer from 1 January of the next year
    assert committed.vat_immediate_czk == 2_536_500  # 100 000 EUR: payer from the next day
    assert committed.oss_threshold_eur == 10_000
    assert committed == TaxLimitsConfig()  # boards.json says what the defaults say


@pytest.mark.parametrize("fields", [{"czk_per_usd": 0}, {"eur_per_usd": -1}, {"warn_percent": 0}, {"warn_percent": 101}, {"vat_registration_czk": 0}, {"vat_immediate_czk": 0},
                                    {"vat_registration_czk": 3_000_000},  # above the default immediate limit
                                    {"vat_immediate_czk": 2_000_000},  # not above the first limit
                                    {"unknown": 1}])
def test_a_nonsensical_limit_is_refused(fields):
    with pytest.raises(ValidationError):
        TaxLimitsConfig(**fields)


# --- The Czech turnover ----------------------------------------------------------


async def test_the_turnover_is_counted_per_calendar_year_of_confirmed_dollar_boost_payments(db_session):
    await _pay(db_session, paid_at=datetime(2031, 1, 1, 0, 30, tzinfo=PRAGUE), usd=100)  # January 1st in Prague, December 31st in UTC
    await _pay(db_session, paid_at=datetime(2031, 3, 15, 9, 0, tzinfo=timezone.utc), usd=50)
    await _pay(db_session, paid_at=datetime(2030, 12, 31, 23, 30, tzinfo=PRAGUE), usd=200)  # last year's - not this year's
    await _pay(db_session, paid_at=datetime(2029, 6, 1, tzinfo=timezone.utc), usd=1000)  # two years back: not shown
    await _pay(db_session, paid_at=datetime(2031, 1, 5, tzinfo=timezone.utc), usd=1000, status="pending")
    await _pay(db_session, paid_at=datetime(2031, 1, 5, tzinfo=timezone.utc), usd=1000, purpose="something_else")
    await _pay(db_session, paid_at=datetime(2031, 1, 5, tzinfo=timezone.utc), usd=1000, currency="eur")

    overview = await limits.build_overview(db_session, BoardsConfig(), NOW)

    vat = overview.vat_registration
    assert (vat.limit_czk, vat.immediate_limit_czk) == (2_000_000, 2_536_500)
    previous, current = vat.years
    assert (previous.year, previous.payments, previous.paid_usd_cents) == (2030, 1, 20000)
    assert (current.year, current.payments, current.paid_usd_cents) == (2031, 2, 15000)
    assert current.estimated_czk == 3600  # 150 USD at the default 24 CZK
    assert (current.percent, current.level) == (0.2, "ok")
    assert (current.immediate_percent, current.immediate_level) == (0.1, "ok")
    assert overview.vat_payer is False


async def test_the_turnover_is_judged_against_both_limits_and_each_warns_and_then_says_exceeded(db_session):
    config = BoardsConfig(
        tax_limits=TaxLimitsConfig(vat_registration_czk=10_000, vat_immediate_czk=20_000, czk_per_usd=20.0, warn_percent=50)
    )

    async def this_year():
        return (await limits.build_overview(db_session, config, NOW)).vat_registration.years[1]

    await _pay(db_session, paid_at=datetime(2031, 3, 1, tzinfo=timezone.utc), usd=300)  # 6 000 CZK
    year = await this_year()
    assert (year.percent, year.level, year.immediate_percent, year.immediate_level) == (60.0, "warn", 30.0, "ok")

    await _pay(db_session, paid_at=datetime(2031, 3, 2, tzinfo=timezone.utc), usd=200)  # 10 000 CZK: the first limit
    year = await this_year()
    assert (year.percent, year.level, year.immediate_percent, year.immediate_level) == (100.0, "exceeded", 50.0, "warn")

    await _pay(db_session, paid_at=datetime(2031, 3, 3, tzinfo=timezone.utc), usd=500)  # 20 000 CZK: the second one too
    year = await this_year()
    assert (year.estimated_czk, year.immediate_percent, year.immediate_level) == (20_000, 100.0, "exceeded")


async def test_last_years_turnover_does_not_count_toward_this_years(db_session):
    config = BoardsConfig(tax_limits=TaxLimitsConfig(vat_registration_czk=10_000, vat_immediate_czk=20_000, czk_per_usd=20.0))
    await _pay(db_session, paid_at=datetime(2030, 11, 1, tzinfo=timezone.utc), usd=600)  # 12 000 CZK: over the first limit

    previous, current = (await limits.build_overview(db_session, config, NOW)).vat_registration.years

    assert (previous.level, current.payments, current.level) == ("exceeded", 0, "ok")


async def test_an_empty_database_is_all_zero_and_ok(db_session):
    overview = await limits.build_overview(db_session, BoardsConfig(), NOW)

    assert [(y.year, y.payments, y.level, y.immediate_level) for y in overview.vat_registration.years] == [
        (2030, 0, "ok", "ok"),
        (2031, 0, "ok", "ok"),
    ]
    assert [(y.year, y.eu_payments, y.level, y.countries) for y in overview.oss_years] == [(2030, 0, "ok", []), (2031, 0, "ok", [])]


# --- Sales to the other EU member states ------------------------------------------


async def test_sales_to_other_eu_countries_are_summed_per_calendar_year_in_the_providers_time_zone(db_session):
    config = BoardsConfig(tax_limits=TaxLimitsConfig(eur_per_usd=0.5))
    for paid_at, usd, country in [
        (datetime(2031, 2, 1, tzinfo=timezone.utc), 100, "DE"),
        (datetime(2031, 2, 2, tzinfo=timezone.utc), 50, "DE"),
        (datetime(2031, 3, 1, tzinfo=timezone.utc), 20, "SK"),
        (datetime(2031, 3, 2, tzinfo=timezone.utc), 500, "CZ"),  # home market: not a sale to another member state
        (datetime(2031, 3, 3, tzinfo=timezone.utc), 300, "US"),  # outside the EU
        (datetime(2031, 3, 4, tzinfo=timezone.utc), 10, None),  # the country was never reported
        (datetime(2030, 12, 31, 23, 30, tzinfo=timezone.utc), 8, "DE"),  # already January 1st in Prague
        (datetime(2030, 6, 1, tzinfo=timezone.utc), 200, "FR"),
        (datetime(2029, 6, 1, tzinfo=timezone.utc), 999, "FR"),  # two years back: not shown
    ]:
        await _pay(db_session, paid_at=paid_at, usd=usd, country=country)

    previous, current = (await limits.build_overview(db_session, config, NOW)).oss_years

    assert (previous.year, previous.eu_payments, previous.eu_paid_usd_cents) == (2030, 1, 20000)
    assert (current.year, current.eu_payments, current.eu_paid_usd_cents) == (2031, 4, 17800)
    assert (current.estimated_eur, current.limit_eur, current.percent, current.level) == (89, 10_000, 0.9, "ok")
    assert current.unknown_country_payments == 1
    # every country paid from, biggest first; only the member states other than Czechia are "eu"
    assert [(c.country, c.eu, c.paid_usd_cents) for c in current.countries] == [
        ("CZ", False, 50000),
        ("US", False, 30000),
        ("DE", True, 15800),
        ("SK", True, 2000),
        (None, False, 1000),
    ]


async def test_the_eu_limit_warns_and_says_exceeded_per_year(db_session):
    config = BoardsConfig(tax_limits=TaxLimitsConfig(oss_threshold_eur=100, eur_per_usd=1.0, warn_percent=90))
    await _pay(db_session, paid_at=datetime(2030, 5, 1, tzinfo=timezone.utc), usd=95, country="FR")
    await _pay(db_session, paid_at=datetime(2031, 2, 1, tzinfo=timezone.utc), usd=100, country="DE")

    previous, current = (await limits.build_overview(db_session, config, NOW)).oss_years

    assert (previous.percent, previous.level) == (95.0, "warn")
    assert (current.percent, current.level) == (100.0, "exceeded")


async def test_a_provider_that_is_a_vat_payer_is_reported_as_one(db_session):
    config = BoardsConfig(invoicing=InvoicingConfig(provider=ProviderConfig(vat_payer=True)))
    assert (await limits.build_overview(db_session, config, NOW)).vat_payer is True


# --- The administrators' endpoint -------------------------------------------------

_app = FastAPI()
_app.include_router(boards_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_config] = lambda: BoardsConfig()
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
def make_person(db_session, make_access_token):
    async def _make(**fields):
        sub = uuid.uuid4()
        db_session.add(User(auth_sub=sub, **fields))
        await db_session.commit()
        return {"Authorization": f"Bearer {make_access_token(sub=str(sub))}"}

    return _make


async def test_only_administrators_may_see_the_limits(client, make_person):
    ordinary = await make_person()

    anonymous = await client.get(f"{BASE}/manage/payments-overview")
    refused = await client.get(f"{BASE}/manage/payments-overview", headers=ordinary)

    assert (anonymous.status_code, refused.status_code) == (401, 403)


async def test_an_administrator_gets_the_overview_with_the_figures_it_is_measured_by(client, make_person, db_session):
    admin = await make_person(is_admin=True)
    await _pay(db_session, paid_at=datetime.now(timezone.utc), usd=25, country="DE")

    resp = await client.get(f"{BASE}/manage/payments-overview", headers=admin)

    assert resp.status_code == 200
    body = resp.json()
    assert body["vat_payer"] is False
    assert (body["warn_percent"], body["czk_per_usd"], body["eur_per_usd"]) == (80, 24.0, 0.95)
    assert (body["vat_registration"]["limit_czk"], body["vat_registration"]["immediate_limit_czk"]) == (2_000_000, 2_536_500)
    vat_years = body["vat_registration"]["years"]
    assert len(vat_years) == 2 and vat_years[0]["year"] + 1 == vat_years[1]["year"]
    assert vat_years[1]["payments"] >= 1
    years = body["oss_years"]
    assert len(years) == 2 and years[0]["year"] + 1 == years[1]["year"] and years[0]["limit_eur"] == 10_000
    assert any(c["country"] == "DE" and c["eu"] for c in years[1]["countries"])
