# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The prepared (mock-only) AI level and how the assessment pipeline uses
it."""

import pytest

from app.modules.boards.config import ModerationConfig
from app.modules.boards.moderation.ai import (
    RESPONSE_SCHEMA,
    TOPIC_ASPECTS,
    VIOLATION_ASPECTS,
    AiFinding,
    AiResponseError,
    AiReviewRequest,
    AiReviewResult,
    MockAiModerator,
    get_ai_moderator,
    parse_review_response,
)
from app.modules.boards.moderation.assess import assess_category, assess_post
from app.modules.boards.moderation.scorer import score_violations
from app.modules.boards.moderation.topic import build_rules

ENABLED = ModerationConfig(ai_review_enabled=True)
DISABLED = ModerationConfig(ai_review_enabled=False)
RULES = build_rules("Technology", "Software, hardware and networks")


def _post(config, ai, *, title="A title", body="A calm and ordinary body.", rules=RULES):
    return assess_post(
        title=title,
        body=body,
        category_title="Technology",
        category_description="Software, hardware and networks",
        category_rules=rules,
        config=config,
        ai=ai,
    )


# --- The prepared contract ------------------------------------------------------


def test_only_the_mock_is_connected():
    """No model is wired in yet - when one is, this test is the reminder to
    cover it."""
    assert isinstance(get_ai_moderator(), MockAiModerator)


def test_the_prompt_carries_the_rules_the_submission_and_the_category():
    request = AiReviewRequest("post", "My title", "My text", "Technology", "About software", RULES)
    prompt = request.prompt()

    assert "My title" in prompt and "My text" in prompt
    assert "Technology" in prompt and "About software" in prompt
    assert "technology, software" in prompt  # the category's machine-rule keywords
    assert "must not contain" in prompt  # the rules themselves
    assert "violation_percent" in prompt and "topic_mismatch_percent" in prompt


def test_the_prompt_for_a_category_has_no_topic_part():
    prompt = AiReviewRequest("category", "New board", "What it is for").prompt()
    assert "new category" in prompt
    assert "New board" in prompt and "What it is for" in prompt
    assert "Keywords the category stands for" not in prompt


def test_the_response_schema_lists_exactly_the_aspects_the_parser_knows():
    codes = RESPONSE_SCHEMA["properties"]["findings"]["items"]["properties"]["code"]["enum"]
    assert set(codes) == {*VIOLATION_ASPECTS, *TOPIC_ASPECTS}


def test_a_valid_answer_is_parsed():
    result = parse_review_response(
        {
            "violation_percent": 62,
            "topic_mismatch_percent": 10,
            "findings": [{"code": "threat", "matches": ["I will find you"]}, {"code": "off_topic"}],
        },
        model="some-model",
    )
    assert result == AiReviewResult(
        62, 10, (AiFinding("threat", ("I will find you",)), AiFinding("off_topic", ())), "some-model"
    )
    assert [f.aspect for f in result.findings] == ["violation", "topic"]


def test_an_answer_for_a_category_may_have_no_topic_score_or_findings():
    result = parse_review_response({"violation_percent": 5}, model="m")
    assert (result.violation_percent, result.topic_mismatch_percent, result.findings) == (5, None, ())


def test_an_unknown_aspect_is_kept_as_ai_other_and_extra_fields_are_ignored():
    result = parse_review_response(
        {"violation_percent": 40, "extra": 1, "findings": [{"code": "vibes", "matches": list("abcdefgh"), "note": "x"}]},
        model="m",
    )
    assert result.findings == (AiFinding("ai_other", ("a", "b", "c", "d", "e")),)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"violation_percent": 101},
        {"violation_percent": -1},
        {"violation_percent": "high"},
        {"violation_percent": 10, "topic_mismatch_percent": 400},
        {"violation_percent": 10, "findings": "none"},
        {"violation_percent": 10, "findings": [{"matches": []}]},
    ],
)
def test_an_answer_that_breaks_the_contract_is_rejected(payload):
    with pytest.raises(AiResponseError):
        parse_review_response(payload, model="m")


async def test_the_mock_finds_nothing_wrong_and_remembers_what_it_was_asked():
    mock = MockAiModerator()
    request = AiReviewRequest("category", "T", "D")

    result = await mock.review(request)

    assert (result.violation_percent, result.topic_mismatch_percent, result.findings, result.model) == (0, None, (), "mock")
    assert list(mock.requests) == [request]
    assert await mock.build_category_rules("T", "D") is None
    assert list(mock.rules_requests) == [("T", "D")]


async def test_the_mocks_memory_is_bounded():
    mock = MockAiModerator()
    for i in range(250):
        await mock.review(AiReviewRequest("category", str(i), "d"))
    assert len(mock.requests) == 100
    assert mock.requests[-1].title == "249"


# --- In the pipeline ------------------------------------------------------------


async def test_the_ai_is_not_asked_unless_enabled():
    mock = MockAiModerator()
    assessment = await _post(DISABLED, mock)
    assert not mock.requests
    assert assessment.ai_reviewed is False


async def test_without_an_ai_moderator_nothing_is_asked_either():
    assert (await _post(ENABLED, None)).ai_reviewed is False


async def test_when_enabled_the_ai_is_asked_with_the_post_and_its_category():
    mock = MockAiModerator()
    assessment = await _post(ENABLED, mock, title="Hello", body="World")

    (request,) = mock.requests
    assert (request.kind, request.title, request.text) == ("post", "Hello", "World")
    assert (request.category_title, request.category_rules) == ("Technology", RULES)
    assert assessment.ai_reviewed is True
    assert assessment.level == "ok"


async def test_the_higher_of_the_local_and_the_ai_score_wins():
    ai = MockAiModerator(
        result=AiReviewResult(80, 60, (AiFinding("misinformation", ("claim",)), AiFinding("off_topic")), "m")
    )

    assessment = await _post(ENABLED, ai)

    assert assessment.violation.percent == 80 and assessment.violation.level == "blocked"
    assert assessment.topic.percent == 60 and assessment.topic.level == "risk"
    codes = [(f.code, f.aspect) for f in assessment.findings]
    assert ("misinformation", "violation") in codes and ("off_topic", "topic") in codes
    assert assessment.allowed is False


async def test_a_lower_ai_score_never_lowers_the_local_one():
    body = "You are an idiot and I hate this shit"
    ai = MockAiModerator(result=AiReviewResult(0, 0, (), "m"))

    assessment = await _post(ENABLED, ai, body=body)

    assert assessment.violation.percent == score_violations("A title\n" + body).percent > 0


async def test_an_ai_topic_score_counts_even_without_machine_rules():
    ai = MockAiModerator(result=AiReviewResult(0, 55, (), "m"))
    assessment = await _post(ENABLED, ai, rules=None)
    assert assessment.topic.percent == 55 and assessment.level == "risk"


async def test_the_ai_is_not_asked_about_what_the_local_check_already_blocks():
    mock = MockAiModerator()
    assessment = await _post(ENABLED, mock, body="I will kill you tomorrow")
    assert assessment.level == "blocked"
    assert not mock.requests
    assert assessment.ai_reviewed is False


async def test_an_unusable_ai_answer_does_not_stop_a_post():
    class Broken:
        async def review(self, request):
            raise AiResponseError("not json")

        async def build_category_rules(self, title, description):
            return None

    assessment = await _post(ENABLED, Broken())
    assert (assessment.level, assessment.ai_reviewed) == ("ok", False)


async def test_a_category_is_reviewed_without_a_topic():
    ai = MockAiModerator(result=AiReviewResult(40, 90, (AiFinding("spam"),), "m"))

    assessment = await assess_category(title="Board", description="What for", config=ENABLED, ai=ai)

    (request,) = ai.requests
    assert request.kind == "category"
    assert assessment.topic is None
    assert assessment.violation.percent == 40 and assessment.violation.level == "warn"
