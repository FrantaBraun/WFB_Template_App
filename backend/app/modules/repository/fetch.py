# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Downloading an image from an address a user typed - by the SERVER, which is
what makes it dangerous: left alone, "import this image" would let anyone make
our server request internal addresses (databases, cloud metadata, other
services on the network) and hand back the answer. So (SSRF):

- only http and https, no credentials in the address, only ports 80 and 443;
- the host name is resolved here, and the download is refused unless EVERY
  address it resolves to is a public one (not loopback, private, link-local,
  carrier-grade NAT, reserved, multicast, unspecified; an IPv4 address wrapped
  in IPv6 - mapped, 6to4, NAT64 - is judged by the IPv4 inside; Teredo never);
- the connection goes to the very address that was checked (the URL carries
  the IP, `Host` and the TLS server name the host name), so the name cannot
  resolve to something else a moment later (DNS rebinding);
- redirects are followed by hand, at most MAX_REDIRECTS of them, each one
  checked from the start - a public address may redirect to an internal one;
- no cookies, no proxies from the environment, no compression, a total time
  limit, and the body is streamed and cut off at `max_bytes`.

What arrives is only bytes; the caller decides whether they are an image (by
their first bytes, never by the Content-Type it was served with).
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

ALLOWED_PORTS = frozenset({80, 443})
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 10.0
MAX_URL_LENGTH = 2000
USER_AGENT = "HomeRepository-image-import/1.0"
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

Resolver = Callable[[str, int], Awaitable[list[str]]]


class FetchError(Exception):
    """The download was refused or failed; `code` is what the frontend translates:
    invalid_url, blocked_port, unresolvable, blocked_address, too_many_redirects,
    bad_status, too_large, timeout, network_error."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def is_public_address(ip: str) -> bool:
    """Whether `ip` is an address on the public internet (see the module docstring)."""
    try:
        address = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return is_public_address(str(address.ipv4_mapped))
        if address.teredo is not None:
            return False
        if address.sixtofour is not None and not is_public_address(str(address.sixtofour)):
            return False
        if address in ipaddress.ip_network("64:ff9b::/96"):  # NAT64: the IPv4 address is the last 32 bits
            return is_public_address(str(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)))
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_reserved
        and not address.is_unspecified
        and not address.is_private
    )


async def resolve_host(host: str, port: int) -> list[str]:
    """Every address `host` resolves to."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise FetchError("unresolvable") from exc
    return list(dict.fromkeys(info[4][0] for info in infos))


def parse_url(url: str) -> tuple[str, str, int, str]:
    """(scheme, host, port, path with query) of an address we are willing to
    request, or FetchError. The fragment is dropped."""
    url = url.strip()
    if not url or len(url) > MAX_URL_LENGTH or any(ord(char) < 33 or ord(char) == 127 for char in url):
        raise FetchError("invalid_url")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise FetchError("invalid_url") from exc
    if parts.scheme not in ("http", "https") or parts.username is not None or parts.password is not None:
        raise FetchError("invalid_url")
    host = parts.hostname
    if not host:
        raise FetchError("invalid_url")
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    if port not in ALLOWED_PORTS:
        raise FetchError("blocked_port")
    return parts.scheme, host, port, urlunsplit(("", "", parts.path or "/", parts.query, ""))


def _url_host(ip: str) -> str:
    return f"[{ip}]" if ":" in ip else ip


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


async def fetch_image_bytes(
    url: str,
    *,
    max_bytes: int,
    resolve: Resolver = resolve_host,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    """The body behind `url` (following up to MAX_REDIRECTS redirects), at most
    `max_bytes` of it. `resolve` and `transport` are for tests."""
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            return await _fetch(url, max_bytes, resolve, transport)
    except TimeoutError as exc:
        raise FetchError("timeout") from exc
    except httpx.TimeoutException as exc:
        raise FetchError("timeout") from exc
    except httpx.HTTPError as exc:
        raise FetchError("network_error") from exc


async def _fetch(url: str, max_bytes: int, resolve: Resolver, transport: httpx.AsyncBaseTransport | None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "image/*", "Accept-Encoding": "identity"}
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=TIMEOUT_SECONDS, transport=transport) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port, target = parse_url(current)
            addresses = await resolve(host, port)
            if not addresses or not all(is_public_address(address) for address in addresses):
                raise FetchError("blocked_address")
            request_url = f"{scheme}://{_url_host(addresses[0])}:{port}{target}"
            extensions = {} if _is_ip_literal(host) else {"sni_hostname": host}
            async with client.stream("GET", request_url, headers={**headers, "Host": host}, extensions=extensions) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("bad_status")
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise FetchError("bad_status")
                declared = response.headers.get("content-length")
                if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                    raise FetchError("too_large")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchError("too_large")
                return bytes(body)
    raise FetchError("too_many_redirects")
