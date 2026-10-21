# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""This application's own wording of the registration e-mails (the committed
backend/modules/event_booking.json): what the shared module's tests do not
check, because the module ships neutral texts and each application writes its
own."""

import pytest

from app.modules.event_booking.config import load_config

BRAND = "Slavíčkovy knihohrátky"
TO_THE_PERSON = ("confirmation", "cancellation", "changed", "cancelled_by_admin")


def test_both_languages_are_written():
    config = load_config()

    assert config.default_language == "cs"
    for by_language in config.templates.values():
        assert {"cs", "en"} <= set(by_language)


@pytest.mark.parametrize("template_type", TO_THE_PERSON)
@pytest.mark.parametrize("language", ["cs", "en"])
def test_what_the_person_receives_is_signed_with_the_applications_name(template_type, language):
    body = load_config().templates[template_type][language].body

    assert body.rstrip().endswith(BRAND)


def test_the_notice_to_the_administrator_is_a_plain_summary():
    body = load_config().templates["admin_notification"]["cs"].body

    assert "{name}" in body and "{email}" in body and "{date}" in body
    assert "{cancel_url}" not in body  # the administrator manages bookings in the administration
