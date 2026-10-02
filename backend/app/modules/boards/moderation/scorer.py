# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The local violation score: how likely a text breaks the public rules, in
percent, with the specific aspects behind it.

Each aspect (profanity, insults, hate, threats, link spam, personal data,
shouting, repetition, gibberish) yields a probability; they are combined as
independent signals (findings.combine), so one mild aspect stays low while
several together climb. Word aspects count every occurrence - with
diminishing weight, and at most MAX_COUNTED of them - so a single slip is a
warning, a few are a block. Thresholds that turn the percent into "edit
this" / "risky" / "not allowed" live in ModerationConfig, not here.
"""

import re
from dataclasses import dataclass

from app.modules.boards.moderation import lexicon
from app.modules.boards.moderation.findings import Finding, combine, shown_matches, to_percent
from app.modules.boards.moderation.text import fold, forms, match_candidates

# Probability one occurrence of the aspect puts on the text being a problem.
PER_HIT = {
    "profanity": 0.35,
    "insult": 0.2,
    "hate": 0.6,
    "threat": 0.8,
    "spam_links": 0.2,
    "spam_phrases": 0.25,
    "personal_data": 0.25,
}
MAX_COUNTED = 5
CAP = 0.95

SHOUTING_CAPS = 0.25
SHOUTING_PUNCTUATION = 0.1
REPETITION = 0.3
CHARACTER_RUN = 0.2
GIBBERISH = 0.2

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_CHARACTER_RUN = re.compile(r"(\w|[\U0001F000-\U0001FAFF])\1{11,}")
_PUNCTUATION_RUN = re.compile(r"[!?]{4,}")
_MIN_LETTERS_FOR_CAPS = 20
_CAPS_RATIO = 0.7
_MIN_WORDS_FOR_DIVERSITY = 12
_MIN_DIVERSITY = 0.3
_REPEATED_WORD_RUN = 5
_GIBBERISH_LENGTH = 30


@dataclass(frozen=True)
class ViolationScore:
    percent: int
    findings: tuple[Finding, ...]


def _counted(code: str, hits: list[str]) -> Finding | None:
    if not hits:
        return None
    probability = min(CAP, 1.0 - (1.0 - PER_HIT[code]) ** min(len(hits), MAX_COUNTED))
    return Finding(code, probability, shown_matches(hits))


def _word_hits(candidates: list[tuple[str, ...]], terms: frozenset[str]) -> list[str]:
    return [
        candidate[0]
        for candidate in candidates
        if any(form in terms for spelling in candidate for form in forms(spelling))
    ]


def _phrase_hits(patterns: tuple[re.Pattern, ...], folded: str) -> list[str]:
    return [match.group() for pattern in patterns for match in pattern.finditer(folded)]


def _longest_identical_run(words: list[str]) -> int:
    longest = run = 1
    for previous, current in zip(words, words[1:]):
        run = run + 1 if current == previous and len(current) >= 2 else 1
        longest = max(longest, run)
    return longest


def _shouting(text: str) -> Finding | None:
    letters = [char for char in text if char.isalpha()]
    if len(letters) >= _MIN_LETTERS_FOR_CAPS and sum(c.isupper() for c in letters) / len(letters) >= _CAPS_RATIO:
        return Finding("shouting", SHOUTING_CAPS)
    if _PUNCTUATION_RUN.search(text):
        return Finding("shouting", SHOUTING_PUNCTUATION)
    return None


def _repetition(text: str, words: list[str]) -> Finding | None:
    weights = []
    if len(words) >= _MIN_WORDS_FOR_DIVERSITY and len(set(words)) / len(words) < _MIN_DIVERSITY:
        weights.append(REPETITION)
    if len(words) >= _REPEATED_WORD_RUN and _longest_identical_run(words) >= _REPEATED_WORD_RUN:
        weights.append(REPETITION)
    if _CHARACTER_RUN.search(text):
        weights.append(CHARACTER_RUN)
    return Finding("repetition", combine(weights)) if weights else None


def score_violations(text: str) -> ViolationScore:
    folded = fold(text)
    candidates = match_candidates(text)
    no_email = lexicon.EMAIL.sub(" ", folded)
    plain_words = _WORD.findall(no_email)

    emails = lexicon.EMAIL.findall(folded)
    links = [url.rstrip(".,;:!?)") for url in lexicon.URL.findall(no_email)]
    phones = [phone.strip() for phone in lexicon.PHONE.findall(no_email)]

    findings = [
        _counted("profanity", _word_hits(candidates, lexicon.PROFANITY)),
        _counted("insult", _word_hits(candidates, lexicon.INSULTS)),
        _counted("hate", _word_hits(candidates, lexicon.SLURS) + _phrase_hits(lexicon.HATE_PHRASES, folded)),
        _counted("threat", _phrase_hits(lexicon.THREATS, folded)),
        _counted("spam_links", links),
        _counted("spam_phrases", _phrase_hits(lexicon.SPAM_PHRASES, folded)),
        _counted("personal_data", emails + phones),
        _shouting(text),
        _repetition(text, plain_words),
        Finding("gibberish", GIBBERISH) if any(len(word) >= _GIBBERISH_LENGTH for word in plain_words) else None,
    ]
    found = tuple(sorted((f for f in findings if f is not None), key=lambda f: f.weight, reverse=True))
    return ViolationScore(to_percent(combine(f.weight for f in found)), found)
