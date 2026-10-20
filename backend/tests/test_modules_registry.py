# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the app.modules discovery/enable-disable framework. Builds
throwaway fixture packages on app.modules.__path__ rather than committing a
real example module under app/modules/ - this repo's module system ships as
pure structure, with no concrete modules of its own."""

import logging
import sys

import pytest

import app.modules as modules_pkg
from app.modules.registry import (
    MODULES_CONFIG_FILE,
    check_module_dependencies,
    discover_modules,
    get_enabled_modules,
    import_all_module_models,
    load_enabled_module_keys,
)


def _write_fixture_module(tmp_path, name, *, manifest_key=None, with_models=False, requires=()):
    """Create tmp_path/<name>/ as an importable app.modules.<name> subpackage."""
    pkg_dir = tmp_path / name
    pkg_dir.mkdir()
    key = name if manifest_key is None else manifest_key
    (pkg_dir / "__init__.py").write_text(
        "from app.modules.base import ModuleManifest\n"
        f"manifest = ModuleManifest(key={key!r}, requires={tuple(requires)!r})\n"
    )
    if with_models:
        (pkg_dir / "models.py").write_text("MODELS_IMPORTED = True\n")
    return pkg_dir


@pytest.fixture()
def fixture_modules_path(tmp_path, monkeypatch):
    """Extends app.modules.__path__ with tmp_path so fixture packages written
    there import as app.modules.<name>, and cleans up whatever got imported
    afterwards so tests don't leak state to each other."""
    monkeypatch.setattr(modules_pkg, "__path__", list(modules_pkg.__path__) + [str(tmp_path)])
    before = set(sys.modules)
    yield tmp_path
    for name in set(sys.modules) - before:
        if name.startswith("app.modules.") and name not in ("app.modules.base", "app.modules.registry"):
            del sys.modules[name]


def test_discover_modules_finds_valid_fixture(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_alpha")

    found = {manifest.key: manifest for manifest in discover_modules()}

    assert "fixture_alpha" in found
    assert found["fixture_alpha"].router is None


def test_discover_modules_skips_package_without_manifest(fixture_modules_path):
    pkg_dir = fixture_modules_path / "fixture_no_manifest"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")

    found = {manifest.key for manifest in discover_modules()}

    assert "fixture_no_manifest" not in found


def test_discover_modules_skips_mismatched_key(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_renamed", manifest_key="fixture_original")

    found = {manifest.key for manifest in discover_modules()}

    assert "fixture_renamed" not in found
    assert "fixture_original" not in found


def test_get_enabled_modules_filters_by_keys(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_on")
    _write_fixture_module(fixture_modules_path, "fixture_off")

    enabled = {manifest.key for manifest in get_enabled_modules(["fixture_on"])}

    assert enabled == {"fixture_on"}


def test_load_enabled_module_keys_reads_enabled_array(tmp_path):
    config = tmp_path / "modules.json"
    config.write_text('{"enabled": ["alpha", "beta"]}', encoding="utf-8")

    assert load_enabled_module_keys(config) == ["alpha", "beta"]


def test_load_enabled_module_keys_missing_file_enables_nothing(tmp_path):
    assert load_enabled_module_keys(tmp_path / "missing.json") == []


def test_load_enabled_module_keys_missing_enabled_key_enables_nothing(tmp_path):
    config = tmp_path / "modules.json"
    config.write_text("{}", encoding="utf-8")

    assert load_enabled_module_keys(config) == []


@pytest.mark.parametrize("enabled", ['"notifications"', '[1, 2]', "null"])
def test_load_enabled_module_keys_rejects_non_list_of_strings(tmp_path, enabled):
    config = tmp_path / "modules.json"
    config.write_text(f'{{"enabled": {enabled}}}', encoding="utf-8")

    with pytest.raises(ValueError, match="list of module keys"):
        load_enabled_module_keys(config)


def test_committed_modules_json_only_enables_existing_modules():
    """Guards this branch's own backend/modules.json: every enabled key must
    name a real module under app/modules/, so a typo fails the suite instead
    of silently leaving that module unmounted."""
    discovered = {manifest.key for manifest in discover_modules()}

    unknown = set(load_enabled_module_keys(MODULES_CONFIG_FILE)) - discovered

    assert not unknown, f"backend/modules.json enables unknown module(s): {sorted(unknown)}"


def test_import_all_module_models_imports_only_modules_with_models(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_with_models", with_models=True)
    _write_fixture_module(fixture_modules_path, "fixture_without_models")

    import_all_module_models()

    assert "app.modules.fixture_with_models.models" in sys.modules
    assert "app.modules.fixture_without_models.models" not in sys.modules


# --- Module dependencies ------------------------------------------------------


def test_manifest_requires_defaults_to_nothing(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_plain")

    found = {manifest.key: manifest for manifest in discover_modules()}

    assert found["fixture_plain"].requires == ()


def test_enabled_module_without_its_requirement_is_warned_about(fixture_modules_path, caplog):
    _write_fixture_module(fixture_modules_path, "fixture_base")
    _write_fixture_module(fixture_modules_path, "fixture_top", requires=["fixture_base"])

    with caplog.at_level(logging.WARNING, logger="app.modules.registry"):
        problems = check_module_dependencies(["fixture_top"])

    assert problems == ["module 'fixture_top' is enabled but requires 'fixture_base', which is not enabled"]
    assert problems[0] in caplog.text


def test_satisfied_requirement_is_silent(fixture_modules_path, caplog):
    _write_fixture_module(fixture_modules_path, "fixture_base")
    _write_fixture_module(fixture_modules_path, "fixture_top", requires=["fixture_base"])

    with caplog.at_level(logging.WARNING, logger="app.modules.registry"):
        problems = check_module_dependencies(["fixture_base", "fixture_top"])

    assert problems == []
    assert "requires" not in caplog.text


def test_disabled_module_with_missing_requirement_is_not_warned_about(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_base")
    _write_fixture_module(fixture_modules_path, "fixture_top", requires=["fixture_base"])

    assert check_module_dependencies([]) == []
    assert check_module_dependencies(["fixture_base"]) == []


def test_requirement_that_no_module_provides_is_reported_as_unknown(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_typo", requires=["fixture_missing"])

    problems = check_module_dependencies(["fixture_typo", "fixture_missing"])

    assert problems == ["module 'fixture_typo' requires unknown module 'fixture_missing'"]


def test_dependency_check_never_raises_and_reports_every_problem(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_a")
    _write_fixture_module(fixture_modules_path, "fixture_b")
    _write_fixture_module(fixture_modules_path, "fixture_c", requires=["fixture_a", "fixture_b"])

    problems = check_module_dependencies(["fixture_c"])

    assert len(problems) == 2


def test_committed_modules_json_has_its_requirements_met():
    """This branch's own enabled set shouldn't ship a warning at startup."""
    assert check_module_dependencies(load_enabled_module_keys(MODULES_CONFIG_FILE)) == []
