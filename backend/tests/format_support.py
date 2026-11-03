# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Sample documents of the kinds besides OpenAPI, shared by the tests of their
comparison (test_spec_diff_formats.py) and of their endpoint list
(test_spec_outline.py)."""

import json

from app.services.openapi_spec import parse_spec

BASE_SDL = """
directive @cache(ttl: Int) on FIELD_DEFINITION
interface Node { id: ID! }
enum Role { ADMIN USER }
input UserFilter { role: Role  name: String }
type Error { message: String! }
type User implements Node { id: ID!  name: String  role: Role }
union Result = User | Error
type Query {
  users(limit: Int, filter: UserFilter): [User!]!
  user(id: ID!): User
}
"""

SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


def pm_request(name, method, path, query=(), headers=(), host="{{baseUrl}}"):
    url = {"raw": f"{host}/{'/'.join(path)}", "host": [host], "path": list(path), "query": [{"key": k, **({"disabled": True} if k.startswith("~") else {})} for k in query]}
    return {"name": name, "request": {"method": method, "url": url, "header": [{"key": h} for h in headers]}}


def pm(*items, **info):
    return parse_spec(json.dumps({"info": {"name": "Pets", "schema": SCHEMA, **info}, "item": list(items)}).encode())
