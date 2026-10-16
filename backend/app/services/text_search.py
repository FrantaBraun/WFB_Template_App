# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Free-text search over a few text columns: every whitespace-separated word of
the query must appear (as a substring) in at least one of the columns, with
case and diacritics ignored - typing "zakaznik" finds "Zákaznický portál".

Done with plain SQL (lower() + translate()) rather than Postgres' unaccent
extension, so it needs no CREATE EXTENSION and works on any deployment's
database. The same character table is applied to the query in Python and to
the columns in SQL, so both sides always fold identically."""

import unicodedata

from sqlalchemy import Text, and_, func, or_
from sqlalchemy.sql.elements import ColumnElement

MAX_TERMS = 8


def _build_fold_map() -> dict[str, str]:
    """Latin letters carrying a diacritic -> their plain lowercase ASCII letter.
    Upper-case forms are included on purpose: SQL's lower() only folds
    non-ASCII capitals when the database's locale supports it, and this makes
    the result independent of that."""
    mapping: dict[str, str] = {}
    for codepoint in range(0xC0, 0x250):
        char = chr(codepoint)
        base = "".join(c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c))
        if len(base) == 1 and base.isascii() and base.isalpha():
            mapping[char] = base.lower()
    # Distinct letters rather than accented ones, so NFKD leaves them alone.
    mapping.update({"ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ø": "o", "Ø": "o"})
    return mapping


_FOLD_MAP = _build_fold_map()
_TRANSLATION = str.maketrans(_FOLD_MAP)
_SQL_FROM = "".join(_FOLD_MAP)
_SQL_TO = "".join(_FOLD_MAP.values())


def fold(text: str) -> str:
    return text.lower().translate(_TRANSLATION)


def search_terms(query: str | None) -> list[str]:
    if not query:
        return []
    return fold(query).split()[:MAX_TERMS]


def _folded(column) -> ColumnElement[str]:
    return func.translate(func.lower(func.coalesce(column, "")), _SQL_FROM, _SQL_TO, type_=Text)


def matches_all_terms(query: str | None, *columns) -> ColumnElement[bool] | None:
    """A WHERE condition for `query`, or None when it has no words (so the
    caller leaves the list unfiltered). LIKE wildcards in the query are
    escaped, so "50%" searches for the literal text."""
    terms = search_terms(query)
    if not terms:
        return None
    haystacks = [_folded(column) for column in columns]
    return and_(*(or_(*(haystack.contains(term, autoescape=True) for haystack in haystacks)) for term in terms))
