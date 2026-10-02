# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the stripe_payment_gate module's endpoints: POST /checkout,
GET /payments/{id} and POST /webhook.

Deliberately does NOT use conftest.py's `client` fixture (TestClient over
the real app.main app): whether this module's routes exist at all depends
on backend/modules.json at the moment app.api.router was first imported - see
test_modules_notifications_router.py for the full rationale. Mounts just
this module's router on a throwaway FastAPI app instead, and uses
ASGITransport since these routes need both a real JWT dependency chain and
db_session on the same event loop. Every Stripe call is mocked with respx
against a fake API host - no test ever reaches api.stripe.com."""

import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import parse_qs

import pytest
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.modules.stripe_payment_gate.models import StripePayment
from app.modules.stripe_payment_gate.purposes import (
    PaymentPurpose,
    PaymentQuote,
    PaymentRejected,
    register_purpose,
    unregister_purpose,
)
from app.modules.stripe_payment_gate.router import router as stripe_router

STRIPE_URL = "https://stripe.test"
WEBHOOK_SECRET = "whsec_test"
BASE = "/api/modules/stripe_payment_gate"

_stripe_app = FastAPI()
_stripe_app.include_router(stripe_router, prefix=BASE)

_stripe_settings = Settings(
    stripe_secret_key="sk_test_123",
    stripe_webhook_secret=WEBHOOK_SECRET,
    stripe_api_url=STRIPE_URL,
    frontend_url="http://front.test",
)


@pytest.fixture(autouse=True)
def _overrides(db_session):
    _stripe_app.dependency_overrides[get_db] = lambda: db_session
    _stripe_app.dependency_overrides[get_settings] = lambda: _stripe_settings
    yield
    _stripe_app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _public_key(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)


@pytest.fixture()
def paid_calls():
    """Registers two test purposes for the duration of one test and yields
    the list every on_paid call appends its payment id to."""
    calls: list[uuid.UUID] = []

    async def resolve(db, user, payload):
        if payload.get("reject"):
            raise PaymentRejected("Already paid", status_code=409)
        return PaymentQuote(
            amount=19900,
            currency="CZK",
            description="Test order",
            reference=payload.get("order_id"),
            return_path="/orders",
        )

    async def on_paid(db, payment):
        calls.append(payment.id)

    async def on_paid_broken(db, payment):
        raise RuntimeError("downstream failure")

    register_purpose(PaymentPurpose(key="test_order", resolve=resolve, on_paid=on_paid))
    register_purpose(PaymentPurpose(key="test_donation", resolve=resolve, on_paid=on_paid, require_user=False))
    register_purpose(PaymentPurpose(key="test_broken", resolve=resolve, on_paid=on_paid_broken))
    yield calls
    for key in ("test_order", "test_donation", "test_broken"):
        unregister_purpose(key)


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_stripe_app), base_url="http://test") as ac:
        yield ac


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _session(payment_id, *, status="open", payment_status="unpaid", session_id="cs_test_1") -> dict:
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


def _signed(event: dict, *, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    ts = str(timestamp if timestamp is not None else int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


async def _seed_payment(db_session, *, user_id=None, purpose="test_order", status="pending") -> StripePayment:
    payment = StripePayment(
        id=uuid.uuid4(),
        user_id=user_id,
        purpose=purpose,
        reference="order-1",
        amount=19900,
        currency="czk",
        description="Test order",
        return_path="/orders",
        extra={},
        status=status,
        stripe_session_id=f"cs_{uuid.uuid4().hex}",
    )
    db_session.add(payment)
    await db_session.commit()
    return payment


# --- POST /checkout -----------------------------------------------------------


@respx.mock
async def test_checkout_creates_session_with_server_side_price(client, db_session, make_access_token, paid_calls):
    route = respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(
        side_effect=lambda request: Response(200, json=_session(uuid.uuid4()))
    )
    token = make_access_token(sub=str(uuid.uuid4()), email="payer@example.com")

    resp = await client.post(
        f"{BASE}/checkout",
        json={"purpose": "test_order", "payload": {"order_id": "o-42", "amount": 1}},
        headers=_auth(token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["checkout_url"] == "https://checkout.stripe.test/cs_test_1"
    form = parse_qs(route.calls.last.request.content.decode())
    assert form["line_items[0][price_data][unit_amount]"] == ["19900"]
    assert form["line_items[0][price_data][currency]"] == ["czk"]
    assert form["customer_email"] == ["payer@example.com"]
    assert form["metadata[payment_id]"] == [body["payment_id"]]
    assert form["success_url"] == [f"http://front.test/platba/vysledek?payment_id={body['payment_id']}"]
    assert form["cancel_url"] == [f"http://front.test/platba/vysledek?payment_id={body['payment_id']}&canceled=1"]
    assert route.calls.last.request.headers["Idempotency-Key"] == body["payment_id"]

    payment = await db_session.get(StripePayment, uuid.UUID(body["payment_id"]))
    assert payment.status == "pending"
    assert payment.reference == "o-42"
    assert payment.stripe_session_id == "cs_test_1"
    assert payment.user_id is not None


@respx.mock
async def test_checkout_records_consents(client, db_session, make_access_token, paid_calls):
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(200, json=_session(uuid.uuid4())))
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await client.post(
        f"{BASE}/checkout",
        json={"purpose": "test_order", "consents": ["terms", "digital_content_waiver"]},
        headers=_auth(token),
    )

    assert resp.status_code == 200
    payment = await db_session.get(StripePayment, uuid.UUID(resp.json()["payment_id"]))
    assert payment.extra["consents"] == ["digital_content_waiver", "terms"]
    assert payment.extra["consented_at"]


@respx.mock
async def test_checkout_without_consents_stores_none(client, db_session, make_access_token, paid_calls):
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(200, json=_session(uuid.uuid4())))
    token = make_access_token(sub=str(uuid.uuid4()))

    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_order"}, headers=_auth(token))

    payment = await db_session.get(StripePayment, uuid.UUID(resp.json()["payment_id"]))
    assert "consents" not in payment.extra


async def test_checkout_rejects_unknown_consent(client, make_access_token, paid_calls):
    token = make_access_token(sub=str(uuid.uuid4()))
    resp = await client.post(
        f"{BASE}/checkout", json={"purpose": "test_order", "consents": ["marketing"]}, headers=_auth(token)
    )
    assert resp.status_code == 422


async def test_checkout_unknown_purpose_404(client, make_access_token, paid_calls):
    token = make_access_token(sub=str(uuid.uuid4()))
    resp = await client.post(f"{BASE}/checkout", json={"purpose": "nope"}, headers=_auth(token))
    assert resp.status_code == 404


async def test_checkout_requires_user_by_default(client, paid_calls):
    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_order"})
    assert resp.status_code == 401


async def test_checkout_invalid_token_is_401_not_anonymous(client, paid_calls):
    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_donation"}, headers=_auth("garbage"))
    assert resp.status_code == 401


@respx.mock
async def test_checkout_anonymous_purpose(client, db_session, paid_calls):
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(200, json=_session(uuid.uuid4())))

    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_donation"})

    assert resp.status_code == 200
    payment = await db_session.get(StripePayment, uuid.UUID(resp.json()["payment_id"]))
    assert payment.user_id is None


async def test_checkout_resolve_rejection_passes_status(client, make_access_token, paid_calls):
    token = make_access_token(sub=str(uuid.uuid4()))
    resp = await client.post(
        f"{BASE}/checkout", json={"purpose": "test_order", "payload": {"reject": True}}, headers=_auth(token)
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Already paid"


@respx.mock
async def test_checkout_stripe_error_502_and_no_row(client, db_session, make_access_token, paid_calls):
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(400, json={"error": {}}))
    sub = str(uuid.uuid4())
    # Read the id up front: create_payment's rollback expires every object
    # in this shared session, and a lazy reload afterwards can't run here.
    user_id = (await get_current_user(claims={"sub": sub}, db=db_session)).id

    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_order"}, headers=_auth(make_access_token(sub=sub)))

    assert resp.status_code == 502
    # Scoped to this test's own user - the table may hold rows from outside
    # this rolled-back test transaction (e.g. a local dev run).
    count = await db_session.scalar(
        select(func.count()).select_from(StripePayment).where(StripePayment.user_id == user_id)
    )
    assert count == 0


async def test_checkout_not_configured_503(client, make_access_token, paid_calls):
    _stripe_app.dependency_overrides[get_settings] = lambda: Settings(stripe_secret_key="")
    token = make_access_token(sub=str(uuid.uuid4()))
    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_order"}, headers=_auth(token))
    assert resp.status_code == 503


# --- GET /payments/{id} ---------------------------------------------------------


async def test_get_payment_owner_only(client, db_session, make_access_token, paid_calls):
    sub = str(uuid.uuid4())
    owner = await get_current_user(claims={"sub": sub}, db=db_session)
    payment = await _seed_payment(db_session, user_id=owner.id, status="paid")

    own = await client.get(f"{BASE}/payments/{payment.id}", headers=_auth(make_access_token(sub=sub)))
    other = await client.get(
        f"{BASE}/payments/{payment.id}", headers=_auth(make_access_token(sub=str(uuid.uuid4())))
    )
    anonymous = await client.get(f"{BASE}/payments/{payment.id}")

    assert own.status_code == 200
    assert own.json()["status"] == "paid"
    assert own.json()["return_path"] == "/orders"
    assert other.status_code == 404
    assert anonymous.status_code == 404


async def test_get_anonymous_payment_by_id(client, db_session, paid_calls):
    payment = await _seed_payment(db_session, purpose="test_donation", status="expired")
    resp = await client.get(f"{BASE}/payments/{payment.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "expired"


async def test_get_payment_404_unknown(client, paid_calls):
    resp = await client.get(f"{BASE}/payments/{uuid.uuid4()}")
    assert resp.status_code == 404


@respx.mock
async def test_get_pending_payment_reconciles_from_stripe(client, db_session, paid_calls):
    payment = await _seed_payment(db_session, purpose="test_donation")
    respx.get(f"{STRIPE_URL}/v1/checkout/sessions/{payment.stripe_session_id}").mock(
        return_value=Response(200, json=_session(payment.id, status="complete", payment_status="paid"))
    )

    resp = await client.get(f"{BASE}/payments/{payment.id}")

    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"
    assert resp.json()["paid_at"] is not None
    assert paid_calls == [payment.id]


@respx.mock
async def test_get_pending_payment_stripe_down_stays_pending(client, db_session, paid_calls):
    payment = await _seed_payment(db_session, purpose="test_donation")
    respx.get(f"{STRIPE_URL}/v1/checkout/sessions/{payment.stripe_session_id}").mock(return_value=Response(500))

    resp = await client.get(f"{BASE}/payments/{payment.id}")

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    assert paid_calls == []


# --- POST /webhook --------------------------------------------------------------


async def test_webhook_completed_marks_paid_once(client, db_session, paid_calls):
    payment = await _seed_payment(db_session)
    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {"object": _session(payment.id, status="complete", payment_status="paid")},
    }

    for _ in range(2):  # Stripe may deliver the same event more than once
        body, headers = _signed(event)
        resp = await client.post(f"{BASE}/webhook", content=body, headers=headers)
        assert resp.status_code == 200

    refreshed = await db_session.get(StripePayment, payment.id)
    await db_session.refresh(refreshed)
    assert refreshed.status == "paid"
    assert refreshed.stripe_payment_intent_id == "pi_test_1"
    assert paid_calls == [payment.id]


async def test_webhook_completed_but_unpaid_stays_pending(client, db_session, paid_calls):
    """Delayed methods (e.g. bank transfer) complete the session before the
    money arrives - only async_payment_succeeded later means paid."""
    payment = await _seed_payment(db_session)
    body, headers = _signed(
        {"type": "checkout.session.completed", "data": {"object": _session(payment.id, status="complete")}}
    )

    resp = await client.post(f"{BASE}/webhook", content=body, headers=headers)

    assert resp.status_code == 200
    await db_session.refresh(payment)
    assert payment.status == "pending"
    assert paid_calls == []


@pytest.mark.parametrize(
    ("event_type", "session_status", "expected"),
    [
        ("checkout.session.expired", "expired", "expired"),
        ("checkout.session.async_payment_failed", "complete", "failed"),
    ],
)
async def test_webhook_terminal_non_paid_states(client, db_session, paid_calls, event_type, session_status, expected):
    payment = await _seed_payment(db_session)
    body, headers = _signed({"type": event_type, "data": {"object": _session(payment.id, status=session_status)}})

    resp = await client.post(f"{BASE}/webhook", content=body, headers=headers)

    assert resp.status_code == 200
    await db_session.refresh(payment)
    assert payment.status == expected
    assert paid_calls == []


async def test_webhook_rejects_bad_signature(client, db_session, paid_calls):
    payment = await _seed_payment(db_session)
    event = {"type": "checkout.session.completed", "data": {"object": _session(payment.id, status="complete", payment_status="paid")}}
    body, headers = _signed(event, secret="whsec_wrong")

    resp = await client.post(f"{BASE}/webhook", content=body, headers=headers)

    assert resp.status_code == 400
    await db_session.refresh(payment)
    assert payment.status == "pending"


async def test_webhook_rejects_stale_timestamp(client, paid_calls):
    body, headers = _signed({"type": "ping"}, timestamp=int(time.time()) - 3600)
    resp = await client.post(f"{BASE}/webhook", content=body, headers=headers)
    assert resp.status_code == 400


async def test_webhook_missing_signature(client, paid_calls):
    resp = await client.post(f"{BASE}/webhook", content=b"{}")
    assert resp.status_code == 400


async def test_webhook_ignores_unrelated_events_and_foreign_sessions(client, paid_calls):
    for event in (
        {"type": "customer.created", "data": {"object": {}}},
        {"type": "checkout.session.completed", "data": {"object": {"id": "cs_x", "metadata": {}}}},
    ):
        body, headers = _signed(event)
        resp = await client.post(f"{BASE}/webhook", content=body, headers=headers)
        assert resp.status_code == 200
    assert paid_calls == []


async def test_webhook_on_paid_failure_rolls_back_and_500s(db_session, paid_calls):
    payment = await _seed_payment(db_session, purpose="test_broken")
    body, headers = _signed(
        {"type": "checkout.session.completed", "data": {"object": _session(payment.id, status="complete", payment_status="paid")}}
    )

    transport = ASGITransport(app=_stripe_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as raw_client:
        resp = await raw_client.post(f"{BASE}/webhook", content=body, headers=headers)

    assert resp.status_code == 500
    await db_session.refresh(payment)
    assert payment.status == "pending"


@respx.mock
async def test_checkout_refuses_a_payment_missing_a_consent_the_purpose_requires(client, db_session, make_access_token):
    """A purpose can insist on consents (e.g. the express request for
    immediate delivery); a request that skips the pay button must not skip
    them, and nothing is created or sent to Stripe without them."""

    async def resolve(db, user, payload):
        return PaymentQuote(amount=500, currency="usd", description="Boost", reference="p-1")

    register_purpose(
        PaymentPurpose(key="test_consent", resolve=resolve, required_consents=("terms", "digital_content_waiver"))
    )
    try:
        route = respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(
            return_value=Response(200, json=_session(uuid.uuid4()))
        )
        headers = _auth(make_access_token(sub=str(uuid.uuid4())))

        for consents in ([], ["terms"], ["digital_content_waiver"]):
            resp = await client.post(
                f"{BASE}/checkout", json={"purpose": "test_consent", "consents": consents}, headers=headers
            )
            assert resp.status_code == 422
            assert "Missing consent" in resp.json()["detail"]
        assert not route.called
        assert (await db_session.scalar(select(func.count()).select_from(StripePayment))) == 0

        ok = await client.post(
            f"{BASE}/checkout",
            json={"purpose": "test_consent", "consents": ["terms", "digital_content_waiver"]},
            headers=headers,
        )
        assert ok.status_code == 200
        assert route.called
    finally:
        unregister_purpose("test_consent")


async def test_a_purpose_without_required_consents_needs_none(client, make_access_token, paid_calls):
    """The default is unchanged: nothing is required unless a purpose says so."""
    with respx.mock:
        respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(200, json=_session(uuid.uuid4())))
        resp = await client.post(
            f"{BASE}/checkout", json={"purpose": "test_order"}, headers=_auth(make_access_token(sub=str(uuid.uuid4())))
        )
    assert resp.status_code == 200


# --- The payer's email and the after-commit hook ------------------------------


@respx.mock
async def test_checkout_keeps_the_payers_email_with_the_payment(client, db_session, make_access_token, paid_calls):
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(200, json=_session(uuid.uuid4())))
    token = make_access_token(sub=str(uuid.uuid4()), email="payer@example.com")

    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_order"}, headers=_auth(token))

    payment = await db_session.get(StripePayment, uuid.UUID(resp.json()["payment_id"]))
    assert payment.extra["customer_email"] == "payer@example.com"


@respx.mock
async def test_an_anonymous_payment_has_no_email_to_keep(client, db_session, paid_calls):
    respx.post(f"{STRIPE_URL}/v1/checkout/sessions").mock(return_value=Response(200, json=_session(uuid.uuid4())))

    resp = await client.post(f"{BASE}/checkout", json={"purpose": "test_donation"})

    payment = await db_session.get(StripePayment, uuid.UUID(resp.json()["payment_id"]))
    assert "customer_email" not in payment.extra


@pytest.fixture()
def after_paid_log():
    """Three purposes for one test: one with an after_paid hook, one whose
    hook raises, and one whose on_paid raises (so the payment never commits).
    Everything they do is appended to the yielded dict's lists."""
    log = {"after": [], "on_paid": []}

    async def resolve(db, user, payload):
        return PaymentQuote(amount=500, currency="usd", description="Boost", reference="p-1")

    async def on_paid(db, payment):
        log["on_paid"].append(payment.id)

    async def on_paid_broken(db, payment):
        raise RuntimeError("downstream failure")

    async def after_paid(db, payment):
        log["after"].append((payment.id, payment.status))

    async def after_paid_broken(db, payment):
        log["after"].append((payment.id, "tried"))
        raise RuntimeError("smtp is down")

    register_purpose(PaymentPurpose(key="test_after", resolve=resolve, on_paid=on_paid, after_paid=after_paid))
    register_purpose(PaymentPurpose(key="test_after_broken", resolve=resolve, on_paid=on_paid, after_paid=after_paid_broken))
    register_purpose(PaymentPurpose(key="test_after_blocked", resolve=resolve, on_paid=on_paid_broken, after_paid=after_paid))
    yield log
    for key in ("test_after", "test_after_broken", "test_after_blocked"):
        unregister_purpose(key)


def _completed(payment) -> tuple[bytes, dict]:
    return _signed(
        {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": _session(payment.id, status="complete", payment_status="paid")}}
    )


async def test_after_paid_runs_once_when_the_payment_is_confirmed(client, db_session, after_paid_log):
    payment = await _seed_payment(db_session, purpose="test_after")

    for _ in range(3):  # a webhook delivered again, and again
        body, headers = _completed(payment)
        assert (await client.post(f"{BASE}/webhook", content=body, headers=headers)).status_code == 200

    assert after_paid_log["after"] == [(payment.id, "paid")]
    assert after_paid_log["on_paid"] == [payment.id]


async def test_the_result_page_poll_after_the_webhook_does_not_run_after_paid_again(client, db_session, after_paid_log):
    payment = await _seed_payment(db_session, purpose="test_after")  # anonymous, so no token is needed to read it
    body, headers = _completed(payment)
    await client.post(f"{BASE}/webhook", content=body, headers=headers)

    resp = await client.get(f"{BASE}/payments/{payment.id}")

    assert resp.status_code == 200
    assert len(after_paid_log["after"]) == 1


async def test_a_failing_after_paid_does_not_undo_or_fail_the_payment(client, db_session, after_paid_log):
    payment = await _seed_payment(db_session, purpose="test_after_broken")
    body, headers = _completed(payment)

    resp = await client.post(f"{BASE}/webhook", content=body, headers=headers)

    assert resp.status_code == 200  # Stripe must not retry: the payment is done
    await db_session.refresh(payment)
    assert payment.status == "paid" and payment.paid_at is not None
    assert after_paid_log["on_paid"] == [payment.id]
    assert after_paid_log["after"] == [(payment.id, "tried")]


async def test_after_paid_does_not_run_when_the_payment_could_not_be_applied(db_session, after_paid_log):
    """A failing on_paid rolls the payment back (Stripe retries), and then the
    after-commit hook must not announce a payment that was never committed."""
    payment = await _seed_payment(db_session, purpose="test_after_blocked")
    body, headers = _completed(payment)
    transport = ASGITransport(app=_stripe_app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"{BASE}/webhook", content=body, headers=headers)

    assert resp.status_code == 500
    await db_session.refresh(payment)
    assert payment.status == "pending"
    assert after_paid_log["after"] == []


@pytest.mark.parametrize(
    ("event_type", "session_status"),
    [("checkout.session.expired", "expired"), ("checkout.session.async_payment_failed", "complete")],
)
async def test_after_paid_does_not_run_for_a_payment_that_did_not_succeed(client, db_session, after_paid_log, event_type, session_status):
    payment = await _seed_payment(db_session, purpose="test_after")
    body, headers = _signed({"id": "evt_1", "type": event_type, "data": {"object": _session(payment.id, status=session_status)}})

    assert (await client.post(f"{BASE}/webhook", content=body, headers=headers)).status_code == 200

    assert after_paid_log["after"] == []
