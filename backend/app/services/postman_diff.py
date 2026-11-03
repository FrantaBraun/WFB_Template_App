# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What changed between two Postman collections: which requests (method and
path) came or went, and which query parameters and headers they gained or lost.
A collection says nothing about what is required, so a parameter that appears is
only ever "info" and one that disappears a "warning"; a request that disappears
is breaking, as an operation removed from an OpenAPI document is. Everything
else - names, folders, descriptions, bodies - is not compared."""

from app.services.postman_spec import PostmanRequest, requests
from app.services.spec_diff import Change, SpecDiff


def diff_postman(old: dict, new: dict) -> SpecDiff:
    old_requests = {(r.method, r.path): r for r in requests(old)}
    new_requests = {(r.method, r.path): r for r in requests(new)}
    changes: list[Change] = []

    for key in sorted(old_requests.keys() | new_requests.keys()):
        method, path = key
        if key not in new_requests:
            changes.append(Change("operation_removed", "breaking", method, path))
        elif key not in old_requests:
            changes.append(Change("operation_added", "info", method, path))
        else:
            _compare_request(changes, method, path, old_requests[key], new_requests[key])

    changes.sort(key=Change.sort_key)
    return SpecDiff(changes)


def _compare_request(changes: list[Change], method: str, path: str, old: PostmanRequest, new: PostmanRequest) -> None:
    for kind, before, after in (("query", old.query, new.query), ("header", old.headers, new.headers)):
        for name in sorted(set(before) - set(after)):
            changes.append(Change("parameter_removed", "warning", method, path, scope="parameter", location=f"{kind}:{name}"))
        for name in sorted(set(after) - set(before)):
            changes.append(
                Change("parameter_added", "info", method, path, scope="parameter", location=f"{kind}:{name}", detail={"required": False})
            )
