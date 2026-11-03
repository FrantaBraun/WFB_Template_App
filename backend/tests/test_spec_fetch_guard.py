# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for fetching a documentation's source_url from this server: it is an
address a user typed in, so it must not reach the server's own network. The
host has to resolve to public addresses only, the connection goes to the
address that was checked, redirects are not followed, the body is read only up
to the size limit - and a refusal is recorded on the document like any failed
check and reported as a 422, never a crash. Where the deployment allows
private addresses (Settings.outbound_allow_private_addresses) the URL is used
as written.

conftest.py switches that allowance on for the rest of the suite, so every
test here builds its own strict Settings. DNS is what the tests say
(safe_http._getaddrinfo is replaced) and the receiver is respx."""

import httpx
import pytest
import respx
from sqlalchemy import func, select

import app.security.jwt as jwt_module
import app.services.safe_http as safe_http
from app.config import Settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.services.api_document_versions import fetch_and_process
from app.services.openapi_spec import SpecValidationError, fetch_spec_from_url
from tests.version_support import make_document, make_team, make_user, pets_spec, request, spec_bytes, token_for

PUBLIC = "93.184.216.34"
LIMIT = 10_000


@pytest.fixture(autouse=True)
def _signed_in(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


def _dns(monkeypatch, *addresses: str) -> list[str]:
    lookups: list[str] = []

    async def fake(host: str, port: int) -> list[str]:
        lookups.append(host)
        return list(addresses)

    monkeypatch.setattr(safe_http, "_getaddrinfo", fake)
    return lookups


def _strict(tmp_path, **overrides) -> Settings:
    values = {
        "uploads_dir": str(tmp_path),
        "spec_fetch_timeout_seconds": 2.0,
        "max_spec_file_size_bytes": LIMIT,
        "outbound_allow_private_addresses": False,
    }
    values.update(overrides)
    return Settings(**values)


async def _fetch(url: str, **kwargs) -> bytes:
    return await fetch_spec_from_url(url, 2.0, max_bytes=kwargs.pop("max_bytes", LIMIT), **kwargs)


# --- fetch_spec_from_url ------------------------------------------------------------


@respx.mock
async def test_a_public_host_is_fetched_through_the_address_that_was_checked(monkeypatch):
    _dns(monkeypatch, PUBLIC)
    route = respx.get(f"https://{PUBLIC}/openapi.json").mock(return_value=httpx.Response(200, content=b'{"a":1}'))

    body = await _fetch("https://api.example.com/openapi.json")

    assert body == b'{"a":1}'
    request_sent = route.calls.last.request
    assert request_sent.url.host == PUBLIC  # not the host name again
    assert request_sent.headers["host"] == "api.example.com"
    assert request_sent.extensions["sni_hostname"] == "api.example.com"


@respx.mock
async def test_plain_http_is_fine_for_a_public_host(monkeypatch):
    """Plenty of public specifications are served over http - what makes the call safe is the address."""
    _dns(monkeypatch, PUBLIC)
    route = respx.get(f"http://{PUBLIC}/v2/swagger.json").mock(return_value=httpx.Response(200, content=b"{}"))

    assert await _fetch("http://petstore.example.com/v2/swagger.json") == b"{}"
    assert route.calls.last.request.headers["host"] == "petstore.example.com"


@respx.mock
@pytest.mark.parametrize("resolved", [["10.0.0.5"], ["127.0.0.1"], ["169.254.169.254"], ["::1"], [PUBLIC, "192.168.1.9"]])
async def test_a_host_that_resolves_to_a_non_public_address_is_refused_and_not_called(monkeypatch, resolved):
    _dns(monkeypatch, *resolved)
    route = respx.route().mock(return_value=httpx.Response(200, content=b"{}"))

    with pytest.raises(SpecValidationError, match="not a public one"):
        await _fetch("https://docs.internal.example.com/openapi.json")

    assert not route.called


@respx.mock
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # the cloud metadata address, written out
        "http://127.0.0.1:5432/",
        "http://[::1]/openapi.json",
        "http://10.1.2.3/openapi.json",
        "http://0.0.0.0/openapi.json",
    ],
)
async def test_an_address_written_out_is_judged_without_a_lookup(monkeypatch, url):
    lookups = _dns(monkeypatch, PUBLIC)
    route = respx.route().mock(return_value=httpx.Response(200))

    with pytest.raises(SpecValidationError):
        await _fetch(url)

    assert lookups == [] and not route.called


@respx.mock
@pytest.mark.parametrize("url", ["ftp://example.com/openapi.json", "file:///etc/passwd", "https://user:pw@example.com/openapi.json", "//example.com/x", "not a url"])
async def test_other_schemes_and_credentials_in_the_url_are_refused(monkeypatch, url):
    _dns(monkeypatch, PUBLIC)
    route = respx.route().mock(return_value=httpx.Response(200))

    with pytest.raises(SpecValidationError):
        await _fetch(url)

    assert not route.called


async def test_a_host_that_does_not_resolve_is_refused(monkeypatch):
    async def nowhere(host: str, port: int) -> list[str]:
        raise OSError("not found")

    monkeypatch.setattr(safe_http, "_getaddrinfo", nowhere)

    with pytest.raises(SpecValidationError, match="cannot be resolved"):
        await _fetch("https://nowhere.example.com/openapi.json")


@respx.mock
async def test_a_redirect_is_not_followed(monkeypatch):
    """Where it leads was never checked - it could be the metadata address."""
    _dns(monkeypatch, PUBLIC)
    first = respx.get(f"https://{PUBLIC}/openapi.json").mock(
        return_value=httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
    )
    elsewhere = respx.route(host="169.254.169.254").mock(return_value=httpx.Response(200, content=b"secret"))

    with pytest.raises(httpx.HTTPStatusError) as caught:
        await _fetch("https://api.example.com/openapi.json")

    assert caught.value.response.status_code == 302 and "302" in str(caught.value)
    assert first.call_count == 1 and not elsewhere.called


@respx.mock
async def test_a_non_2xx_answer_is_an_http_status_error_with_the_status(monkeypatch):
    _dns(monkeypatch, PUBLIC)
    respx.get(f"https://{PUBLIC}/openapi.json").mock(return_value=httpx.Response(404))

    with pytest.raises(httpx.HTTPStatusError) as caught:
        await _fetch("https://api.example.com/openapi.json")

    assert caught.value.response.status_code == 404 and "404" in str(caught.value)


@respx.mock
async def test_a_body_over_the_limit_is_refused_and_one_at_the_limit_is_not(monkeypatch):
    _dns(monkeypatch, PUBLIC)
    route = respx.get(f"https://{PUBLIC}/openapi.json")

    route.mock(return_value=httpx.Response(200, content=b"x" * LIMIT))
    assert len(await _fetch("https://api.example.com/openapi.json")) == LIMIT

    route.mock(return_value=httpx.Response(200, content=b"x" * (LIMIT * 100)))
    with pytest.raises(SpecValidationError, match=f"larger than the {LIMIT} byte limit"):
        await _fetch("https://api.example.com/openapi.json")


@respx.mock
@pytest.mark.parametrize("failure", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
async def test_connection_failures_stay_httpx_errors(monkeypatch, failure):
    _dns(monkeypatch, PUBLIC)
    respx.get(f"https://{PUBLIC}/openapi.json").mock(side_effect=failure)

    with pytest.raises(type(failure)):
        await _fetch("https://api.example.com/openapi.json")


@respx.mock
async def test_where_private_addresses_are_allowed_the_url_is_used_as_written(monkeypatch):
    lookups = _dns(monkeypatch, "127.0.0.1")
    route = respx.get("http://localhost:9000/openapi.json").mock(return_value=httpx.Response(200, content=b"{}"))

    assert await _fetch("http://localhost:9000/openapi.json", allow_private=True) == b"{}"
    assert route.called and lookups == []


# --- a check that is refused --------------------------------------------------------


@respx.mock
async def test_a_refused_check_is_recorded_on_the_document_and_creates_no_version(db_session, tmp_path, monkeypatch):
    _dns(monkeypatch, "10.0.0.5")
    doc = await make_document(db_session, source_url="https://docs.internal.example.com/openapi.json")
    route = respx.route().mock(return_value=httpx.Response(200, content=spec_bytes(pets_spec())))

    with pytest.raises(SpecValidationError):
        await fetch_and_process(doc, source="auto_recheck", db=db_session, settings=_strict(tmp_path))

    await db_session.refresh(doc)
    assert doc.last_check_error == "The address is not a public one"
    assert not route.called
    assert await db_session.scalar(select(func.count()).select_from(ApiDocumentVersion).where(ApiDocumentVersion.documentation_id == doc.id)) == 0


@respx.mock
async def test_an_oversized_download_is_recorded_too(db_session, tmp_path, monkeypatch):
    _dns(monkeypatch, PUBLIC)
    doc = await make_document(db_session, source_url="https://api.example.com/openapi.json")
    respx.get(f"https://{PUBLIC}/openapi.json").mock(return_value=httpx.Response(200, content=b"x" * (LIMIT * 5)))

    with pytest.raises(SpecValidationError):
        await fetch_and_process(doc, source="auto_recheck", db=db_session, settings=_strict(tmp_path))

    await db_session.refresh(doc)
    assert "byte limit" in doc.last_check_error


@respx.mock
async def test_a_public_documentation_is_still_fetched_and_recorded(db_session, tmp_path, monkeypatch):
    _dns(monkeypatch, PUBLIC)
    doc = await make_document(db_session, source_url="https://api.example.com/openapi.json")
    respx.get(f"https://{PUBLIC}/openapi.json").mock(return_value=httpx.Response(200, content=spec_bytes(pets_spec("1.2.3"))))

    version = await fetch_and_process(doc, source="auto_recheck", db=db_session, settings=_strict(tmp_path))

    assert version.version == "1.2.3" and doc.last_check_error is None


# --- through the API ----------------------------------------------------------------


@respx.mock
async def test_a_recheck_of_a_private_address_is_a_422_that_says_why(db_session, make_access_token, tmp_path, monkeypatch):
    _dns(monkeypatch, "169.254.169.254")
    owner = await make_user(db_session, email="owner@example.com")
    doc = await make_document(db_session, members=(owner,), source_url="https://metadata.example.com/latest")
    route = respx.route().mock(return_value=httpx.Response(200))

    resp = await request(
        db_session, "POST", f"/api/api-docs/{doc.id}/recheck", token=token_for(make_access_token, owner), settings=_strict(tmp_path)
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "The address is not a public one"
    assert not route.called
    await db_session.refresh(doc)
    assert doc.last_check_error == "The address is not a public one"


@respx.mock
async def test_creating_a_documentation_by_a_private_url_is_refused_but_the_row_is_kept(db_session, make_access_token, tmp_path, monkeypatch):
    """Like any failed first fetch: the row stays so the address can be fixed and rechecked."""
    _dns(monkeypatch, "10.0.0.5")
    owner = await make_user(db_session, email="owner@example.com")
    team = await make_team(db_session, "Owners", members=(owner,))
    route = respx.route().mock(return_value=httpx.Response(200))

    resp = await request(
        db_session,
        "POST",
        "/api/api-docs",
        token=token_for(make_access_token, owner),
        settings=_strict(tmp_path),
        json={"team_id": str(team.id), "title": "Internal", "source_url": "https://docs.internal.example.com/openapi.json"},
    )

    assert resp.status_code == 422 and "not a public one" in resp.json()["detail"]
    assert not route.called
    kept = (await db_session.execute(select(ApiDocument).where(ApiDocument.team_id == team.id))).scalar_one()
    assert kept.last_check_error == "The address is not a public one"


@respx.mock
async def test_the_same_documentation_is_fetched_where_private_addresses_are_allowed(db_session, make_access_token, tmp_path, monkeypatch):
    lookups = _dns(monkeypatch, "10.0.0.5")
    owner = await make_user(db_session, email="owner@example.com")
    doc = await make_document(db_session, members=(owner,), source_url="http://docs.internal.example.com/openapi.json")
    respx.get("http://docs.internal.example.com/openapi.json").mock(return_value=httpx.Response(200, content=spec_bytes(pets_spec("1.0.0"))))

    resp = await request(
        db_session,
        "POST",
        f"/api/api-docs/{doc.id}/recheck",
        token=token_for(make_access_token, owner),
        settings=_strict(tmp_path, outbound_allow_private_addresses=True),
    )

    assert resp.status_code == 200 and resp.json()["current_version"]["version"] == "1.0.0"
    assert lookups == []
