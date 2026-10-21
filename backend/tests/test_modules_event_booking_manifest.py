# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""How the booking module presents itself to the module system: its manifest,
the warning when it is switched on without what it builds on, and that its
tables are known to Alembic whether or not it is enabled."""

import logging

from app.modules.event_booking import manifest
from app.modules.event_booking.router import router
from app.modules.registry import check_module_dependencies, discover_modules, import_all_module_models


def test_the_manifest_names_the_module_its_router_and_what_it_builds_on():
    assert manifest.key == "event_booking"
    assert manifest.router is router
    assert manifest.requires == ("event_calendar", "forms")


def test_the_module_is_discovered():
    assert "event_booking" in {found.key for found in discover_modules()}


def test_enabling_bookings_without_the_calendar_or_forms_is_warned_about(caplog):
    with caplog.at_level(logging.WARNING):
        both_missing = check_module_dependencies(["event_booking"])
        no_forms = check_module_dependencies(["event_booking", "event_calendar", "articles"])
        no_calendar = check_module_dependencies(["event_booking", "forms"])

    assert both_missing == [
        "module 'event_booking' is enabled but requires 'event_calendar', which is not enabled",
        "module 'event_booking' is enabled but requires 'forms', which is not enabled",
    ]
    assert no_forms == ["module 'event_booking' is enabled but requires 'forms', which is not enabled"]
    assert no_calendar == ["module 'event_booking' is enabled but requires 'event_calendar', which is not enabled"]
    assert any("requires 'forms'" in record.getMessage() for record in caplog.records)


def test_enabling_it_with_everything_it_builds_on_is_silent():
    assert check_module_dependencies(["event_booking", "event_calendar", "articles", "forms"]) == []


def test_a_disabled_module_is_not_warned_about():
    assert check_module_dependencies(["forms"]) == []


def test_the_tables_are_registered_with_alembic_even_when_the_module_is_disabled():
    import_all_module_models()
    from app.models.base import Base

    assert {
        "module_booking_registrations",
        "module_booking_blocks",
        "module_booking_bookings",
        "module_booking_changes",
    } <= set(Base.metadata.tables)
