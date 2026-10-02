# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The document issued for a confirmed payment, and the confirmation email.

Rendering is tested on snapshots; numbering and the stored document against
the database; delivery through the payment gateway's real webhook with Stripe
mocked (respx). Every mail goes through fastapi-mail's SUPPRESS_SEND and is
read back from its recorder - nothing here opens an SMTP connection."""

import hashlib
import hmac
import itertools
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr

import pytest
import respx
from fastapi import FastAPI
from fastapi_mail import FastMail
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.boards import documents, payments, receipts
from app.modules.boards.config import BoardsConfig, InvoicingConfig, ProviderConfig, get_config
from app.modules.boards.models import Category, Post, Receipt, ReceiptCounter, Resonance
from app.modules.boards.payments import POST_BOOST
from app.modules.boards.router import gateway_enabled
from app.modules.boards.router import router as boards_router
from app.modules.stripe_payment_gate.models import StripePayment
from app.modules.stripe_payment_gate.router import router as stripe_router
from app.services.email import _connection_config

STRIPE_URL = "https://stripe.test"
WEBHOOK_SECRET = "whsec_test"
BOARDS = "/api/modules/boards"
STRIPE = "/api/modules/stripe_payment_gate"
CONSENTS = ["terms", "digital_content_waiver"]


def _session(payment_id, *, status="complete", payment_status="paid", session_id="cs_test_1") -> dict:
    return {
        "id": session_id,
        "object": "checkout.session",
        "url": f"https://checkout.stripe.test/{session_id}",
        "status": status,
        "payment_status": payment_status,
        "payment_intent": "pi_test_1" if payment_status == "paid" else None,
        "client_reference_id": str(payment_id),
        "metadata": {"payment_id": str(payment_id)},
    }


def _signed(event: dict) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    ts = str(int(time.time()))
    sig = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}

PROVIDER = ProviderConfig(
    name="Jan Novák",
    ico="12345678",
    dic="CZ12345678",
    address="Ulice 1, 110 00 Praha 1",
    email="info@example.com",
    phone="+420 123 456 789",
    registration={"cs": "fyzická osoba zapsaná v živnostenském rejstříku", "en": "sole trader in the Trade Register"},
)
VAT_PAYER = PROVIDER.model_copy(update={"vat_payer": True})

_settings = Settings(
    stripe_secret_key="sk_test_123",
    stripe_webhook_secret=WEBHOOK_SECRET,
    stripe_api_url=STRIPE_URL,
    frontend_url="http://front.test",
    mail_username="user",
    mail_password="pass",
    mail_from="noreply@example.com",
    mail_server="smtp.example.com",
    mail_port=587,
    mail_starttls=True,
    mail_ssl_tls=False,
    mail_suppress_send=True,
)

_app = FastAPI()
_app.include_router(boards_router, prefix=BOARDS)
_app.include_router(stripe_router, prefix=STRIPE)


def _config(provider: ProviderConfig = PROVIDER, **fields) -> BoardsConfig:
    return BoardsConfig(invoicing=InvoicingConfig(provider=provider), **fields)


def _use_config(config: BoardsConfig, monkeypatch=None):
    _app.dependency_overrides[get_config] = lambda: config
    if monkeypatch is not None:
        monkeypatch.setattr(payments, "get_config", lambda: config)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await db_session.execute(delete(Receipt))
    await db_session.execute(delete(ReceiptCounter))
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))
    await db_session.execute(delete(StripePayment))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    monkeypatch.setattr(payments, "get_settings", lambda: _settings)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_settings] = lambda: _settings
    _app.dependency_overrides[gateway_enabled] = lambda: True
    _use_config(_config(page_size=20), monkeypatch)
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


class Person:
    def __init__(self, user: User, token: str):
        self.user = user
        self.headers = {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_person(db_session, make_access_token):
    async def _make(email: str | None = "payer@example.com", **fields) -> Person:
        sub = uuid.uuid4()
        user = User(auth_sub=sub, **fields)
        db_session.add(user)
        await db_session.commit()
        return Person(user, make_access_token(sub=str(sub), email=email))

    return _make


@pytest.fixture()
async def alice(make_person) -> Person:
    return await make_person("alice@example.com")


@pytest.fixture()
async def bob(make_person) -> Person:
    return await make_person("bob@example.com")


@pytest.fixture()
async def admin(make_person) -> Person:
    return await make_person("admin@example.com", is_admin=True)


async def _post(db_session, person, title="Attention", slug="general") -> Post:
    category = (await db_session.scalars(select(Category).where(Category.slug == slug))).first()
    if category is None:
        category = Category(title=slug.title(), slug=slug, description="d", created_by_id=person.user.id)
        db_session.add(category)
        await db_session.commit()
    post = Post(category_id=category.id, author_id=person.user.id, title=title, body="Body")
    db_session.add(post)
    await db_session.commit()
    return post


def _snapshot(**changes) -> dict:
    values = dict(
        number="2026-000007",
        issued_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
        paid_at=datetime(2026, 10, 2, 11, 59, tzinfo=timezone.utc),
        timezone="Europe/Prague",
        language="cs",
        provider=PROVIDER.model_dump(),
        customer_email="payer@example.com",
        post_title="Ownership of attention",
        points=70,
        amount_cents=700,
        currency="usd",
        payment_id="11111111-2222-3333-4444-555555555555",
        payment_intent="pi_test_1",
        consents=CONSENTS,
    )
    values.update(changes)
    return documents.build_snapshot(**values)


# --- The document -------------------------------------------------------------


def test_a_receipt_names_the_issuer_the_customer_the_item_the_amount_and_its_number():
    html = documents.render_document(_snapshot())

    for expected in (
        "Doklad o přijaté platbě",
        "2026-000007",
        "Jan Novák",
        "Ulice 1, 110 00 Praha 1",
        "IČO: 12345678",
        "fyzická osoba zapsaná v živnostenském rejstříku",
        "info@example.com",
        "payer@example.com",
        "Zvýšení hodnoty příspěvku „Ownership of attention“ o 70 bodů",
        "7,00 USD",
        "11111111-2222-3333-4444-555555555555",
        "Poskytovatel není plátcem DPH.",
    ):
        assert expected in html


def test_the_heading_reads_like_a_title_not_a_label():
    assert "<h2" in documents.render_document(_snapshot(), "cs")
    assert "Doklad o přijaté platbě č. 2026-000007</h2>" in documents.render_document(_snapshot(), "cs")
    assert "Payment receipt no. 2026-000007</h2>" in documents.render_document(_snapshot(), "en")
    vat = _snapshot(provider=VAT_PAYER.model_dump())
    assert "Potvrzení o přijaté platbě č. 2026-000007</h2>" in documents.render_document(vat, "cs")


def test_money_and_dates_are_written_the_way_each_language_writes_them():
    cs = documents.render_document(_snapshot(), "cs")
    en = documents.render_document(_snapshot(), "en")

    assert "7,00 USD" in cs and "2. 10. 2026" in cs
    assert "USD 7.00" in en and "2026-10-02" in en
    assert "Payment receipt" in en and "The provider is not a VAT payer." in en
    assert "sole trader in the Trade Register" in en


def test_a_provider_that_is_not_a_vat_payer_shows_no_vat_id():
    """The VAT ID of a non-payer would suggest a tax document it is not."""
    html = documents.render_document(_snapshot())
    assert "CZ12345678" not in html and "DIČ" not in html


def test_a_vat_payer_gets_only_a_confirmation_that_says_it_is_not_a_tax_document():
    html = documents.render_document(_snapshot(provider=VAT_PAYER.model_dump()))

    assert "Potvrzení o přijaté platbě" in html and "Doklad o přijaté platbě" not in html
    assert "DIČ: CZ12345678" in html
    assert "není daňovým dokladem" in html
    assert "není plátcem DPH" not in html


def test_everything_that_came_from_outside_is_escaped():
    hostile = "<script>alert(1)</script> & \"quotes\""
    provider = PROVIDER.model_copy(update={"name": "<b>Evil</b> s.r.o.", "address": hostile}).model_dump()

    page = documents.render_page(_snapshot(post_title=hostile, customer_email="<x@y.cz>", provider=provider))

    assert "<script>" not in page and "<b>Evil</b>" not in page and "<x@y.cz>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;quotes&quot;" in page
    assert "&lt;b&gt;Evil&lt;/b&gt; s.r.o." in page


def test_the_date_is_the_providers_not_utc():
    """23:30 UTC on 31 December is already New Year in Prague."""
    snap = _snapshot(
        issued_at=datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc),
        paid_at=datetime(2026, 12, 31, 23, 29, tzinfo=timezone.utc),
    )
    assert "1. 1. 2027" in documents.render_document(snap, "cs")
    assert "2027-01-01" in documents.render_document(snap, "en")


def test_the_document_is_in_its_own_language_unless_another_is_asked_for():
    snap = _snapshot(language="en")
    assert "Payment receipt" in documents.render_document(snap)
    assert "Payment receipt" in documents.render_document(snap, "de")  # unsupported -> its own
    assert "Doklad o přijaté platbě" in documents.render_document(snap, "cs-CZ")


def test_the_page_is_a_complete_html_document():
    page = documents.render_page(_snapshot(language="en"))
    assert page.startswith("<!doctype html>") and '<html lang="en">' in page
    assert "<title>2026-000007</title>" in page and page.endswith("</body></html>")


def test_the_confirmation_email_says_what_was_bought_when_and_under_which_terms():
    subject, html = documents.render_email(_snapshot(), "cs", terms_url="http://front.test/obchodni-podminky", receipts_url="http://front.test/receipts")

    assert subject == "ThoughtAuction: potvrzení smlouvy a doklad č. 2026-000007"
    assert "Potvrzujeme uzavření smlouvy o placené službě" in html
    assert "„Ownership of attention“ o 70 bodů za 7,00 USD" in html
    assert "dne 2. 10. 2026" in html
    assert '<a href="http://front.test/obchodni-podminky">pravidla a podmínky</a>' in html
    assert '<a href="http://front.test/receipts">Moje doklady</a>' in html
    assert "Doklad č. 2026-000007 najdete níže" in html
    assert "Doklad o přijaté platbě" in html  # the document itself, below
    assert "info@example.com" in html


def test_the_english_email_is_a_full_translation():
    subject, html = documents.render_email(_snapshot(language="en"), None, terms_url="http://t", receipts_url="http://r")
    assert subject == "ThoughtAuction: contract confirmation and document no. 2026-000007"
    assert "We confirm the conclusion of the contract" in html and "raising the value of the post" in html
    assert "Potvrzujeme" not in html


def test_the_right_of_withdrawal_is_mentioned_only_where_immediate_performance_was_asked_for():
    with_waiver = documents.render_email(_snapshot(), "cs", terms_url="http://t", receipts_url="http://r")[1]
    without = documents.render_email(_snapshot(consents=["terms"]), "cs", terms_url="http://t", receipts_url="http://r")[1]

    assert "právo odstoupit od smlouvy do 14 dnů zaniklo" in with_waiver
    assert "odstoupit" not in without


def test_a_hostile_title_cannot_break_out_of_the_email_either():
    _, html = documents.render_email(_snapshot(post_title="<img src=x onerror=alert(1)>"), "cs", terms_url="http://t", receipts_url="http://r")
    assert "<img" not in html


# --- Numbering and the stored document ----------------------------------------


async def _paid(db_session, post, amount=700, **extra) -> StripePayment:
    payment = StripePayment(
        id=uuid.uuid4(),
        user_id=post.author_id,
        purpose=POST_BOOST,
        reference=str(post.id),
        amount=amount,
        currency="usd",
        description="Boost",
        status="paid",
        paid_at=datetime.now(timezone.utc),
        stripe_payment_intent_id="pi_test_1",
        extra={"points": amount // 10, "customer_email": "payer@example.com", "language": "cs", "consents": CONSENTS, **extra},
    )
    db_session.add(payment)
    await db_session.flush()
    return payment


async def test_numbers_run_within_a_year_and_start_over_in_the_next(db_session, alice):
    post = await _post(db_session, alice)
    in_2026 = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
    in_2027 = datetime(2027, 6, 1, 12, tzinfo=timezone.utc)

    numbers = [
        (await receipts.issue_receipt(db_session, await _paid(db_session, post), _config(), now)).number
        for now in (in_2026, in_2026, in_2027, in_2026)
    ]

    assert numbers == ["2026-000001", "2026-000002", "2027-000001", "2026-000003"]


async def test_the_year_of_a_number_is_the_providers_not_utc(db_session, alice):
    post = await _post(db_session, alice)
    new_year_in_prague = datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc)

    receipt = await receipts.issue_receipt(db_session, await _paid(db_session, post), _config(), new_year_in_prague)

    assert receipt.number == "2027-000001"


async def test_a_number_whose_transaction_rolls_back_is_not_used_up(db_session, alice):
    """Gapless numbering: the counter moves in the confirming transaction, so
    a confirmation that fails and is retried does not leave a hole."""
    post = await _post(db_session, alice)
    now = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
    payment = await _paid(db_session, post)

    nested = await db_session.begin_nested()
    assert (await receipts.issue_receipt(db_session, payment, _config(), now)).number == "2026-000001"
    await nested.rollback()

    again = await receipts.issue_receipt(db_session, payment, _config(), now)
    assert again.number == "2026-000001"


async def test_a_payment_can_have_only_one_document(db_session, alice):
    post = await _post(db_session, alice)
    payment = await _paid(db_session, post)
    await receipts.issue_receipt(db_session, payment, _config())

    nested = await db_session.begin_nested()
    with pytest.raises(IntegrityError):
        await receipts.issue_receipt(db_session, payment, _config())
    await nested.rollback()


async def test_the_document_keeps_what_was_true_when_the_payment_was_confirmed(db_session, alice):
    post = await _post(db_session, alice, title="Original title")
    receipt = await receipts.issue_receipt(db_session, await _paid(db_session, post), _config())
    await db_session.commit()

    post.title = "Changed afterwards"
    await db_session.commit()
    stored = await db_session.get(Receipt, receipt.id)

    assert stored.document["item"]["post_title"] == "Original title"
    assert stored.document["provider"]["name"] == "Jan Novák"
    assert stored.document["customer"]["email"] == "payer@example.com"
    assert stored.document["currency"] == "usd" and stored.document["amount"] == 700
    assert stored.document["consents"] == CONSENTS
    assert stored.email_to == "payer@example.com"
    assert stored.user_id == alice.user.id


async def test_a_document_for_a_post_that_no_longer_exists_is_still_issued(db_session):
    """The money was taken; the document must exist even if the post is gone."""
    ghost = Post(id=uuid.uuid4())
    payment = await _paid(db_session, ghost)

    receipt = await receipts.issue_receipt(db_session, payment, _config())

    assert receipt.document["item"]["post_title"] == ""


# --- Delivery through the gateway ---------------------------------------------


def _outbox():
    return FastMail(_connection_config(_settings)).record_messages()


def _to(message) -> str:
    """The bare address a message went to (the header reads `name <address>`)."""
    return parseaddr(str(message["To"]))[1]


def _subject(message) -> str:
    return str(make_header(decode_header(message["Subject"])))


def _html(message) -> str:
    part = next(p for p in message.walk() if p.get_content_type() == "text/html")
    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")


_session_numbers = itertools.count(1)


@dataclass
class Paid:
    payment_id: str
    session_id: str

    def confirmation(self) -> tuple[bytes, dict]:
        """Stripe's signed checkout.session.completed webhook for this payment."""
        event = {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {"object": _session(self.payment_id, session_id=self.session_id)},
        }
        return _signed(event)


@respx.mock
async def _pay(client, person, post, amount_usd=7, *, language="cs", confirm=True) -> Paid:
    """Starts a boost checkout and (by default) delivers Stripe's confirmation."""
    session_id = f"cs_test_{next(_session_numbers)}"
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(
        return_value=Response(200, json=_session(uuid.uuid4(), status="open", payment_status="unpaid", session_id=session_id))
    )
    started = await client.post(
        f"{STRIPE}/checkout",
        json={
            "purpose": POST_BOOST,
            "payload": {"post_id": str(post.id), "amount_usd": amount_usd, "language": language},
            "consents": CONSENTS,
        },
        headers=person.headers,
    )
    assert started.status_code == 200, started.text
    paid = Paid(started.json()["payment_id"], session_id)
    if confirm:
        body, headers = paid.confirmation()
        assert (await client.post(f"{STRIPE}/webhook", content=body, headers=headers)).status_code == 200
    return paid


async def _receipts(db_session) -> list[Receipt]:
    return list((await db_session.scalars(select(Receipt).order_by(Receipt.number))).all())


async def test_confirming_a_payment_emails_the_confirmation_and_document_to_the_payer(client, db_session, alice):
    post = await _post(db_session, alice, title="Ownership of attention")

    with _outbox() as outbox:
        await _pay(client, alice, post, 7)

    assert len(outbox) == 1
    message = outbox[0]
    assert _to(message) == "alice@example.com"
    assert _subject(message) == "ThoughtAuction: potvrzení smlouvy a doklad č. " + (await _receipts(db_session))[0].number
    html = _html(message)
    assert "Ownership of attention" in html and "70 bodů" in html and "7,00 USD" in html
    assert "http://front.test/obchodni-podminky" in html and "http://front.test/receipts" in html

    (receipt,) = await _receipts(db_session)
    assert receipt.number.endswith("-000001")
    assert (receipt.email_to, receipt.email_attempts, receipt.email_error) == ("alice@example.com", 1, None)
    assert receipt.emailed_at is not None


async def test_the_email_is_in_the_language_the_payer_was_using(client, db_session, alice):
    post = await _post(db_session, alice)
    with _outbox() as outbox:
        await _pay(client, alice, post, language="en-GB")
    assert "contract confirmation and document no." in _subject(outbox[0])
    assert "We confirm the conclusion of the contract" in _html(outbox[0])


async def test_the_same_confirmation_arriving_again_sends_and_issues_nothing_more(client, db_session, alice):
    post = await _post(db_session, alice)
    body, headers = (await _pay(client, alice, post, confirm=False)).confirmation()

    with _outbox() as outbox:
        for _ in range(3):
            assert (await client.post(f"{STRIPE}/webhook", content=body, headers=headers)).status_code == 200

    assert len(outbox) == 1
    assert len(await _receipts(db_session)) == 1


async def test_a_failing_mail_server_does_not_touch_the_payment(client, db_session, alice, monkeypatch):
    async def smtp_down(*args, **kwargs):
        raise ConnectionRefusedError("smtp is down")

    monkeypatch.setattr(receipts, "send_email", smtp_down)
    post = await _post(db_session, alice)

    paid = await _pay(client, alice, post, 7)

    await db_session.refresh(post)
    payment = await db_session.get(StripePayment, uuid.UUID(paid.payment_id))
    assert (payment.status, post.paid_cents) == ("paid", 700)
    (receipt,) = await _receipts(db_session)
    assert receipt.emailed_at is None
    assert receipt.email_attempts == 1
    assert "ConnectionRefusedError: smtp is down" in receipt.email_error


async def test_a_failed_email_is_tried_again_when_the_next_payment_is_confirmed(client, db_session, alice, bob, monkeypatch):
    real_send = receipts.send_email

    async def smtp_down(*args, **kwargs):
        raise ConnectionRefusedError("smtp is down")

    monkeypatch.setattr(receipts, "send_email", smtp_down)
    await _pay(client, alice, await _post(db_session, alice), 7)
    monkeypatch.setattr(receipts, "send_email", real_send)  # the mail server is back

    with _outbox() as outbox:
        await _pay(client, bob, await _post(db_session, bob), 3)

    assert sorted(_to(m) for m in outbox) == ["alice@example.com", "bob@example.com"]
    first, second = await _receipts(db_session)
    assert first.emailed_at is not None and first.email_error is None and first.email_attempts == 2
    assert second.emailed_at is not None and second.email_attempts == 1


async def test_after_five_failed_attempts_it_is_left_to_an_administrator(client, db_session, alice, bob):
    old = await receipts.issue_receipt(db_session, await _paid(db_session, await _post(db_session, alice)), _config())
    old.email_attempts = receipts.MAX_AUTOMATIC_ATTEMPTS
    old.email_error = "gave up"
    await db_session.commit()

    with _outbox() as outbox:
        await _pay(client, bob, await _post(db_session, bob), 3)

    assert [_to(m) for m in outbox] == ["bob@example.com"]  # alice's was not retried
    await db_session.refresh(old)
    assert old.emailed_at is None


async def test_a_payer_whose_email_is_not_known_still_gets_a_document_to_read_in_the_app(client, db_session, make_person):
    nameless = await make_person(email=None)

    with _outbox() as outbox:
        await _pay(client, nameless, await _post(db_session, nameless), 7)

    assert len(outbox) == 0
    (receipt,) = await _receipts(db_session)
    assert receipt.email_to is None and receipt.emailed_at is None
    assert "No recipient" in receipt.email_error
    listing = await client.get(f"{BOARDS}/me/receipts", headers=nameless.headers)
    assert [r["number"] for r in listing.json()] == [receipt.number]


async def test_a_second_payment_gets_the_next_number(client, db_session, alice):
    post = await _post(db_session, alice)
    await _pay(client, alice, post, 7)
    await _pay(client, alice, post, 3)
    assert [r.number[-6:] for r in await _receipts(db_session)] == ["000001", "000002"]


# --- No money without an issuer -----------------------------------------------


@respx.mock
async def test_no_payment_is_accepted_until_the_provider_is_filled_in(client, db_session, alice, monkeypatch):
    _use_config(_config(provider=ProviderConfig()), monkeypatch)
    post = await _post(db_session, alice)
    route = respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(200, json=_session(uuid.uuid4())))

    resp = await client.post(
        f"{STRIPE}/checkout",
        json={"purpose": POST_BOOST, "payload": {"post_id": str(post.id), "amount_usd": 5}, "consents": CONSENTS},
        headers=alice.headers,
    )
    info = await client.get(f"{BOARDS}/payments")

    assert resp.status_code == 503 and "not available" in resp.json()["detail"]
    assert not route.called
    assert (await db_session.scalar(select(func.count()).select_from(StripePayment))) == 0
    assert info.json()["enabled"] is False


@pytest.mark.parametrize("missing", ["name", "ico", "address", "email"])
async def test_each_of_the_issuers_essentials_is_required(missing):
    assert not receipts.provider_ready(_config(provider=PROVIDER.model_copy(update={missing: "  "})))
    assert receipts.provider_ready(_config())


# --- Reading your documents ---------------------------------------------------


async def test_my_receipts_lists_only_my_documents_newest_first(client, db_session, alice, bob):
    await _pay(client, alice, await _post(db_session, alice, "first"), 7)
    await _pay(client, alice, await _post(db_session, alice, "second"), 3)
    await _pay(client, bob, await _post(db_session, bob, "bobs"), 5)

    assert (await client.get(f"{BOARDS}/me/receipts")).status_code == 401
    mine = (await client.get(f"{BOARDS}/me/receipts", headers=alice.headers)).json()

    assert [(r["post_title"], r["amount"], r["points"], r["emailed"]) for r in mine] == [("second", 300, 30, True), ("first", 700, 70, True)]
    assert mine[0]["number"] > mine[1]["number"]
    assert set(mine[0]) == {"id", "number", "issued_at", "amount", "currency", "post_title", "points", "emailed"}


async def test_a_document_can_be_read_only_by_the_one_who_paid(client, db_session, alice, bob):
    await _pay(client, alice, await _post(db_session, alice, "first"), 7)
    receipt_id = (await client.get(f"{BOARDS}/me/receipts", headers=alice.headers)).json()[0]["id"]
    url = f"{BOARDS}/me/receipts/{receipt_id}/document"

    ok = await client.get(url, headers=alice.headers)
    assert ok.status_code == 200 and ok.headers["content-type"].startswith("text/html")
    assert "Doklad o přijaté platbě" in ok.text and "7,00 USD" in ok.text

    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers=bob.headers)).status_code == 404
    assert (await client.get(f"{BOARDS}/me/receipts/{uuid.uuid4()}/document", headers=alice.headers)).status_code == 404


async def test_the_document_page_can_be_asked_for_in_the_viewers_language(client, db_session, alice):
    await _pay(client, alice, await _post(db_session, alice), 7, language="cs")
    receipt_id = (await client.get(f"{BOARDS}/me/receipts", headers=alice.headers)).json()[0]["id"]
    url = f"{BOARDS}/me/receipts/{receipt_id}/document"

    assert "Payment receipt" in (await client.get(url, params={"language": "en"}, headers=alice.headers)).text
    assert "Doklad o přijaté platbě" in (await client.get(url, headers=alice.headers)).text


# --- Administrators -----------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), [("get", "/manage/receipts"), ("post", "/manage/receipts/retry")])
async def test_the_receipt_tools_are_for_administrators_only(client, alice, method, path):
    assert (await getattr(client, method)(BOARDS + path)).status_code == 401
    assert (await getattr(client, method)(BOARDS + path, headers=alice.headers)).status_code == 403


async def test_an_administrator_sees_delivery_state_and_can_retry_everything_unsent(client, db_session, alice, admin, monkeypatch):
    async def smtp_down(*args, **kwargs):
        raise ConnectionRefusedError("smtp is down")

    real_send = receipts.send_email
    monkeypatch.setattr(receipts, "send_email", smtp_down)
    await _pay(client, alice, await _post(db_session, alice), 7)
    (stuck,) = await _receipts(db_session)
    stuck.email_attempts = receipts.MAX_AUTOMATIC_ATTEMPTS  # automatic retries have given up
    await db_session.commit()

    unsent = (await client.get(f"{BOARDS}/manage/receipts", params={"unsent": "true"}, headers=admin.headers)).json()
    assert [(r["email_to"], r["email_attempts"], "smtp is down" in r["email_error"]) for r in unsent] == [("alice@example.com", 5, True)]

    monkeypatch.setattr(receipts, "send_email", real_send)
    with _outbox() as outbox:
        retried = await client.post(f"{BOARDS}/manage/receipts/retry", headers=admin.headers)

    assert retried.json() == {"tried": 1, "sent": 1, "still_unsent": 0}
    assert len(outbox) == 1
    assert (await client.get(f"{BOARDS}/manage/receipts", params={"unsent": "true"}, headers=admin.headers)).json() == []
    assert len((await client.get(f"{BOARDS}/manage/receipts", headers=admin.headers)).json()) == 1
