# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.safe_http: that a URL a user typed in cannot aim the
server at its own network - which addresses count as public, what a URL may
look like, that every resolved address is checked, that the connection goes
to the address that was checked (with the original Host and TLS name), that
redirects are not followed and that a hostile answer is read only so far.

Nothing here touches the network: DNS is what the tests say it is (`_getaddrinfo`
is replaced) and the HTTP side is respx."""

import ipaddress

import httpx
import pytest
import respx

import app.services.safe_http as safe_http
from app.services.safe_http import (
    MAX_RESPONSE_BYTES,
    UnsafeUrlError,
    check_url,
    is_public_address,
    resolve_public,
    safe_post,
    split_url,
)

PUBLIC = "93.184.216.34"


def _dns(monkeypatch, *addresses: str) -> list[tuple[str, int]]:
    """Make every host name resolve to `addresses`; the list collects the lookups."""
    lookups: list[tuple[str, int]] = []

    async def fake(host: str, port: int) -> list[str]:
        lookups.append((host, port))
        return list(addresses)

    monkeypatch.setattr(safe_http, "_getaddrinfo", fake)
    return lookups


# --- which addresses are public -----------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "127.1.2.3", "10.0.0.1", "172.16.0.1", "172.31.255.255", "192.168.1.1",  # loopback, private
        "169.254.169.254", "169.254.0.1",  # link-local: the cloud metadata address
        "100.64.0.1", "0.0.0.0", "224.0.0.1", "239.255.255.250", "240.0.0.1", "255.255.255.255",  # CGNAT, unspecified, multicast, reserved
        "::1", "::", "fe80::1", "fc00::1", "fd12:3456::1", "ff02::1",  # IPv6 loopback, link-local, unique-local, multicast
        "::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254",  # IPv4 inside IPv6
        "64:ff9b::7f00:1", "64:ff9b::a00:1",  # NAT64 carrying a loopback / private address
        "2002:7f00:1::1",  # 6to4
    ],
)
def test_addresses_that_are_not_public_are_refused(address):
    assert is_public_address(ipaddress.ip_address(address)) is False


@pytest.mark.parametrize("address", ["8.8.8.8", PUBLIC, "1.1.1.1", "2606:4700:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"])
def test_public_addresses_are_allowed(address):
    assert is_public_address(ipaddress.ip_address(address)) is True


# --- what a URL may look like -------------------------------------------------------


def test_a_plain_https_url_is_split_up():
    assert split_url("https://hooks.example.com/services/T0/B0/xyz?token=1") == (
        "https", "hooks.example.com", 443, "/services/T0/B0/xyz?token=1",
    )
    assert split_url("https://example.com:8443") == ("https", "example.com", 8443, "/")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",  # not encrypted
        "ftp://example.com/hook",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "//example.com/hook",
        "https:///nohost",
        "https://user:secret@example.com/hook",  # credentials
        "https://user@example.com/hook",
        "https://example.com:0/hook",
        "https://example.com:99999/hook",
        "https://example.com:notaport/hook",
        "https://" + "a" * 2100,
        "",
    ],
)
def test_urls_that_may_not_be_called_are_refused(url):
    with pytest.raises(UnsafeUrlError):
        split_url(url)


def test_http_is_allowed_only_where_private_addresses_are():
    assert split_url("http://localhost:8080/hook", allow_private=True) == ("http", "localhost", 8080, "/hook")
    with pytest.raises(UnsafeUrlError):
        split_url("http://localhost:8080/hook")


# --- resolving ----------------------------------------------------------------------


async def test_a_host_that_resolves_to_a_public_address_is_accepted(monkeypatch):
    lookups = _dns(monkeypatch, PUBLIC)

    assert await resolve_public("hooks.example.com", 443) == [PUBLIC]
    assert lookups == [("hooks.example.com", 443)]


async def test_one_private_address_among_public_ones_refuses_the_host(monkeypatch):
    _dns(monkeypatch, PUBLIC, "10.0.0.5")

    with pytest.raises(UnsafeUrlError, match="not a public one"):
        await resolve_public("sneaky.example.com", 443)


async def test_a_host_that_resolves_to_the_loopback_is_refused(monkeypatch):
    _dns(monkeypatch, "127.0.0.1")

    with pytest.raises(UnsafeUrlError):
        await resolve_public("localtest.me", 443)


async def test_a_host_that_does_not_resolve_is_refused(monkeypatch):
    async def failing(host: str, port: int):
        raise OSError("Name or service not known")

    monkeypatch.setattr(safe_http, "_getaddrinfo", failing)

    with pytest.raises(UnsafeUrlError, match="cannot be resolved"):
        await resolve_public("nowhere.invalid", 443)


async def test_an_empty_answer_is_refused(monkeypatch):
    _dns(monkeypatch)

    with pytest.raises(UnsafeUrlError):
        await resolve_public("empty.example.com", 443)


async def test_an_ip_address_in_the_url_is_checked_as_it_is_without_a_lookup(monkeypatch):
    lookups = _dns(monkeypatch, PUBLIC)

    assert await resolve_public(PUBLIC, 443) == [PUBLIC]
    for private in ("127.0.0.1", "169.254.169.254", "::1"):
        with pytest.raises(UnsafeUrlError):
            await resolve_public(private, 443)
    assert lookups == []


async def test_an_ipv6_scope_id_is_not_part_of_the_address(monkeypatch):
    _dns(monkeypatch, "fe80::1%eth0")  # link-local with a scope: still refused, not a crash

    with pytest.raises(UnsafeUrlError):
        await resolve_public("scoped.example.com", 443)


async def test_check_url_refuses_what_resolves_privately_and_allows_it_where_configured(monkeypatch):
    _dns(monkeypatch, "10.1.2.3")

    with pytest.raises(UnsafeUrlError):
        await check_url("https://internal.example.com/hook")
    await check_url("https://internal.example.com/hook", allow_private=True)  # must not raise


# --- posting ------------------------------------------------------------------------


@respx.mock
async def test_the_connection_goes_to_the_checked_address_with_the_original_host_and_tls_name(monkeypatch):
    _dns(monkeypatch, PUBLIC)
    route = respx.post(f"https://{PUBLIC}/services/T0/B0").mock(return_value=httpx.Response(200, text="ok"))

    result = await safe_post(
        "https://hooks.example.com/services/T0/B0", b'{"text":"hi"}', {"Content-Type": "application/json"}, timeout=5
    )

    assert (result.status_code, result.body) == (200, b"ok")
    request = route.calls.last.request
    assert request.url.host == PUBLIC  # not the host name again: no second DNS answer to be fooled by
    assert request.headers["host"] == "hooks.example.com"
    assert request.extensions["sni_hostname"] == "hooks.example.com"
    assert request.headers["content-type"] == "application/json"
    assert request.content == b'{"text":"hi"}'


@respx.mock
async def test_a_non_default_port_stays_in_the_host_header(monkeypatch):
    _dns(monkeypatch, PUBLIC)
    route = respx.post(f"https://{PUBLIC}:8443/hook").mock(return_value=httpx.Response(204))

    result = await safe_post("https://hooks.example.com:8443/hook", b"{}", {}, timeout=5)

    assert result.status_code == 204
    assert route.calls.last.request.headers["host"] == "hooks.example.com:8443"


@respx.mock
async def test_an_ipv6_address_is_put_in_brackets(monkeypatch):
    _dns(monkeypatch, "2606:4700:4700::1111")
    route = respx.post("https://[2606:4700:4700::1111]/hook").mock(return_value=httpx.Response(200))

    await safe_post("https://hooks.example.com/hook", b"{}", {}, timeout=5)

    assert route.called


@respx.mock
async def test_nothing_is_sent_to_an_address_that_must_not_be_called(monkeypatch):
    _dns(monkeypatch, "169.254.169.254")
    route = respx.route().mock(return_value=httpx.Response(200))

    with pytest.raises(UnsafeUrlError):
        await safe_post("https://metadata.example.com/latest/meta-data", b"{}", {}, timeout=5)

    assert not route.called


@respx.mock
async def test_a_redirect_is_not_followed(monkeypatch):
    """Where a redirect leads was never checked - it could be the metadata address."""
    _dns(monkeypatch, PUBLIC)
    route = respx.post(f"https://{PUBLIC}/hook").mock(
        return_value=httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})
    )
    elsewhere = respx.route(host="169.254.169.254").mock(return_value=httpx.Response(200, text="secret"))

    result = await safe_post("https://hooks.example.com/hook", b"{}", {}, timeout=5)

    assert result.status_code == 302
    assert route.call_count == 1 and not elsewhere.called


@respx.mock
async def test_the_next_address_is_tried_when_a_connection_fails(monkeypatch):
    _dns(monkeypatch, "93.184.216.35", PUBLIC)
    respx.post("https://93.184.216.35/hook").mock(side_effect=httpx.ConnectError("refused"))
    second = respx.post(f"https://{PUBLIC}/hook").mock(return_value=httpx.Response(200, text="ok"))

    result = await safe_post("https://hooks.example.com/hook", b"{}", {}, timeout=5)

    assert result.status_code == 200 and second.called


@respx.mock
async def test_a_failure_that_is_not_a_connection_failure_is_final(monkeypatch):
    _dns(monkeypatch, "93.184.216.35", PUBLIC)
    respx.post("https://93.184.216.35/hook").mock(side_effect=httpx.ReadTimeout("slow"))
    second = respx.post(f"https://{PUBLIC}/hook").mock(return_value=httpx.Response(200))

    with pytest.raises(httpx.ReadTimeout):
        await safe_post("https://hooks.example.com/hook", b"{}", {}, timeout=5)

    assert not second.called


@respx.mock
async def test_all_addresses_failing_raises_the_last_error(monkeypatch):
    _dns(monkeypatch, "93.184.216.35", PUBLIC)
    respx.post("https://93.184.216.35/hook").mock(side_effect=httpx.ConnectError("refused"))
    respx.post(f"https://{PUBLIC}/hook").mock(side_effect=httpx.ConnectTimeout("no answer"))

    with pytest.raises(httpx.ConnectTimeout):
        await safe_post("https://hooks.example.com/hook", b"{}", {}, timeout=5)


@respx.mock
async def test_a_huge_answer_is_read_only_as_far_as_the_limit(monkeypatch):
    _dns(monkeypatch, PUBLIC)
    respx.post(f"https://{PUBLIC}/hook").mock(return_value=httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES * 10)))

    result = await safe_post("https://hooks.example.com/hook", b"{}", {}, timeout=5)

    assert len(result.body) == MAX_RESPONSE_BYTES


@respx.mock
async def test_where_private_addresses_are_allowed_the_url_is_used_as_written(monkeypatch):
    lookups = _dns(monkeypatch, "127.0.0.1")
    route = respx.post("http://localhost:9000/hook").mock(return_value=httpx.Response(200, text="ok"))

    result = await safe_post("http://localhost:9000/hook", b"{}", {"X-Test": "1"}, timeout=5, allow_private=True)

    assert (result.status_code, route.calls.last.request.headers["x-test"]) == (200, "1")
    assert lookups == []  # no pinning: a development receiver on the same machine
