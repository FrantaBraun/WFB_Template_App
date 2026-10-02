# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import math
from collections.abc import Iterable
from dataclasses import dataclass

MAX_MATCHES = 5
MAX_MATCH_LENGTH = 40


@dataclass(frozen=True)
class Finding:
    """One specific aspect of why a text was scored the way it was - what the
    author is shown ("contains vulgar expressions: ...").

    `code` is language-neutral (the frontend translates it), `weight` is the
    probability (0..1) this aspect alone puts on the text being a problem,
    `matches` are the offending words or phrases from the author's own text,
    and `aspect` says which score it belongs to: "violation" (breaks the
    rules) or "topic" (does not fit the category).
    """

    code: str
    weight: float
    matches: tuple[str, ...] = ()
    aspect: str = "violation"


def shown_matches(matches: Iterable[str]) -> tuple[str, ...]:
    """Distinct matches in first-seen order, few and short enough to show."""
    distinct = dict.fromkeys(match[:MAX_MATCH_LENGTH] for match in matches)
    return tuple(distinct)[:MAX_MATCHES]


def combine(weights: Iterable[float]) -> float:
    """Independent probabilities folded into one: several weak signals add up
    to a strong one, and the result never passes 1."""
    return 1.0 - math.prod(1.0 - weight for weight in weights)


def to_percent(probability: float) -> int:
    return max(0, min(100, round(probability * 100)))
