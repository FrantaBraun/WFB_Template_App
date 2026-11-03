# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Calling an address a USER typed in, without letting them aim the server at
its own network (SSRF).

Two things in this application call such addresses: a team's webhooks
(app/services/webhooks.py, POST) and the documentation a user registers by
URL (app/services/openapi_spec.py's fetch_spec_from_url, GET). The server
makes those calls from inside its own network - so
`http://169.254.169.254/...` (cloud metadata), `http://localhost:5432` or
`http://10.0.0.5/admin` must never be reachable that way. Three things keep
it so:

- only https (and http where the caller says it is fine, as for fetching a
  public specification), no credentials in the URL;
- the host is resolved HERE and every address it resolves to has to be a
  public one - one private address among several rejects the lot;
- the connection goes to the address that was checked, not to the host name
  again (the Host header and the TLS server name stay the original host's),
  so a DNS answer that changes between the check and the connection - DNS
  rebinding - cannot swap in a private one. Redirects are never followed,
  since the target of a redirect was never checked.

A deployment that really does need to call private addresses (documentation
served inside the company network, a webhook receiver on localhost while
developing) sets Settings.outbound_allow_private_addresses, which turns the
address check off and uses the URL as written.

The response is read only as far as the caller allows: the answer of a chat
tool is a word, and a hostile server must not be able to fill the memory."""

import asyncio
import functools
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

MAX_URL_LENGTH = 2048
MAX_RESPONSE_BYTES = 4096
_MAX_ADDRESSES_TRIED = 3

# Ranges that embed an IPv4 address and so could smuggle a private one past a
# check of the IPv6 address alone.
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIX_TO_FOUR = ipaddress.ip_network("2002::/16")


@functools.lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    """One TLS context for every call: building it loads the whole CA bundle,
    which is CPU work that blocks the event loop - far too much to pay for each
    delivery. It is built on the first call and kept."""
    return httpx.create_ssl_context()


class UnsafeUrlError(ValueError):
    """The URL must not be called: wrong scheme, credentials in it, a host
    that does not resolve, or an address that is not a public one."""


@dataclass(frozen=True)
class SafeResponse:
    """What came back: the status, the body up to the caller's limit, and
    whether there was more than that (truncated) - in which case body is
    only the part that was read."""

    status_code: int
    body: bytes
    truncated: bool = False


def is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether an address is one on the public internet. Stricter than
    `is_global` alone, which counts multicast as global; IPv4 carried inside
    IPv6 (mapped or NAT64) is judged as the IPv4 address it carries, and
    6to4 is refused outright."""
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return is_public_address(address.ipv4_mapped)
        if address in _NAT64:
            return is_public_address(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
        if address in _SIX_TO_FOUR:
            return False
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return False
    return address.is_global


def split_url(url: str, *, allow_private: bool = False, allow_http: bool = False) -> tuple[str, str, int, str]:
    """(scheme, host, port, path with query) of a URL that may be called, else
    UnsafeUrlError. Looks only at the URL - whether the host is safe is for
    `resolve_public`. Plain http is accepted when the caller allows it, and
    wherever private addresses are allowed (development)."""
    if len(url) > MAX_URL_LENGTH:
        raise UnsafeUrlError("The URL is too long")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise UnsafeUrlError("The URL is not valid") from exc
    plain_http_ok = allow_http or allow_private
    if parts.scheme not in (("https", "http") if plain_http_ok else ("https",)):
        raise UnsafeUrlError("The URL must be http or https" if plain_http_ok else "The URL must start with https://")
    if not parts.hostname:
        raise UnsafeUrlError("The URL has no host")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("The URL must not contain a user name or password")
    if port is not None and not 1 <= port <= 65535:
        raise UnsafeUrlError("The URL has an invalid port")
    default_port = 443 if parts.scheme == "https" else 80
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return parts.scheme, parts.hostname, port or default_port, path


async def _getaddrinfo(host: str, port: int) -> list[str]:
    """The addresses a host name resolves to, as text. A separate function so
    tests can say what DNS answers."""
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


async def resolve_public(host: str, port: int) -> list[str]:
    """The addresses `host` resolves to, every one of which is public - else
    UnsafeUrlError. A host that is already an IP address is checked as it is."""
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            addresses = await _getaddrinfo(host, port)
        except OSError as exc:
            raise UnsafeUrlError("The host name cannot be resolved") from exc
    if not addresses:
        raise UnsafeUrlError("The host name cannot be resolved")
    parsed = []
    for text in addresses:
        try:
            parsed.append(ipaddress.ip_address(text.split("%")[0]))  # an IPv6 scope id is not part of the address
        except ValueError as exc:
            raise UnsafeUrlError("The host resolved to something that is not an address") from exc
    if not all(is_public_address(address) for address in parsed):
        raise UnsafeUrlError("The address is not a public one")
    return list(dict.fromkeys(str(address) for address in parsed))


async def check_url(url: str, *, allow_private: bool = False, allow_http: bool = False) -> None:
    """Raise UnsafeUrlError unless `url` may be called (what a webhook is
    asked to satisfy when it is saved - and again every time it is called)."""
    _, host, port, _ = split_url(url, allow_private=allow_private, allow_http=allow_http)
    if not allow_private:
        await resolve_public(host, port)


async def safe_post(
    url: str,
    body: bytes,
    headers: dict[str, str],
    *,
    timeout: float,
    allow_private: bool = False,
) -> SafeResponse:
    """POST `body` to `url` as described in the module docstring (https only,
    answer read up to MAX_RESPONSE_BYTES). Raises UnsafeUrlError for an
    address that must not be called and httpx.HTTPError for a connection that
    fails; an answer of any status is a result, the caller decides what a 404
    means."""
    return await _send(
        "POST", url, body, headers, timeout=timeout, allow_private=allow_private, allow_http=False, max_bytes=MAX_RESPONSE_BYTES
    )


async def safe_get(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float,
    max_bytes: int,
    allow_private: bool = False,
    allow_http: bool = True,
) -> SafeResponse:
    """GET `url` as described in the module docstring. The body is read only up
    to `max_bytes`; a longer one comes back with `truncated` set and the rest
    unread. http is allowed by default - a public specification served over
    plain http is an ordinary thing, and what makes the call safe is the
    address, not the scheme. Raises like safe_post."""
    return await _send(
        "GET", url, None, headers, timeout=timeout, allow_private=allow_private, allow_http=allow_http, max_bytes=max_bytes
    )


async def _send(
    method: str,
    url: str,
    body: bytes | None,
    headers: dict[str, str],
    *,
    timeout: float,
    allow_private: bool,
    allow_http: bool,
    max_bytes: int,
) -> SafeResponse:
    scheme, host, port, path = split_url(url, allow_private=allow_private, allow_http=allow_http)
    if allow_private:
        # A deployment that allows private addresses: the URL is used as written.
        return await _request(method, url, body, headers, timeout=timeout, extensions={}, max_bytes=max_bytes)

    addresses = await resolve_public(host, port)
    default_port = 443 if scheme == "https" else 80
    host_header = host if port == default_port else f"{host}:{port}"
    extensions = {"sni_hostname": host} if scheme == "https" else {}
    last_error: httpx.HTTPError | None = None
    for address in addresses[:_MAX_ADDRESSES_TRIED]:
        literal = f"[{address}]" if ":" in address else address
        try:
            return await _request(
                method,
                f"{scheme}://{literal}:{port}{path}",
                body,
                {**headers, "Host": host_header},
                timeout=timeout,
                extensions=extensions,
                max_bytes=max_bytes,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:  # try the next address; anything else is final
            last_error = exc
    assert last_error is not None
    raise last_error


async def _request(
    method: str,
    url: str,
    body: bytes | None,
    headers: dict[str, str],
    *,
    timeout: float,
    extensions: dict,
    max_bytes: int,
) -> SafeResponse:
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, trust_env=False, verify=_ssl_context()
    ) as client:
        async with client.stream(method, url, content=body, headers=headers, extensions=extensions) as response:
            received = b""
            truncated = False
            async for chunk in response.aiter_bytes():
                received += chunk
                if len(received) > max_bytes:
                    truncated = True
                    break
            return SafeResponse(status_code=response.status_code, body=received[:max_bytes], truncated=truncated)
