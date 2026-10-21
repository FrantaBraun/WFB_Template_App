# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""backend/modules/table_reservations.json: the committed file is valid, and a
broken one fails when it is loaded - not when somebody reserves."""

import copy
import json

import pytest
from pydantic import ValidationError

from app.modules.table_reservations import rules
from app.modules.table_reservations.config import (
    CONFIG_FILE,
    TEMPLATE_TYPES,
    TableReservationsConfig,
    allowed_placeholders,
    load_config,
)


def committed() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def parsed(raw: dict) -> TableReservationsConfig:
    return TableReservationsConfig.model_validate(raw)


def test_the_committed_file_is_valid_and_has_a_template_for_every_type_in_czech_and_english():
    config = load_config()

    assert set(config.templates) == set(TEMPLATE_TYPES)
    for template_type in TEMPLATE_TYPES:
        assert {"cs", "en"} <= set(config.templates[template_type])
    assert config.default_language == "cs"
    assert config.default_duration == rules.DEFAULT_DURATION == 120
    assert config.default_duration in config.duration_options


def test_every_committed_template_renders_with_every_placeholder_it_allows():
    config = load_config()

    for template_type in TEMPLATE_TYPES:
        values = {name: f"<{name}>" for name in allowed_placeholders(template_type)}
        for language, template in config.templates[template_type].items():
            subject, body = template.render(values)
            assert subject and body, (template_type, language)


def test_the_message_of_the_pub_reaches_the_guest_only_in_the_cancelled_by_admin_template():
    config = load_config()

    for language in ("cs", "en"):
        assert "{note_section}" in config.templates["cancelled_by_admin"][language].body
        for template_type in ("confirmation", "cancellation", "admin_notification"):
            assert "{note_section}" not in config.templates[template_type][language].body


def test_the_guests_own_details_are_in_the_notice_to_the_pub_but_the_table_is_not_in_the_guests_mails():
    assert "table" in allowed_placeholders("admin_notification")
    assert "phone" in allowed_placeholders("admin_notification")
    for template_type in ("confirmation", "cancellation", "cancelled_by_admin"):
        assert "table" not in allowed_placeholders(template_type)
        assert "phone" not in allowed_placeholders(template_type)


def test_an_unknown_placeholder_is_refused_when_loading():
    raw = copy.deepcopy(committed())
    raw["templates"]["confirmation"]["cs"]["body"] += "{nonsense}"

    with pytest.raises(ValidationError, match="unknown placeholder"):
        parsed(raw)


def test_a_placeholder_of_another_type_is_refused():
    raw = copy.deepcopy(committed())
    raw["templates"]["confirmation"]["cs"]["body"] += "{note_section}"

    with pytest.raises(ValidationError, match="unknown placeholder"):
        parsed(raw)


def test_attribute_access_in_a_template_is_refused():
    raw = copy.deepcopy(committed())
    raw["templates"]["confirmation"]["cs"]["subject"] = "{name.__class__}"

    with pytest.raises(ValidationError, match="unknown placeholder"):
        parsed(raw)


def test_a_missing_template_type_or_default_language_is_refused():
    missing_type = copy.deepcopy(committed())
    del missing_type["templates"]["cancellation"]
    no_default = copy.deepcopy(committed())
    del no_default["templates"]["confirmation"]["cs"]

    with pytest.raises(ValidationError, match="templates must have exactly"):
        parsed(missing_type)
    with pytest.raises(ValidationError, match="default_language"):
        parsed(no_default)


@pytest.mark.parametrize("options", [[60, 100], [15, 60], [60, 600], [0, 60]])
def test_durations_must_be_steps_within_the_allowed_range(options):
    raw = copy.deepcopy(committed())
    raw["duration_options"] = options

    with pytest.raises(ValidationError):
        parsed(raw)


def test_the_default_duration_must_be_one_of_the_options():
    raw = copy.deepcopy(committed())
    raw["default_duration"] = 135

    with pytest.raises(ValidationError):
        parsed(raw)


def test_kind_labels_need_both_kinds():
    raw = copy.deepcopy(committed())
    del raw["kind_labels"]["cs"]["whole_venue"]

    with pytest.raises(ValidationError, match="kind_labels"):
        parsed(raw)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "//evil.example", "ftp://x"])
def test_a_privacy_url_must_be_a_site_path_or_an_http_address(url):
    raw = copy.deepcopy(committed())
    raw["privacy_url"] = url

    with pytest.raises(ValidationError, match="privacy_url"):
        parsed(raw)


def test_a_privacy_url_may_be_a_path_an_address_or_nothing():
    for good, expected in (("/ochrana-udaju", "/ochrana-udaju"), ("https://pub.example/privacy", "https://pub.example/privacy"), ("  ", None), (None, None)):
        raw = copy.deepcopy(committed())
        raw["privacy_url"] = good
        assert parsed(raw).privacy_url == expected


def test_unknown_keys_are_refused_so_a_typo_does_not_silently_do_nothing():
    raw = copy.deepcopy(committed())
    raw["retention_month"] = 6

    with pytest.raises(ValidationError):
        parsed(raw)


def test_the_language_of_an_email_is_the_guests_then_the_primary_subtag_then_the_default():
    config = load_config()

    assert config.resolve_language("en") == "en"
    assert config.resolve_language("en-US") == "en"
    assert config.resolve_language("EN_gb") == "en"
    assert config.resolve_language("cs") == "cs"
    assert config.resolve_language("de") == "cs"
    assert config.resolve_language(None) == "cs"
    assert config.template("confirmation", "de").subject == config.templates["confirmation"]["cs"].subject
    assert config.kind_label("whole_venue", "en") == "the whole pub"
    assert config.kind_label("table", "de") == "stůl"
    assert config.note_heading("en").startswith("A message")
