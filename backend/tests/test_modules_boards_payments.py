# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Paying to raise a post's value: the boards module's payment purpose, run
through the stripe_payment_gate module's real endpoints with Stripe mocked
(respx against a fake API host - nothing here ever reaches api.stripe.com),
plus the endpoints that let an author find and boost their own posts."""

import hashlib
import hmac
import itertools
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import pytest
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, func, select

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.boards import payments
from app.modules.boards.config import BoardsConfig, InvoicingConfig, PaymentsConfig, ProviderConfig, get_config
from app.modules.boards.models import Category, Post, Resonance
from app.modules.boards.payments import POST_BOOST, apply_boost, resolve_boost
from app.modules.boards.router import gateway_enabled
from app.modules.boards.router import router as boards_router
from app.modules.boards.service import post_value
from app.modules.stripe_payment_gate.models import StripePayment
from app.modules.stripe_payment_gate.purposes import PaymentRejected
from app.modules.stripe_payment_gate.router import router as stripe_router

STRIPE_URL = "https://stripe.test"
WEBHOOK_SECRET = "whsec_test"
BOARDS = "/api/modules/boards"
STRIPE = "/api/modules/stripe_payment_gate"
CONSENTS = ["terms", "digital_content_waiver"]

_app = FastAPI()
_app.include_router(boards_router, prefix=BOARDS)
_app.include_router(stripe_router, prefix=STRIPE)

# mail_suppress_send: the confirmation email is built and "sent" but no SMTP
# connection is ever opened - these tests must never really send anything.
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

PROVIDER = ProviderConfig(
    name="Jan Novák",
    ico="12345678",
    address="Ulice 1, 110 00 Praha 1",
    email="info@example.com",
    registration={"cs": "fyzická osoba zapsaná v živnostenském rejstříku", "en": "sole trader"},
)


def _config(**fields) -> BoardsConfig:
    """A configuration with the issuer filled in - payments are refused without one."""
    return BoardsConfig(invoicing=InvoicingConfig(provider=PROVIDER), **fields)


def _use_config(config: BoardsConfig, monkeypatch=None):
    _app.dependency_overrides[get_config] = lambda: config
    if monkeypatch is not None:
        monkeypatch.setattr(payments, "get_config", lambda: config)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))
    await db_session.execute(delete(StripePayment))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_settings] = lambda: _settings
    _app.dependency_overrides[gateway_enabled] = lambda: True
    monkeypatch.setattr(payments, "get_settings", lambda: _settings)
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
    async def _make(**fields) -> Person:
        sub = uuid.uuid4()
        user = User(auth_sub=sub, **fields)
        db_session.add(user)
        await db_session.commit()
        return Person(user, make_access_token(sub=str(sub), email="payer@example.com"))

    return _make


@pytest.fixture()
async def alice(make_person) -> Person:
    return await make_person()


@pytest.fixture()
async def bob(make_person) -> Person:
    return await make_person()


async def _category(db_session, person, slug="general") -> Category:
    category = Category(title=slug.title(), slug=slug, description="d", created_by_id=person.user.id)
    db_session.add(category)
    await db_session.commit()
    return category


async def _post(db_session, person, category, title="My post", **fields) -> Post:
    post = Post(category_id=category.id, author_id=person.user.id, title=title, body="Body", **fields)
    db_session.add(post)
    await db_session.commit()
    return post


def _payload(post, amount_usd=5, **extra):
    return {"post_id": str(post.id), "amount_usd": amount_usd, **extra}


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


_session_numbers = itertools.count(1)
LAST_SESSION = {"id": None}


async def _checkout(client, person, post, amount_usd=5, *, consents=CONSENTS, **extra):
    """Starts a boost checkout. Stripe's session creation answers with a new
    open session each time; its id is left in LAST_SESSION."""
    session_id = f"cs_test_{next(_session_numbers)}"
    LAST_SESSION["id"] = session_id
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(
        return_value=Response(200, json=_session(uuid.uuid4(), status="open", payment_status="unpaid", session_id=session_id))
    )
    return await client.post(
        f"{STRIPE}/checkout",
        json={"purpose": POST_BOOST, "payload": _payload(post, amount_usd, **extra), "consents": consents},
        headers=person.headers,
    )


async def _confirm(client, payment_id, *, session_id=None):
    session = _session(payment_id, session_id=session_id or LAST_SESSION["id"])
    event = {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": session}}
    body, headers = _signed(event)
    return await client.post(f"{STRIPE}/webhook", content=body, headers=headers)


async def _paid_cents(db_session, post) -> int:
    await db_session.refresh(post)
    return post.paid_cents


# --- Pricing a boost (resolve) ------------------------------------------------


async def test_a_boost_is_priced_server_side_in_dollars_for_the_authors_own_post(db_session, alice):
    category = await _category(db_session, alice, "philosophy")
    post = await _post(db_session, alice, category, title="Attention")

    quote = await resolve_boost(db_session, alice.user, _payload(post, 5))

    assert (quote.amount, quote.currency) == (500, "usd")
    assert quote.reference == str(post.id)
    assert quote.return_path == "/categories/philosophy"
    assert "Attention" in quote.description and "50 points" in quote.description
    assert quote.extra == {"post_id": str(post.id), "amount_usd": 5, "points": 50, "language": "cs"}


@pytest.mark.parametrize(
    ("sent", "kept"),
    [("en", "en"), ("EN", "en"), ("en-GB", "en"), ("cs-CZ", "cs"), ("de", "cs"), ("", "cs"), (None, "cs"), (5, "cs"), ("x" * 99, "cs")],
)
async def test_the_payers_language_is_kept_for_their_document_or_falls_back(db_session, alice, sent, kept):
    post = await _post(db_session, alice, await _category(db_session, alice))
    payload = {**_payload(post), "language": sent}
    assert (await resolve_boost(db_session, alice.user, payload)).extra["language"] == kept


async def test_the_points_in_the_description_follow_the_configured_factor(db_session, alice, monkeypatch):
    _use_config(_config(points_per_usd=20), monkeypatch)
    post = await _post(db_session, alice, await _category(db_session, alice))
    quote = await resolve_boost(db_session, alice.user, _payload(post, 5))
    assert quote.extra["points"] == 100


async def test_a_long_title_is_cut_in_the_description(db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice), title="x" * 120)
    quote = await resolve_boost(db_session, alice.user, _payload(post))
    assert "x" * 49 + "…" in quote.description
    assert "x" * 51 not in quote.description


@pytest.mark.parametrize("amount", [0, -5, 501, 4.5, 5.0, "5", True, None, [5]])
async def test_an_amount_that_is_not_a_whole_number_inside_the_range_is_refused(db_session, alice, amount):
    post = await _post(db_session, alice, await _category(db_session, alice))

    with pytest.raises(PaymentRejected) as raised:
        await resolve_boost(db_session, alice.user, {"post_id": str(post.id), "amount_usd": amount})

    assert raised.value.status_code == 422
    assert "from 1 to 500" in raised.value.detail


async def test_a_missing_amount_is_refused(db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))
    with pytest.raises(PaymentRejected) as raised:
        await resolve_boost(db_session, alice.user, {"post_id": str(post.id)})
    assert raised.value.status_code == 422


@pytest.mark.parametrize("amount", [1, 500])
async def test_the_ends_of_the_range_are_allowed(db_session, alice, amount):
    post = await _post(db_session, alice, await _category(db_session, alice))
    assert (await resolve_boost(db_session, alice.user, _payload(post, amount))).amount == amount * 100


async def test_the_range_comes_from_the_configuration(db_session, alice, monkeypatch):
    _use_config(_config(payments=PaymentsConfig(min_amount_usd=5, max_amount_usd=50)), monkeypatch)
    post = await _post(db_session, alice, await _category(db_session, alice))

    for amount in (4, 51):
        with pytest.raises(PaymentRejected):
            await resolve_boost(db_session, alice.user, _payload(post, amount))
    assert (await resolve_boost(db_session, alice.user, _payload(post, 50))).amount == 5000


async def test_somebody_elses_post_looks_exactly_like_a_missing_one(db_session, alice, bob):
    """Whether a post is a given user's must not be learnable by trying to pay for it."""
    post = await _post(db_session, alice, await _category(db_session, alice))

    with pytest.raises(PaymentRejected) as theirs:
        await resolve_boost(db_session, bob.user, _payload(post))
    with pytest.raises(PaymentRejected) as missing:
        await resolve_boost(db_session, bob.user, {"post_id": str(uuid.uuid4()), "amount_usd": 5})

    assert (theirs.value.status_code, theirs.value.detail) == (missing.value.status_code, missing.value.detail) == (404, "Post not found")


@pytest.mark.parametrize("post_id", ["not-a-uuid", None, 5, ""])
async def test_a_post_id_that_is_not_a_uuid_is_a_missing_post(db_session, alice, post_id):
    with pytest.raises(PaymentRejected) as raised:
        await resolve_boost(db_session, alice.user, {"post_id": post_id, "amount_usd": 5})
    assert raised.value.status_code == 404


@pytest.mark.parametrize("status", ["blocked", "removed"])
async def test_a_post_that_is_no_longer_published_cannot_be_paid_for(db_session, alice, status):
    post = await _post(db_session, alice, await _category(db_session, alice), status=status)
    with pytest.raises(PaymentRejected) as raised:
        await resolve_boost(db_session, alice.user, _payload(post))
    assert raised.value.status_code == 409


async def test_a_post_in_a_blocked_category_cannot_be_paid_for(db_session, alice):
    category = await _category(db_session, alice)
    post = await _post(db_session, alice, category)
    category.status = "blocked"
    await db_session.commit()

    with pytest.raises(PaymentRejected) as raised:
        await resolve_boost(db_session, alice.user, _payload(post))

    assert (raised.value.status_code, raised.value.detail) == (409, "The category is blocked")


async def test_a_blocked_account_cannot_pay(make_person, db_session):
    blocked = await make_person(is_blocked=True)
    post = await _post(db_session, blocked, await _category(db_session, blocked))
    with pytest.raises(PaymentRejected) as raised:
        await resolve_boost(db_session, blocked.user, _payload(post))
    assert raised.value.status_code == 403


# --- Applying a paid boost (on_paid) ------------------------------------------


async def _payment(db_session, post, amount, currency="usd") -> StripePayment:
    """A confirmed payment, stored - the receipt issued for it refers to its row."""
    payment = StripePayment(
        id=uuid.uuid4(),
        user_id=getattr(post, "author_id", None),
        purpose=POST_BOOST,
        reference=str(post.id),
        amount=amount,
        currency=currency,
        description="Boost",
        status="paid",
        paid_at=datetime.now(timezone.utc),
        extra={"points": amount // 10, "customer_email": "payer@example.com", "language": "cs"},
    )
    db_session.add(payment)
    await db_session.flush()
    return payment


async def test_a_paid_boost_adds_the_amount_to_the_post(db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))
    await apply_boost(db_session, await _payment(db_session, post, 500))
    assert await _paid_cents(db_session, post) == 500


async def test_payments_accumulate(db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice), paid_cents=300)
    await apply_boost(db_session, await _payment(db_session, post, 500))
    await apply_boost(db_session, await _payment(db_session, post, 200))
    assert await _paid_cents(db_session, post) == 1000


async def test_dollars_become_points_in_the_value(db_session, alice):
    """A new payment raises the value by exactly what was paid: $5 = 50 points."""
    post = await _post(db_session, alice, await _category(db_session, alice))
    now = datetime.now(timezone.utc)
    before = post_value(post.paid_cents, post.resonance_count, post.created_at, now, BoardsConfig())

    await apply_boost(db_session, await _payment(db_session, post, 500))
    await db_session.refresh(post)

    assert post_value(post.paid_cents, post.resonance_count, post.created_at, now, BoardsConfig()) - before == 50


@pytest.mark.parametrize("status", ["blocked", "removed"])
async def test_a_payment_that_lands_after_a_block_is_still_recorded(db_session, alice, status):
    """The money has been taken either way; nothing is refunded."""
    post = await _post(db_session, alice, await _category(db_session, alice), status=status)
    await apply_boost(db_session, await _payment(db_session, post, 500))
    assert await _paid_cents(db_session, post) == 500


async def test_a_payment_that_lands_after_the_category_was_blocked_is_still_recorded(db_session, alice):
    category = await _category(db_session, alice)
    post = await _post(db_session, alice, category)
    category.status = "blocked"
    await db_session.commit()

    await apply_boost(db_session, await _payment(db_session, post, 500))

    assert await _paid_cents(db_session, post) == 500


async def test_a_payment_for_a_missing_post_does_not_raise(db_session, caplog):
    """Raising would make Stripe retry the webhook for ever."""
    ghost = Post(id=uuid.uuid4())
    await apply_boost(db_session, await _payment(db_session, ghost, 500))
    assert "does not exist" in caplog.text


async def test_a_payment_in_another_currency_is_not_applied(db_session, alice, caplog):
    post = await _post(db_session, alice, await _category(db_session, alice))
    await apply_boost(db_session, await _payment(db_session, post, 500, currency="czk"))
    assert await _paid_cents(db_session, post) == 0
    assert "not applied" in caplog.text


# --- The whole flow through the gateway's endpoints ---------------------------


@respx.mock
async def test_paying_for_a_post_raises_its_value_once_stripe_confirms(client, db_session, alice, bob):
    category = await _category(db_session, alice)
    boosted = await _post(db_session, alice, category, title="boosted")
    await _post(db_session, bob, category, title="popular", resonance_count=5)

    started = await _checkout(client, alice, boosted, 10)

    assert started.status_code == 200
    payment_id = started.json()["payment_id"]
    assert await _paid_cents(db_session, boosted) == 0  # nothing counts until Stripe confirms
    form = parse_qs(respx.calls.last.request.content.decode())
    assert form["line_items[0][price_data][unit_amount]"] == ["1000"]
    assert form["line_items[0][price_data][currency]"] == ["usd"]
    assert "boosted" in form["line_items[0][price_data][product_data][name]"][0]
    assert form["success_url"] == [f"http://front.test/platba/vysledek?payment_id={payment_id}"]

    assert (await _confirm(client, payment_id)).status_code == 200

    assert await _paid_cents(db_session, boosted) == 1000
    payment = await db_session.get(StripePayment, uuid.UUID(payment_id))
    assert (payment.status, payment.purpose, payment.reference) == ("paid", POST_BOOST, str(boosted.id))
    assert payment.return_path == "/categories/general"
    assert payment.extra["consents"] == ["digital_content_waiver", "terms"]
    # $10 = 100 points beats five resonances.
    listing = (await client.get(f"{BOARDS}/categories/general/posts")).json()["items"]
    assert [(p["title"], p["value"]) for p in listing] == [("boosted", 100), ("popular", 5)]


@respx.mock
async def test_the_same_confirmation_arriving_twice_counts_once(client, db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))
    payment_id = (await _checkout(client, alice, post, 5)).json()["payment_id"]

    for _ in range(3):
        assert (await _confirm(client, payment_id)).status_code == 200

    assert await _paid_cents(db_session, post) == 500


@respx.mock
async def test_later_payments_add_to_earlier_ones(client, db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))

    first = (await _checkout(client, alice, post, 5)).json()["payment_id"]
    await _confirm(client, first)
    second = (await _checkout(client, alice, post, 3)).json()["payment_id"]
    await _confirm(client, second)

    assert await _paid_cents(db_session, post) == 800


@respx.mock
async def test_the_result_page_poll_also_applies_a_payment_the_webhook_has_not_delivered(client, db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))
    started = await _checkout(client, alice, post, 5)
    payment_id = started.json()["payment_id"]
    respx.get(f"{STRIPE_URL}/v1/checkout/sessions/{LAST_SESSION['id']}").mock(
        return_value=Response(200, json=_session(payment_id, session_id=LAST_SESSION["id"]))
    )

    polled = await client.get(f"{STRIPE}/payments/{payment_id}", headers=alice.headers)
    await client.get(f"{STRIPE}/payments/{payment_id}", headers=alice.headers)

    assert polled.json()["status"] == "paid"
    assert await _paid_cents(db_session, post) == 500


@respx.mock
async def test_a_payment_confirmed_after_the_post_was_blocked_is_kept_not_refunded(client, db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))
    payment_id = (await _checkout(client, alice, post, 5)).json()["payment_id"]
    post.status = "blocked"
    await db_session.commit()

    assert (await _confirm(client, payment_id)).status_code == 200

    assert await _paid_cents(db_session, post) == 500
    assert (await client.get(f"{BOARDS}/categories/general/posts")).json()["items"] == []


@respx.mock
async def test_the_browser_cannot_name_the_price(client, db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))

    resp = await _checkout(client, alice, post, 5, amount=1, amount_cents=1, price=1)

    form = parse_qs(respx.calls.last.request.content.decode())
    assert resp.status_code == 200
    assert form["line_items[0][price_data][unit_amount]"] == ["500"]


@respx.mock
async def test_a_payment_cannot_start_without_the_consent_to_immediate_performance(client, db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))

    for consents in ([], ["terms"], ["digital_content_waiver"]):
        resp = await _checkout(client, alice, post, 5, consents=consents)
        assert resp.status_code == 422
        assert "Missing consent" in resp.json()["detail"]

    assert (await db_session.scalar(select(func.count()).select_from(StripePayment))) == 0


@respx.mock
async def test_nobody_can_start_a_payment_for_somebody_elses_post(client, db_session, alice, bob):
    post = await _post(db_session, alice, await _category(db_session, alice))

    resp = await _checkout(client, bob, post, 5)

    assert resp.status_code == 404
    assert (await db_session.scalar(select(func.count()).select_from(StripePayment))) == 0


@respx.mock
async def test_signing_in_is_required_to_pay(client, db_session, alice):
    post = await _post(db_session, alice, await _category(db_session, alice))
    resp = await client.post(
        f"{STRIPE}/checkout", json={"purpose": POST_BOOST, "payload": _payload(post), "consents": CONSENTS}
    )
    assert resp.status_code == 401


# --- Finding your own posts ---------------------------------------------------


async def test_an_author_sees_their_own_posts_marked_and_what_they_paid(client, db_session, alice, bob):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category, title="mine", paid_cents=700)
    await _post(db_session, bob, category, title="theirs", paid_cents=900)
    url = f"{BOARDS}/categories/general/posts"

    def seen(resp):
        return {p["title"]: (p["mine"], p["paid_cents"]) for p in resp.json()["items"]}

    assert seen(await client.get(url, headers=alice.headers)) == {"mine": (True, 700), "theirs": (False, None)}
    assert seen(await client.get(url, headers=bob.headers)) == {"mine": (False, None), "theirs": (True, 900)}
    assert seen(await client.get(url)) == {"mine": (False, None), "theirs": (False, None)}


async def test_the_flag_never_gives_away_who_wrote_somebody_elses_post(client, db_session, alice, bob):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category, paid_cents=700)

    resp = await client.get(f"{BOARDS}/categories/general/posts", headers=bob.headers)

    assert "700" not in resp.text
    assert str(alice.user.id) not in resp.text and str(alice.user.auth_sub) not in resp.text


async def test_a_new_post_and_a_resonance_report_ownership_to_the_right_person(client, db_session, alice, bob):
    await _category(db_session, alice)

    created = await client.post(
        f"{BOARDS}/categories/general/posts", json={"title": "T", "body": "A calm and ordinary body."}, headers=alice.headers
    )
    post_id = created.json()["id"]
    by_other = await client.post(f"{BOARDS}/posts/{post_id}/resonance", headers=bob.headers)

    assert (created.json()["mine"], created.json()["paid_cents"]) == (True, 0)
    assert (by_other.json()["mine"], by_other.json()["paid_cents"]) == (False, None)


async def test_my_posts_lists_only_my_posts_in_every_state_newest_first(client, db_session, alice, bob):
    one, two = await _category(db_session, alice, "one"), await _category(db_session, alice, "two")
    now = datetime.now(timezone.utc)
    await _post(db_session, alice, one, "oldest", created_at=now - timedelta(days=2))
    await _post(db_session, alice, two, "newest", created_at=now, paid_cents=500, resonance_count=3)
    await _post(
        db_session, alice, one, "blocked", status="blocked", moderation_reason="Personal attacks.", created_at=now - timedelta(days=1)
    )
    await _post(db_session, bob, one, "not mine")

    resp = await client.get(f"{BOARDS}/me/posts", headers=alice.headers)

    assert resp.status_code == 200
    page = resp.json()
    assert [p["title"] for p in page["items"]] == ["newest", "blocked", "oldest"]
    newest, blocked, _ = page["items"]
    assert (newest["category_slug"], newest["category_title"], newest["status"]) == ("two", "Two", "published")
    assert (newest["paid_cents"], newest["resonance_count"], newest["value"]) == (500, 3, 53)
    assert (blocked["status"], blocked["moderation_reason"]) == ("blocked", "Personal attacks.")
    assert page["has_more"] is False
    assert str(alice.user.id) not in resp.text


async def test_my_posts_needs_a_login_and_pages(client, db_session, alice):
    assert (await client.get(f"{BOARDS}/me/posts")).status_code == 401
    _use_config(_config(page_size=2))
    category = await _category(db_session, alice)
    for i in range(5):
        await _post(db_session, alice, category, f"p{i}", created_at=datetime.now(timezone.utc) - timedelta(minutes=i))

    pages = [(await client.get(f"{BOARDS}/me/posts", params={"offset": o}, headers=alice.headers)).json() for o in (0, 2, 4)]

    assert [[p["title"] for p in page["items"]] for page in pages] == [["p0", "p1"], ["p2", "p3"], ["p4"]]
    assert [page["has_more"] for page in pages] == [True, True, False]


async def test_a_blocked_account_can_still_see_its_posts(client, db_session, make_person):
    blocked = await make_person(is_blocked=True)
    await _post(db_session, blocked, await _category(db_session, blocked), status="removed", moderation_reason="account_blocked")

    resp = await client.get(f"{BOARDS}/me/posts", headers=blocked.headers)

    assert resp.status_code == 200
    assert resp.json()["items"][0]["moderation_reason"] == "account_blocked"


# --- Whether payments are on --------------------------------------------------


async def test_the_payment_options_are_public_and_carry_the_limits(client):
    resp = await client.get(f"{BOARDS}/payments")
    assert resp.json() == {"enabled": True, "currency": "usd", "min_amount_usd": 1, "max_amount_usd": 500, "points_per_usd": 10}


async def test_payments_are_off_unless_the_gateway_is_enabled_and_configured(client, monkeypatch):
    _app.dependency_overrides.pop(gateway_enabled)
    router_module = __import__("sys").modules["app.modules.boards.router"]

    async def enabled():
        return (await client.get(f"{BOARDS}/payments")).json()["enabled"]

    monkeypatch.setattr(router_module, "load_enabled_module_keys", lambda: ["boards", "stripe_payment_gate"])
    assert await enabled() is True

    monkeypatch.setattr(router_module, "load_enabled_module_keys", lambda: ["boards"])
    assert await enabled() is False  # the gateway module is not switched on

    monkeypatch.setattr(router_module, "load_enabled_module_keys", lambda: ["boards", "stripe_payment_gate"])
    _app.dependency_overrides[get_settings] = lambda: Settings(stripe_secret_key="sk_test_123", stripe_webhook_secret="")
    assert await enabled() is False  # a key is missing
    _app.dependency_overrides[get_settings] = lambda: Settings(stripe_secret_key="", stripe_webhook_secret="whsec")
    assert await enabled() is False
