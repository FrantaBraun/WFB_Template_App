# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""app/services/text_search.py: the Python-side folding, and - against the real
database, since the matching itself is SQL (lower() + translate() + LIKE) -
the "every word, case and diacritics ignored" behavior and its edge cases.
Rows are created inside the test's own rolled-back transaction and every query
is scoped to this test's own team, so other data in the database can't affect
the result."""

import uuid

from sqlalchemy import select

from app.models.api_document import ApiDocument
from app.models.team import Team
from app.models.user import User
from app.services.text_search import MAX_TERMS, fold, matches_all_terms, search_terms


def test_fold_lowercases_and_strips_diacritics():
    assert fold("Zákaznický PORTÁL") == "zakaznicky portal"
    assert fold("ŘEŘICHA Ďábel Žluťoučký Kůň") == "rericha dabel zlutoucky kun"
    assert fold("Łódź Đá Øl") == "lodz da ol"
    assert fold("plain ascii 123") == "plain ascii 123"


def test_search_terms_splits_on_whitespace_and_ignores_blanks():
    assert search_terms("  Foo   BÁR\tbaz ") == ["foo", "bar", "baz"]
    assert search_terms("") == []
    assert search_terms("   ") == []
    assert search_terms(None) == []


def test_search_terms_caps_the_number_of_words():
    assert len(search_terms(" ".join(f"w{i}" for i in range(50)))) == MAX_TERMS


def test_matches_all_terms_is_none_without_words():
    assert matches_all_terms("  ", ApiDocument.title) is None
    assert matches_all_terms(None, ApiDocument.title) is None


async def _team_and_user(db_session) -> tuple[Team, User]:
    user = User(auth_sub=uuid.uuid4(), email=f"{uuid.uuid4().hex}@example.com")
    team = Team(name="Search Team")
    db_session.add_all([user, team])
    await db_session.flush()
    return team, user


async def _doc(db_session, team: Team, user: User, title: str, notes: str | None = None) -> ApiDocument:
    doc = ApiDocument(team_id=team.id, title=title, notes=notes, created_by_user_id=user.id)
    db_session.add(doc)
    await db_session.flush()
    return doc


async def _titles(db_session, team: Team, query: str) -> list[str]:
    condition = matches_all_terms(query, ApiDocument.title, ApiDocument.notes)
    stmt = select(ApiDocument.title).where(ApiDocument.team_id == team.id).order_by(ApiDocument.title)
    if condition is not None:
        stmt = stmt.where(condition)
    return list((await db_session.execute(stmt)).scalars().all())


async def test_matching_ignores_case_and_diacritics_on_either_side(db_session):
    team, user = await _team_and_user(db_session)
    await _doc(db_session, team, user, "Zákaznický portál")
    await _doc(db_session, team, user, "Łódź ŘÍZENÍ")

    assert await _titles(db_session, team, "zakaznicky PORTAL") == ["Zákaznický portál"]
    assert await _titles(db_session, team, "Zákaznický") == ["Zákaznický portál"]
    assert await _titles(db_session, team, "lodz rizeni") == ["Łódź ŘÍZENÍ"]
    assert await _titles(db_session, team, "ŘÍZENÍ") == ["Łódź ŘÍZENÍ"]


async def test_every_word_must_match_in_some_column(db_session):
    team, user = await _team_and_user(db_session)
    await _doc(db_session, team, user, "Billing", notes="Fakturační rozhraní")
    await _doc(db_session, team, user, "Portal", notes="Jen zákazníci")

    assert await _titles(db_session, team, "billing fakturacni") == ["Billing"]
    assert await _titles(db_session, team, "billing zakaznici") == []
    assert await _titles(db_session, team, "rozhrani") == ["Billing"]


async def test_a_missing_description_is_treated_as_empty(db_session):
    team, user = await _team_and_user(db_session)
    await _doc(db_session, team, user, "No notes", notes=None)

    assert await _titles(db_session, team, "notes") == ["No notes"]
    assert await _titles(db_session, team, "anything-in-notes") == []


async def test_like_wildcards_in_the_query_are_literal(db_session):
    team, user = await _team_and_user(db_session)
    await _doc(db_session, team, user, "100% coverage")
    await _doc(db_session, team, user, "1000 coverage")
    await _doc(db_session, team, user, "a_b")
    await _doc(db_session, team, user, "axb")

    assert await _titles(db_session, team, "100%") == ["100% coverage"]
    assert await _titles(db_session, team, "a_b") == ["a_b"]
    assert await _titles(db_session, team, "%") == ["100% coverage"]


async def test_blank_query_applies_no_filter(db_session):
    team, user = await _team_and_user(db_session)
    await _doc(db_session, team, user, "One")
    await _doc(db_session, team, user, "Two")

    assert await _titles(db_session, team, "   ") == ["One", "Two"]
