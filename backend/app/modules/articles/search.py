# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Diacritics- and case-insensitive text search without a database extension.

Both the stored Article.search_text and the visitor's query go through
normalize_text(), so "krava" finds "Kráva" and vice versa; matching is then
a plain LIKE on the already-normalized text. Other modules that search
articles use matches() so the rule is the same everywhere.
"""

import html
import re
import unicodedata

from sqlalchemy import and_, false

from app.modules.articles.models import Article

_TAG = re.compile(r"<[^>]*>")
_SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _SPACES.sub(" ", stripped.casefold()).strip()


def plain_text(content_html: str) -> str:
    """The text of (already sanitized) editor HTML, tags replaced by spaces so
    neighbouring paragraphs don't run together."""
    return html.unescape(_TAG.sub(" ", content_html))


def build_search_text(title: str, perex: str, content_html: str) -> str:
    return normalize_text(f"{title} {perex} {plain_text(content_html)}")


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def matches(query: str, column=None):
    """SQL condition: every word of `query` appears in `column`, a text column
    holding text already passed through normalize_text() (default: the
    article's own search_text). Other modules that keep their own normalized
    search text (the event calendar) pass it here so the rule stays the same.
    An empty (all-whitespace) query matches nothing."""
    column = Article.search_text if column is None else column
    terms = normalize_text(query).split(" ")
    terms = [term for term in terms if term]
    if not terms:
        return false()
    return and_(*(column.like(_like_pattern(term), escape="\\") for term in terms))
