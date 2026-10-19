# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the freelancer module's one endpoint: GET
/api/modules/freelancer/provider, the provider details the legal pages show.

Like the other module tests this mounts just the module's router on a
throwaway FastAPI app instead of going through app.main, whose routes depend
on backend/modules.json. The settings are always built with `_env_file=None`
so a developer's own backend/.env never leaks into an expectation."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.freelancer.router import router as freelancer_router
from app.modules.freelancer.settings import ProviderSettings, get_provider_settings

_freelancer_app = FastAPI()
_freelancer_app.include_router(freelancer_router, prefix="/api/modules/freelancer")

URL = "/api/modules/freelancer/provider"

FULL = {
    "name": "Jan Novak",
    "ico": "12345678",
    "dic": "CZ12345678",
    "vat_payer": True,
    "address": "Hlavni 1, 110 00 Praha 1",
    "registration_cs": "Fyzicka osoba zapsana v zivnostenskem rejstriku",
    "registration_en": "A natural person entered in the trade register",
    "email": "jan@example.com",
    "phone": "+420 123 456 789",
    "web": "https://example.com",
    "dpo_email": "gdpr@example.com",
    "effective_from": "2026-11-01",
}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_freelancer_app)


@pytest.fixture()
def use_provider():
    def _use(**values) -> None:
        _freelancer_app.dependency_overrides[get_provider_settings] = lambda: ProviderSettings(_env_file=None, **values)

    yield _use
    _freelancer_app.dependency_overrides.pop(get_provider_settings, None)


def test_nothing_configured_is_empty_and_not_configured(client, use_provider):
    use_provider()

    body = client.get(URL).json()

    assert body["configured"] is False
    assert body["effective_from"] is None
    assert body["vat_payer"] is False
    assert all(body[key] == "" for key in ("name", "ico", "dic", "address", "registration", "email", "phone", "web", "dpo_email"))


def test_everything_configured_is_returned(client, use_provider):
    use_provider(**FULL)

    body = client.get(URL).json()

    assert body == {
        "name": "Jan Novak",
        "ico": "12345678",
        "dic": "CZ12345678",
        "vat_payer": True,
        "address": "Hlavni 1, 110 00 Praha 1",
        "registration": "Fyzicka osoba zapsana v zivnostenskem rejstriku",
        "email": "jan@example.com",
        "phone": "+420 123 456 789",
        "web": "https://example.com",
        "dpo_email": "gdpr@example.com",
        "effective_from": "2026-11-01",
        "configured": True,
    }


@pytest.mark.parametrize("missing", ["name", "ico", "address", "email"])
def test_the_four_minimum_fields_decide_configured(client, use_provider, missing):
    use_provider(**{**FULL, missing: "   "})

    assert client.get(URL).json()["configured"] is False


@pytest.mark.parametrize("optional", ["dic", "phone", "web", "dpo_email", "effective_from", "registration_cs", "registration_en"])
def test_the_optional_fields_do_not_decide_configured(client, use_provider, optional):
    use_provider(**{**FULL, optional: ""})

    assert client.get(URL).json()["configured"] is True


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (None, "cs text"),
        ("cs", "cs text"),
        ("en", "en text"),
        ("en-GB", "en text"),
        ("EN_us", "en text"),
        ("de", "cs text"),
    ],
)
def test_registration_follows_the_language(client, use_provider, language, expected):
    use_provider(registration_cs="cs text", registration_en="en text")

    params = {"language": language} if language else {}
    assert client.get(URL, params=params).json()["registration"] == expected


def test_registration_falls_back_to_the_other_language(client, use_provider):
    use_provider(registration_cs="", registration_en="only english")
    assert client.get(URL, params={"language": "cs"}).json()["registration"] == "only english"

    use_provider(registration_cs="jen cesky", registration_en="")
    assert client.get(URL, params={"language": "en"}).json()["registration"] == "jen cesky"


@pytest.mark.parametrize("web", ["javascript:alert(1)", "ftp://example.com", "example.com", "https://", "//example.com"])
def test_a_web_address_that_is_not_http_is_left_out(client, use_provider, web, caplog):
    use_provider(**{**FULL, "web": web})

    with caplog.at_level("WARNING"):
        body = client.get(URL).json()

    assert body["web"] == ""
    assert "PROVIDER_WEB is not an http(s) URL" in caplog.text


@pytest.mark.parametrize("value", ["1.11.2026", "2026-13-01", "soon", "2026-11"])
def test_an_effective_date_that_is_not_iso_is_left_out(client, use_provider, value, caplog):
    use_provider(**{**FULL, "effective_from": value})

    with caplog.at_level("WARNING"):
        body = client.get(URL).json()

    assert body["effective_from"] is None
    assert "PROVIDER_EFFECTIVE_FROM is not an ISO date" in caplog.text


def test_values_are_trimmed(client, use_provider):
    use_provider(**{**FULL, "name": "  Jan Novak  ", "effective_from": " 2026-11-01 "})

    body = client.get(URL).json()

    assert body["name"] == "Jan Novak"
    assert body["effective_from"] == "2026-11-01"


def test_nothing_beyond_the_provider_fields_is_exposed(client, use_provider):
    use_provider(**FULL)

    body = client.get(URL).json()

    assert set(body) == {
        "name", "ico", "dic", "vat_payer", "address", "registration", "email", "phone", "web", "dpo_email", "effective_from", "configured",
    }


def test_an_overlong_language_is_rejected(client, use_provider):
    use_provider()

    assert client.get(URL, params={"language": "x" * 36}).status_code == 422


def test_settings_are_read_from_provider_prefixed_environment_variables(monkeypatch):
    monkeypatch.setenv("PROVIDER_NAME", "From Env")
    monkeypatch.setenv("PROVIDER_VAT_PAYER", "true")
    monkeypatch.setenv("PROVIDER_REGISTRATION_EN", "Registered")
    monkeypatch.setenv("NAME", "not this one")

    settings = ProviderSettings(_env_file=None)

    assert settings.name == "From Env"
    assert settings.vat_payer is True
    assert settings.registration_en == "Registered"
    assert settings.ico == ""
