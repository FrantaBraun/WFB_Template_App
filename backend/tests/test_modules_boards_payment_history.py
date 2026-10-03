# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""An author's payment overview (GET /me/payments): the payments they started
for their posts, what became of each, the post's state today and the
document, and the total they have actually paid.

Payments and documents are written straight into the tables - how they come
about is tested with the gateway in test_modules_boards_payments.py and
test_modules_boards_receipts.py. Same setup as the other boards router tests:
the module's router on a throwaway app, ASGITransport, tables emptied inside
each test's rolled-back transaction."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import get_db
from app.models.user import User
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.boards.models import Category, Post, Receipt, Resonance
from app.modules.boards.payments import POST_BOOST
from app.modules.boards.router import router as boards_router
from app.modules.stripe_payment_gate.models import StripePayment

BASE = "/api/modules/boards"
URL = f"{BASE}/me/payments"

_app = FastAPI()
_app.include_router(boards_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await db_session.execute(delete(Receipt))
    await db_session.execute(delete(StripePayment))
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=20)
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
        return Person(user, make_access_token(sub=str(sub)))

    return _make


@pytest.fixture()
async def alice(make_person) -> Person:
    return await make_person()


@pytest.fixture()
async def bob(make_person) -> Person:
    return await make_person()


async def _category(db_session, person, slug="general", **fields) -> Category:
    category = Category(title=slug.title(), slug=slug, description="d", created_by_id=person.user.id, **fields)
    db_session.add(category)
    await db_session.commit()
    return category


async def _post(db_session, person, category, title="My post", **fields) -> Post:
    post = Post(category_id=category.id, author_id=person.user.id, title=title, body="Body", **fields)
    db_session.add(post)
    await db_session.commit()
    return post


_clock = iter(range(1, 10_000))


async def _payment(db_session, person, post, amount=500, status="paid", **fields) -> StripePayment:
    """Each one a minute later than the one before, so the order is certain."""
    started = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=next(_clock))
    payment = StripePayment(
        id=uuid.uuid4(),
        user_id=person.user.id,
        purpose=fields.pop("purpose", POST_BOOST),
        reference=fields.pop("reference", str(post.id) if post else None),
        amount=amount,
        currency=fields.pop("currency", "usd"),
        description="Boost",
        status=status,
        created_at=started,
        paid_at=started + timedelta(seconds=30) if status == "paid" else None,
        extra={"points": amount // 10},
        **fields,
    )
    db_session.add(payment)
    await db_session.commit()
    return payment


async def _receipt(db_session, payment, number="2026-000001", title="My post") -> Receipt:
    receipt = Receipt(
        payment_id=payment.id,
        user_id=payment.user_id,
        number=number,
        document={"amount": payment.amount, "currency": payment.currency, "item": {"post_title": title, "points": 50}},
    )
    db_session.add(receipt)
    await db_session.commit()
    return receipt


async def _overview(client, person, **params):
    resp = await client.get(URL, params=params, headers=person.headers)
    assert resp.status_code == 200
    return resp.json()


# --- Who sees what ------------------------------------------------------------


async def test_the_overview_needs_a_login(client):
    assert (await client.get(URL)).status_code == 401


async def test_an_author_with_no_payments_sees_an_empty_overview(client, alice):
    assert await _overview(client, alice) == {
        "summary": {"paid_count": 0, "paid_cents": 0, "currency": "usd"},
        "items": [],
        "has_more": False,
    }


async def test_only_the_users_own_boost_payments_are_listed(client, alice, bob, db_session):
    category = await _category(db_session, alice)
    mine = await _post(db_session, alice, category, "mine")
    theirs = await _post(db_session, bob, category, "theirs")
    mine_payment = await _payment(db_session, alice, mine)
    await _payment(db_session, bob, theirs)  # somebody else's
    await _payment(db_session, alice, None, purpose="shop_order", reference="order-17")  # another purpose

    overview = await _overview(client, alice)

    assert [p["id"] for p in overview["items"]] == [str(mine_payment.id)]
    assert (overview["summary"]["paid_count"], overview["summary"]["paid_cents"]) == (1, 500)


async def test_payments_come_newest_first(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    first = await _payment(db_session, alice, post, 100)
    second = await _payment(db_session, alice, post, 200)
    third = await _payment(db_session, alice, post, 300)

    overview = await _overview(client, alice)

    assert [p["id"] for p in overview["items"]] == [str(third.id), str(second.id), str(first.id)]


# --- The total ----------------------------------------------------------------


async def test_the_total_counts_completed_payments_only(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    await _payment(db_session, alice, post, 500)
    await _payment(db_session, alice, post, 1000)
    for status in ("pending", "failed", "expired"):
        await _payment(db_session, alice, post, 9900, status=status)

    overview = await _overview(client, alice)

    assert overview["summary"] == {"paid_count": 2, "paid_cents": 1500, "currency": "usd"}
    # ... while every attempt is listed, with what became of it.
    assert [p["status"] for p in overview["items"]] == ["expired", "failed", "pending", "paid", "paid"]
    assert [p["paid_at"] is None for p in overview["items"]] == [True, True, True, False, False]


async def test_the_total_is_in_the_boards_currency_only(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    await _payment(db_session, alice, post, 500)
    await _payment(db_session, alice, post, 70000, currency="czk")

    assert (await _overview(client, alice))["summary"] == {"paid_count": 1, "paid_cents": 500, "currency": "usd"}


async def test_the_total_covers_every_page(client, alice, db_session):
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=2)
    post = await _post(db_session, alice, await _category(db_session, alice))
    for _ in range(5):
        await _payment(db_session, alice, post, 500)

    first = await _overview(client, alice)
    last = await _overview(client, alice, offset=4)

    assert (len(first["items"]), first["has_more"]) == (2, True)
    assert (len(last["items"]), last["has_more"]) == (1, False)
    assert first["summary"] == last["summary"] == {"paid_count": 5, "paid_cents": 2500, "currency": "usd"}


async def test_the_pages_do_not_overlap_or_skip(client, alice, db_session):
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=2)
    post = await _post(db_session, alice, await _category(db_session, alice))
    made = [await _payment(db_session, alice, post, 100 * (i + 1)) for i in range(5)]

    seen = []
    for offset in (0, 2, 4):
        seen += [p["id"] for p in (await _overview(client, alice, offset=offset))["items"]]

    assert seen == [str(p.id) for p in reversed(made)]


# --- What each payment says ---------------------------------------------------


async def test_a_payment_carries_its_amount_points_and_the_post_as_it_is_now(client, alice, db_session):
    category = await _category(db_session, alice)
    post = await _post(db_session, alice, category, "Original title")
    payment = await _payment(db_session, alice, post, 500)
    await _receipt(db_session, payment, title="Original title")
    post.title = "Edited since"
    await db_session.commit()

    item = (await _overview(client, alice))["items"][0]

    assert (item["amount"], item["currency"], item["points"], item["status"]) == (500, "usd", 50, "paid")
    assert (item["post_title"], item["post_status"], item["category_blocked"]) == ("Edited since", "published", False)


@pytest.mark.parametrize("status", ["blocked", "removed"])
async def test_a_payment_for_a_post_that_was_taken_down_says_so(client, alice, db_session, status):
    post = await _post(db_session, alice, await _category(db_session, alice), status=status, paid_cents=500)
    await _payment(db_session, alice, post, 500)

    overview = await _overview(client, alice)

    assert overview["items"][0]["post_status"] == status
    assert overview["summary"]["paid_cents"] == 500  # what was paid stays paid


async def test_a_payment_for_a_post_in_a_blocked_category_says_so(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice, status="blocked"))
    await _payment(db_session, alice, post)

    item = (await _overview(client, alice))["items"][0]

    assert (item["post_status"], item["category_blocked"]) == ("published", True)


async def test_a_paid_payment_points_to_its_document_and_an_unpaid_one_has_none(client, alice, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    paid = await _payment(db_session, alice, post)
    receipt = await _receipt(db_session, paid, number="2026-000042")
    await _payment(db_session, alice, post, status="pending")

    pending, done = (await _overview(client, alice))["items"]

    assert (done["receipt_id"], done["receipt_number"]) == (str(receipt.id), "2026-000042")
    assert (pending["receipt_id"], pending["receipt_number"]) == (None, None)


async def test_a_payment_whose_post_is_gone_still_lists_with_the_documents_title(client, alice, db_session):
    ghost = Post(id=uuid.uuid4())
    payment = await _payment(db_session, alice, ghost)
    await _receipt(db_session, payment, title="Title on the document")

    item = (await _overview(client, alice))["items"][0]

    assert (item["post_title"], item["post_status"], item["category_blocked"]) == ("Title on the document", None, False)


@pytest.mark.parametrize("reference", [None, "", "not-a-uuid"])
async def test_a_payment_without_a_usable_post_reference_does_not_break_the_list(client, alice, db_session, reference):
    await _payment(db_session, alice, None, reference=reference)

    item = (await _overview(client, alice))["items"][0]

    assert (item["post_title"], item["post_status"]) == (None, None)


async def test_a_blocked_account_can_still_look(client, make_person, db_session):
    blocked = await make_person(is_blocked=True)
    post = await _post(db_session, blocked, await _category(db_session, blocked))
    await _payment(db_session, blocked, post)

    assert len((await _overview(client, blocked))["items"]) == 1
