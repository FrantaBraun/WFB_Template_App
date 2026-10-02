# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""boards.json loading - including a guard that this branch's committed file
is valid, so a broken edit fails the suite, not production."""

import pydantic
import pytest

from app.modules.boards.config import CONFIG_FILE, BoardsConfig, ModerationConfig, load_config


def test_committed_config_is_valid():
    if CONFIG_FILE.exists():
        assert isinstance(load_config(), BoardsConfig)


def test_committed_config_keeps_the_documented_formula():
    """1 USD = 10 points, 1 resonance = 1 point, 1 day of age = -1 point."""
    config = load_config()
    assert (config.points_per_usd, config.points_per_resonance, config.points_per_day) == (10, 1, 1)


def test_committed_config_keeps_the_documented_moderation_thresholds():
    """Above 30 % advise an edit, above 50 % warn of a risk, above 75 % refuse."""
    moderation = load_config().moderation
    assert (moderation.warn_percent, moderation.risk_percent, moderation.block_percent) == (30, 50, 75)
    assert moderation.ai_review_enabled is False  # only a mock is connected


def test_missing_file_means_defaults(tmp_path):
    config = load_config(tmp_path / "missing.json")
    assert config == BoardsConfig(page_size=20, points_per_usd=10, points_per_resonance=1, points_per_day=1)


def test_partial_file_keeps_defaults_for_the_rest(tmp_path):
    path = tmp_path / "boards.json"
    path.write_text('{"page_size": 5}', encoding="utf-8")
    config = load_config(path)
    assert config.page_size == 5
    assert config.points_per_usd == 10


@pytest.mark.parametrize(
    "content",
    [
        '{"page_size": "ten"}',
        '{"page_size": 0}',
        '{"page_size": 51}',
        '{"points_per_usd": -1}',
        '{"points_per_day": -1}',
        '{"unknown": true}',
        '{"moderation": {"warn_percent": 60}}',
        '{"moderation": {"warn_percent": 50, "risk_percent": 50}}',
        '{"moderation": {"block_percent": 101}}',
        '{"moderation": {"strike_limit": 0}}',
        '{"moderation": {"strike_period_days": 0}}',
        '{"moderation": {"topic_similarity_scale": 0}}',
        '{"moderation": {"unknown": 1}}',
        '{"payments": {"min_amount_usd": 0}}',
        '{"payments": {"max_amount_usd": 0}}',
        '{"payments": {"min_amount_usd": 10, "max_amount_usd": 5}}',
        '{"payments": {"min_amount_usd": 1.5}}',
        '{"payments": {"unknown": 1}}',
        "not json",
    ],
)
def test_malformed_file_raises(tmp_path, content):
    path = tmp_path / "boards.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        load_config(path)


def test_moderation_defaults_and_partial_overrides(tmp_path):
    assert BoardsConfig().moderation == ModerationConfig(
        warn_percent=30, risk_percent=50, block_percent=75, strike_limit=3, strike_period_days=30
    )
    path = tmp_path / "boards.json"
    path.write_text('{"moderation": {"strike_limit": 5, "ai_review_enabled": true}}', encoding="utf-8")
    moderation = load_config(path).moderation
    assert (moderation.strike_limit, moderation.ai_review_enabled, moderation.block_percent) == (5, True, 75)


def test_the_committed_payment_range_is_the_documented_one():
    """One to 500 US dollars per payment, as the public terms say."""
    payments = load_config().payments
    assert (payments.min_amount_usd, payments.max_amount_usd) == (1, 500)


def test_payments_have_defaults_and_can_be_narrowed(tmp_path):
    assert BoardsConfig().payments.min_amount_usd == 1 and BoardsConfig().payments.max_amount_usd == 500
    path = tmp_path / "boards.json"
    path.write_text('{"payments": {"min_amount_usd": 5, "max_amount_usd": 5}}', encoding="utf-8")
    payments = load_config(path).payments
    assert (payments.min_amount_usd, payments.max_amount_usd) == (5, 5)  # a fixed price is a valid range
