# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the crm module's partner and task endpoints and its
administrator-only gate (invoice uploads: test_modules_crm_invoices.py).

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` (whether the module is mounted on the real app
depends on the branch's backend/modules.json - see
test_modules_notifications_router.py). ASGITransport keeps the JWT
dependency chain and db_session on one event loop. Each test starts from
empty crm tables (inside its own rolled-back transaction)."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.crm import manifest
from app.modules.crm.models import Invoice, Partner, Task
from app.modules.crm.router import router as crm_router

BASE = "/api/modules/crm"

_crm_app = FastAPI()
_crm_app.include_router(crm_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, tmp_path, rsa_keypair, monkeypatch):
    for model in (Invoice, Task, Partner):
        await db_session.execute(delete(model))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    settings = Settings(uploads_dir=str(tmp_path))
    _crm_app.dependency_overrides[get_db] = lambda: db_session
    _crm_app.dependency_overrides[get_settings] = lambda: settings
    yield
    _crm_app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_crm_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    """An administrator of this application (local User.is_admin) - with a
    plain auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    """Not an administrator here - even though the auth service calls them
    "admin": role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


async def _partner(client, admin, **fields) -> dict:
    resp = await client.post(f"{BASE}/partners", json={"name": "Jana Nováková", **fields}, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _task(client, admin, partner_id: str, **fields) -> dict:
    resp = await client.post(
        f"{BASE}/partners/{partner_id}/tasks", json={"title": "Nový web", **fields}, headers=admin
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_manifest_key_matches_its_folder():
    assert manifest.key == "crm"
    assert manifest.router is crm_router


# --- Administrator-only gate ---------------------------------------------------


def _all_routes():
    return [(method, route.path) for route in crm_router.routes for method in sorted(route.methods)]


async def _call(client, method: str, path: str, headers: dict):
    concrete = path.replace("{partner_id}", str(uuid.uuid4())).replace("{task_id}", str(uuid.uuid4()))
    concrete = concrete.replace("{invoice_id}", str(uuid.uuid4()))
    return await client.request(method, f"{BASE}{concrete}", headers=headers)


@pytest.mark.parametrize(("method", "path"), _all_routes())
async def test_anonymous_requests_are_rejected_on_every_route(client, method, path):
    resp = await _call(client, method, path, headers={})

    assert resp.status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _all_routes())
async def test_non_admins_are_rejected_on_every_route(client, non_admin, method, path):
    resp = await _call(client, method, path, headers=non_admin)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


# --- Partners -----------------------------------------------------------------


async def test_create_and_get_partner(client, admin):
    created = await _partner(
        client,
        admin,
        company="Novák s.r.o.",
        company_id="12345678",
        vat_id="CZ12345678",
        address="Hlavní 1\n110 00 Praha",
        email="jana@example.com",
        phone="+420 123 456 789",
        notes="Doporučení od Petra.",
    )

    resp = await client.get(f"{BASE}/partners/{created['id']}", headers=admin)

    assert resp.status_code == 200
    assert resp.json() == created
    assert created["name"] == "Jana Nováková"
    assert created["company"] == "Novák s.r.o."
    assert created["company_id"] == "12345678"
    assert created["vat_id"] == "CZ12345678"
    assert created["email"] == "jana@example.com"
    assert created["archived"] is False


async def test_partner_text_is_stripped_and_blank_optionals_become_null(client, admin):
    created = await _partner(client, admin, name="  Jana  ", company="  ", email="", phone="", company_id=" ")

    assert created["name"] == "Jana"
    assert created["company"] is None
    assert created["email"] is None
    assert created["phone"] is None
    assert created["company_id"] is None
    assert created["address"] == ""


@pytest.mark.parametrize(
    "body",
    [{}, {"name": ""}, {"name": "   "}, {"name": "x", "email": "not-an-email"}, {"name": "x" * 201}],
)
async def test_create_partner_rejects_invalid_input(client, admin, body):
    resp = await client.post(f"{BASE}/partners", json=body, headers=admin)

    assert resp.status_code == 422


async def test_get_unknown_partner_is_404(client, admin):
    resp = await client.get(f"{BASE}/partners/{uuid.uuid4()}", headers=admin)

    assert resp.status_code == 404


async def test_list_partners_sorted_by_name_with_task_counts(client, admin):
    zeta = await _partner(client, admin, name="Zeta")
    await _partner(client, admin, name="alfa")
    await _task(client, admin, zeta["id"], title="One")
    await _task(client, admin, zeta["id"], title="Two")

    resp = await client.get(f"{BASE}/partners", headers=admin)

    assert resp.status_code == 200
    assert [(p["name"], p["task_count"]) for p in resp.json()] == [("alfa", 0), ("Zeta", 2)]


async def test_list_partners_hides_archived_unless_asked(client, admin):
    await _partner(client, admin, name="Active")
    archived = await _partner(client, admin, name="Gone")
    await client.patch(f"{BASE}/partners/{archived['id']}", json={"archived": True}, headers=admin)

    default = await client.get(f"{BASE}/partners", headers=admin)
    everything = await client.get(f"{BASE}/partners", params={"include_archived": "true"}, headers=admin)

    assert [p["name"] for p in default.json()] == ["Active"]
    assert [p["name"] for p in everything.json()] == ["Active", "Gone"]


async def test_search_matches_name_company_email_and_company_id(client, admin):
    await _partner(client, admin, name="Alice", company="Zebra Ltd")
    await _partner(client, admin, name="Bob", email="bob@findme.example")
    await _partner(client, admin, name="Carol", company_id="87654321")
    await _partner(client, admin, name="Dave")

    async def search(q):
        resp = await client.get(f"{BASE}/partners", params={"q": q}, headers=admin)
        return [p["name"] for p in resp.json()]

    assert await search("zebra") == ["Alice"]
    assert await search("FINDME") == ["Bob"]
    assert await search("8765") == ["Carol"]
    assert await search("ali") == ["Alice"]
    assert await search("nobody") == []


async def test_search_treats_like_wildcards_literally(client, admin):
    await _partner(client, admin, name="Plain")
    await _partner(client, admin, name="100% Fresh")

    resp = await client.get(f"{BASE}/partners", params={"q": "%"}, headers=admin)

    assert [p["name"] for p in resp.json()] == ["100% Fresh"]


async def test_update_partner_changes_only_sent_fields(client, admin):
    created = await _partner(client, admin, company="Old", phone="123")

    resp = await client.patch(
        f"{BASE}/partners/{created['id']}", json={"notes": "Called back", "company": ""}, headers=admin
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"] == "Called back"
    assert body["company"] is None
    assert body["phone"] == "123"
    assert body["name"] == "Jana Nováková"


@pytest.mark.parametrize("body", [{"name": None}, {"name": ""}, {"notes": None}, {"archived": None}, {"email": "x"}])
async def test_update_partner_rejects_invalid_input(client, admin, body):
    created = await _partner(client, admin)

    resp = await client.patch(f"{BASE}/partners/{created['id']}", json=body, headers=admin)

    assert resp.status_code == 422


async def test_update_unknown_partner_is_404(client, admin):
    resp = await client.patch(f"{BASE}/partners/{uuid.uuid4()}", json={"name": "x"}, headers=admin)

    assert resp.status_code == 404


async def test_delete_partner_without_tasks(client, admin):
    created = await _partner(client, admin)

    resp = await client.delete(f"{BASE}/partners/{created['id']}", headers=admin)

    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/partners/{created['id']}", headers=admin)).status_code == 404


async def test_delete_partner_with_tasks_is_refused(client, admin):
    created = await _partner(client, admin)
    await _task(client, admin, created["id"])

    resp = await client.delete(f"{BASE}/partners/{created['id']}", headers=admin)

    assert resp.status_code == 409
    assert (await client.get(f"{BASE}/partners/{created['id']}", headers=admin)).status_code == 200


# --- Tasks --------------------------------------------------------------------


async def test_create_task_applies_defaults(client, admin):
    partner = await _partner(client, admin)

    task = await _task(client, admin, partner["id"])

    assert task["partner_id"] == partner["id"]
    assert task["title"] == "Nový web"
    assert task["status"] == "new"
    assert task["currency"] == "CZK"
    assert task["price"] is None
    assert task["description"] == ""
    assert task["start_date"] is None and task["due_date"] is None


async def test_create_task_with_all_fields(client, admin):
    partner = await _partner(client, admin)

    task = await _task(
        client,
        admin,
        partner["id"],
        description="Přepis webu",
        status="in_progress",
        price="15000.5",
        currency="eur",
        start_date="2026-10-01",
        due_date="2026-11-15",
    )

    assert task["status"] == "in_progress"
    assert task["price"] == "15000.50"
    assert task["currency"] == "EUR"
    assert task["start_date"] == "2026-10-01"
    assert task["due_date"] == "2026-11-15"


async def test_create_task_for_unknown_partner_is_404(client, admin):
    resp = await client.post(f"{BASE}/partners/{uuid.uuid4()}/tasks", json={"title": "x"}, headers=admin)

    assert resp.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": " "},
        {"title": "x", "status": "someday"},
        {"title": "x", "price": -1},
        {"title": "x", "price": "1.234"},
        {"title": "x", "currency": "CZKK"},
        {"title": "x", "currency": "12"},
        {"title": "x", "start_date": "2026-12-01", "due_date": "2026-11-01"},
        {"title": "x", "due_date": "not-a-date"},
    ],
)
async def test_create_task_rejects_invalid_input(client, admin, body):
    partner = await _partner(client, admin)

    resp = await client.post(f"{BASE}/partners/{partner['id']}/tasks", json=body, headers=admin)

    assert resp.status_code == 422


async def test_update_task_changes_only_sent_fields_and_can_clear_price(client, admin):
    partner = await _partner(client, admin)
    task = await _task(client, admin, partner["id"], price="100", due_date="2026-11-01")

    resp = await client.patch(f"{BASE}/tasks/{task['id']}", json={"status": "done"}, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert resp.json()["price"] == "100.00"
    assert resp.json()["due_date"] == "2026-11-01"

    cleared = await client.patch(f"{BASE}/tasks/{task['id']}", json={"price": None, "due_date": None}, headers=admin)
    assert cleared.json()["price"] is None
    assert cleared.json()["due_date"] is None
    assert cleared.json()["status"] == "done"


@pytest.mark.parametrize("body", [{"title": None}, {"title": ""}, {"status": None}, {"status": "x"}, {"currency": None}])
async def test_update_task_rejects_invalid_input(client, admin, body):
    partner = await _partner(client, admin)
    task = await _task(client, admin, partner["id"])

    resp = await client.patch(f"{BASE}/tasks/{task['id']}", json=body, headers=admin)

    assert resp.status_code == 422


async def test_update_task_checks_date_order_against_the_stored_dates(client, admin):
    partner = await _partner(client, admin)
    task = await _task(client, admin, partner["id"], start_date="2026-10-10", due_date="2026-10-20")

    resp = await client.patch(f"{BASE}/tasks/{task['id']}", json={"due_date": "2026-10-01"}, headers=admin)

    assert resp.status_code == 422
    unchanged = (await client.get(f"{BASE}/tasks/{task['id']}", headers=admin)).json()
    assert unchanged["due_date"] == "2026-10-20"


async def test_update_unknown_task_is_404(client, admin):
    resp = await client.patch(f"{BASE}/tasks/{uuid.uuid4()}", json={"title": "x"}, headers=admin)

    assert resp.status_code == 404


async def test_list_partner_tasks_newest_first_and_only_that_partners(client, admin, db_session):
    partner = await _partner(client, admin)
    other = await _partner(client, admin, name="Other")
    first = await _task(client, admin, partner["id"], title="First")
    second = await _task(client, admin, partner["id"], title="Second")
    await _task(client, admin, other["id"], title="Elsewhere")
    # now() is the transaction's start time, and this whole test is one transaction.
    await db_session.execute(
        update(Task).where(Task.id == uuid.UUID(first["id"])).values(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    )
    await db_session.execute(
        update(Task).where(Task.id == uuid.UUID(second["id"])).values(created_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
    )
    db_session.add(
        Invoice(task_id=uuid.UUID(first["id"]), original_filename="a.pdf", stored_name="a" * 32 + ".pdf", size_bytes=1)
    )
    await db_session.commit()

    resp = await client.get(f"{BASE}/partners/{partner['id']}/tasks", headers=admin)

    assert resp.status_code == 200
    assert [(t["title"], t["invoice_count"]) for t in resp.json()] == [("Second", 0), ("First", 1)]
    assert resp.json()[0]["id"] == second["id"]


async def test_list_tasks_of_unknown_partner_is_404(client, admin):
    resp = await client.get(f"{BASE}/partners/{uuid.uuid4()}/tasks", headers=admin)

    assert resp.status_code == 404


async def test_get_task_includes_partner_and_invoices(client, admin, db_session):
    partner = await _partner(client, admin, company="Novák s.r.o.")
    task = await _task(client, admin, partner["id"])
    db_session.add(
        Invoice(
            task_id=uuid.UUID(task["id"]),
            number="2026-001",
            original_filename="faktura.pdf",
            stored_name="b" * 32 + ".pdf",
            size_bytes=1234,
        )
    )
    await db_session.commit()

    resp = await client.get(f"{BASE}/tasks/{task['id']}", headers=admin)

    assert resp.status_code == 200
    body = resp.json()
    assert body["partner"] == {"id": partner["id"], "name": "Jana Nováková", "company": "Novák s.r.o."}
    assert [(i["number"], i["original_filename"], i["size_bytes"]) for i in body["invoices"]] == [
        ("2026-001", "faktura.pdf", 1234)
    ]
    assert "stored_name" not in body["invoices"][0]


async def test_get_unknown_task_is_404(client, admin):
    resp = await client.get(f"{BASE}/tasks/{uuid.uuid4()}", headers=admin)

    assert resp.status_code == 404


async def test_delete_task_without_invoices(client, admin):
    partner = await _partner(client, admin)
    task = await _task(client, admin, partner["id"])

    resp = await client.delete(f"{BASE}/tasks/{task['id']}", headers=admin)

    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/tasks/{task['id']}", headers=admin)).status_code == 404
    # The partner is untouched, and now has no tasks left to block its deletion.
    assert (await client.delete(f"{BASE}/partners/{partner['id']}", headers=admin)).status_code == 204


async def test_delete_task_with_invoices_is_refused(client, admin, db_session):
    partner = await _partner(client, admin)
    task = await _task(client, admin, partner["id"])
    db_session.add(
        Invoice(task_id=uuid.UUID(task["id"]), original_filename="a.pdf", stored_name="c" * 32 + ".pdf", size_bytes=1)
    )
    await db_session.commit()

    resp = await client.delete(f"{BASE}/tasks/{task['id']}", headers=admin)

    assert resp.status_code == 409
    assert (await client.get(f"{BASE}/tasks/{task['id']}", headers=admin)).status_code == 200
