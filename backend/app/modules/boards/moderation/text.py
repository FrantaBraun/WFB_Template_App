# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Text normalization shared by the scorer and the topic check.

Everything is matched on *folded* text - lowercase, diacritics stripped - so
"Kurva" and "kurva" are one word and a Czech text matches whether or not its
author typed the háčky.
"""

import re
import unicodedata

STEM_LEN = 5

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
# Single letters separated by spaces or punctuation: "f u c k", "f.u.c.k".
_SPACED = re.compile(r"(?<![^\W_])(?:[^\W_\d][\s.\-_*,]+){3,}[^\W_\d](?![^\W_])")
_SYMBOL_BETWEEN_LETTERS = re.compile(r"(?<=[^\W\d_])[@$!](?=[^\W\d_])")
_SYMBOL_LETTERS = {"@": "a", "$": "s", "!": "i"}
_DIGIT_LETTERS = str.maketrans("013457", "oieast")


def fold(text: str) -> str:
    """Lowercase with diacritics removed."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def collapse_runs(token: str, keep: int) -> str:
    """Shortens every run of one repeated character to at most `keep`."""
    return re.sub(r"(.)\1{%d,}" % keep, lambda match: match.group(1) * keep, token)


def forms(token: str) -> set[str]:
    """A token as written plus its stretched-letters variants ("fuuuck" ->
    "fuck", "assss" -> "ass"), so a lexicon of plain spellings still hits."""
    return {token, collapse_runs(token, 1), collapse_runs(token, 2)}


def match_candidates(text: str) -> list[tuple[str, ...]]:
    """The words of `text` for lexicon matching, each as a tuple of
    candidate spellings (a hit on any candidate counts the word once).

    Undoes the usual disguises: digits and @ $ ! inside a word read as
    letters ("sh1t", "k0kot", "sh!t"), and letters spread apart ("f u c k")
    are joined. Digits are only read as letters inside a word that also has
    letters, so plain numbers are left alone.
    """
    folded = _SYMBOL_BETWEEN_LETTERS.sub(lambda match: _SYMBOL_LETTERS[match.group()], fold(text))
    candidates: list[tuple[str, ...]] = []
    for token in _WORD.findall(folded):
        if any(c.isdigit() for c in token) and any(c.isalpha() for c in token):
            candidates.append((token, token.translate(_DIGIT_LETTERS)))
        else:
            candidates.append((token,))
    for match in _SPACED.finditer(folded):
        candidates.append((re.sub(r"[\W_]+", "", match.group()),))
    return candidates


def content_terms(text: str, stopwords: frozenset[str]) -> list[tuple[str, str]]:
    """(as written, folded) for each word that carries meaning: alphabetic,
    at least 3 letters, not a stopword. The as-written form is lowercase but
    keeps its diacritics - it is what an administrator reads in a category's
    rules; the folded one is what gets compared."""
    terms = []
    for raw in _WORD.findall(text.lower()):
        folded = fold(raw)
        if folded.isalpha() and len(folded) >= 3 and folded not in stopwords:
            terms.append((raw, folded))
    return terms


def content_words(text: str, stopwords: frozenset[str]) -> list[str]:
    """The folded forms of content_terms."""
    return [folded for _, folded in content_terms(text, stopwords)]


def stem(word: str) -> str:
    """A crude stemmer - the first STEM_LEN letters - so inflected forms
    ("filosofie", "filosofii", "filosofický") meet in one key."""
    return word[:STEM_LEN]
