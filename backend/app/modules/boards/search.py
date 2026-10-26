# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Searching categories by their title and description, ignoring case and
diacritics, without a database extension.

Category.search_text holds the title and description already put through
normalize_text() (it is derived when the row is written, see models.py), and
the visitor's query goes through the same function, so "priroda" finds
"Příroda" and the other way round; matching is then a plain LIKE on the
normalized text. This module imports no model, so the model can import it."""

import re
import unicodedata

from sqlalchemy import and_, false

from app.services.sql import like_pattern

_SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _SPACES.sub(" ", stripped.casefold()).strip()


def build_search_text(title: str, description: str) -> str:
    return normalize_text(f"{title} {description}")


def matches(query: str, column):
    """SQL condition: every word of `query` appears in `column`, a text column
    holding text already passed through normalize_text(). An empty
    (all-whitespace) query matches nothing - callers that treat it as "no
    search" skip the condition instead."""
    terms = [term for term in normalize_text(query).split(" ") if term]
    if not terms:
        return false()
    return and_(*(column.like(like_pattern(term), escape="\\") for term in terms))
