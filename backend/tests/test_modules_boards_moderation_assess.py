# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""How the local scores of a post or a category become one assessment."""

import pytest

from app.modules.boards.config import ModerationConfig
from app.modules.boards.moderation.assess import Assessment, Score, assess_category, assess_post
from app.modules.boards.moderation.findings import Finding
from app.modules.boards.moderation.topic import build_rules

CONFIG = ModerationConfig()
RICH_RULES = build_rules(
    "Philosophy of everyday life",
    "Short thoughts on how we live, decide and doubt. Reflections about habits, choices, meaning, "
    "happiness, friendship and time. No quotes, only your own words.",
)
ON_TOPIC_TEXT = (
    "Our daily habits shape the meaning we find in life; friendship and time teach us to doubt "
    "our choices, and happiness often hides in ordinary decisions we make without thinking about them."
)
OFF_TOPIC = (
    "The new graphics card renders frames faster than the previous generation, with better ray tracing, "
    "more memory bandwidth and improved driver support for modern games and engines, while consuming "
    "less power under typical gaming load conditions."
)


def _post(title, body, rules=None):
    return assess_post(
        title=title,
        body=body,
        category_title="Philosophy",
        category_description="Everyday life",
        category_rules=rules,
        config=CONFIG,
    )


async def test_a_clean_post_is_ok_and_has_nothing_to_report():
    assessment = await _post("Attention", "Attention is the only thing we spend that we can never earn back.")
    assert assessment.level == "ok"
    assert assessment.allowed is True
    assert assessment.findings == ()
    assert assessment.violation == Score(0, "ok")
    assert assessment.topic is None  # the category has no machine rules


async def test_the_title_is_judged_with_the_text():
    assessment = await _post("You absolute idiot, shit", "Nothing wrong in here.")
    assert assessment.violation.percent > 0
    assert {f.code for f in assessment.findings} == {"profanity", "insult"}


async def test_a_post_has_a_topic_score_once_the_category_has_rules():
    assessment = await _post("Attention", ON_TOPIC_TEXT, RICH_RULES)
    assert assessment.topic == Score(0, "ok")


async def test_the_overall_level_is_the_worse_of_violation_and_topic():
    off_topic = await _post("Graphics", OFF_TOPIC, RICH_RULES)
    assert off_topic.violation.level == "ok"
    assert off_topic.topic.level == "blocked"
    assert off_topic.level == "blocked" and off_topic.allowed is False

    rude = await _post("Philosophy", ON_TOPIC_TEXT + " This is bullshit.", RICH_RULES)
    assert (rude.violation.level, rude.topic.level) == ("warn", "ok")
    assert rude.level == "warn"


async def test_findings_say_which_score_they_belong_to():
    assessment = await _post("Graphics shit", OFF_TOPIC, RICH_RULES)
    aspects = {f.code: f.aspect for f in assessment.findings}
    assert aspects == {"profanity": "violation", "off_topic": "topic"}


async def test_a_category_is_only_judged_for_violations():
    rude = await assess_category(title="Shit board", description="For all the bullshit", config=CONFIG)
    assert rude.topic is None
    assert rude.level == "risk"

    clean = await assess_category(title="Everyday life", description="Short thoughts", config=CONFIG)
    assert clean.level == "ok" and clean.findings == ()


async def test_levels_follow_the_configured_thresholds():
    strict = ModerationConfig(warn_percent=5, risk_percent=10, block_percent=15)
    assessment = await assess_category(title="One idiot", description="Fine", config=strict)
    assert assessment.violation.level == "blocked"  # 20 % > 15 %


def test_to_json_is_what_an_administrator_later_reads():
    assessment = Assessment(
        Score(62, "risk"),
        Score(12, "ok"),
        (Finding("profanity", 0.35, ("shit",)), Finding("off_topic", 0.12, ("philosophy",), aspect="topic")),
    )
    assert assessment.to_json() == {
        "violation": 62,
        "topic": 12,
        "ai_reviewed": False,
        "findings": [
            {"code": "profanity", "aspect": "violation", "matches": ["shit"]},
            {"code": "off_topic", "aspect": "topic", "matches": ["philosophy"]},
        ],
    }


def test_to_json_of_a_category_has_no_topic():
    assert Assessment(Score(0, "ok"), None, ()).to_json()["topic"] is None


@pytest.mark.parametrize(
    ("violation", "topic", "level"),
    [("ok", None, "ok"), ("ok", "warn", "warn"), ("risk", "warn", "risk"), ("warn", "blocked", "blocked")],
)
def test_the_level_is_the_worst_of_the_scores(violation, topic, level):
    assessment = Assessment(Score(0, violation), Score(0, topic) if topic else None, ())
    assert assessment.level == level
