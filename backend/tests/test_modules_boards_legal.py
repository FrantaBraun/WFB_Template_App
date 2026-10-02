# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The numbers the public Terms and Privacy pages quote must be the numbers
the application actually enforces.

The pages are static text in the frontend, filled from the `params` in
frontend/public/legal.json; the thresholds, limits and points are enforced by
this module from backend/modules/boards.json and its models. This is the one
place the two meet, so a change to either side without the other fails the
suite instead of quietly making the published rules false."""

import json

import pytest

from app.config import BASE_DIR
from app.modules.boards.config import load_config
from app.modules.boards.models import (
    CATEGORY_DESCRIPTION_MAX,
    CATEGORY_TITLE_MAX,
    POST_BODY_MAX,
    POST_TITLE_MAX,
)

LEGAL_FILE = BASE_DIR.parent / "frontend" / "public" / "legal.json"

pytestmark = pytest.mark.skipif(not LEGAL_FILE.exists(), reason="the frontend is not checked out next to the backend")


@pytest.fixture(scope="module")
def params() -> dict:
    return json.loads(LEGAL_FILE.read_text(encoding="utf-8"))["params"]


def test_the_points_formula_quoted_in_the_terms_is_the_one_enforced(params):
    config = load_config()
    assert params["pointsPerUsd"] == config.points_per_usd
    assert params["pointsPerResonance"] == config.points_per_resonance
    assert params["pointsPerDay"] == config.points_per_day


def test_the_moderation_thresholds_quoted_in_the_terms_are_the_ones_enforced(params):
    moderation = load_config().moderation
    assert params["warnPercent"] == moderation.warn_percent
    assert params["riskPercent"] == moderation.risk_percent
    assert params["blockPercent"] == moderation.block_percent


def test_the_account_block_rule_quoted_in_the_terms_is_the_one_enforced(params):
    moderation = load_config().moderation
    assert params["strikeLimit"] == moderation.strike_limit
    assert params["strikePeriodDays"] == moderation.strike_period_days


def test_the_text_limits_quoted_in_the_terms_are_the_ones_enforced(params):
    assert params["postTitleMax"] == POST_TITLE_MAX
    assert params["postBodyMax"] == POST_BODY_MAX
    assert params["categoryTitleMax"] == CATEGORY_TITLE_MAX
    assert params["categoryDescriptionMax"] == CATEGORY_DESCRIPTION_MAX


def test_the_payment_range_quoted_in_the_terms_is_the_one_enforced(params):
    payments = load_config().payments
    assert params["minAmountUsd"] == payments.min_amount_usd
    assert params["maxAmountUsd"] == payments.max_amount_usd


def test_every_param_is_checked_above(params):
    """A new param added to legal.json without a guard here would be exactly
    the drift this file exists to prevent."""
    guarded = {
        "pointsPerUsd", "pointsPerResonance", "pointsPerDay",
        "warnPercent", "riskPercent", "blockPercent",
        "strikeLimit", "strikePeriodDays",
        "postTitleMax", "postBodyMax", "categoryTitleMax", "categoryDescriptionMax",
        "minAmountUsd", "maxAmountUsd",
    }  # fmt: skip
    assert set(params) == guarded
