# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""app/services/sql.py"""

import pytest

from app.services.sql import like_pattern


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("abc", "%abc%"),
        ("", "%%"),
        ("100%", "%100\%%"),
        ("snake_case", "%snake\_case%"),
        ("a\b", "%a\\b%"),
        ("%_\\", "%\%\_\\%"),
    ],
)
def test_like_pattern_matches_anywhere_and_takes_wildcards_literally(text, pattern):
    assert like_pattern(text) == pattern
