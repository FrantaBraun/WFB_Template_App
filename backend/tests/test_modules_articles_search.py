# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The articles module's text normalization (the same rule builds the stored
search text and normalizes every query, so they always match alike)."""

import pytest

from app.modules.articles.search import build_search_text, normalize_text, plain_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Příliš žluťoučký KŮŇ", "prilis zlutoucky kun"),
        ("  many   spaces\tand\nlines ", "many spaces and lines"),
        ("Ǆ Straße", "dz strasse"),
        ("", ""),
    ],
)
def test_normalize_text_lowercases_strips_diacritics_and_collapses_whitespace(raw, expected):
    assert normalize_text(raw) == expected


def test_plain_text_replaces_tags_with_spaces_and_unescapes_entities():
    assert plain_text("<p>a</p><p>b &amp; c</p><br>d").split() == ["a", "b", "&", "c", "d"]


def test_build_search_text_covers_title_perex_and_content():
    text = build_search_text("Jarní Bazar", "Perex ŽÁDNÝ", "<h2>Knihy</h2><p>a hračky</p>")

    assert text == "jarni bazar perex zadny knihy a hracky"
