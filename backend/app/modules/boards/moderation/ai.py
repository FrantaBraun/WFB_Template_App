# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Level 2 of the content checks: an AI model judges a text against the
rules. **Only prepared so far - no model is connected.**

What is ready: the request the model gets (AiReviewRequest), the prompt built
from it (AiReviewRequest.prompt, with the aspects it may report), the JSON
the model must answer with (RESPONSE_SCHEMA) and the parser that validates
that answer into an AiReviewResult (parse_review_response), plus the place
the pipeline calls it (assess.py, when ModerationConfig.ai_review_enabled).
What is a mock: MockAiModerator, the only AiModerator there is - it answers
"nothing wrong" and records what it was asked.

To connect a real model, write a class with the same two coroutines (build
the prompt, send it, run the reply through parse_review_response) and return
it from get_ai_moderator(); nothing else needs to change.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# The aspects a model may report; anything else is kept as "ai_other" rather
# than shown to authors as an untranslated code.
VIOLATION_ASPECTS = (
    "profanity", "insult", "hate", "threat", "spam", "personal_data", "shouting",
    "repetition", "gibberish", "sexual_content", "self_harm", "illegal_content", "misinformation",
)  # fmt: skip
TOPIC_ASPECTS = ("off_topic",)

POLICY = """\
Posts and categories on this site must not contain: vulgar or abusive language aimed at people;
hate speech or discrimination; threats or incitement to violence or self-harm; spam, scams or
advertising links; personal data of others; sexual content involving minors or any illegal content;
deliberate misinformation that could cause harm. Posts must also fit the topic of the category
they are published in."""

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["violation_percent"],
    "properties": {
        "violation_percent": {"type": "integer", "minimum": 0, "maximum": 100},
        "topic_mismatch_percent": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["code"],
                "properties": {
                    "code": {"type": "string", "enum": [*VIOLATION_ASPECTS, *TOPIC_ASPECTS]},
                    "matches": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


@dataclass(frozen=True)
class AiReviewRequest:
    """One text to judge. For a post: the category's title, description and
    machine rules go along, so the model can also judge the topic."""

    kind: Literal["post", "category"]
    title: str
    text: str
    category_title: str | None = None
    category_description: str | None = None
    category_rules: dict | None = None

    def prompt(self) -> str:
        parts = [
            "You are a content moderator. Judge the submission below against these rules.",
            POLICY,
            "Answer with one JSON object only, matching this schema: "
            f"violation_percent (0-100, how likely the submission breaks the rules), "
            f"topic_mismatch_percent (0-100, how little it fits the category; null for a category), "
            f"findings (a list of {{code, matches}}, code one of: "
            f"{', '.join([*VIOLATION_ASPECTS, *TOPIC_ASPECTS])}; matches are quotes from the submission).",
        ]
        if self.kind == "post":
            parts.append(f"The submission is a post in the category '{self.category_title}': {self.category_description}")
            if self.category_rules and self.category_rules.get("keywords"):
                keywords = ", ".join(k["term"] for k in self.category_rules["keywords"])
                parts.append(f"Keywords the category stands for: {keywords}.")
        else:
            parts.append("The submission is a new category (its title and description).")
        parts.append(f"Title: {self.title}\nText: {self.text}")
        return "\n\n".join(parts)


class _ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    matches: list[str] = Field(default_factory=list)


class _ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    violation_percent: int = Field(ge=0, le=100)
    topic_mismatch_percent: int | None = Field(default=None, ge=0, le=100)
    findings: list[_ReviewFinding] = Field(default_factory=list)


@dataclass(frozen=True)
class AiFinding:
    code: str
    matches: tuple[str, ...] = ()

    @property
    def aspect(self) -> str:
        return "topic" if self.code in TOPIC_ASPECTS else "violation"


@dataclass(frozen=True)
class AiReviewResult:
    violation_percent: int
    topic_mismatch_percent: int | None = None
    findings: tuple[AiFinding, ...] = ()
    model: str = "unknown"


class AiResponseError(ValueError):
    """The model's answer was not the JSON the contract asks for."""


def parse_review_response(payload: dict, *, model: str) -> AiReviewResult:
    """Validates a model's decoded JSON answer into an AiReviewResult. An
    answer that does not match the contract raises AiResponseError - the
    caller decides whether a failed review blocks anything (it should not:
    the local checks have already run). Unknown finding codes are kept as
    "ai_other"."""
    try:
        response = _ReviewResponse.model_validate(payload)
    except ValidationError as exc:
        raise AiResponseError(str(exc)) from exc
    known = {*VIOLATION_ASPECTS, *TOPIC_ASPECTS}
    findings = tuple(
        AiFinding(f.code if f.code in known else "ai_other", tuple(f.matches[:5])) for f in response.findings
    )
    return AiReviewResult(response.violation_percent, response.topic_mismatch_percent, findings, model)


class AiModerator(Protocol):
    async def review(self, request: AiReviewRequest) -> AiReviewResult: ...

    async def build_category_rules(self, title: str, description: str) -> dict | None:
        """Machine rules for a new category in the shape topic.build_rules
        returns, or None to keep the algorithmic ones."""
        ...


@dataclass
class MockAiModerator:
    """The stand-in until a model is connected: finds nothing wrong, offers no
    rules of its own, and remembers what it was asked (so tests can see the
    requests - including their prompts - that a real model would have got).
    Give it a `result` to make it answer something else."""

    result: AiReviewResult = field(default_factory=lambda: AiReviewResult(0, None, (), "mock"))
    # Bounded: the module-level mock lives as long as the process does.
    requests: deque[AiReviewRequest] = field(default_factory=lambda: deque(maxlen=100))
    rules_requests: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=100))
    rules: dict | None = None

    async def review(self, request: AiReviewRequest) -> AiReviewResult:
        self.requests.append(request)
        return self.result

    async def build_category_rules(self, title: str, description: str) -> dict | None:
        self.rules_requests.append((title, description))
        return self.rules


_moderator: AiModerator = MockAiModerator()


def get_ai_moderator() -> AiModerator:
    """The one place that decides which AiModerator the app uses - also a
    FastAPI dependency, so tests override it."""
    return _moderator
