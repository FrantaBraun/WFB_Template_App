# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Postman collections (v2.0 / v2.1 JSON) as documentation: recognising one,
getting its requests out, and the fingerprint of their structure.

A collection is a tree of folders holding requests; what matters to someone
who consumes the API is which requests exist - method and path - and which
query parameters and headers they carry. The host is dropped (it is usually a
`{{baseUrl}}` variable anyway) so a collection that only changes its server
does not look like every request changed.

A collection rarely carries a version number: when `info.version` is missing
the version is derived from the structure (`rev-` + a hash, see
graphql_spec.revision_label), so a changed set of requests is a new version
and a changed description only a content change."""

import re
from dataclasses import dataclass

from app.services.graphql_spec import revision_label

_SCHEME_AND_HOST = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/?#]*")
_VARIABLE_HOST = re.compile(r"^\{\{[^}]*\}\}")
_MAX_DEPTH = 20


@dataclass(frozen=True)
class PostmanRequest:
    name: str
    method: str
    path: str
    query: tuple[str, ...]
    headers: tuple[str, ...]
    description: str | None


def is_postman(document: dict) -> bool:
    """A collection says so in info.schema (the URL of its JSON schema) or, in
    older exports, by having both `info._postman_id` and a list of `item`s."""
    info = document.get("info")
    if not isinstance(info, dict):
        return False
    schema = info.get("schema")
    if isinstance(schema, str) and "getpostman.com" in schema:
        return True
    return "_postman_id" in info and isinstance(document.get("item"), list)


def declared_version(document: dict) -> str | None:
    """info.version when there is one: a string, or the {major, minor, patch}
    object some exports use (-> "1.2.3")."""
    version = (document.get("info") or {}).get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()
    if isinstance(version, dict) and all(key in version for key in ("major", "minor", "patch")):
        return f"{version['major']}.{version['minor']}.{version['patch']}"
    return None


def title(document: dict) -> str | None:
    name = (document.get("info") or {}).get("name")
    return name if isinstance(name, str) else None


def _description(value: object) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict) and isinstance(value.get("content"), str):  # {"content": ..., "type": "text/markdown"}
        return value["content"] or None
    return None


def _path_of(url: object) -> str:
    """The path of a request URL as "/a/b", whichever way it is written: a
    string, or the object with `path` segments (strings, or {"value": ...})."""
    if isinstance(url, dict):
        segments = url.get("path")
        if isinstance(segments, list):
            parts = [s if isinstance(s, str) else str(s.get("value", "")) if isinstance(s, dict) else "" for s in segments]
            return "/" + "/".join(p for p in parts if p)
        if isinstance(segments, str):
            return "/" + segments.strip("/")
        url = url.get("raw")
    if isinstance(url, str):
        rest = _SCHEME_AND_HOST.sub("", url.strip())
        rest = _VARIABLE_HOST.sub("", rest) if not rest.startswith("/") else rest
        rest = rest.split("?")[0].split("#")[0]
        return "/" + rest.strip("/")
    return "/"


def _names(entries: object, key: str) -> list[str]:
    """The names of the enabled entries of a `query` / `header` list."""
    if not isinstance(entries, list):
        return []
    return [e[key] for e in entries if isinstance(e, dict) and isinstance(e.get(key), str) and e[key] and not e.get("disabled")]


def requests(document: dict) -> list[PostmanRequest]:
    """Every request of the collection, folders flattened, in document order.
    A request that appears twice (same method and path in two folders) is
    kept once, with the query parameters and headers of both."""
    found: dict[tuple[str, str], PostmanRequest] = {}

    def walk(items: object, depth: int) -> None:
        if not isinstance(items, list) or depth > _MAX_DEPTH:
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            request = item.get("request")
            if isinstance(request, dict):
                method = str(request.get("method") or "GET").upper()
                url = request.get("url")
                path = _path_of(url)
                query = _names(url.get("query") if isinstance(url, dict) else None, "key")
                headers = _names(request.get("header"), "key")
                name = item.get("name") if isinstance(item.get("name"), str) else path
                key = (method, path)
                if key in found:
                    previous = found[key]
                    query = [*previous.query, *query]
                    headers = [*previous.headers, *headers]
                    name, description = previous.name, previous.description
                else:
                    description = _description(request.get("description"))
                found[key] = PostmanRequest(
                    name=name,
                    method=method,
                    path=path,
                    query=tuple(dict.fromkeys(query)),
                    headers=tuple(dict.fromkeys(headers)),
                    description=description,
                )
            walk(item.get("item"), depth + 1)

    walk(document.get("item"), 0)
    return list(found.values())


def structure_signature(document: dict) -> str:
    """Same for two collections with the same requests (method, path, query
    parameters, headers) however they are arranged in folders or described."""
    lines = [
        f"{r.method} {r.path} ?{','.join(sorted(r.query))} #{','.join(sorted(r.headers))}" for r in requests(document)
    ]
    return "\n".join(sorted(lines))


def version_of(document: dict) -> str:
    return declared_version(document) or revision_label(structure_signature(document))
