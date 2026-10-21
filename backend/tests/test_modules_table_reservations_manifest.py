# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""How the table reservations module presents itself to the module system: its
manifest, that it needs nothing else, and that its tables are known to Alembic
whether or not it is enabled."""

from app.modules.registry import check_module_dependencies, discover_modules, import_all_module_models
from app.modules.table_reservations import manifest
from app.modules.table_reservations.router import router


def test_the_manifest_names_the_module_and_its_router_and_requires_nothing():
    assert manifest.key == "table_reservations"
    assert manifest.router is router
    assert manifest.requires == ()


def test_the_module_is_discovered():
    assert "table_reservations" in {found.key for found in discover_modules()}


def test_enabling_it_alone_is_silent():
    assert check_module_dependencies(["table_reservations"]) == []


def test_the_tables_are_registered_with_alembic_even_when_the_module_is_disabled():
    import_all_module_models()
    from app.models.base import Base

    assert {
        "module_res_tables",
        "module_res_opening_hours",
        "module_res_opening_exceptions",
        "module_res_reservations",
    } <= set(Base.metadata.tables)
