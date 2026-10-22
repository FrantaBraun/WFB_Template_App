# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Downloading an image by URL on the server (app/modules/repository/fetch.py):
the SSRF protections. No real network and no real DNS - a fake resolver and an
httpx MockTransport stand in for both."""

import httpx
import pytest

from app.modules.repository import fetch
from app.modules.repository.fetch import FetchError

PUBLIC_IP = "93.184.216.34"
PUBLIC_IP_2 = "151.101.1.69"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _resolver(mapping: dict[str, list[str]]):
    async def resolve(host: str, port: int) -> list[str]:
        if host not in mapping:
            raise FetchError("unresolvable")
        return mapping[host]

    return resolve


async def _fetch(url: str, handler, hosts: dict[str, list[str]] | None = None, max_bytes: int = 1000) -> bytes:
    return await fetch.fetch_image_bytes(
        url,
        max_bytes=max_bytes,
        resolve=_resolver(hosts or {"example.com": [PUBLIC_IP]}),
        transport=httpx.MockTransport(handler),
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=PNG)


# --- Which addresses are public -----------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        PUBLIC_IP,
        PUBLIC_IP_2,
        "8.8.8.8",
        "2606:2800:220:1:248:1893:25c8:1946",
        "2001:4860:4860::8888",
        "::ffff:93.184.216.34",
    ],
)
def test_public_addresses_are_allowed(address):
    assert fetch.is_public_address(address) is True


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "127.1.2.3",
        "0.0.0.0",
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "192.0.2.1",
        "198.18.0.1",
        "224.0.0.1",
        "239.255.255.250",
        "240.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fe80::1%eth0",
        "fc00::1",
        "fd12:3456::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        "2002:7f00:0001::1",
        "64:ff9b::7f00:1",
        "64:ff9b::a00:1",
        "2001::1",
        "2001:db8::1",
        "not an address",
        "",
    ],
)
def test_internal_and_special_addresses_are_refused(address):
    assert fetch.is_public_address(address) is False


def test_nat64_of_a_public_address_is_public():
    assert fetch.is_public_address("64:ff9b::5db8:d822") is True  # 93.184.216.34


# --- Which addresses are requested ----------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://example.com/a.png", ("http", "example.com", 80, "/a.png")),
        ("https://example.com/a.png?x=1&y=2", ("https", "example.com", 443, "/a.png?x=1&y=2")),
        ("https://Example.COM", ("https", "example.com", 443, "/")),
        ("https://example.com:443/a", ("https", "example.com", 443, "/a")),
        ("http://example.com:80/a", ("http", "example.com", 80, "/a")),
        ("https://example.com/a.png#fragment", ("https", "example.com", 443, "/a.png")),
        ("  https://example.com/a  ", ("https", "example.com", 443, "/a")),
        ("http://[2606:2800:220:1:248:1893:25c8:1946]/a", ("http", "2606:2800:220:1:248:1893:25c8:1946", 80, "/a")),
    ],
)
def test_parse_url(url, expected):
    assert fetch.parse_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "example.com/a.png",
        "//example.com/a.png",
        "ftp://example.com/a.png",
        "file:///etc/passwd",
        "gopher://example.com/",
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "https://user@example.com/a",
        "https://user:pass@example.com/a",
        "https:///a",
        "http://example.com:abc/a",
        "http://example.com:99999/a",
        "https://exa mple.com/a",
        "https://example.com/a\nHost: evil",
        "https://example.com/a\x00",
        "https://example.com/" + "a" * 2000,
    ],
)
def test_parse_url_refuses_what_is_not_a_plain_web_address(url):
    with pytest.raises(FetchError) as raised:
        fetch.parse_url(url)

    assert raised.value.code == "invalid_url"


@pytest.mark.parametrize("url", ["http://example.com:8080/a", "https://example.com:22/a", "http://example.com:6379/", "https://example.com:0/a"])
def test_parse_url_refuses_other_ports(url):
    with pytest.raises(FetchError) as raised:
        fetch.parse_url(url)

    assert raised.value.code in ("blocked_port", "invalid_url")


# --- The download --------------------------------------------------------------------


async def test_the_image_is_fetched_from_the_address_that_was_checked():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=PNG, headers={"content-type": "text/html"})

    body = await _fetch("https://example.com/a.png?x=1", handler)

    assert body == PNG  # the Content-Type it was served with is not this module's business
    (request,) = seen
    assert request.url.host == PUBLIC_IP
    assert request.url.port in (None, 443)  # httpx leaves out a scheme's default port
    assert request.url.scheme == "https"
    assert request.url.raw_path == b"/a.png?x=1"
    assert request.headers["host"] == "example.com"
    assert request.extensions["sni_hostname"] == "example.com"
    assert request.headers["accept-encoding"] == "identity"
    assert "cookie" not in request.headers
    assert "authorization" not in request.headers


async def test_plain_http_goes_to_port_80():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=PNG)

    await _fetch("http://example.com/a.png", handler)

    assert (seen[0].url.scheme, seen[0].url.host) == ("http", PUBLIC_IP)
    assert seen[0].url.port in (None, 80)


async def test_an_ipv6_address_is_requested_in_brackets():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=PNG)

    await _fetch("http://example.com/a", handler, hosts={"example.com": ["2606:2800:220:1:248:1893:25c8:1946"]})

    assert seen[0].url.host == "2606:2800:220:1:248:1893:25c8:1946"


async def test_an_address_given_as_an_ip_literal_is_checked_like_a_name():
    assert await _fetch(f"http://{PUBLIC_IP}/a.png", _ok, hosts={PUBLIC_IP: [PUBLIC_IP]}) == PNG

    for literal in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "[::1]", "[::ffff:127.0.0.1]"):
        host = literal.strip("[]")
        with pytest.raises(FetchError) as raised:
            await _fetch(f"http://{literal}/a.png", _ok, hosts={host: [host]})
        assert raised.value.code == "blocked_address", literal


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "192.168.1.1", "169.254.169.254", "::1", "fd00::1", "100.64.0.1"])
async def test_a_name_that_resolves_to_an_internal_address_is_refused_before_any_request(address):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=PNG)

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a.png", handler, hosts={"example.com": [address]})

    assert raised.value.code == "blocked_address"
    assert calls == []


async def test_one_internal_address_among_public_ones_is_enough_to_refuse():
    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", _ok, hosts={"example.com": [PUBLIC_IP, "10.0.0.1"]})

    assert raised.value.code == "blocked_address"


async def test_a_name_that_resolves_to_nothing_is_refused():
    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", _ok, hosts={"example.com": []})
    assert raised.value.code == "blocked_address"

    with pytest.raises(FetchError) as raised:
        await _fetch("https://nowhere.example/a", _ok, hosts={})
    assert raised.value.code == "unresolvable"


async def test_localhost_is_refused_by_name_too():
    with pytest.raises(FetchError) as raised:
        await _fetch("http://localhost/a", _ok, hosts={"localhost": ["127.0.0.1", "::1"]})

    assert raised.value.code == "blocked_address"


async def test_a_redirect_is_followed_and_checked_again():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        if request.headers["host"] == "example.com":
            return httpx.Response(302, headers={"location": "https://cdn.example.net/real.png"})
        return httpx.Response(200, content=PNG)

    hosts = {"example.com": [PUBLIC_IP], "cdn.example.net": [PUBLIC_IP_2]}

    assert await _fetch("https://example.com/a.png", handler, hosts=hosts) == PNG

    assert [(r.url.host, r.headers["host"], r.url.raw_path) for r in seen] == [
        (PUBLIC_IP, "example.com", b"/a.png"),
        (PUBLIC_IP_2, "cdn.example.net", b"/real.png"),
    ]


async def test_a_relative_redirect_stays_on_the_same_host():
    def handler(request):
        if request.url.raw_path == b"/old":
            return httpx.Response(301, headers={"location": "/new/a.png"})
        return httpx.Response(200, content=PNG)

    assert await _fetch("https://example.com/old", handler) == PNG


async def test_a_redirect_to_an_internal_address_is_refused():
    calls = []

    def handler(request):
        calls.append(request.headers["host"])
        return httpx.Response(302, headers={"location": "http://internal.example/secret"})

    hosts = {"example.com": [PUBLIC_IP], "internal.example": ["10.0.0.7"]}

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", handler, hosts=hosts)

    assert raised.value.code == "blocked_address"
    assert calls == ["example.com"]


@pytest.mark.parametrize("location", ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd", "http://example.com:8080/", "ftp://example.com/x"])
async def test_a_redirect_to_a_forbidden_address_is_refused(location):
    def handler(request):
        return httpx.Response(302, headers={"location": location})

    hosts = {"example.com": [PUBLIC_IP], "127.0.0.1": ["127.0.0.1"], "169.254.169.254": ["169.254.169.254"]}

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", handler, hosts=hosts)

    assert raised.value.code in ("blocked_address", "invalid_url", "blocked_port")


async def test_at_most_three_redirects_are_followed():
    hops = []

    def handler(request):
        hops.append(request.url.raw_path)
        return httpx.Response(302, headers={"location": f"/hop{len(hops)}"})

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/start", handler)

    assert raised.value.code == "too_many_redirects"
    assert len(hops) == fetch.MAX_REDIRECTS + 1


async def test_exactly_three_redirects_are_fine():
    def handler(request):
        if request.url.raw_path == b"/hop3":
            return httpx.Response(200, content=PNG)
        number = 0 if request.url.raw_path == b"/start" else int(request.url.raw_path[4:])
        return httpx.Response(302, headers={"location": f"/hop{number + 1}"})

    assert await _fetch("https://example.com/start", handler) == PNG


async def test_a_redirect_without_a_location_is_a_bad_status():
    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", lambda request: httpx.Response(302))

    assert raised.value.code == "bad_status"


@pytest.mark.parametrize("status", [204, 400, 401, 403, 404, 500, 503])
async def test_anything_but_200_is_a_bad_status(status):
    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", lambda request: httpx.Response(status, content=b"nope"))

    assert raised.value.code == "bad_status"


async def test_a_declared_size_over_the_limit_is_refused_without_reading_the_body():
    def handler(request):
        return httpx.Response(200, content=b"x" * 10, headers={"content-length": "5000"})

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", handler, max_bytes=1000)

    assert raised.value.code == "too_large"


async def test_a_body_over_the_limit_is_cut_off_even_when_it_does_not_say_how_big_it_is():
    def handler(request):
        return httpx.Response(200, stream=httpx.ByteStream(b"x" * 5000))

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", handler, max_bytes=1000)

    assert raised.value.code == "too_large"


async def test_a_body_of_exactly_the_limit_is_fine():
    assert len(await _fetch("https://example.com/a", lambda request: httpx.Response(200, content=b"x" * 1000), max_bytes=1000)) == 1000


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (httpx.ReadTimeout("slow"), "timeout"),
        (httpx.ConnectTimeout("slow"), "timeout"),
        (httpx.ConnectError("refused"), "network_error"),
        (httpx.RemoteProtocolError("garbage"), "network_error"),
    ],
)
async def test_network_failures_are_reported(error, code):
    def handler(request):
        raise error

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", handler)

    assert raised.value.code == code


async def test_the_whole_download_has_a_time_limit(monkeypatch):
    import asyncio

    monkeypatch.setattr(fetch, "TIMEOUT_SECONDS", 0.05)

    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, content=PNG)

    with pytest.raises(FetchError) as raised:
        await _fetch("https://example.com/a", handler)

    assert raised.value.code == "timeout"


async def test_proxies_from_the_environment_are_not_used(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.internal:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.internal:3128")
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=PNG)

    assert await _fetch("https://example.com/a", handler) == PNG
    assert seen[0].url.host == PUBLIC_IP


async def test_the_real_resolver_refuses_a_name_that_does_not_exist():
    with pytest.raises(FetchError) as raised:
        await fetch.resolve_host("definitely-not-a-real-host.invalid", 443)

    assert raised.value.code == "unresolvable"


async def test_the_real_resolver_turns_loopback_into_something_that_is_then_refused():
    addresses = await fetch.resolve_host("localhost", 80)

    assert addresses
    assert not any(fetch.is_public_address(address) for address in addresses)
