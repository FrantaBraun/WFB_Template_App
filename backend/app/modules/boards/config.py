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
- payments: what an author may pay to raise a post's value (PaymentsConfig).
- invoicing: who issues the payment documents and in what language/time zone
  (InvoicingConfig). Payments are refused until the provider is filled in.

The text limits (post title / text, category title / description) are
fixed in schemas.py and the column sizes in models.py, not configured here:
changing one would need a migration.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class PaymentsConfig(BaseModel):
    """What one payment for a post may be: a whole number of US dollars from
    min_amount_usd to max_amount_usd (1 USD buys points_per_usd points of
    value). Whole dollars keep every payment an exact number of points. The
    range is quoted in the public terms - keep legal.json's params in step."""

    model_config = ConfigDict(extra="forbid")

    min_amount_usd: int = Field(default=1, ge=1)
    max_amount_usd: int = Field(default=500, ge=1)

    @model_validator(mode="after")
    def _range_is_not_empty(self) -> "PaymentsConfig":
        if self.min_amount_usd > self.max_amount_usd:
            raise ValueError("min_amount_usd must not be above max_amount_usd")
        return self


class ProviderConfig(BaseModel):
    """Who is selling: printed on every payment document. The same data as
    the `provider` in the frontend's public/legal.json (which the legal pages
    show) - a test keeps the two equal. `registration` is per language."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    ico: str = ""
    dic: str = ""
    vat_payer: bool = False
    address: str = ""
    registration: dict[Literal["cs", "en"], str] = Field(default_factory=dict)
    email: str = ""
    phone: str = ""
    web: str = ""

    @property
    def complete(self) -> bool:
        """The minimum a document needs to identify its issuer."""
        return all((self.name.strip(), self.ico.strip(), self.address.strip(), self.email.strip()))


class InvoicingConfig(BaseModel):
    """Payment documents and the confirmation email.

    - provider: the issuer. While it is incomplete, payments are not offered
      or accepted - a document without an issuer would be worthless, and the
      money would already be taken.
    - default_language: the document's language when the payer's is unknown.
    - timezone: where "the date" of a document and the year of its number are
      reckoned (the provider's, not the server's).
    """

    model_config = ConfigDict(extra="forbid")

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    default_language: Literal["cs", "en"] = "cs"
    timezone: str = "Europe/Prague"

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (KeyError, ValueError, OSError) as exc:  # not a validation error until we say so
            raise ValueError(f"unknown time zone {value!r}") from exc
        return value


class BoardsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_size: int = Field(default=20, ge=1, le=50)
    points_per_usd: int = Field(default=10, ge=0)
    points_per_resonance: int = Field(default=1, ge=0)
    points_per_day: int = Field(default=1, ge=0)
    moderation: ModerationConfig = Field(default_factory=ModerationConfig)
    payments: PaymentsConfig = Field(default_factory=PaymentsConfig)
    invoicing: InvoicingConfig = Field(default_factory=InvoicingConfig)


def load_config(path: Path = CONFIG_FILE) -> BoardsConfig:
    """A missing file means the defaults; a malformed one raises (fail at
    startup/first use, not silently with surprising settings)."""
    if not path.exists():
        return BoardsConfig()
    return BoardsConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_config() -> BoardsConfig:
    return load_config()
