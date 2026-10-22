# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Saved filters and statistics of the repository module: creating, editing,
ordering and deleting them, what a definition has to be, and how they hold the
attributes of their table in place. What a statistic computes is in
test_modules_repository_statistics.py, the owner isolation in
test_modules_repository_structure.py."""

import uuid

import pytest

from tests.repository_support import (  # noqa: F401  (the fixtures are used by name)
    BASE,
    _overrides,
    alice,
    attribute,
    bob,
    client,
    create_repository,
    create_table,
    make_table,
    make_user,
    put_attributes,
    set_limits,
)


def _url(repository: dict, table: dict, suffix: str) -> str:
    return f"{BASE}/repositories/{repository['slug']}/tables/{table['slug']}{suffix}"


async def _shop(client, headers):
    """A table with a text, a number, a date and a boolean attribute."""
    attrs = {
        "region": attribute("text", "Region"),
        "amount": attribute("number", "Amount"),
        "sold": attribute("date", "Sold on"),
        "paid": attribute("boolean", "Paid"),
        "cover": attribute("image", "Cover"),
    }
    repository, table, _ = await make_table(client, headers, *attrs.values(), table_name="Sales")
    return repository, table, {key: value["id"] for key, value in attrs.items()}


def _filter(name="Paid", **parts) -> dict:
    return {"name": name, **parts}


def _statistic(ids, name="By region", **parts) -> dict:
    body = {"name": name, "group_by": [{"field": ids["region"]}], "aggregation": {"fn": "count"}}
    body.update(parts)
    return body


# --- Saved filters ---------------------------------------------------------------------------


async def test_a_filter_is_saved_with_its_normalized_definition(client, alice):
    repository, table, ids = await _shop(client, alice)

    resp = await client.post(
        _url(repository, table, "/filters"),
        json=_filter(
            "Big sales",
            conditions=[{"field": ids["amount"], "op": "gte", "value": 100}, {"field": ids["region"], "op": "contains", "value": "  north "}],
            sort={"field": ids["amount"], "dir": "desc"},
            include_deleted=True,
            q="  shop ",
        ),
        headers=alice,
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    uuid.UUID(body["id"])
    assert (body["name"], body["position"]) == ("Big sales", 0)
    assert body["definition"] == {
        "conditions": [
            {"field": ids["amount"], "op": "gte", "value": 100},
            {"field": ids["region"], "op": "contains", "value": "north"},
        ],
        "sort": {"field": ids["amount"], "dir": "desc"},
        "include_deleted": True,
        "q": "shop",
    }
    assert (await client.get(_url(repository, table, "/filters"), headers=alice)).json() == [body]


async def test_a_filter_may_be_empty_and_has_the_defaults(client, alice):
    repository, table, _ = await _shop(client, alice)

    body = (await client.post(_url(repository, table, "/filters"), json=_filter("Everything"), headers=alice)).json()

    assert body["definition"] == {"conditions": [], "sort": None, "include_deleted": False, "q": None}


async def test_an_invalid_filter_is_a_422_naming_what_is_wrong(client, alice):
    repository, table, ids = await _shop(client, alice)

    resp = await client.post(
        _url(repository, table, "/filters"),
        json=_filter(
            conditions=[
                {"field": ids["amount"], "op": "contains", "value": "x"},
                {"field": ids["cover"], "op": "empty"},
                {"field": ids["sold"], "op": "eq", "value": "yesterday"},
            ],
            sort={"field": "nope"},
        ),
        headers=alice,
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == {
        "errors": {"conditions.0": "invalid_operator", "conditions.1": "unknown_field", "conditions.2": "invalid_date", "sort": "unknown_field"}
    }
    assert (await client.get(_url(repository, table, "/filters"), headers=alice)).json() == []


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "   "}, {"name": "x" * 121}, {"name": "x", "other": 1}, {"name": "x", "page": 2}])
async def test_a_malformed_filter_body_is_a_422(client, alice, body):
    repository, table, _ = await _shop(client, alice)

    assert (await client.post(_url(repository, table, "/filters"), json=body, headers=alice)).status_code == 422


async def test_filters_keep_their_order_and_can_be_reordered(client, alice):
    repository, table, _ = await _shop(client, alice)
    created = [(await client.post(_url(repository, table, "/filters"), json=_filter(name), headers=alice)).json() for name in ("C", "A", "B")]
    assert [item["position"] for item in created] == [0, 1, 2]
    by_name = {item["name"]: item["id"] for item in created}

    resp = await client.put(_url(repository, table, "/filters-order"), json={"ids": [by_name["A"], by_name["B"], by_name["C"]]}, headers=alice)

    assert resp.status_code == 204
    assert [item["name"] for item in (await client.get(_url(repository, table, "/filters"), headers=alice)).json()] == ["A", "B", "C"]


async def test_the_order_must_list_every_filter_once(client, alice):
    repository, table, _ = await _shop(client, alice)
    first = (await client.post(_url(repository, table, "/filters"), json=_filter("A"), headers=alice)).json()
    second = (await client.post(_url(repository, table, "/filters"), json=_filter("B"), headers=alice)).json()

    for ids in ([first["id"]], [first["id"], first["id"]], [first["id"], second["id"], str(uuid.uuid4())], []):
        resp = await client.put(_url(repository, table, "/filters-order"), json={"ids": ids}, headers=alice)
        assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"ids": "must_list_every_item_once"}})


async def test_a_filter_is_replaced_as_a_whole(client, alice):
    repository, table, ids = await _shop(client, alice)
    created = (
        await client.post(
            _url(repository, table, "/filters"),
            json=_filter("Old", conditions=[{"field": ids["region"], "op": "equals", "value": "north"}], include_deleted=True),
            headers=alice,
        )
    ).json()

    resp = await client.put(
        _url(repository, table, f"/filters/{created['id']}"),
        json=_filter("New", conditions=[{"field": ids["paid"], "op": "equals", "value": True}]),
        headers=alice,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert (body["id"], body["name"], body["position"]) == (created["id"], "New", 0)
    assert body["definition"] == {"conditions": [{"field": ids["paid"], "op": "equals", "value": True}], "sort": None, "include_deleted": False, "q": None}


async def test_an_invalid_replacement_changes_nothing(client, alice):
    repository, table, ids = await _shop(client, alice)
    created = (await client.post(_url(repository, table, "/filters"), json=_filter("Keep", q="x"), headers=alice)).json()

    resp = await client.put(_url(repository, table, f"/filters/{created['id']}"), json=_filter("Changed", sort={"field": "nope"}), headers=alice)

    assert resp.status_code == 422
    assert (await client.get(_url(repository, table, "/filters"), headers=alice)).json() == [created]


async def test_a_filter_of_another_table_is_not_found(client, alice):
    repository, table, _ = await _shop(client, alice)
    other = await create_table(client, alice, repository["slug"], name="Other")
    created = (await client.post(_url(repository, table, "/filters"), json=_filter("Mine"), headers=alice)).json()

    assert (await client.put(_url(repository, other, f"/filters/{created['id']}"), json=_filter("X"), headers=alice)).status_code == 404
    assert (await client.delete(_url(repository, other, f"/filters/{created['id']}"), headers=alice)).status_code == 404
    assert (await client.delete(_url(repository, table, f"/filters/{uuid.uuid4()}"), headers=alice)).status_code == 404
    assert (await client.get(_url(repository, other, "/filters"), headers=alice)).json() == []


async def test_the_number_of_filters_per_table_is_limited(client, alice):
    set_limits(max_filters_per_table=2)
    repository, table, _ = await _shop(client, alice)
    await client.post(_url(repository, table, "/filters"), json=_filter("One"), headers=alice)
    await client.post(_url(repository, table, "/filters"), json=_filter("Two"), headers=alice)

    resp = await client.post(_url(repository, table, "/filters"), json=_filter("Three"), headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"limit": "max_filters_per_table", "max": 2}


async def test_a_filter_is_deleted(client, alice):
    repository, table, _ = await _shop(client, alice)
    created = (await client.post(_url(repository, table, "/filters"), json=_filter("Gone"), headers=alice)).json()

    assert (await client.delete(_url(repository, table, f"/filters/{created['id']}"), headers=alice)).status_code == 204

    assert (await client.get(_url(repository, table, "/filters"), headers=alice)).json() == []


# --- Statistics ---------------------------------------------------------------------------------


async def test_a_statistic_is_saved_with_its_defaults(client, alice):
    repository, table, ids = await _shop(client, alice)

    resp = await client.post(_url(repository, table, "/statistics"), json=_statistic(ids), headers=alice)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    uuid.UUID(body["id"])
    assert body["name"] == "By region"
    assert body["filter_id"] is None
    assert body["group_by"] == [{"field": ids["region"], "bucket": None}]
    assert body["aggregation"] == {"fn": "count", "attribute_id": None}
    assert (body["display"], body["chart_type"], body["position"]) == ("both", "bar", 0)
    assert (await client.get(_url(repository, table, "/statistics"), headers=alice)).json() == [body]


async def test_a_statistic_keeps_what_it_was_given(client, alice):
    repository, table, ids = await _shop(client, alice)
    saved_filter = (await client.post(_url(repository, table, "/filters"), json=_filter("Paid"), headers=alice)).json()

    body = (
        await client.post(
            _url(repository, table, "/statistics"),
            json={
                "name": "Revenue",
                "filter_id": saved_filter["id"],
                "group_by": [{"field": ids["sold"], "bucket": "month"}, {"field": ids["region"]}],
                "aggregation": {"fn": "sum", "attribute_id": ids["amount"]},
                "display": "table",
                "chart_type": "line",
            },
            headers=alice,
        )
    ).json()

    assert body["filter_id"] == saved_filter["id"]
    assert body["group_by"] == [{"field": ids["sold"], "bucket": "month"}, {"field": ids["region"], "bucket": None}]
    assert body["aggregation"] == {"fn": "sum", "attribute_id": ids["amount"]}
    assert (body["display"], body["chart_type"]) == ("table", "line")


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"group_by": [{"field": "name"}]}, {"group_by.0": "not_groupable"}),
        ({"group_by": [{"field": "nope"}]}, {"group_by.0": "unknown_field"}),
        ({"group_by": [{"field": "SOLD", "bucket": "month"}]}, {"group_by.0": "unknown_field"}),
        ({"aggregation": {"fn": "sum"}}, {"aggregation": "attribute_required"}),
        ({"chart_type": "pie", "group_by": "two"}, {"chart_type": "pie_needs_one_dimension"}),
    ],
)
async def test_an_invalid_statistic_is_a_422_naming_what_is_wrong(client, alice, changes, errors):
    repository, table, ids = await _shop(client, alice)
    body = _statistic(ids, **changes)
    if changes.get("group_by") == "two":
        body["group_by"] = [{"field": ids["region"]}, {"field": ids["paid"]}]
    if changes.get("group_by") == [{"field": "SOLD", "bucket": "month"}]:
        body["group_by"] = [{"field": ids["sold"]}]
        errors = {"group_by.0": "bucket_required"}

    resp = await client.post(_url(repository, table, "/statistics"), json=body, headers=alice)

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == {"errors": errors}
    assert (await client.get(_url(repository, table, "/statistics"), headers=alice)).json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x"},
        {"name": "x", "group_by": [], "aggregation": {"fn": "count"}},
        {"name": "x", "group_by": [{"field": "a"}, {"field": "b"}, {"field": "c"}], "aggregation": {"fn": "count"}},
        {"name": "x", "group_by": [{"field": "created_on", "bucket": "week"}], "aggregation": {"fn": "count"}},
        {"name": "x", "group_by": [{"field": "created_on", "bucket": "day"}], "aggregation": {"fn": "median"}},
        {"name": "x", "group_by": [{"field": "created_on", "bucket": "day"}], "aggregation": {"fn": "count"}, "display": "huge"},
        {"name": "x", "group_by": [{"field": "created_on", "bucket": "day"}], "aggregation": {"fn": "count"}, "chart_type": "donut"},
        {"name": "x", "group_by": [{"field": "created_on", "bucket": "day"}], "aggregation": {"fn": "count"}, "other": 1},
        {"name": "", "group_by": [{"field": "created_on", "bucket": "day"}], "aggregation": {"fn": "count"}},
    ],
)
async def test_a_malformed_statistic_body_is_a_422(client, alice, body):
    repository, table, _ = await _shop(client, alice)

    assert (await client.post(_url(repository, table, "/statistics"), json=body, headers=alice)).status_code == 422


async def test_a_statistic_can_only_use_a_filter_of_its_own_table(client, alice):
    repository, table, ids = await _shop(client, alice)
    other = await create_table(client, alice, repository["slug"], name="Other")
    foreign = (await client.post(_url(repository, other, "/filters"), json=_filter("Foreign"), headers=alice)).json()

    for filter_id in (foreign["id"], str(uuid.uuid4())):
        resp = await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, filter_id=filter_id), headers=alice)
        assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"filter_id": "unknown_filter"}})


async def test_a_statistic_is_replaced_as_a_whole(client, alice):
    repository, table, ids = await _shop(client, alice)
    created = (await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, display="chart"), headers=alice)).json()

    resp = await client.put(
        _url(repository, table, f"/statistics/{created['id']}"),
        json=_statistic(ids, name="Renamed", group_by=[{"field": ids["paid"]}], aggregation={"fn": "max", "attribute_id": ids["amount"]}),
        headers=alice,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["id"], body["name"], body["display"]) == (created["id"], "Renamed", "both")
    assert body["group_by"] == [{"field": ids["paid"], "bucket": None}]
    assert body["aggregation"] == {"fn": "max", "attribute_id": ids["amount"]}


async def test_an_invalid_replacement_of_a_statistic_changes_nothing(client, alice):
    repository, table, ids = await _shop(client, alice)
    created = (await client.post(_url(repository, table, "/statistics"), json=_statistic(ids), headers=alice)).json()

    resp = await client.put(_url(repository, table, f"/statistics/{created['id']}"), json=_statistic(ids, group_by=[{"field": "name"}]), headers=alice)

    assert resp.status_code == 422
    assert (await client.get(_url(repository, table, "/statistics"), headers=alice)).json() == [created]


async def test_statistics_are_ordered_and_deleted(client, alice):
    repository, table, ids = await _shop(client, alice)
    created = [(await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, name=name), headers=alice)).json() for name in ("C", "A", "B")]
    by_name = {item["name"]: item["id"] for item in created}

    ordered = await client.put(_url(repository, table, "/statistics-order"), json={"ids": [by_name["B"], by_name["C"], by_name["A"]]}, headers=alice)
    bad = await client.put(_url(repository, table, "/statistics-order"), json={"ids": [by_name["B"]]}, headers=alice)
    assert ordered.status_code == 204
    assert bad.status_code == 422
    assert [item["name"] for item in (await client.get(_url(repository, table, "/statistics"), headers=alice)).json()] == ["B", "C", "A"]

    assert (await client.delete(_url(repository, table, f"/statistics/{by_name['C']}"), headers=alice)).status_code == 204
    assert [item["name"] for item in (await client.get(_url(repository, table, "/statistics"), headers=alice)).json()] == ["B", "A"]
    assert (await client.delete(_url(repository, table, f"/statistics/{by_name['C']}"), headers=alice)).status_code == 404


async def test_the_number_of_statistics_per_table_is_limited(client, alice):
    set_limits(max_statistics_per_table=1)
    repository, table, ids = await _shop(client, alice)
    await client.post(_url(repository, table, "/statistics"), json=_statistic(ids), headers=alice)

    resp = await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, name="Second"), headers=alice)

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"limit": "max_statistics_per_table", "max": 1}


async def test_a_statistic_of_another_table_is_not_found(client, alice):
    repository, table, ids = await _shop(client, alice)
    other = await create_table(client, alice, repository["slug"], name="Other")
    created = (await client.post(_url(repository, table, "/statistics"), json=_statistic(ids), headers=alice)).json()

    assert (await client.get(_url(repository, other, f"/statistics/{created['id']}/result"), headers=alice)).status_code == 404
    assert (await client.put(_url(repository, other, f"/statistics/{created['id']}"), json=_statistic(ids), headers=alice)).status_code == 404


# --- A filter in use ----------------------------------------------------------------------------


async def test_a_filter_that_a_statistic_is_based_on_cannot_be_deleted(client, alice):
    repository, table, ids = await _shop(client, alice)
    saved_filter = (await client.post(_url(repository, table, "/filters"), json=_filter("Paid"), headers=alice)).json()
    statistic = (await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, filter_id=saved_filter["id"]), headers=alice)).json()

    refused = await client.delete(_url(repository, table, f"/filters/{saved_filter['id']}"), headers=alice)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"in_use": [{"id": statistic["id"], "name": "By region"}]}
    assert len((await client.get(_url(repository, table, "/filters"), headers=alice)).json()) == 1

    await client.delete(_url(repository, table, f"/statistics/{statistic['id']}"), headers=alice)
    assert (await client.delete(_url(repository, table, f"/filters/{saved_filter['id']}"), headers=alice)).status_code == 204


async def test_a_statistic_may_change_to_a_different_filter_or_none(client, alice):
    repository, table, ids = await _shop(client, alice)
    first = (await client.post(_url(repository, table, "/filters"), json=_filter("First"), headers=alice)).json()
    second = (await client.post(_url(repository, table, "/filters"), json=_filter("Second"), headers=alice)).json()
    statistic = (await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, filter_id=first["id"]), headers=alice)).json()

    await client.put(_url(repository, table, f"/statistics/{statistic['id']}"), json=_statistic(ids, filter_id=second["id"]), headers=alice)
    assert (await client.delete(_url(repository, table, f"/filters/{first['id']}"), headers=alice)).status_code == 204

    await client.put(_url(repository, table, f"/statistics/{statistic['id']}"), json=_statistic(ids), headers=alice)
    assert (await client.delete(_url(repository, table, f"/filters/{second['id']}"), headers=alice)).status_code == 204


async def test_deleting_the_table_takes_its_filters_and_statistics_with_it(client, alice):
    repository, table, ids = await _shop(client, alice)
    saved_filter = (await client.post(_url(repository, table, "/filters"), json=_filter("Paid"), headers=alice)).json()
    await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, filter_id=saved_filter["id"]), headers=alice)

    resp = await client.delete(_url(repository, table, ""), params={"confirm_name": "Sales"}, headers=alice)

    assert resp.status_code == 204


async def test_deleting_the_repository_takes_its_filters_and_statistics_with_it(client, alice):
    repository, table, ids = await _shop(client, alice)
    saved_filter = (await client.post(_url(repository, table, "/filters"), json=_filter("Paid"), headers=alice)).json()
    await client.post(_url(repository, table, "/statistics"), json=_statistic(ids, filter_id=saved_filter["id"]), headers=alice)

    resp = await client.delete(f"{BASE}/repositories/{repository['slug']}", params={"confirm_name": repository["name"]}, headers=alice)

    assert resp.status_code == 204


# --- Attributes they use cannot be removed -----------------------------------------------------------


async def _remove(client, headers, repository, table, ids, *names):
    kept = [
        attribute(
            {"region": "text", "amount": "number", "sold": "date", "paid": "boolean", "cover": "image"}[key], key.title()
        )
        | {"id": value}
        for key, value in ids.items()
        if key not in names
    ]
    return await put_attributes(client, headers, repository["slug"], table["slug"], kept)


async def test_an_attribute_a_filter_uses_cannot_be_removed(client, alice):
    repository, table, ids = await _shop(client, alice)
    await client.post(
        _url(repository, table, "/filters"),
        json=_filter("Big", conditions=[{"field": ids["amount"], "op": "gt", "value": 5}]),
        headers=alice,
    )
    await client.post(_url(repository, table, "/filters"), json=_filter("Sorted", sort={"field": ids["region"], "dir": "asc"}), headers=alice)
    saved = (await client.get(_url(repository, table, "/filters"), headers=alice)).json()

    by_condition = await _remove(client, alice, repository, table, ids, "amount")
    by_sort = await _remove(client, alice, repository, table, ids, "region")

    assert by_condition.status_code == by_sort.status_code == 409
    assert by_condition.json()["detail"] == {"in_use": [{"kind": "filter", "id": saved[0]["id"], "name": "Big"}]}
    assert by_sort.json()["detail"] == {"in_use": [{"kind": "filter", "id": saved[1]["id"], "name": "Sorted"}]}
    assert len((await client.get(_url(repository, table, ""), headers=alice)).json()["attributes"]) == 5


async def test_an_attribute_a_statistic_uses_cannot_be_removed(client, alice):
    repository, table, ids = await _shop(client, alice)
    grouped = (await client.post(_url(repository, table, "/statistics"), json=_statistic(ids), headers=alice)).json()
    summed = (
        await client.post(
            _url(repository, table, "/statistics"),
            json=_statistic(ids, name="Revenue", group_by=[{"field": ids["sold"], "bucket": "year"}], aggregation={"fn": "sum", "attribute_id": ids["amount"]}),
            headers=alice,
        )
    ).json()

    by_dimension = await _remove(client, alice, repository, table, ids, "region")
    by_aggregation = await _remove(client, alice, repository, table, ids, "amount")
    both = await _remove(client, alice, repository, table, ids, "region", "amount")

    assert by_dimension.json()["detail"] == {"in_use": [{"kind": "statistic", "id": grouped["id"], "name": "By region"}]}
    assert by_aggregation.json()["detail"] == {"in_use": [{"kind": "statistic", "id": summed["id"], "name": "Revenue"}]}
    assert [item["name"] for item in both.json()["detail"]["in_use"]] == ["By region", "Revenue"]


async def test_removing_an_attribute_nothing_uses_is_still_fine_and_so_is_one_whose_users_are_gone(client, alice):
    repository, table, ids = await _shop(client, alice)
    created = (await client.post(_url(repository, table, "/statistics"), json=_statistic(ids), headers=alice)).json()

    assert (await _remove(client, alice, repository, table, ids, "paid")).status_code == 200

    await client.delete(_url(repository, table, f"/statistics/{created['id']}"), headers=alice)
    remaining = {key: value for key, value in ids.items() if key != "paid"}
    assert (await _remove(client, alice, repository, table, remaining, "region")).status_code == 200
