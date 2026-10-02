# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""One assessment of a post or a category: the local checks, then - when
enabled and nothing is blocked yet - the AI moderator, folded into a single
result with levels.

Levels, from the percentages and ModerationConfig's thresholds (a percent
must be strictly *above* a threshold): "ok", "warn" (edit it), "risk"
(potentially violating - publishing needs the author's confirmation) and
"blocked" (publishing not allowed). A post has two scores, violation and
topic, and its overall level is the worse of the two.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from app.modules.boards.config import ModerationConfig
from app.modules.boards.moderation.ai import AiModerator, AiReviewRequest
from app.modules.boards.moderation.findings import Finding, shown_matches
from app.modules.boards.moderation.scorer import score_violations
from app.modules.boards.moderation.topic import topic_mismatch

logger = logging.getLogger(__name__)

Level = Literal["ok", "warn", "risk", "blocked"]
_ORDER: tuple[Level, ...] = ("ok", "warn", "risk", "blocked")


def level_for(percent: int, config: ModerationConfig) -> Level:
    if percent > config.block_percent:
        return "blocked"
    if percent > config.risk_percent:
        return "risk"
    if percent > config.warn_percent:
        return "warn"
    return "ok"


@dataclass(frozen=True)
class Score:
    percent: int
    level: Level


@dataclass(frozen=True)
class Assessment:
    violation: Score
    topic: Score | None
    findings: tuple[Finding, ...]
    ai_reviewed: bool = False

    @property
    def level(self) -> Level:
        scores = [self.violation] + ([self.topic] if self.topic else [])
        return max((s.level for s in scores), key=_ORDER.index)

    @property
    def allowed(self) -> bool:
        return self.level != "blocked"

    def to_json(self) -> dict:
        """What is stored with a published post, for an administrator
        reviewing it later."""
        return {
            "violation": self.violation.percent,
            "topic": self.topic.percent if self.topic else None,
            "ai_reviewed": self.ai_reviewed,
            "findings": [{"code": f.code, "aspect": f.aspect, "matches": list(f.matches)} for f in self.findings],
        }


async def _ask_ai(ai: AiModerator, request: AiReviewRequest):
    try:
        return await ai.review(request)
    except Exception:
        # A model that is down, slow or answers badly (AiResponseError, a
        # network error, ...) must not stop anyone posting - the local checks
        # have already passed.
        logger.warning("AI moderation review failed - ignored", exc_info=True)
        return None


async def assess_post(
    *,
    title: str,
    body: str,
    category_title: str,
    category_description: str,
    category_rules: dict | None,
    config: ModerationConfig,
    ai: AiModerator | None = None,
) -> Assessment:
    text = f"{title}\n{body}"
    violation = score_violations(text)
    topic = topic_mismatch(text, category_rules, config)
    violation_percent = violation.percent
    topic_percent = topic.percent if topic else None
    findings = list(violation.findings) + list(topic.findings if topic else ())

    ai_reviewed = False
    if config.ai_review_enabled and ai is not None and level_for(max(violation_percent, topic_percent or 0), config) != "blocked":
        result = await _ask_ai(
            ai,
            AiReviewRequest("post", title, body, category_title, category_description, category_rules),
        )
        if result is not None:
            ai_reviewed = True
            violation_percent = max(violation_percent, result.violation_percent)
            if result.topic_mismatch_percent is not None:
                topic_percent = max(topic_percent or 0, result.topic_mismatch_percent)
            findings += [Finding(f.code, 0.0, shown_matches(f.matches), f.aspect) for f in result.findings]

    return Assessment(
        Score(violation_percent, level_for(violation_percent, config)),
        Score(topic_percent, level_for(topic_percent, config)) if topic_percent is not None else None,
        tuple(findings),
        ai_reviewed,
    )


async def assess_category(
    *, title: str, description: str, config: ModerationConfig, ai: AiModerator | None = None
) -> Assessment:
    violation = score_violations(f"{title}\n{description}")
    violation_percent = violation.percent
    findings = list(violation.findings)

    ai_reviewed = False
    if config.ai_review_enabled and ai is not None and level_for(violation_percent, config) != "blocked":
        result = await _ask_ai(ai, AiReviewRequest("category", title, description))
        if result is not None:
            ai_reviewed = True
            violation_percent = max(violation_percent, result.violation_percent)
            findings += [Finding(f.code, 0.0, shown_matches(f.matches), "violation") for f in result.findings]

    return Assessment(Score(violation_percent, level_for(violation_percent, config)), None, tuple(findings), ai_reviewed)
