# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""boards.json loading - including a guard that this branch's committed file
is valid, so a broken edit fails the suite, not production."""

import pydantic
import pytest

from app.modules.boards.config import CONFIG_FILE, BoardsConfig, load_config


def test_committed_config_is_valid():
    if CONFIG_FILE.exists():
        assert isinstance(load_config(), BoardsConfig)


def test_committed_config_keeps_the_documented_formula():
    """1 USD = 10 points, 1 resonance = 1 point, 1 day of age = -1 point."""
    config = load_config()
    assert (config.points_per_usd, config.points_per_resonance, config.points_per_day) == (10, 1, 1)


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
        "not json",
    ],
)
def test_malformed_file_raises(tmp_path, content):
    path = tmp_path / "boards.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        load_config(path)
