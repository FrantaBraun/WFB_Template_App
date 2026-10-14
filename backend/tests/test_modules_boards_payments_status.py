# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Why payments are off, and the two places that say so: the console at
startup and the administrators' endpoint behind the moderation page's notice.

Payments are offered only where the gateway module is on, both Stripe keys
are set and the provider's details are filled in - and with any of them
missing the frontend just leaves the payment options out. These tests pin the
conditions down in one place and keep the public GET /payments, the
administrators' view and the console from ever disagreeing about them."""

import logging
import sys
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.boards import manifest, payments_status
from app.modules.boards.config import BoardsConfig, InvoicingConfig, ProviderConfig, get_config
from app.modules.boards.payments_status import Problem
from app.modules.boards.router import gateway_enabled
from app.modules.boards.router import router as boards_router
from app.modules.registry import run_startup_hooks

BASE = "/api/modules/boards"
SECRET = "sk_live_must-never-appear-in-a-log"
WEBHOOK = "whsec_must-never-appear-in-a-log"

COMPLETE = ProviderConfig(name="Jan Novák", ico="12345678", address="Ulice 1, Praha", email="info@example.com")


def _settings(secret=SECRET, webhook=WEBHOOK) -> Settings:
    return Settings(stripe_secret_key=secret, stripe_webhook_secret=webhook)


def _config(provider: ProviderConfig = COMPLETE) -> BoardsConfig:
    return BoardsConfig(invoicing=InvoicingConfig(provider=provider))


def _codes(found: list[Problem]) -> list[str]:
    return [p.code for p in found]


ON = ["boards", "stripe_payment_gate"]


# --- The provider's missing fields --------------------------------------------


def test_a_complete_provider_misses_nothing():
    assert COMPLETE.missing_fields() == []
    assert COMPLETE.complete is True


def test_an_empty_provider_misses_the_four_required_fields():
    assert ProviderConfig().missing_fields() == ["name", "ico", "address", "email"]
    assert ProviderConfig().complete is False


@pytest.mark.parametrize("blank", ["name", "ico", "address", "email"])
def test_each_required_field_is_reported_when_it_alone_is_blank(blank):
    fields = {"name": "Jan", "ico": "1", "address": "Praha", "email": "a@b.cz", blank: ""}
    assert ProviderConfig(**fields).missing_fields() == [blank]


def test_a_field_of_only_spaces_counts_as_blank():
    assert ProviderConfig(name="  ", ico="1", address="Praha", email="a@b.cz").missing_fields() == ["name"]


def test_the_optional_fields_are_not_required():
    assert ProviderConfig(name="Jan", ico="1", address="Praha", email="a@b.cz", dic="", phone="", web="").complete


# --- The conditions -----------------------------------------------------------


def test_nothing_is_wrong_when_everything_is_in_place():
    assert payments_status.problems(_settings(), _config(), ON) == []


def test_each_condition_is_reported_on_its_own():
    assert _codes(payments_status.problems(_settings(), _config(), ["boards"])) == ["gateway_module_disabled"]
    assert _codes(payments_status.problems(_settings(secret=""), _config(), ON)) == ["stripe_secret_key_missing"]
    assert _codes(payments_status.problems(_settings(webhook=""), _config(), ON)) == ["stripe_webhook_secret_missing"]
    assert _codes(payments_status.problems(_settings(), _config(ProviderConfig()), ON)) == ["provider_incomplete"]


def test_every_condition_is_reported_together_so_one_fix_is_not_followed_by_another_surprise():
    found = payments_status.problems(_settings(secret="", webhook=""), _config(ProviderConfig(name="Jan")), [])

    assert _codes(found) == [
        "gateway_module_disabled",
        "stripe_secret_key_missing",
        "stripe_webhook_secret_missing",
        "provider_incomplete",
    ]
    assert found[-1].missing == ("ico", "address", "email")


def test_an_unrelated_enabled_module_does_not_count_as_the_gateway():
    assert _codes(payments_status.problems(_settings(), _config(), ["boards", "notifications"])) == ["gateway_module_disabled"]


# --- The public answer and the administrators' agree --------------------------

_app = FastAPI()
_app.include_router(boards_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


def _set(monkeypatch, *, modules, settings, config):
    """Make the app see this configuration - in the router, the administrators' router and the logger alike."""
    _app.dependency_overrides[get_settings] = lambda: settings
    _app.dependency_overrides[get_config] = lambda: config
    for name in ("router", "admin_router"):
        monkeypatch.setattr(sys.modules[f"app.modules.boards.{name}"], "load_enabled_module_keys", lambda: modules)
    monkeypatch.setattr(payments_status, "get_settings", lambda: settings)
    monkeypatch.setattr(payments_status, "get_config", lambda: config)
    monkeypatch.setattr(payments_status, "load_enabled_module_keys", lambda: modules)


COMBINATIONS = [
    pytest.param(ON, _settings(), COMPLETE, id="all in place"),
    pytest.param(["boards"], _settings(), COMPLETE, id="module off"),
    pytest.param(ON, _settings(secret=""), COMPLETE, id="no secret key"),
    pytest.param(ON, _settings(webhook=""), COMPLETE, id="no webhook secret"),
    pytest.param(ON, _settings(), ProviderConfig(), id="no provider"),
    pytest.param(ON, _settings(), ProviderConfig(name="Jan", ico="1", address="Praha"), id="no provider email"),
    pytest.param([], _settings(secret="", webhook=""), ProviderConfig(), id="nothing"),
]


@pytest.mark.parametrize(("modules", "settings", "provider"), COMBINATIONS)
async def test_the_public_flag_is_on_exactly_when_nothing_is_wrong(client, monkeypatch, modules, settings, provider):
    _set(monkeypatch, modules=modules, settings=settings, config=_config(provider))
    _app.dependency_overrides.pop(gateway_enabled, None)

    public = (await client.get(f"{BASE}/payments")).json()["enabled"]

    assert public is (payments_status.problems(settings, _config(provider), modules) == [])


# --- The administrators' endpoint ---------------------------------------------


@pytest.fixture()
def make_person(db_session, make_access_token):
    async def _make(**fields):
        sub = uuid.uuid4()
        db_session.add(User(auth_sub=sub, **fields))
        await db_session.commit()
        return {"Authorization": f"Bearer {make_access_token(sub=str(sub))}"}

    return _make


async def test_only_administrators_may_ask_why_payments_are_off(client, make_person, monkeypatch):
    _set(monkeypatch, modules=ON, settings=_settings(), config=_config())
    ordinary = await make_person()

    anonymous = await client.get(f"{BASE}/manage/payments-status")
    refused = await client.get(f"{BASE}/manage/payments-status", headers=ordinary)

    assert (anonymous.status_code, refused.status_code) == (401, 403)


async def test_an_administrator_is_told_payments_are_on(client, make_person, monkeypatch):
    _set(monkeypatch, modules=ON, settings=_settings(), config=_config())
    admin = await make_person(is_admin=True)

    resp = await client.get(f"{BASE}/manage/payments-status", headers=admin)

    assert (resp.status_code, resp.json()) == (200, {"enabled": True, "problems": []})


async def test_an_administrator_is_told_every_reason_and_the_blank_fields(client, make_person, monkeypatch):
    _set(monkeypatch, modules=["boards"], settings=_settings(secret=""), config=_config(ProviderConfig(name="Jan")))
    admin = await make_person(is_admin=True)

    body = (await client.get(f"{BASE}/manage/payments-status", headers=admin)).json()

    assert body["enabled"] is False
    assert body["problems"] == [
        {"code": "gateway_module_disabled", "missing": []},
        {"code": "stripe_secret_key_missing", "missing": []},
        {"code": "provider_incomplete", "missing": ["ico", "address", "email"]},
    ]


async def test_the_administrators_answer_never_contains_a_secret(client, make_person, monkeypatch):
    _set(monkeypatch, modules=["boards"], settings=_settings(webhook=""), config=_config(ProviderConfig()))
    admin = await make_person(is_admin=True)

    text = (await client.get(f"{BASE}/manage/payments-status", headers=admin)).text

    assert SECRET not in text and WEBHOOK not in text


# --- The console --------------------------------------------------------------


def test_the_console_warns_once_listing_every_reason_and_how_to_fix_it(monkeypatch, caplog):
    _set(monkeypatch, modules=["boards"], settings=_settings(secret=""), config=_config(ProviderConfig(name="Jan")))

    with caplog.at_level(logging.INFO, logger=payments_status.logger.name):
        payments_status.log_payments_status()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1  # one block, not a line per reason scattered among others
    text = warnings[0].getMessage()
    assert "Payments are OFF" in text
    assert "backend/modules.json" in text
    assert "STRIPE_SECRET_KEY is not set in backend/.env" in text
    assert "backend/modules/boards.json" in text and "missing ico, address, email" in text
    assert "frontend/public/legal.json" in text
    assert "Restart the backend" in text
    assert "STRIPE_WEBHOOK_SECRET" not in text  # that one is set - only what is wrong is listed


def test_the_console_says_when_payments_are_on_and_does_not_warn(monkeypatch, caplog):
    _set(monkeypatch, modules=ON, settings=_settings(), config=_config())

    with caplog.at_level(logging.INFO, logger=payments_status.logger.name):
        payments_status.log_payments_status()

    assert [r.getMessage() for r in caplog.records] == ["Payments are on"]


@pytest.mark.parametrize("settings", [_settings(), _settings(secret=""), _settings(webhook="")], ids=["both set", "no secret key", "no webhook secret"])
def test_the_console_never_prints_a_secret(monkeypatch, caplog, settings):
    """Whichever key is missing, the other one - which is set - must not turn up in the explanation."""
    _set(monkeypatch, modules=["boards"], settings=settings, config=_config(ProviderConfig()))

    with caplog.at_level(logging.DEBUG):
        payments_status.log_payments_status()

    assert SECRET not in caplog.text and WEBHOOK not in caplog.text


def test_the_boards_module_registers_the_check_to_run_at_startup(monkeypatch, caplog):
    assert manifest.on_startup is payments_status.log_payments_status
    _set(monkeypatch, modules=["boards"], settings=_settings(), config=_config())

    with caplog.at_level(logging.WARNING, logger=payments_status.logger.name):
        run_startup_hooks(["boards"])  # what the application's lifespan does

    assert any("Payments are OFF" in r.getMessage() for r in caplog.records)


def test_a_disabled_boards_module_says_nothing(monkeypatch, caplog):
    _set(monkeypatch, modules=[], settings=_settings(), config=_config())

    with caplog.at_level(logging.INFO, logger=payments_status.logger.name):
        run_startup_hooks([])

    assert caplog.records == []


async def test_the_applications_startup_runs_the_enabled_modules_hooks(monkeypatch):
    """The wiring in main.py: without it the hook exists but nothing ever calls it."""
    import app.main as main

    calls = []

    class Closable:
        async def aclose(self):
            pass

        async def dispose(self):
            pass

    monkeypatch.setattr(main, "run_startup_hooks", lambda keys: calls.append(list(keys)))
    monkeypatch.setattr(main, "load_enabled_module_keys", lambda: ["boards"])
    monkeypatch.setattr(main, "auth_client", Closable())
    monkeypatch.setattr(main, "engine", Closable())

    async with main.lifespan(main.app):
        assert calls == [["boards"]]
