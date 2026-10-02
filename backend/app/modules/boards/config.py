# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Boards settings, read from the git-tracked backend/modules/boards.json -
per-application values that follow the branch, like backend/modules.json
(see app/modules/registry.py).

- page_size: how many posts / categories one page of a listing loads.
- points_per_usd, points_per_resonance, points_per_day: the post value
  formula - value = paid USD * points_per_usd + resonances *
  points_per_resonance - whole days of age * points_per_day (see service.py).
- moderation: the thresholds and parameters of the content checks (see
  ModerationConfig and moderation/).

The text limits (post title / text, category title / description) are
fixed in schemas.py and the column sizes in models.py, not configured here:
changing one would need a migration.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import BASE_DIR

CONFIG_FILE = BASE_DIR / "modules" / "boards.json"


class ModerationConfig(BaseModel):
    """Parameters of the content checks (moderation/).

    - warn_percent / risk_percent / block_percent: a violation score (or a
      topic-mismatch score) strictly above warn_percent advises the author to
      edit; above risk_percent it is shown as potentially violating - it may
      be blocked without a refund on closer review, and publishing needs the
      author's explicit confirmation; above block_percent publishing is not
      allowed.
    - strike_limit / strike_period_days: an account is blocked (and its
      remaining posts removed) once an administrator has marked
      strike_limit of its posts as violating within the last
      strike_period_days days. State the same numbers in the public rules.
    - ai_review_enabled: also ask the AI moderator (moderation/ai.py - a mock
      until a real model is connected) after the local checks pass.
    - topic_full_confidence_words / topic_full_confidence_keywords /
      topic_similarity_scale: how much the topic check may say. A short post,
      or a category whose machine rules have few keywords, is weak evidence
      either way, so its mismatch score is scaled down until the post has
      this many distinct content words and the rules this many keywords
      (see moderation/topic.py).
    """

    model_config = ConfigDict(extra="forbid")

    warn_percent: int = Field(default=30, ge=0, le=100)
    risk_percent: int = Field(default=50, ge=0, le=100)
    block_percent: int = Field(default=75, ge=0, le=100)
    strike_limit: int = Field(default=3, ge=1)
    strike_period_days: int = Field(default=30, ge=1)
    ai_review_enabled: bool = False
    topic_full_confidence_words: int = Field(default=25, ge=1)
    topic_full_confidence_keywords: int = Field(default=8, ge=1)
    topic_similarity_scale: float = Field(default=1.5, gt=0)

    @model_validator(mode="after")
    def _thresholds_ascend(self) -> "ModerationConfig":
        if not self.warn_percent < self.risk_percent < self.block_percent:
            raise ValueError("warn_percent < risk_percent < block_percent must hold")
        return self


class BoardsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_size: int = Field(default=20, ge=1, le=50)
    points_per_usd: int = Field(default=10, ge=0)
    points_per_resonance: int = Field(default=1, ge=0)
    points_per_day: int = Field(default=1, ge=0)
    moderation: ModerationConfig = Field(default_factory=ModerationConfig)


def load_config(path: Path = CONFIG_FILE) -> BoardsConfig:
    """A missing file means the defaults; a malformed one raises (fail at
    startup/first use, not silently with surprising settings)."""
    if not path.exists():
        return BoardsConfig()
    return BoardsConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_config() -> BoardsConfig:
    return load_config()
