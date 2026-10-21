# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""backend/modules/pub_menu.json and how the module presents itself to the module
system: the committed file is valid, a broken one fails when it is loaded, and the
tables are known to Alembic whether or not the module is enabled."""

import json

import pytest
from pydantic import ValidationError

from app.modules.pub_menu import manifest
from app.modules.pub_menu.config import CONFIG_FILE, PubMenuConfig, load_config
from app.modules.pub_menu.router import router
from app.modules.registry import check_module_dependencies, discover_modules, import_all_module_models


def test_the_committed_file_is_valid():
    config = load_config()

    assert (config.currency, config.weeks_back, config.weeks_ahead) == ("CZK", 1, 4)
    assert set(json.loads(CONFIG_FILE.read_text(encoding="utf-8"))) == {"currency", "weeks_back", "weeks_ahead"}


@pytest.mark.parametrize(
    "raw",
    [
        {"currency": "czk"},
        {"currency": "KORUNA"},
        {"currency": "CZ"},
        {"weeks_back": -1},
        {"weeks_ahead": 53},
        {"surprise": 1},
    ],
)
def test_a_broken_file_is_refused_when_loading(raw):
    with pytest.raises(ValidationError):
        PubMenuConfig.model_validate(raw)


def test_every_key_has_a_default():
    config = PubMenuConfig.model_validate({})

    assert (config.currency, config.weeks_back, config.weeks_ahead) == ("CZK", 1, 4)


def test_the_manifest_names_the_module_and_its_router_and_requires_nothing():
    assert manifest.key == "pub_menu"
    assert manifest.router is router
    assert manifest.requires == ()


def test_the_module_is_discovered_and_enabling_it_alone_is_silent():
    assert "pub_menu" in {found.key for found in discover_modules()}
    assert check_module_dependencies(["pub_menu"]) == []


def test_the_tables_are_registered_with_alembic_even_when_the_module_is_disabled():
    import_all_module_models()
    from app.models.base import Base

    assert {
        "module_menu_categories",
        "module_menu_items",
        "module_menu_prices",
        "module_menu_days",
        "module_menu_day_items",
        "module_menu_settings",
    } <= set(Base.metadata.tables)
