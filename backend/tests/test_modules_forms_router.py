# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the forms module's administrators' API and for the service other
modules call (saving questions, storing and listing answers, statistics).

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` (whether the module is mounted on the real app
depends on the branch's backend/modules.json - see
test_modules_notifications_router.py). ASGITransport keeps the JWT
dependency chain and db_session on one event loop. Each test starts from
empty forms tables (inside its own rolled-back transaction).

Answers are seeded through the service itself (validate_answers +
store_submission), the way a consumer module stores them - the module has no
public route to post them to. created_at gets explicit values where order
matters: inside one transaction Postgres' now() is the same for every row."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.database import get_db
from app.models.user import User
from app.modules.forms import manifest, service
from app.modules.forms.models import Form, FormQuestion, FormSubmission
from app.modules.forms.router import router as forms_router
from app.modules.forms.schemas import QuestionsReplace

BASE = "/api/modules/forms"
OPTIONS = {"options": [{"id": "a", "label": "Alpha"}, {"id": "b", "label": "Beta"}]}
Q1, Q2, Q3, Q4 = (str(uuid.UUID(int=i)) for i in (101, 102, 103, 104))

_forms_app = FastAPI()
_forms_app.include_router(forms_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    # Answers refer to forms (ON DELETE RESTRICT): clear them first.
    for model in (FormSubmission, FormQuestion, Form):
        await db_session.execute(delete(model))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _forms_app.dependency_overrides[get_db] = lambda: db_session
    yield
    _forms_app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_forms_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    """An administrator of this application (local User.is_admin) - with a
    plain auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    """Not an administrator here - even though the auth service calls them
    "admin": role_name is global to the user, not per application."""
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


def _question(id, type, label="Q", config=None, conditions=(), required=False, help_text="") -> dict:
    return {"id": id, "type": type, "label": label, "help_text": help_text, "required": required, "config": config or {}, "conditions": list(conditions)}


async def _form(client, admin, questions=None, name="Registration") -> dict:
    created = await client.post(f"{BASE}/manage", json={"name": name}, headers=admin)
    assert created.status_code == 201, created.text
    form = created.json()
    if questions is not None:
        saved = await client.put(f"{BASE}/manage/{form['id']}/questions", json={"questions": questions}, headers=admin)
        assert saved.status_code == 200, saved.text
        form = saved.json()
    return form


async def _answer(db_session, form_id: str, raw: dict, *, minutes_ago: int = 0) -> FormSubmission:
    """Stores an answer the way a consumer module does."""
    form_uuid = uuid.UUID(form_id)
    questions = service.to_logic_questions(await service.get_questions(db_session, form_uuid))
    submission = await service.store_submission(db_session, form_uuid, service.validate_answers(questions, raw))
    submission.created_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc) - timedelta(minutes=minutes_ago)
    await db_session.commit()
    return submission


def test_manifest_has_no_requirements_and_mounts_the_router():
    assert manifest.key == "forms"
    assert manifest.router is forms_router
    assert manifest.requires == ()


# --- Administrator-only gate --------------------------------------------------------------


def _all_routes():
    """Every (method, path) of the module, read from the OpenAPI schema - the
    router is mounted as one object on newer FastAPI."""
    paths = _forms_app.openapi()["paths"]
    return [(method.upper(), path.removeprefix(BASE)) for path, operations in paths.items() for method in operations]


async def _call(client, method: str, path: str, headers: dict):
    concrete = path.replace("{form_id}", str(uuid.uuid4())).replace("{submission_id}", str(uuid.uuid4()))
    return await client.request(method, f"{BASE}{concrete}", headers=headers)


def test_there_are_routes_to_check_and_all_are_under_manage():
    routes = _all_routes()
    assert len(routes) >= 7
    assert all(path.startswith("/manage") for _, path in routes)


@pytest.mark.parametrize(("method", "path"), _all_routes())
async def test_anonymous_requests_are_rejected_on_every_route(client, method, path):
    assert (await _call(client, method, path, headers={})).status_code in (401, 403)


@pytest.mark.parametrize(("method", "path"), _all_routes())
async def test_non_admins_are_rejected_on_every_route(client, non_admin, method, path):
    resp = await _call(client, method, path, headers=non_admin)

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


# --- Forms and their questions -----------------------------------------------------------------


async def test_create_and_get_a_form(client, admin):
    created = await client.post(f"{BASE}/manage", json={"name": "Registration"}, headers=admin)

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Registration" and body["questions"] == []
    assert (await client.get(f"{BASE}/manage/{body['id']}", headers=admin)).json() == body


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "x" * 201}, {"name": "ok", "extra": 1}])
async def test_create_form_rejects_invalid_input(client, admin, body):
    assert (await client.post(f"{BASE}/manage", json=body, headers=admin)).status_code == 422


async def test_unknown_form_is_404_everywhere(client, admin):
    unknown = uuid.uuid4()

    assert (await client.get(f"{BASE}/manage/{unknown}", headers=admin)).status_code == 404
    assert (await client.put(f"{BASE}/manage/{unknown}/questions", json={"questions": []}, headers=admin)).status_code == 404
    assert (await client.delete(f"{BASE}/manage/{unknown}", headers=admin)).status_code == 404
    assert (await client.get(f"{BASE}/manage/{unknown}/submissions", headers=admin)).status_code == 404
    assert (await client.get(f"{BASE}/manage/{unknown}/stats", headers=admin)).status_code == 404


async def test_replace_questions_stores_them_in_order_with_defaults_filled(client, admin):
    form = await _form(
        client,
        admin,
        [
            _question(Q1, "text", "Name", required=True, help_text="As on your ID"),
            _question(Q2, "radio", "Colour", OPTIONS),
            _question(Q3, "number", "Age", {"min": 0, "max": 120}),
        ],
    )

    assert [q["id"] for q in form["questions"]] == [Q1, Q2, Q3]
    assert [q["position"] for q in form["questions"]] == [0, 1, 2]
    first = form["questions"][0]
    assert first["required"] is True and first["help_text"] == "As on your ID"
    assert first["config"] == {"multiline": False, "min_length": 0, "max_length": 2000, "regex": None}
    assert form["questions"][2]["config"] == {"kind": "integer", "min": 0.0, "max": 120.0}


async def test_replace_questions_reorders_updates_inserts_and_deletes_in_one_go(client, admin):
    form = await _form(client, admin, [_question(Q1, "text", "One"), _question(Q2, "text", "Two"), _question(Q3, "text", "Three")])

    saved = await client.put(
        f"{BASE}/manage/{form['id']}/questions",
        json={"questions": [_question(Q3, "text", "Three, moved first"), _question(Q1, "number", "One, now a number"), _question(Q4, "text", "Brand new")]},
        headers=admin,
    )

    assert saved.status_code == 200
    questions = saved.json()["questions"]
    assert [q["id"] for q in questions] == [Q3, Q1, Q4]  # Q2 is gone
    assert [q["label"] for q in questions] == ["Three, moved first", "One, now a number", "Brand new"]
    assert questions[1]["type"] == "number"


async def test_replacing_with_an_empty_list_removes_every_question(client, admin):
    form = await _form(client, admin, [_question(Q1, "text")])

    saved = await client.put(f"{BASE}/manage/{form['id']}/questions", json={"questions": []}, headers=admin)

    assert saved.json()["questions"] == []


async def test_replace_questions_is_all_or_nothing(client, admin):
    form = await _form(client, admin, [_question(Q1, "text", "Original")])

    bad = await client.put(
        f"{BASE}/manage/{form['id']}/questions",
        json={"questions": [_question(Q1, "text", "Changed"), _question(Q2, "checkbox", config={})]},
        headers=admin,
    )

    assert bad.status_code == 422
    assert [q["label"] for q in (await client.get(f"{BASE}/manage/{form['id']}", headers=admin)).json()["questions"]] == ["Original"]


async def test_a_question_id_that_belongs_to_another_form_is_a_409_and_changes_nothing(client, admin):
    first = await _form(client, admin, [_question(Q1, "text", "Mine")], name="First")
    second = await _form(client, admin, [_question(Q2, "text", "Theirs")], name="Second")

    resp = await client.put(f"{BASE}/manage/{second['id']}/questions", json={"questions": [_question(Q1, "text", "Stolen"), _question(Q2, "text")]}, headers=admin)

    assert resp.status_code == 409
    assert (await client.get(f"{BASE}/manage/{first['id']}", headers=admin)).json()["questions"][0]["label"] == "Mine"
    assert [q["id"] for q in (await client.get(f"{BASE}/manage/{second['id']}", headers=admin)).json()["questions"]] == [Q2]


@pytest.mark.parametrize(
    "questions",
    [
        [_question(Q1, "text", "")],
        [_question(Q1, "slider")],
        [_question(Q1, "checkbox", config={})],
        [_question(Q1, "text", config={"regex": "(unclosed"})],
        [_question(Q1, "text", config={"regex": "(a|aa)+$"})],  # catastrophic backtracking
        [_question(Q1, "text"), _question(Q1, "text")],
        [_question(Q1, "text", conditions=[{"question_id": Q2, "operator": "answered"}]), _question(Q2, "text")],  # refers to a later question
        [_question(Q1, "text", conditions=[{"question_id": Q1, "operator": "answered"}])],  # itself
        [_question(Q1, "radio", config=OPTIONS), _question(Q2, "text", conditions=[{"question_id": Q1, "operator": "gt", "value": 1}])],
        [_question(Q1, "radio", config=OPTIONS), _question(Q2, "text", conditions=[{"question_id": Q1, "operator": "equals", "value": "zzz"}])],
        [_question(Q1, "text", conditions=[{"question_id": "not-a-uuid", "operator": "answered"}])],
        [{"id": "not-a-uuid", "type": "text", "label": "x"}],
    ],
)
async def test_replace_questions_rejects_invalid_forms(client, admin, questions):
    form = await _form(client, admin)

    resp = await client.put(f"{BASE}/manage/{form['id']}/questions", json={"questions": questions}, headers=admin)

    assert resp.status_code == 422, resp.text


async def test_conditions_are_stored_normalised(client, admin):
    form = await _form(
        client,
        admin,
        [
            _question(Q1, "number"),
            _question(Q2, "text", conditions=[{"question_id": Q1, "operator": "gte", "value": 10.0}]),
            _question(Q3, "text", conditions=[{"question_id": Q1, "operator": "answered", "value": "ignored"}]),
        ],
    )

    assert form["questions"][1]["conditions"] == [{"question_id": Q1, "operator": "gte", "value": 10}]
    assert form["questions"][2]["conditions"] == [{"question_id": Q1, "operator": "answered", "value": None}]


async def test_delete_form_removes_its_questions(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "text")])

    resp = await client.delete(f"{BASE}/manage/{form['id']}", headers=admin)

    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/manage/{form['id']}", headers=admin)).status_code == 404
    assert (await db_session.scalars(select(FormQuestion))).all() == []


async def test_a_form_with_answers_cannot_be_deleted_until_they_are(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "text", "Name")])
    submission_id = (await _answer(db_session, form["id"], {Q1: "Eva"})).id  # read now: the router's rollback expires the instance

    blocked = await client.delete(f"{BASE}/manage/{form['id']}", headers=admin)

    assert blocked.status_code == 409
    assert (await client.get(f"{BASE}/manage/{form['id']}", headers=admin)).status_code == 200

    assert await service.delete_submissions(db_session, [submission_id]) == 1
    await db_session.commit()
    assert (await client.delete(f"{BASE}/manage/{form['id']}", headers=admin)).status_code == 204


# --- Browsing the answers ----------------------------------------------------------------------


async def test_submissions_are_listed_newest_first_with_their_snapshot(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "text", "Name"), _question(Q2, "radio", "Colour", OPTIONS)])
    await _answer(db_session, form["id"], {Q1: "Oldest", Q2: "a"}, minutes_ago=30)
    await _answer(db_session, form["id"], {Q1: "Newest", Q2: "b"}, minutes_ago=0)
    await _answer(db_session, form["id"], {Q1: "Middle"}, minutes_ago=10)

    resp = await client.get(f"{BASE}/manage/{form['id']}/submissions", headers=admin)

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["answers"][0]["value"] for i in items] == ["Newest", "Middle", "Oldest"]
    assert items[0]["form_id"] == form["id"]
    assert items[0]["answers"][1] == {
        "question_id": Q2, "position": 1, "label": "Colour", "type": "radio",
        "shown": True, "value": "b", "display": "Beta", "options": OPTIONS["options"],
    }
    assert resp.json()["has_more"] is False


async def test_submissions_are_paged(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "text", "Name")])
    for i in range(5):
        await _answer(db_session, form["id"], {Q1: f"n{i}"}, minutes_ago=i)

    first = (await client.get(f"{BASE}/manage/{form['id']}/submissions", params={"limit": 2}, headers=admin)).json()
    last = (await client.get(f"{BASE}/manage/{form['id']}/submissions", params={"limit": 2, "offset": 4}, headers=admin)).json()

    assert [i["answers"][0]["value"] for i in first["items"]] == ["n0", "n1"] and first["has_more"] is True
    assert [i["answers"][0]["value"] for i in last["items"]] == ["n4"] and last["has_more"] is False
    assert (await client.get(f"{BASE}/manage/{form['id']}/submissions", params={"limit": 0}, headers=admin)).status_code == 422
    assert (await client.get(f"{BASE}/manage/{form['id']}/submissions", params={"limit": 101}, headers=admin)).status_code == 422


async def test_one_submission_of_a_form_and_not_of_another(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "text", "Name")])
    other = await _form(client, admin, [], name="Other")
    submission = await _answer(db_session, form["id"], {Q1: "Eva"})

    ok = await client.get(f"{BASE}/manage/{form['id']}/submissions/{submission.id}", headers=admin)
    wrong_form = await client.get(f"{BASE}/manage/{other['id']}/submissions/{submission.id}", headers=admin)
    unknown = await client.get(f"{BASE}/manage/{form['id']}/submissions/{uuid.uuid4()}", headers=admin)

    assert ok.status_code == 200 and ok.json()["answers"][0]["value"] == "Eva"
    assert wrong_form.status_code == 404 and unknown.status_code == 404


async def test_the_form_without_answers_lists_nothing_and_has_empty_statistics(client, admin):
    form = await _form(client, admin, [_question(Q1, "text")])

    assert (await client.get(f"{BASE}/manage/{form['id']}/submissions", headers=admin)).json() == {"items": [], "has_more": False}
    assert (await client.get(f"{BASE}/manage/{form['id']}/stats", headers=admin)).json() == {"submission_count": 0, "questions": []}


# --- Statistics ----------------------------------------------------------------------------------


async def _survey(client, admin, db_session) -> dict:
    form = await _form(
        client,
        admin,
        [
            _question(Q1, "radio", "Come?", OPTIONS, required=True),
            _question(Q2, "text", "Why not?", conditions=[{"question_id": Q1, "operator": "equals", "value": "b"}]),
            _question(Q3, "number", "Guests", {"min": 0}),
        ],
    )
    await _answer(db_session, form["id"], {Q1: "a", Q3: 2}, minutes_ago=3)
    await _answer(db_session, form["id"], {Q1: "b", Q2: "busy", Q3: 4}, minutes_ago=2)
    await _answer(db_session, form["id"], {Q1: "b", Q3: 6}, minutes_ago=1)
    return form


async def test_statistics_of_a_form_with_a_conditional_question(client, admin, db_session):
    form = await _survey(client, admin, db_session)

    stats = (await client.get(f"{BASE}/manage/{form['id']}/stats", headers=admin)).json()

    assert stats["submission_count"] == 3
    by_id = {q["question_id"]: q for q in stats["questions"]}
    assert [q["question_id"] for q in stats["questions"]] == [Q1, Q2, Q3]
    assert [(o["id"], o["count"]) for o in by_id[Q1]["options"]] == [("a", 1), ("b", 2)]
    assert (by_id[Q2]["shown_count"], by_id[Q2]["answered_count"]) == (2, 1)  # shown to the two who said "b", one answered
    assert by_id[Q3]["numeric"] == {"min": 2, "max": 6, "average": 4, "median": 4}


async def test_statistics_survive_the_question_being_edited_and_deleted_afterwards(client, admin, db_session):
    form = await _survey(client, admin, db_session)

    # Reword Q1, rename an option, drop Q2 entirely.
    await client.put(
        f"{BASE}/manage/{form['id']}/questions",
        json={"questions": [_question(Q1, "radio", "Will you come? (new wording)", {"options": [{"id": "b", "label": "Maybe (renamed)"}]}), _question(Q3, "number", "Guests", {"min": 0})]},
        headers=admin,
    )
    stats = (await client.get(f"{BASE}/manage/{form['id']}/stats", headers=admin)).json()

    by_id = {q["question_id"]: q for q in stats["questions"]}
    assert Q2 in by_id and by_id[Q2]["label"] == "Why not?"  # deleted since, still summarised
    assert by_id[Q1]["label"] == "Come?"  # every stored answer was given to the old wording
    assert [(o["id"], o["label"], o["count"]) for o in by_id[Q1]["options"]] == [("a", "Alpha", 1), ("b", "Beta", 2)]

    # Everything already stored is untouched; the next answer carries the new wording and the old option is gone from it.
    newer = await _answer(db_session, form["id"], {Q1: "b", Q3: 1})
    entry = (await client.get(f"{BASE}/manage/{form['id']}/submissions/{newer.id}", headers=admin)).json()["answers"][0]
    assert entry["label"] == "Will you come? (new wording)" and entry["display"] == "Maybe (renamed)"


# --- The service other modules call ------------------------------------------------------------


async def test_the_service_lists_and_summarises_only_the_submissions_it_is_given(client, admin, db_session):
    form = await _survey(client, admin, db_session)
    everything, _ = await service.list_submissions(db_session, uuid.UUID(form["id"]))
    kept = [everything[0].id, everything[2].id]  # newest and oldest; the middle one "was cancelled"

    listed, has_more = await service.list_submissions(db_session, uuid.UUID(form["id"]), submission_ids=kept)
    stats = await service.compute_stats(db_session, uuid.UUID(form["id"]), submission_ids=kept)
    nobody = await service.compute_stats(db_session, uuid.UUID(form["id"]), submission_ids=[])

    assert [s.id for s in listed] == kept and has_more is False
    assert stats["submission_count"] == 2
    assert {q["question_id"]: q for q in stats["questions"]}[Q3]["numeric"]["average"] == 4
    assert nobody == {"submission_count": 0, "questions": []}
    assert (await service.compute_stats(db_session, uuid.UUID(form["id"])))["submission_count"] == 3


async def test_the_service_paginates_with_a_filter(db_session, client, admin):
    form = await _survey(client, admin, db_session)
    everything, _ = await service.list_submissions(db_session, uuid.UUID(form["id"]))

    page, has_more = await service.list_submissions(db_session, uuid.UUID(form["id"]), submission_ids=[s.id for s in everything], limit=2)

    assert len(page) == 2 and has_more is True


async def test_an_answer_that_fails_validation_stores_nothing(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "number", "Guests", {"min": 1})])
    questions = service.to_logic_questions(await service.get_questions(db_session, uuid.UUID(form["id"])))

    with pytest.raises(service.FormValidationError) as excinfo:
        service.validate_answers(questions, {Q1: 0})

    assert excinfo.value.errors == {Q1: "too_small"}
    assert (await db_session.scalars(select(FormSubmission))).all() == []


async def test_delete_submissions_reports_how_many_it_removed(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "text")])
    first = await _answer(db_session, form["id"], {Q1: "a"})
    second = await _answer(db_session, form["id"], {Q1: "b"})

    assert await service.delete_submissions(db_session, []) == 0
    assert await service.delete_submissions(db_session, [first.id, uuid.uuid4()]) == 1
    remaining, _ = await service.list_submissions(db_session, uuid.UUID(form["id"]))
    assert [s.id for s in remaining] == [second.id]


async def test_the_service_creates_a_form_and_refuses_to_delete_one_in_use(client, admin, db_session):
    form = await service.create_form(db_session, "Made by a consumer")
    await service.replace_questions(db_session, form.id, QuestionsReplace.model_validate({"questions": [_question(Q1, "text", "Name")]}).questions)
    await db_session.commit()
    await _answer(db_session, str(form.id), {Q1: "Eva"})

    with pytest.raises(service.FormInUseError):
        await service.delete_form(db_session, form.id)
    assert await service.delete_form(db_session, uuid.uuid4()) is False


async def test_question_rows_convert_to_the_plain_objects_the_rules_use(client, admin, db_session):
    form = await _form(client, admin, [_question(Q1, "radio", "Colour", OPTIONS, required=True), _question(Q2, "text")])

    questions = service.to_logic_questions(await service.get_questions(db_session, uuid.UUID(form["id"])))

    assert [(q.id, q.type, q.label, q.required, q.position) for q in questions] == [(Q1, "radio", "Colour", True, 0), (Q2, "text", "Q", False, 1)]
    assert questions[0].config["options"] == OPTIONS["options"]
