# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The payment document and the confirmation email, as HTML.

Everything is rendered from a *snapshot* (build_snapshot) taken when the
payment was confirmed and stored with the receipt, never from live data, so a
document reads the same years later. Every value that came from outside -
the post's title, the payer's email, the issuer's details - goes through
html.escape. There is no PDF: no PDF library is installed, and an electronic
document may be any form the recipient can read and keep; the same HTML is
the body of the email and what the app shows under "My receipts".

What kind of document this is depends on the issuer. A provider that is not a
VAT payer issues a **receipt** (doklad o přijaté platbě) - not a tax document,
because it has no VAT to show. A VAT payer needs a real tax document (rate,
tax base in CZK, the date of the taxable supply, OSS for other EU countries),
which this module does not produce: for them the document is only a
**payment confirmation** that says so, and the tax document has to be issued
separately, in the accounting system.
"""

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

SUPPORTED_LANGUAGES = ("cs", "en")

_TEXTS = {
    "cs": {
        "receipt": "Doklad o přijaté platbě",
        "confirmation": "Potvrzení o přijaté platbě",
        "no": "č.",
        "issued": "Datum vystavení",
        "paid": "Datum přijetí platby a poskytnutí služby",
        "provider": "Poskytovatel",
        "customer": "Odběratel",
        "ico": "IČO",
        "dic": "DIČ",
        "email": "E-mail",
        "phone": "Telefon",
        "item": "Předmět",
        "item_text": "Zvýšení hodnoty příspěvku „{title}“ o {points} bodů",
        "amount": "Zaplaceno",
        "method": "Způsob platby",
        "method_text": "Platební brána Stripe",
        "reference": "Číslo platby",
        "not_vat_payer": "Poskytovatel není plátcem DPH.",
        "vat_payer": "Poskytovatel je plátcem DPH. Toto potvrzení není daňovým dokladem; daňový doklad bude vystaven samostatně.",
        "footer": "Cena je konečná. Doklad byl vystaven elektronicky a je platný bez podpisu a razítka.",
        "subject": "ThoughtAuction: potvrzení smlouvy a doklad č. {number}",
        "thanks": "Děkujeme za platbu.",
        "contract": "Potvrzujeme uzavření smlouvy o placené službě – zvýšení hodnoty příspěvku „{title}“ o {points} bodů za {amount}. Smlouva byla uzavřena dne {date} připsáním platby a řídí se pravidly a podmínkami: {terms}.",
        "withdrawal": "Na vaši žádost jsme službu poskytli ihned po zaplacení. Poté, co byla služba úplně poskytnuta, právo odstoupit od smlouvy do 14 dnů zaniklo.",
        "see_document": "Doklad č. {number} najdete níže a kdykoli také v aplikaci: {receipts}.",
        "questions": "S dotazy se na nás obraťte na {email}.",
        "terms_link": "pravidla a podmínky",
        "receipts_link": "Moje doklady",
    },
    "en": {
        "receipt": "Payment receipt",
        "confirmation": "Payment confirmation",
        "no": "no.",
        "issued": "Date of issue",
        "paid": "Date of payment and of provision of the service",
        "provider": "Provider",
        "customer": "Customer",
        "ico": "Company ID",
        "dic": "VAT ID",
        "email": "Email",
        "phone": "Phone",
        "item": "Subject",
        "item_text": "Raising the value of the post “{title}” by {points} points",
        "amount": "Paid",
        "method": "Payment method",
        "method_text": "Stripe payment gateway",
        "reference": "Payment number",
        "not_vat_payer": "The provider is not a VAT payer.",
        "vat_payer": "The provider is a VAT payer. This confirmation is not a tax document; the tax document will be issued separately.",
        "footer": "The price is final. This document was issued electronically and is valid without a signature or stamp.",
        "subject": "ThoughtAuction: contract confirmation and document no. {number}",
        "thanks": "Thank you for your payment.",
        "contract": "We confirm the conclusion of the contract for a paid service – raising the value of the post “{title}” by {points} points for {amount}. The contract was concluded on {date} when the payment was received and is governed by the terms and rules: {terms}.",
        "withdrawal": "At your request we provided the service immediately after payment. Once the service had been fully provided, the 14-day right to withdraw from the contract ended.",
        "see_document": "Document no. {number} is below, and also available in the app at any time: {receipts}.",
        "questions": "For any questions, contact us at {email}.",
        "terms_link": "terms and rules",
        "receipts_link": "My receipts",
    },
}

_CZECH_MONTH_FORMAT = "{d}. {m}. {y}"


def normalize_language(value: object, default: str) -> str:
    """"cs", "cs-CZ", "EN" ... -> a supported language, else `default`."""
    if isinstance(value, str):
        primary = value.strip().lower().split("-")[0]
        if primary in SUPPORTED_LANGUAGES:
            return primary
    return default


def money(cents: int, currency: str, language: str) -> str:
    whole, part = divmod(cents, 100)
    code = currency.upper()
    return f"{whole},{part:02d} {code}" if language == "cs" else f"{code} {whole}.{part:02d}"


def local_date(iso: str, timezone: str, language: str) -> str:
    """The date of an ISO timestamp in the provider's time zone."""
    moment = datetime.fromisoformat(iso).astimezone(ZoneInfo(timezone))
    if language == "cs":
        return _CZECH_MONTH_FORMAT.format(d=moment.day, m=moment.month, y=moment.year)
    return moment.strftime("%Y-%m-%d")


def build_snapshot(
    *,
    number: str,
    issued_at: datetime,
    paid_at: datetime,
    timezone: str,
    language: str,
    provider: dict,
    customer_email: str | None,
    post_title: str,
    points: int,
    amount_cents: int,
    currency: str,
    payment_id: str,
    payment_intent: str | None,
    consents: list[str],
) -> dict:
    return {
        "number": number,
        "issued_at": issued_at.isoformat(),
        "paid_at": paid_at.isoformat(),
        "timezone": timezone,
        "language": language,
        "provider": provider,
        "customer": {"email": customer_email},
        "item": {"post_title": post_title, "points": points},
        "amount": amount_cents,
        "currency": currency,
        "payment": {"id": payment_id, "stripe_payment_intent": payment_intent},
        "consents": consents,
    }


def _row(label: str, value: str) -> str:
    return (
        f'<tr><td style="padding:4px 12px 4px 0;color:#555;vertical-align:top">{escape(label)}</td>'
        f'<td style="padding:4px 0">{value}</td></tr>'
    )


def _party(heading: str, lines: list[str]) -> str:
    body = "<br>".join(escape(line) for line in lines if line)
    return (
        '<td style="vertical-align:top;padding:0 16px 12px 0">'
        f'<div style="font-weight:bold;margin-bottom:4px">{escape(heading)}</div>{body}</td>'
    )


def render_document(snapshot: dict, language: str | None = None) -> str:
    """The document as an HTML fragment (a self-contained <div>, inline styles
    only, so it works inside an email as well as in a page)."""
    language = normalize_language(language, snapshot["language"])
    t = _TEXTS[language]
    provider = snapshot["provider"]
    tz = snapshot["timezone"]
    vat_payer = bool(provider.get("vat_payer"))
    title = t["confirmation"] if vat_payer else t["receipt"]
    registration = (provider.get("registration") or {}).get(language) or ""

    provider_lines = [
        provider.get("name", ""),
        provider.get("address", ""),
        f"{t['ico']}: {provider['ico']}" if provider.get("ico") else "",
        f"{t['dic']}: {provider['dic']}" if vat_payer and provider.get("dic") else "",
        registration,
        f"{t['email']}: {provider['email']}" if provider.get("email") else "",
        f"{t['phone']}: {provider['phone']}" if provider.get("phone") else "",
    ]
    customer_lines = [snapshot["customer"].get("email") or ""]
    item = t["item_text"].format(title=snapshot["item"]["post_title"], points=snapshot["item"]["points"])
    payment = snapshot["payment"]
    vat_text = t["vat_payer"] if vat_payer else t["not_vat_payer"]

    rows = "".join(
        [
            _row(t["item"], escape(item)),
            _row(t["amount"], f"<strong>{escape(money(snapshot['amount'], snapshot['currency'], language))}</strong>"),
            _row(t["paid"], escape(local_date(snapshot["paid_at"], tz, language))),
            _row(t["method"], escape(t["method_text"])),
            _row(t["reference"], f'<span style="font-family:monospace">{escape(payment["id"])}</span>'),
        ]
    )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#111;max-width:640px;'
        'border:1px solid #ccc;padding:20px">'
        f'<h2 style="margin:0 0 4px 0;font-size:20px">{escape(title)} {escape(t["no"])} {escape(snapshot["number"])}</h2>'
        f'<div style="color:#555;margin-bottom:16px">{escape(t["issued"])}: {escape(local_date(snapshot["issued_at"], tz, language))}</div>'
        f'<table style="border-collapse:collapse;margin-bottom:8px"><tr>{_party(t["provider"], provider_lines)}'
        f'{_party(t["customer"], customer_lines)}</tr></table>'
        f'<table style="border-collapse:collapse;margin:8px 0">{rows}</table>'
        f'<p style="margin:12px 0 4px 0">{escape(vat_text)}</p>'
        f'<p style="margin:0;color:#555;font-size:12px">{escape(t["footer"])}</p>'
        "</div>"
    )


def render_page(snapshot: dict, language: str | None = None) -> str:
    """The document as a complete HTML page - what the app shows in a
    sandboxed frame."""
    language = normalize_language(language, snapshot["language"])
    return (
        f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(snapshot["number"])}</title></head>'
        f'<body style="margin:12px;background:#fff">{render_document(snapshot, language)}</body></html>'
    )


def render_email(snapshot: dict, language: str | None, *, terms_url: str, receipts_url: str) -> tuple[str, str]:
    """(subject, HTML body): the confirmation of the contract - what was
    bought, for how much, when, under which terms, and that the right of
    withdrawal ended where the payer asked for immediate performance - and
    the document itself below it."""
    language = normalize_language(language, snapshot["language"])
    t = _TEXTS[language]
    provider = snapshot["provider"]
    paid = local_date(snapshot["paid_at"], snapshot["timezone"], language)

    def link(url: str, label: str) -> str:
        return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'

    contract = escape(
        t["contract"].format(
            title=snapshot["item"]["post_title"],
            points=snapshot["item"]["points"],
            amount=money(snapshot["amount"], snapshot["currency"], language),
            date=paid,
            terms="\0",
        )
    ).replace("\0", link(terms_url, t["terms_link"]))
    see_document = escape(t["see_document"].format(number=snapshot["number"], receipts="\0")).replace(
        "\0", link(receipts_url, t["receipts_link"])
    )
    parts = [
        f"<p>{escape(t['thanks'])}</p>",
        f"<p>{contract}</p>",
    ]
    if "digital_content_waiver" in snapshot.get("consents", []):
        parts.append(f"<p>{escape(t['withdrawal'])}</p>")
    parts.append(f"<p>{see_document}</p>")
    parts.append(render_document(snapshot, language))
    if provider.get("email"):
        parts.append(f'<p style="color:#555">{escape(t["questions"].format(email=provider["email"]))}</p>')
    body = '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#111">' + "".join(parts) + "</div>"
    return t["subject"].format(number=snapshot["number"]), body
