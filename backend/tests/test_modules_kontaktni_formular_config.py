# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the kontaktni_formular module's reply-email config
(app/modules/kontaktni_formular/config.py): validation at load time,
language matching, and the branch's own committed
backend/modules/kontaktni_formular.json."""

import json

import pytest
from pydantic import ValidationError

from app.modules.kontaktni_formular.config import CONFIG_FILE, ContactFormConfig, PageTexts, load_contact_form_config


def _config(**overrides) -> dict:
    data = {
        "default_language": "cs",
        "reply_templates": {
            "cs": {"subject": "Díky: {subject}", "body": "{message}"},
            "en": {"subject": "Thanks: {subject}", "body": "{message}"},
        },
    }
    return {**data, **overrides}


def test_committed_config_file_is_valid():
    """Guards this branch's own backend/modules/kontaktni_formular.json, so
    a broken template fails the suite instead of a visitor's submit."""
    config = load_contact_form_config(CONFIG_FILE)

    assert config.default_language in config.reply_templates


def test_load_reads_json_file(tmp_path):
    path = tmp_path / "kontaktni_formular.json"
    path.write_text(json.dumps(_config(send_reply=False)), encoding="utf-8")

    config = load_contact_form_config(path)

    assert config.send_reply is False
    assert set(config.reply_templates) == {"cs", "en"}


def test_send_reply_defaults_to_true():
    assert ContactFormConfig.model_validate(_config()).send_reply is True


def test_language_codes_are_normalized():
    config = ContactFormConfig.model_validate(
        _config(default_language="CS", reply_templates={"CS": {"subject": "a", "body": "b"}, "pt_BR": {"subject": "c", "body": "d"}})
    )

    assert config.default_language == "cs"
    assert set(config.reply_templates) == {"cs", "pt-br"}
    assert config.reply_template_for("pt-BR").subject == "c"


@pytest.mark.parametrize(
    ("language", "expected_subject"),
    [
        ("en", "Thanks: {subject}"),
        ("EN", "Thanks: {subject}"),
        ("en-GB", "Thanks: {subject}"),
        ("en_GB", "Thanks: {subject}"),
        ("de", "Díky: {subject}"),
        ("", "Díky: {subject}"),
        (None, "Díky: {subject}"),
    ],
)
def test_reply_template_for_matches_or_falls_back(language, expected_subject):
    config = ContactFormConfig.model_validate(_config())

    assert config.reply_template_for(language).subject == expected_subject


def test_default_language_must_have_a_template():
    with pytest.raises(ValidationError, match="default_language 'de' has no entry"):
        ContactFormConfig.model_validate(_config(default_language="de"))


def test_at_least_one_template_is_required():
    with pytest.raises(ValidationError):
        ContactFormConfig.model_validate(_config(reply_templates={}))


@pytest.mark.parametrize(
    "template",
    ["Hi {name}", "{message.__class__}", "{message[0]}", "{0}", "{}", "unclosed {message", "{message!x}"],
)
def test_invalid_template_is_rejected(template):
    with pytest.raises(ValidationError):
        ContactFormConfig.model_validate(
            _config(reply_templates={"cs": {"subject": "ok", "body": template}})
        )


def test_unknown_config_key_is_rejected():
    with pytest.raises(ValidationError):
        ContactFormConfig.model_validate(_config(default_lang="cs"))


def test_render_fills_every_placeholder_and_keeps_literal_braces():
    config = ContactFormConfig.model_validate(
        _config(
            reply_templates={
                "cs": {
                    "subject": "Re: {subject}",
                    "body": "{sender_name} <{reply_to}> {{literal}}\n{message}",
                }
            }
        )
    )

    subject, body = config.reply_template_for("cs").render(
        sender_name="Jana", reply_to="jana@example.com", subject="Dotaz", message="Text {not a placeholder}"
    )

    assert subject == "Re: Dotaz"
    assert body == "Jana <jana@example.com> {literal}\nText {not a placeholder}"


def test_page_texts_and_show_email_default_to_nothing():
    config = ContactFormConfig.model_validate(_config())

    assert config.show_email is False
    assert config.page == {}
    assert config.page_texts_for("cs") == PageTexts()


def test_page_texts_match_language_or_fall_back_to_default_language():
    config = ContactFormConfig.model_validate(
        _config(page={"cs": {"title": "Kontakt"}, "en": {"title": "Contact", "intro": "Hello", "aside": "Mon-Fri"}})
    )

    assert config.page_texts_for("en").title == "Contact"
    assert config.page_texts_for("en-GB").intro == "Hello"
    assert config.page_texts_for("EN_us").aside == "Mon-Fri"
    # a language without texts gets the default language's, not an error
    assert config.page_texts_for("de").title == "Kontakt"
    assert config.page_texts_for(None).title == "Kontakt"


def test_page_texts_are_empty_when_the_default_language_has_none():
    config = ContactFormConfig.model_validate(_config(page={"en": {"title": "Contact"}}))

    assert config.page_texts_for("de") == PageTexts()


def test_page_language_codes_are_normalized():
    config = ContactFormConfig.model_validate(_config(page={"pt_BR": {"title": "Contato"}}))

    assert set(config.page) == {"pt-br"}
    assert config.page_texts_for("pt-BR").title == "Contato"


def test_unknown_page_key_is_rejected():
    with pytest.raises(ValidationError):
        ContactFormConfig.model_validate(_config(page={"cs": {"heading": "Kontakt"}}))


@pytest.mark.parametrize(("field", "limit"), [("title", 120), ("intro", 2000), ("aside", 1000)])
def test_page_text_length_is_limited(field, limit):
    ContactFormConfig.model_validate(_config(page={"cs": {field: "x" * limit}}))

    with pytest.raises(ValidationError):
        ContactFormConfig.model_validate(_config(page={"cs": {field: "x" * (limit + 1)}}))
