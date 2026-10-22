# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What a statistic computes, against the real database (the rules and the shape
of the result are in test_modules_repository_pivot.py, saving them in
test_modules_repository_saved.py)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.repository import pivot
from tests.repository_support import (  # noqa: F401  (the fixtures are used by name)
    BASE,
    _overrides,
    add_record,
    alice,
    attribute,
    bob,
    client,
    create_repository,
    create_table,
    make_table,
    make_user,
    post_record,
    put_attributes,
)


def _url(repository: dict, table: dict, suffix: str) -> str:
    return f"{BASE}/repositories/{repository['slug']}/tables/{table['slug']}{suffix}"


async def _sales(client, db_session, headers):
    """Clients, and Sales with a text, a yes/no, a number, a date, a date and time and a
    reference. Six records count (the 7th is deleted):

        region  paid   amount  sold        called              client
        North   true   100     2026-01-15  2026-01-15T08:30    Anna
        North   false  50      2026-01-20  2026-01-15T17:00    Anna
        South   true   200     2026-02-03  2026-02-03T09:00    Boris
        South   true   300     2026-02-28  -                   Boris
        South   false  25.5    2026-03-01  -                   -
        -       true   -       2026-03-10  -                   Anna
        North   true   1000    2026-01-05  -                   Anna      (deleted)
    """
    repository = await create_repository(client, headers, name="Shop")
    clients = await create_table(client, headers, repository["slug"], name="Clients")
    anna = await post_record(client, headers, repository, clients, name="Anna")
    boris = await post_record(client, headers, repository, clients, name="Boris")
    attrs = {
        "region": attribute("text", "Region"),
        "paid": attribute("boolean", "Paid"),
        "amount": attribute("number", "Amount"),
        "sold": attribute("date", "Sold on"),
        "called": attribute("datetime", "Called at"),
        "client": attribute("reference", "Client", config={"table_id": clients["id"]}),
    }
    sales = await create_table(client, headers, repository["slug"], name="Sales")
    assert (await put_attributes(client, headers, repository["slug"], sales["slug"], list(attrs.values()))).status_code == 200
    ids = {key: value["id"] for key, value in attrs.items()}
    rows = [
        dict(region="North", paid=True, amount=100, sold="2026-01-15", called="2026-01-15T08:30", client=anna["id"]),
        dict(region="North", paid=False, amount=50, sold="2026-01-20", called="2026-01-15T17:00", client=anna["id"]),
        dict(region="South", paid=True, amount=200, sold="2026-02-03", called="2026-02-03T09:00", client=boris["id"]),
        dict(region="South", paid=True, amount=300, sold="2026-02-28", client=boris["id"]),
        dict(region="South", paid=False, amount=25.5, sold="2026-03-01"),
        dict(paid=True, sold="2026-03-10", client=anna["id"]),
    ]
    for index, row in enumerate(rows):
        await add_record(db_session, sales["id"], name=f"Sale {index + 1}", data={ids[key]: value for key, value in row.items()})
    await add_record(
        db_session,
        sales["id"],
        name="Sale 7",
        data={ids["region"]: "North", ids["paid"]: True, ids["amount"]: 1000, ids["sold"]: "2026-01-05", ids["client"]: anna["id"]},
        deleted=True,
    )
    return repository, sales, ids, clients


async def _result(client, headers, repository, table, group_by, aggregation=None, **extra):
    body = {"name": "Preview", "group_by": group_by, "aggregation": aggregation or {"fn": "count"}, **extra}
    resp = await client.post(_url(repository, table, "/statistics-preview"), json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _keys(result: dict, which: str = "rows") -> list:
    return [item["key"] for item in result[which]]


def _flat(result: dict) -> list:
    return [row[0] for row in result["values"]]


# --- One dimension ----------------------------------------------------------------------------


async def test_count_by_a_text_attribute(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["region"]}])

    assert (result["dimensions"], _keys(result), _flat(result)) == (1, ["North", "South", None], [2, 3, 1])
    assert result["columns"] == [] and result["column_totals"] == []
    assert (result["row_totals"], result["total"], result["truncated"]) == ([2, 3, 1], 6, False)


@pytest.mark.parametrize(
    ("fn", "expected", "total"),
    [
        ("sum", [150, 525.5, None], 675.5),
        ("min", [50, 25.5, None], 25.5),
        ("max", [100, 300, None], 300),
    ],
)
async def test_other_functions_work_on_a_number_and_ignore_records_without_one(client, db_session, alice, fn, expected, total):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["region"]}], {"fn": fn, "attribute_id": ids["amount"]})

    assert (_keys(result), _flat(result), result["total"]) == (["North", "South", None], expected, total)


async def test_the_average_total_is_the_average_of_all_the_records_not_of_the_averages(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["region"]}], {"fn": "avg", "attribute_id": ids["amount"]})

    assert result["rows"][0]["key"] == "North" and _flat(result)[0] == 75
    assert _flat(result)[1] == pytest.approx(175.1666667)
    assert _flat(result)[2] is None
    assert result["total"] == pytest.approx(135.1)  # 675.5 / 5; the average of 75 and 175.17 would be 125.08


async def test_a_boolean_is_grouped_by_its_value(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["paid"]}])

    assert (_keys(result), _flat(result)) == (["false", "true"], [2, 4])


@pytest.mark.parametrize(
    ("bucket", "keys", "counts"),
    [
        ("month", ["2026-01", "2026-02", "2026-03"], [2, 2, 2]),
        ("year", ["2026"], [6]),
        ("day", ["2026-01-15", "2026-01-20", "2026-02-03", "2026-02-28", "2026-03-01", "2026-03-10"], [1, 1, 1, 1, 1, 1]),
    ],
)
async def test_a_date_is_grouped_by_day_month_or_year(client, db_session, alice, bucket, keys, counts):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["sold"], "bucket": bucket}])

    assert (_keys(result), _flat(result)) == (keys, counts)


async def test_a_date_and_time_is_grouped_too_and_a_missing_one_is_a_group_of_its_own(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    by_day = await _result(client, alice, repository, sales, [{"field": ids["called"], "bucket": "day"}])
    by_month = await _result(client, alice, repository, sales, [{"field": ids["called"], "bucket": "month"}])

    assert (_keys(by_day), _flat(by_day)) == (["2026-01-15", "2026-02-03", None], [2, 1, 3])
    assert (_keys(by_month), _flat(by_month)) == (["2026-01", "2026-02", None], [2, 1, 3])


async def test_created_on_is_grouped_by_its_date_in_prague(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)
    this_month = datetime.now(ZoneInfo("Europe/Prague")).strftime("%Y-%m")

    result = await _result(client, alice, repository, sales, [{"field": "created_on", "bucket": "month"}])

    assert (_keys(result), _flat(result)) == ([this_month], [6])


async def test_a_number_is_grouped_by_its_value_in_numeric_order(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["amount"]}])

    assert (_keys(result), _flat(result)) == ([25.5, 50, 100, 200, 300, None], [1, 1, 1, 1, 1, 1])


async def test_a_reference_is_grouped_by_the_record_it_points_at_and_named_by_it(client, db_session, alice):
    repository, sales, ids, clients = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["client"]}])

    assert [item["label"] for item in result["rows"]] == ["Anna", "Boris", None]
    assert _flat(result) == [3, 2, 1]
    assert result["rows"][2]["key"] is None


async def test_a_reference_to_a_deleted_record_is_still_named(client, db_session, alice):
    repository, sales, ids, clients = await _sales(client, db_session, alice)
    await client.delete(f"{BASE}/repositories/{repository['slug']}/tables/clients/records/boris", headers=alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["client"]}])

    assert [item["label"] for item in result["rows"]] == ["Anna", "Boris", None]


# --- Two dimensions -----------------------------------------------------------------------------


async def test_two_dimensions_make_a_pivot_table(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["region"]}, {"field": ids["paid"]}])

    assert result["dimensions"] == 2
    assert _keys(result) == ["North", "South", None]
    assert _keys(result, "columns") == ["false", "true"]
    assert result["values"] == [[1, 1], [1, 2], [0, 1]]  # no record for a combination is 0 for a count
    assert (result["row_totals"], result["column_totals"], result["total"]) == ([2, 3, 1], [2, 4], 6)


async def test_a_pivot_of_sums_has_empty_cells_and_exact_totals(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(
        client, alice, repository, sales, [{"field": ids["region"]}, {"field": ids["paid"]}], {"fn": "sum", "attribute_id": ids["amount"]}
    )

    assert result["values"] == [[50, 100], [25.5, 500], [None, None]]
    assert (result["row_totals"], result["column_totals"], result["total"]) == ([150, 525.5, None], [75.5, 600], 675.5)


async def test_a_pivot_by_two_dates_buckets_each_on_its_own(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    result = await _result(client, alice, repository, sales, [{"field": ids["sold"], "bucket": "month"}, {"field": ids["paid"]}])

    assert _keys(result) == ["2026-01", "2026-02", "2026-03"]
    assert result["values"] == [[1, 1], [0, 2], [1, 1]]


# --- Which records count ------------------------------------------------------------------------


async def test_deleted_records_do_not_count_unless_the_filter_says_so(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)
    everything = await client.post(_url(repository, sales, "/filters"), json={"name": "All", "include_deleted": True}, headers=alice)
    assert everything.status_code == 201

    plain = await _result(client, alice, repository, sales, [{"field": ids["region"]}])
    with_deleted = await _result(client, alice, repository, sales, [{"field": ids["region"]}], filter_id=everything.json()["id"])

    assert (_flat(plain), plain["total"]) == ([2, 3, 1], 6)
    assert (_flat(with_deleted), with_deleted["total"]) == ([3, 3, 1], 7)


async def test_a_statistic_counts_only_the_records_of_its_filter(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)
    paid = await client.post(
        _url(repository, sales, "/filters"),
        json={"name": "Paid", "conditions": [{"field": ids["paid"], "op": "equals", "value": True}]},
        headers=alice,
    )

    result = await _result(client, alice, repository, sales, [{"field": ids["region"]}], filter_id=paid.json()["id"])

    assert (_keys(result), _flat(result), result["total"]) == (["North", "South", None], [1, 2, 1], 4)


async def test_a_filters_quick_search_and_conditions_apply_together(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)
    both = await client.post(
        _url(repository, sales, "/filters"),
        json={"name": "Search", "q": "sale", "conditions": [{"field": ids["amount"], "op": "gte", "value": 100}]},
        headers=alice,
    )

    result = await _result(client, alice, repository, sales, [{"field": ids["region"]}], filter_id=both.json()["id"])

    assert (_keys(result), _flat(result), result["total"]) == (["North", "South"], [1, 2], 3)


async def test_a_table_without_records_has_an_empty_statistic(client, alice):
    repository, table, _ = await make_table(client, alice, attribute("text", "Region"))
    region = table["attributes"][0]["id"]

    result = await _result(client, alice, repository, table, [{"field": region}])

    assert (result["rows"], result["values"], result["total"], result["truncated"]) == ([], [], 0, False)


async def test_the_sum_of_nothing_is_empty_not_zero(client, alice):
    repository, table, _ = await make_table(client, alice, attribute("text", "Region"), attribute("number", "Amount"))
    region, amount = (a["id"] for a in table["attributes"])

    result = await _result(client, alice, repository, table, [{"field": region}], {"fn": "sum", "attribute_id": amount})

    assert (result["rows"], result["total"]) == ([], None)


# --- Cut down results ---------------------------------------------------------------------------------


async def test_a_statistic_with_too_many_groups_is_cut_but_its_total_is_not(client, db_session, alice):
    repository, table, _ = await make_table(client, alice, attribute("text", "Region"))
    region = table["attributes"][0]["id"]
    for index in range(pivot.MAX_GROUPS + 20):
        await add_record(db_session, table["id"], name=f"R {index}", data={region: f"r{index:03d}"})

    result = await _result(client, alice, repository, table, [{"field": region}])

    assert len(result["rows"]) == pivot.MAX_GROUPS
    assert result["truncated"] is True
    assert result["total"] == pivot.MAX_GROUPS + 20
    assert _keys(result)[0] == "r000"


async def test_a_pivot_with_too_many_cells_is_cut_to_the_cell_limit(client, db_session, alice):
    repository, table, _ = await make_table(client, alice, attribute("text", "Region"), attribute("text", "Kind"))
    region, kind = (a["id"] for a in table["attributes"])
    for index in range(30):
        await add_record(db_session, table["id"], name=f"R {index}", data={region: f"r{index:02d}", kind: f"k{index % 15:02d}"})

    result = await _result(client, alice, repository, table, [{"field": region}, {"field": kind}])

    assert len(result["columns"]) == pivot.MAX_COLUMNS
    assert len(result["rows"]) * len(result["columns"]) <= pivot.MAX_CELLS
    assert result["truncated"] is True
    assert result["total"] == 30
    assert all(len(row) == len(result["columns"]) for row in result["values"])


# --- Saved statistics ---------------------------------------------------------------------------------


async def test_a_saved_statistic_has_a_result_of_its_own(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)
    saved = (
        await client.post(
            _url(repository, sales, "/statistics"),
            json={"name": "By region", "group_by": [{"field": ids["region"]}], "aggregation": {"fn": "count"}},
            headers=alice,
        )
    ).json()

    result = await client.get(_url(repository, sales, f"/statistics/{saved['id']}/result"), headers=alice)

    assert result.status_code == 200
    assert (_keys(result.json()), _flat(result.json())) == (["North", "South", None], [2, 3, 1])
    assert result.json() == await _result(client, alice, repository, sales, [{"field": ids["region"]}])


async def test_the_results_of_all_the_statistics_that_are_shown(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)
    base = {"group_by": [{"field": ids["region"]}], "aggregation": {"fn": "count"}}
    for name, display in (("Hidden", "hidden"), ("Table", "table"), ("Chart", "chart"), ("Both", "both")):
        await client.post(_url(repository, sales, "/statistics"), json={"name": name, "display": display, **base}, headers=alice)

    resp = await client.get(_url(repository, sales, "/statistics-results"), headers=alice)

    assert resp.status_code == 200
    items = resp.json()
    assert [item["statistic"]["name"] for item in items] == ["Table", "Chart", "Both"]
    assert all(item["result"]["total"] == 6 for item in items)
    assert [item["statistic"]["display"] for item in items] == ["table", "chart", "both"]


async def test_there_are_no_results_without_statistics(client, db_session, alice):
    repository, sales, _, _ = await _sales(client, db_session, alice)

    assert (await client.get(_url(repository, sales, "/statistics-results"), headers=alice)).json() == []


async def test_a_preview_of_an_invalid_statistic_is_a_422(client, db_session, alice):
    repository, sales, ids, _ = await _sales(client, db_session, alice)

    resp = await client.post(
        _url(repository, sales, "/statistics-preview"),
        json={"name": "x", "group_by": [{"field": ids["sold"]}], "aggregation": {"fn": "count"}},
        headers=alice,
    )

    assert (resp.status_code, resp.json()["detail"]) == (422, {"errors": {"group_by.0": "bucket_required"}})


async def test_a_users_statistic_only_ever_counts_their_own_records(client, db_session, alice, bob):
    repository, sales, ids, _ = await _sales(client, db_session, alice)
    other_repository, other_table, _ = await make_table(client, bob, attribute("text", "Region"))
    other_region = other_table["attributes"][0]["id"]
    await add_record(db_session, other_table["id"], name="Bobs", data={other_region: "North"})

    mine = await _result(client, alice, repository, sales, [{"field": ids["region"]}])
    theirs = await _result(client, bob, other_repository, other_table, [{"field": other_region}])

    assert mine["total"] == 6
    assert theirs["total"] == 1
