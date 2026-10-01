# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""event_calendar.json loading - including a guard that this branch's
committed file is valid, so a broken edit fails the suite, not production."""

import pydantic
import pytest

from app.modules.event_calendar.config import CONFIG_FILE, EventCalendarConfig, load_config


def test_committed_config_is_valid():
    if CONFIG_FILE.exists():
        assert isinstance(load_config(), EventCalendarConfig)


def test_missing_file_means_defaults(tmp_path):
    assert load_config(tmp_path / "missing.json").page_size == 10


@pytest.mark.parametrize(
    "content",
    ['{"page_size": "ten"}', '{"page_size": 0}', '{"unknown": true}', '{"editor_roles": ["admin"]}', "not json"],
)
def test_malformed_file_raises(tmp_path, content):
    path = tmp_path / "event_calendar.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        load_config(path)
