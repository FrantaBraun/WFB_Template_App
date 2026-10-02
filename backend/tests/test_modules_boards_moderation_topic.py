# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Machine rules for a category, and the topic-mismatch score computed from
them."""

import pytest

from app.modules.boards.config import ModerationConfig
from app.modules.boards.moderation.assess import level_for
from app.modules.boards.moderation.topic import MAX_KEYWORDS, MAX_WEIGHT, build_rules, topic_mismatch

CONFIG = ModerationConfig()


def distinct_words(count: int, offset: int = 0) -> list[str]:
    """`count` made-up words whose stems (first five letters) all differ, so
    each one counts as its own word to the topic check."""
    return ["".join(chr(97 + ((offset + i) // 26**k) % 26) for k in range(5)) + "z" for i in range(count)]


RICH = build_rules(
    "Philosophy of everyday life",
    "Short thoughts on how we live, decide and doubt. Reflections about habits, choices, meaning, "
    "happiness, friendship and time. No quotes, only your own words.",
)
SPARSE = build_rules("Technology", "What will software do to us next?")
CZECH = build_rules(
    "Filosofie každodenního života",
    "Krátké úvahy o tom, jak žijeme, rozhodujeme se a pochybujeme. Zvyky, volby, smysl, štěstí, přátelství a čas.",
)

ON_TOPIC = (
    "Our daily habits shape the meaning we find in life; friendship and time teach us to doubt "
    "our choices, and happiness often hides in ordinary decisions we make without thinking about them."
)
OFF_TOPIC = (
    "The new graphics card renders frames faster than the previous generation, with better ray tracing, "
    "more memory bandwidth and improved driver support for modern games and engines, while consuming "
    "less power under typical gaming load conditions."
)


def _terms(rules):
    return [keyword["term"] for keyword in rules["keywords"]]


# --- Building rules -------------------------------------------------------------


def test_rules_are_the_meaningful_words_of_title_and_description():
    assert _terms(SPARSE) == ["technology", "software", "next"]
    assert SPARSE["notes"] == ""


def test_title_words_weigh_more_than_description_words():
    weights = {k["term"]: k["weight"] for k in RICH["keywords"]}
    assert weights["philosophy"] == 2.0
    assert weights["habits"] == 1.0
    assert _terms(RICH)[:3] == ["philosophy", "everyday", "life"]


def test_stopwords_and_short_words_are_left_out():
    terms = _terms(RICH)
    assert not {"how", "and", "on", "only", "your", "own"} & set(terms)
    assert all(len(term) >= 3 for term in terms)


def test_czech_rules_keep_their_diacritics_for_the_administrator_to_read():
    assert _terms(CZECH)[:3] == ["filosofie", "každodenního", "života"]
    assert "štěstí" in _terms(CZECH)


def test_inflected_forms_of_a_word_are_one_keyword_under_the_longest_form():
    rules = build_rules("Filosofie", "Filosofii a filosofický pohled na filosofa")
    assert _terms(rules).count("filosofický") == 1
    assert len([term for term in _terms(rules) if term.startswith("filos")]) == 1


def test_a_word_in_both_title_and_description_weighs_the_sum_up_to_a_cap():
    rules = build_rules("Habits", "Habits, habits and more habits")
    assert rules["keywords"][0] == {"term": "habits", "weight": MAX_WEIGHT}


def test_rules_are_limited_to_the_heaviest_keywords():
    rules = build_rules("Many words", " ".join(distinct_words(100)))
    assert len(rules["keywords"]) == MAX_KEYWORDS
    assert _terms(rules)[:2] == ["many", "words"]  # the title's words come first


def test_a_category_without_meaningful_words_gets_empty_rules():
    assert build_rules("The and of", "to be or not")["keywords"] == []


# --- Topic mismatch -------------------------------------------------------------


def test_nothing_to_compare_against_means_no_topic_check():
    assert topic_mismatch(OFF_TOPIC, None, CONFIG) is None
    assert topic_mismatch(OFF_TOPIC, {"keywords": []}, CONFIG) is None
    assert topic_mismatch(OFF_TOPIC, {"keywords": [{"term": "the and", "weight": 1}]}, CONFIG) is None


def test_a_post_on_topic_has_no_mismatch_and_nothing_to_show():
    result = topic_mismatch(ON_TOPIC, RICH, CONFIG)
    assert result.percent == 0
    assert result.findings == ()


def test_a_long_post_that_ignores_a_well_described_category_is_not_allowed():
    result = topic_mismatch(OFF_TOPIC, RICH, CONFIG)
    assert level_for(result.percent, CONFIG) == "blocked"
    (finding,) = result.findings
    assert (finding.code, finding.aspect) == ("off_topic", "topic")
    assert finding.matches[:3] == ("philosophy", "everyday", "life")  # what the category is about


def test_a_sparse_category_can_only_advise_never_block():
    """Three keywords are too little evidence for a hard verdict - even a
    long, plainly unrelated post stays at "warn"."""
    for text in (OFF_TOPIC, ON_TOPIC):
        result = topic_mismatch(text, SPARSE, CONFIG)
        assert level_for(result.percent, CONFIG) in ("ok", "warn")


def test_a_short_post_is_weak_evidence_even_in_a_rich_category():
    result = topic_mismatch("Best pizza recipe ever.", RICH, CONFIG)
    assert level_for(result.percent, CONFIG) == "ok"


def test_czech_inflection_is_matched_through_the_stems():
    on = (
        "Každodenní zvyky a volby určují smysl našeho života, přátelství i čas, který máme, a často "
        "pochybujeme o svých rozhodnutích, i když štěstí bývá v obyčejných věcech kolem nás každý den."
    )
    off = (
        "Nová grafická karta vykresluje snímky rychleji než předchozí generace, má lepší sledování "
        "paprsků, větší propustnost paměti a lepší podporu ovladačů pro moderní hry při nižší spotřebě."
    )
    assert topic_mismatch(on, CZECH, CONFIG).percent == 0
    assert level_for(topic_mismatch(off, CZECH, CONFIG).percent, CONFIG) == "blocked"


def test_a_diacritics_free_post_matches_diacritics_in_the_rules():
    rules = {"keywords": [{"term": "života", "weight": 3}, {"term": "štěstí", "weight": 1}]}
    assert topic_mismatch("zivota stesti", rules, CONFIG).percent == 0


def test_a_multi_word_keyword_needs_all_its_words():
    rules = {"keywords": [{"term": "ray tracing", "weight": 3}] * 8}
    filler = " ".join(distinct_words(30))
    both = topic_mismatch(f"ray tracing {filler}", rules, CONFIG).percent
    one = topic_mismatch(f"ray {filler}", rules, CONFIG).percent
    assert (both, one) == (0, 100)


def test_the_more_keywords_a_post_covers_the_lower_the_mismatch():
    keywords = "alpha bravo charlie delta echo foxtrot golf hotel".split()
    rules = {"keywords": [{"term": word, "weight": 1} for word in keywords]}
    filler = " ".join(distinct_words(30))
    scores = [
        topic_mismatch(" ".join(keywords[:covered]) + " " + filler, rules, CONFIG).percent for covered in (0, 1, 2, 4)
    ]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 100 and scores[-1] < 10


def test_admin_edited_weights_are_respected():
    def rules(graphics_weight):
        others = [{"term": word, "weight": 1} for word in distinct_words(7, offset=5000)]
        return {"keywords": [{"term": "graphics", "weight": graphics_weight}, *others]}

    heavy = topic_mismatch(OFF_TOPIC, rules(3), CONFIG).percent
    light = topic_mismatch(OFF_TOPIC, rules(0.1), CONFIG).percent
    assert heavy < light


@pytest.mark.parametrize(
    ("words", "keywords", "expected_full"),
    [(25, 8, True), (12, 8, False), (25, 4, False)],
)
def test_confidence_reaches_full_only_with_enough_words_and_keywords(words, keywords, expected_full):
    rules = {"keywords": [{"term": word, "weight": 1} for word in distinct_words(keywords, offset=5000)]}
    percent = topic_mismatch(" ".join(distinct_words(words)), rules, CONFIG).percent
    assert (percent == 100) is expected_full


def test_the_scale_and_confidence_follow_the_configuration():
    lenient = ModerationConfig(topic_full_confidence_words=1000)
    assert topic_mismatch(OFF_TOPIC, RICH, lenient).percent < topic_mismatch(OFF_TOPIC, RICH, CONFIG).percent
