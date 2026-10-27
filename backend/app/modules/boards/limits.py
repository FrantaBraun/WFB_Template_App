# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Watching the sales limits that change a provider's tax position.

A provider that is not a VAT payer adds no VAT to a price. That stays true
only while two limits hold, and nothing else in the application would notice
when one is passed:

- **Czech turnover** under the limit for registering as a VAT payer
  (2 000 000 CZK over twelve calendar months). Passing it means registering
  within days of the month's end - and this application cannot issue the tax
  documents a payer needs (see documents.py).
- **Sales to consumers in the other EU member states** of electronic services
  (placing a post on a board is one) under 10 000 EUR in the current and the
  previous calendar year. Above it the VAT of the customer's country applies
  (the OSS scheme).

Both are measured from the confirmed boost payments (`build_overview`), for
the administrators' page (GET /manage/payments-overview). It is an early
warning, not bookkeeping, and every simplification errs toward warning early:

- every payment counts toward the Czech turnover - the real rule counts only
  what is taxed in the Czech Republic, but also the person's *other*
  activities, which this application cannot see;
- every payment from another EU member state counts as a sale to a consumer
  (a business customer would not, but nobody is asked);
- dollars are converted at the rates in `tax_limits` (config.py), set a little
  high on purpose; the tax base itself uses the Czech National Bank's rate;
- a payment whose country was never reported - made before it was kept (the
  payment gateway's `customer_country`) - is in the totals but in no country,
  and is counted separately so an under-count shows.

Months and years are the provider's (`invoicing.timezone`), not the server's.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boards import payments
from app.modules.boards.config import BoardsConfig
from app.modules.boards.schemas import (
    CountryTotalOut,
    LimitLevel,
    OssYearOut,
    PaymentsOverviewOut,
    VatRegistrationOut,
)
from app.modules.stripe_payment_gate.models import STATUS_PAID, StripePayment

# The member states of the EU other than the Czech Republic, as ISO 3166-1
# alpha-2 codes - what Stripe reports (so Greece is GR here, not the VAT prefix EL).
EU_OTHER_COUNTRIES = frozenset(
    "AT BE BG HR CY DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
)


def level_for(percent: float, warn_percent: int) -> LimitLevel:
    """"exceeded" from the limit itself, "warn" from `warn_percent` of it."""
    if percent >= 100:
        return "exceeded"
    if percent >= warn_percent:
        return "warn"
    return "ok"


def window_start(today: date) -> date:
    """The first day of the twelve calendar months that end with today's month."""
    year, month = today.year, today.month - 11
    if month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


async def build_overview(db: AsyncSession, config: BoardsConfig, now: datetime | None = None) -> PaymentsOverviewOut:
    limits = config.tax_limits
    tz = config.invoicing.timezone
    zone = ZoneInfo(tz)
    moment = now or datetime.now(timezone.utc)
    today = moment.astimezone(zone).date()
    window_from = window_start(today)

    confirmed = and_(
        StripePayment.purpose == payments.POST_BOOST,
        StripePayment.status == STATUS_PAID,
        StripePayment.currency == payments.CURRENCY,
        StripePayment.paid_at.is_not(None),
    )

    window = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(StripePayment.amount), 0)).where(
                confirmed,
                StripePayment.paid_at >= datetime(window_from.year, window_from.month, 1, tzinfo=zone),
            )
        )
    ).one()
    window_payments, window_cents = int(window[0]), int(window[1])
    czk = window_cents / 100 * limits.czk_per_usd
    czk_percent = czk / limits.vat_registration_czk * 100

    year = extract("year", func.timezone(tz, StripePayment.paid_at))
    country = StripePayment.extra["customer_country"].as_string()
    rows = (
        await db.execute(
            select(year.label("year"), country.label("country"), func.count(), func.sum(StripePayment.amount))
            .where(confirmed, StripePayment.paid_at >= datetime(today.year - 1, 1, 1, tzinfo=zone))
            .group_by("year", "country")
        )
    ).all()

    countries: dict[int, list[CountryTotalOut]] = {today.year - 1: [], today.year: []}
    for row_year, row_country, count, cents in rows:
        if int(row_year) in countries:
            countries[int(row_year)].append(
                CountryTotalOut(
                    country=row_country,
                    eu=row_country in EU_OTHER_COUNTRIES,
                    payments=int(count),
                    paid_usd_cents=int(cents),
                )
            )

    oss_years = []
    for oss_year, entries in countries.items():
        entries.sort(key=lambda entry: (-entry.paid_usd_cents, entry.country or ""))
        eu_cents = sum(entry.paid_usd_cents for entry in entries if entry.eu)
        eur = eu_cents / 100 * limits.eur_per_usd
        eur_percent = eur / limits.oss_threshold_eur * 100
        oss_years.append(
            OssYearOut(
                year=oss_year,
                eu_payments=sum(entry.payments for entry in entries if entry.eu),
                eu_paid_usd_cents=eu_cents,
                estimated_eur=round(eur),
                limit_eur=limits.oss_threshold_eur,
                percent=round(eur_percent, 1),
                level=level_for(eur_percent, limits.warn_percent),
                unknown_country_payments=sum(entry.payments for entry in entries if entry.country is None),
                countries=entries,
            )
        )

    return PaymentsOverviewOut(
        generated_at=moment,
        vat_payer=config.invoicing.provider.vat_payer,
        warn_percent=limits.warn_percent,
        czk_per_usd=limits.czk_per_usd,
        eur_per_usd=limits.eur_per_usd,
        vat_registration=VatRegistrationOut(
            window_from=window_from,
            window_to=today,
            payments=window_payments,
            paid_usd_cents=window_cents,
            estimated_czk=round(czk),
            limit_czk=limits.vat_registration_czk,
            percent=round(czk_percent, 1),
            level=level_for(czk_percent, limits.warn_percent),
        ),
        oss_years=oss_years,
    )
