# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Does a post fit its category? Compared against the category's *machine
rules* - the keywords that stand for what the category is about.

Rules are built once, when the category is created (build_rules: the
meaningful words of its title and description, title words weighing more),
and an administrator can read and edit them afterwards. They are plain data:

    {"keywords": [{"term": "philosophy", "weight": 2.0}, ...], "notes": ""}

A post's mismatch score (topic_mismatch) is how little of that keyword mass
its words cover, in percent. This is lexical matching with a crude stemmer,
so it is a weak signal for a short post or a category with few keywords: an
honest post on a sparsely described category would otherwise be called
off-topic. The score is therefore scaled down by a confidence that grows
with the number of distinct content words in the post and of keywords in the
rules (ModerationConfig.topic_full_confidence_*) - a hard "not allowed" needs
a long post, a well-described category and almost no overlap.
"""

import math
from collections import Counter
from dataclasses import dataclass

from app.modules.boards.config import ModerationConfig
from app.modules.boards.moderation.findings import Finding, shown_matches
from app.modules.boards.moderation.text import content_terms, content_words, stem

MAX_KEYWORDS = 30
TITLE_WEIGHT = 2.0
DESCRIPTION_WEIGHT = 1.0
MAX_WEIGHT = 3.0

STOPWORDS = frozenset(
    """
    the and for with about from into that this these those have has had was were been being are
    will would can could should may might must not but you your our their his her them its
    what which who whom when where why how all any some more most other such than then there
    very just also only own same out over under again once here both each few one two
    ale ani aby asi bez bude budou budu byl byla byli bylo byly byt cim coz dalsi dnes jak jake
    jako jeho jeji jejich jen jenz jine jiz jsem jsme jsou jste kam kde kdo kdyz ktera ktere
    kteri kterou ktery mate mezi mnou moc muze nad nam nas nase nasi nebo nebyl nejsou neni nez
    nic nich nim nove nyni pak pod podle pokud pouze pred pres pri pro proc proto protoze
    prvni sam sama sami tak take tam tato ten tedy teto tim toho tom tomu toto tuto tyto uz
    vam vas vase vsak vsech vsechno vsichni vy zda zde ze zpet
    """.split()
)


@dataclass(frozen=True)
class TopicScore:
    percent: int
    findings: tuple[Finding, ...]


def build_rules(title: str, description: str) -> dict:
    """The algorithmic machine rules for a category: the meaningful words of
    its title (weight 2 each time) and description (1), the heaviest
    first, one entry per stem, shown under the longest form seen."""
    weights: Counter[str] = Counter()
    forms: dict[str, str] = {}
    for text, weight in ((title, TITLE_WEIGHT), (description, DESCRIPTION_WEIGHT)):
        for written, folded in content_terms(text, STOPWORDS):
            key = stem(folded)
            weights[key] += weight
            if len(written) > len(forms.get(key, "")):
                forms[key] = written
    # Counter.most_common keeps first-seen order among equal weights.
    keywords = [
        {"term": forms[key], "weight": min(weight, MAX_WEIGHT)} for key, weight in weights.most_common(MAX_KEYWORDS)
    ]
    return {"keywords": keywords, "notes": ""}


def _keyword_stems(rules: dict) -> list[tuple[str, frozenset[str], float]]:
    """(term, stems of its words, weight) for every usable keyword. A term
    with several words matches only when all of them appear."""
    usable = []
    for keyword in rules.get("keywords", []):
        stems = frozenset(stem(word) for word in content_words(keyword["term"], STOPWORDS))
        if stems:
            usable.append((keyword["term"], stems, float(keyword["weight"])))
    return usable


def topic_mismatch(text: str, rules: dict | None, config: ModerationConfig) -> TopicScore | None:
    """None when there is nothing to compare against (no rules, or none
    usable) - the check then simply doesn't apply."""
    keywords = _keyword_stems(rules) if rules else []
    if not keywords:
        return None

    post_stems = {stem(word) for word in content_words(text, STOPWORDS)}
    matched = [(term, weight) for term, stems, weight in keywords if stems <= post_stems]
    covered = sum(weight for _, weight in matched)
    similarity = 1.0 - math.exp(-covered / config.topic_similarity_scale)
    confidence = min(1.0, len(post_stems) / config.topic_full_confidence_words) * min(
        1.0, len(keywords) / config.topic_full_confidence_keywords
    )
    percent = max(0, min(100, round(100 * (1.0 - similarity) * confidence)))

    # What the author is shown: the keywords the post did not touch (the
    # heaviest ones), so they can see what the category is about.
    missing = [term for term, stems, _ in sorted(keywords, key=lambda k: -k[2]) if not stems <= post_stems]
    findings = (Finding("off_topic", percent / 100, shown_matches(missing), aspect="topic"),) if percent else ()
    return TopicScore(percent, findings)
