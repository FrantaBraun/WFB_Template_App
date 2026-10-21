# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""event_booking.json loading and the e-mail texts built from it - including a
guard that this branch's committed file is valid, so a broken edit fails the
suite and not the first booking."""

import json
from datetime import date, time

import pydantic
import pytest

from app.config import Settings
from app.modules.event_booking import mail
from app.modules.event_booking.config import (
    ADMIN_PLACEHOLDERS,
    CONFIG_FILE,
    PLACEHOLDERS,
    TEMPLATE_TYPES,
    EventBookingConfig,
    allowed_placeholders,
    load_config,
)


def _raw() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def _write(tmp_path, data) -> object:
    path = tmp_path / "event_booking.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_committed_config_is_valid():
    config = load_config()

    assert isinstance(config, EventBookingConfig)
    assert set(config.templates) == set(TEMPLATE_TYPES)
    assert config.default_language in config.all_day_labels
    assert config.default_language in config.note_headings
    assert config.retention_months >= 1 and config.max_days_ahead >= 1


def test_committed_templates_render_with_every_placeholder_filled_in():
    config = load_config()
    values = {name: f"<{name}>" for name in PLACEHOLDERS | ADMIN_PLACEHOLDERS}

    for template_type in TEMPLATE_TYPES:
        for language, template in config.templates[template_type].items():
            subject, body = template.render(values)
            assert subject and body, (template_type, language)
            assert "{" not in subject and "{" not in body, (template_type, language)


def test_every_language_has_every_template():
    config = load_config()

    languages = {language for by_language in config.templates.values() for language in by_language}
    assert languages >= {"cs", "en"}
    for template_type in TEMPLATE_TYPES:
        assert set(config.templates[template_type]) == languages, template_type


def test_the_note_placeholder_is_only_for_what_an_administrator_does():
    assert "note_section" in allowed_placeholders("changed")
    assert "note_section" in allowed_placeholders("cancelled_by_admin")
    assert "note_section" not in allowed_placeholders("confirmation")
    assert "old_date" not in allowed_placeholders("cancellation")
    assert PLACEHOLDERS <= allowed_placeholders("confirmation")


def test_defaults_when_only_the_required_parts_are_given(tmp_path):
    raw = _raw()
    minimal = {key: raw[key] for key in ("default_language", "all_day_labels", "note_headings", "templates")}

    config = load_config(_write(tmp_path, minimal))

    assert (config.max_days_ahead, config.retention_months, config.max_active_per_email) == (365, 12, 5)
    assert config.send_confirmation is True and config.notify_admin is True and config.privacy_url is None


@pytest.mark.parametrize(
    "change",
    [
        {"max_days_ahead": 0},
        {"max_days_ahead": 1001},
        {"retention_months": 0},
        {"retention_months": "twelve"},
        {"max_active_per_email": 0},
        {"send_confirmation": "maybe"},
        {"unknown": True},
        {"privacy_url": "javascript:alert(1)"},
        {"privacy_url": "//evil.example/x"},
        {"privacy_url": "privacy.html"},
        {"default_language": "de"},
        {"all_day_labels": {}},
        {"note_headings": {"en": "Note:"}},  # no entry for default_language
    ],
)
def test_malformed_settings_raise(tmp_path, change):
    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, {**_raw(), **change}))


def test_a_site_path_or_an_http_address_is_a_valid_privacy_url(tmp_path):
    for url in ("/ochrana-udaju", "https://example.com/privacy", "http://example.com/p"):
        assert load_config(_write(tmp_path, {**_raw(), "privacy_url": url})).privacy_url == url
    assert load_config(_write(tmp_path, {**_raw(), "privacy_url": "  "})).privacy_url is None


@pytest.mark.parametrize("content", ["not json", "[]", ""])
def test_a_file_that_is_not_an_object_raises(tmp_path, content):
    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, content))


def test_a_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.json")


def _with_template(template_type, language, **fields):
    raw = _raw()
    raw["templates"][template_type][language] = {**raw["templates"][template_type][language], **fields}
    return raw


@pytest.mark.parametrize(
    ("template_type", "text"),
    [
        ("confirmation", "Hello {nme}"),  # a typo
        ("confirmation", "{old_date}"),  # administrator-only placeholder
        ("confirmation", "{note_section}"),
        ("cancellation", "{old_time}"),
        ("changed", "{name.__class__}"),  # attribute access
        ("changed", "{email[0]}"),  # index access
        ("changed", "{0}"),  # positional
        ("changed", "{}"),
        ("cancelled_by_admin", "{unknown}"),
        ("admin_notification", "{cancel_url} {oops}"),
        ("changed", "unbalanced {name"),
        ("changed", "stray } brace"),
    ],
)
def test_a_template_with_a_bad_placeholder_or_braces_raises_on_load(tmp_path, template_type, text):
    for field in ("subject", "body"):
        with pytest.raises(pydantic.ValidationError):
            load_config(_write(tmp_path, _with_template(template_type, "cs", **{field: text})))


def test_escaped_braces_are_literal_text(tmp_path):
    config = load_config(_write(tmp_path, _with_template("confirmation", "cs", body="{{name}} is {name}")))

    assert config.template("confirmation", "cs").render({name: "" for name in PLACEHOLDERS | ADMIN_PLACEHOLDERS} | {"name": "Eva"})[1] == "{name} is Eva"


@pytest.mark.parametrize("template_type", TEMPLATE_TYPES)
def test_a_missing_template_type_or_default_language_entry_raises(tmp_path, template_type):
    raw = _raw()
    del raw["templates"][template_type]
    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, raw))

    raw = _raw()
    del raw["templates"][template_type]["cs"]
    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, raw))


def test_an_unknown_template_type_raises(tmp_path):
    raw = _raw()
    raw["templates"]["newsletter"] = raw["templates"]["confirmation"]

    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, raw))


@pytest.mark.parametrize("field", ["subject", "body"])
def test_an_empty_subject_or_body_raises(tmp_path, field):
    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, _with_template("confirmation", "cs", **{field: ""})))


def test_language_codes_are_normalised(tmp_path):
    raw = _raw()
    raw["default_language"] = "CS"
    for by_language in raw["templates"].values():
        by_language["pt_BR"] = by_language["en"]
    raw["all_day_labels"]["pt_BR"] = "dia inteiro"

    config = load_config(_write(tmp_path, raw))

    assert config.default_language == "cs"
    assert all("pt-br" in by_language for by_language in config.templates.values())
    assert config.all_day_label("pt-BR") == "dia inteiro"


# --- Choosing a language -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("requested", "expected"),
    [("cs", "cs"), ("en", "en"), ("en-US", "en"), ("EN_gb", "en"), ("cs-CZ", "cs"), ("de", "cs"), ("", "cs"), (None, "cs"), ("x" * 30, "cs")],
)
def test_the_language_is_the_exact_one_then_its_primary_subtag_else_the_default(requested, expected):
    assert load_config().resolve_language(requested) == expected


def test_an_exact_regional_template_beats_the_primary_subtag(tmp_path):
    raw = _raw()
    for by_language in raw["templates"].values():
        by_language["en-gb"] = {"subject": "GB {event_title}", "body": "GB body"}
    config = load_config(_write(tmp_path, raw))

    assert config.template("confirmation", "en-GB").subject == "GB {event_title}"
    assert config.template("confirmation", "en-US").subject != "GB {event_title}"
    assert config.resolve_language("en-GB") == "en-gb"


def test_texts_fall_back_to_the_default_language():
    config = load_config()

    assert config.all_day_label("en") == "all day"
    assert config.all_day_label("fr") == config.all_day_label("cs")
    assert config.note_heading("en-US") == config.note_heading("en")
    assert config.note_heading(None) == config.note_heading("cs")


# --- Building the e-mails ----------------------------------------------------------------------------


def _settings(**fields) -> Settings:
    return Settings(frontend_url="https://example.org/", **fields)


def test_dates_are_czech_style_in_czech_and_iso_elsewhere():
    assert mail.format_date(date(2027, 5, 7), "cs") == "7. 5. 2027"
    assert mail.format_date(date(2027, 5, 7), "cs-CZ") == "7. 5. 2027"
    assert mail.format_date(date(2027, 5, 7), "en") == "2027-05-07"
    assert mail.format_date(date(2027, 5, 7), None) == "2027-05-07"


def test_a_time_is_hh_mm_and_a_whole_day_is_the_languages_all_day():
    config = load_config()

    assert mail.format_time(time(9, 5), config, "cs") == "09:05"
    assert mail.format_time(None, config, "cs") == "celý den"
    assert mail.format_time(None, config, "en") == "all day"


def test_the_cancel_link_is_built_from_the_frontend_url_without_a_double_slash():
    assert mail.cancel_url(_settings(), "tok") == "https://example.org/bookings/cancel/tok"


def test_the_note_section_is_the_heading_and_the_note_or_nothing():
    config = load_config()

    assert mail.note_section(config, "cs", "Přineste kartu.") == "Poznámka pořadatele:\nPřineste kartu.\n\n"
    assert mail.note_section(config, "en", "  Bring a card. ") == "Note from the organiser:\nBring a card.\n\n"
    assert mail.note_section(config, "cs", None) == ""
    assert mail.note_section(config, "cs", "   ") == ""


def test_template_values_cover_every_placeholder_and_default_the_old_slot_to_the_new_one():
    config = load_config()

    values = mail.template_values(
        config,
        _settings(),
        "en",
        name="Eva",
        email="eva@example.com",
        event_title="Tour",
        registration_name="Tour sign-up",
        slot_date=date(2027, 5, 7),
        slot_time=None,
        cancel_token="tok",
    )

    assert set(values) == PLACEHOLDERS | ADMIN_PLACEHOLDERS
    assert values["date"] == values["old_date"] == "2027-05-07"
    assert values["time"] == values["old_time"] == "all day"
    assert values["note_section"] == ""


def test_template_values_carry_the_old_slot_and_the_note():
    values = mail.template_values(
        load_config(),
        _settings(),
        "cs",
        name="Eva",
        email="eva@example.com",
        event_title="Prohlídka",
        registration_name="Přihlášky",
        slot_date=date(2027, 5, 8),
        slot_time=time(10, 30),
        cancel_token="tok",
        old_slot=(date(2027, 5, 7), time(9)),
        note="Posunuto.",
    )

    assert (values["old_date"], values["old_time"]) == ("7. 5. 2027", "09:00")
    assert (values["date"], values["time"]) == ("8. 5. 2027", "10:30")
    assert values["note_section"] == "Poznámka pořadatele:\nPosunuto.\n\n"


def test_the_notice_goes_to_the_booking_address_else_the_contact_address_else_nowhere():
    assert mail.notify_address(Settings(booking_notify_mail=" team@example.com ", contact_mail="c@example.com")) == "team@example.com"
    assert mail.notify_address(Settings(booking_notify_mail="", contact_mail="c@example.com")) == "c@example.com"
    assert mail.notify_address(Settings(booking_notify_mail="", contact_mail="")) == ""
