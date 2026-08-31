# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the app.modules discovery/enable-disable framework. Builds
throwaway fixture packages on app.modules.__path__ rather than committing a
real example module under app/modules/ - this repo's module system ships as
pure structure, with no concrete modules of its own."""

import sys

import pytest

import app.modules as modules_pkg
from app.config import Settings
from app.modules.registry import discover_modules, get_enabled_modules, import_all_module_models


def _write_fixture_module(tmp_path, name, *, manifest_key=None, with_models=False):
    """Create tmp_path/<name>/ as an importable app.modules.<name> subpackage."""
    pkg_dir = tmp_path / name
    pkg_dir.mkdir()
    key = name if manifest_key is None else manifest_key
    (pkg_dir / "__init__.py").write_text(
        "from app.modules.base import ModuleManifest\n" f"manifest = ModuleManifest(key={key!r})\n"
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


def test_get_enabled_modules_filters_by_settings(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_on")
    _write_fixture_module(fixture_modules_path, "fixture_off")
    settings = Settings(enabled_modules=["fixture_on"])

    enabled = {manifest.key for manifest in get_enabled_modules(settings)}

    assert enabled == {"fixture_on"}


def test_import_all_module_models_imports_only_modules_with_models(fixture_modules_path):
    _write_fixture_module(fixture_modules_path, "fixture_with_models", with_models=True)
    _write_fixture_module(fixture_modules_path, "fixture_without_models")

    import_all_module_models()

    assert "app.modules.fixture_with_models.models" in sys.modules
    assert "app.modules.fixture_without_models.models" not in sys.modules
