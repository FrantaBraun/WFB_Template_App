# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for what a module can contribute through its manifest besides a
router: `hooks` (taken by the module that owns a flow) and `background_tasks`
(started with the application). Like test_modules_registry.py, builds
throwaway packages on app.modules.__path__ instead of committing a fixture
module."""

import asyncio
import logging
import sys
import textwrap

import pytest

import app.modules as modules_pkg
from app.modules.registry import (
    discover_modules,
    get_enabled_hooks,
    start_background_tasks,
    stop_background_tasks,
)


@pytest.fixture()
def fixture_modules_path(tmp_path, monkeypatch):
    monkeypatch.setattr(modules_pkg, "__path__", list(modules_pkg.__path__) + [str(tmp_path)])
    before = set(sys.modules)
    yield tmp_path
    for name in set(sys.modules) - before:
        if name.startswith("app.modules.") and name not in ("app.modules.base", "app.modules.registry"):
            del sys.modules[name]


def _module(tmp_path, name, source=""):
    """app.modules.<name> whose __init__ is `source` plus a manifest built from
    the MANIFEST_ARGS dict that source defines."""
    pkg_dir = tmp_path / name
    pkg_dir.mkdir()
    code = textwrap.dedent(source)
    (pkg_dir / "__init__.py").write_text(
        "from app.modules.base import ModuleManifest\n"
        "MANIFEST_ARGS = {}\n"
        f"{code}\n"
        f"manifest = ModuleManifest(key={name!r}, **MANIFEST_ARGS)\n"
    )


def _hook_module(tmp_path, name, hook_name="thing.happened"):
    _module(
        tmp_path,
        name,
        f"""
        async def hook(*args):
            return {name!r}

        MANIFEST_ARGS = dict(hooks={{{hook_name!r}: hook}})
        """,
    )


def test_hooks_and_background_tasks_default_to_nothing(fixture_modules_path):
    _module(fixture_modules_path, "fixture_plain")

    manifest = {m.key: m for m in discover_modules()}["fixture_plain"]

    assert dict(manifest.hooks) == {} and manifest.background_tasks == ()


def test_only_enabled_modules_contribute_their_hooks_in_key_order(fixture_modules_path):
    for name in ("fixture_b", "fixture_a", "fixture_off"):
        _hook_module(fixture_modules_path, name)
    _hook_module(fixture_modules_path, "fixture_other", hook_name="other.thing")

    hooks = get_enabled_hooks("thing.happened", ["fixture_b", "fixture_a", "fixture_other"])

    assert [asyncio.run(hook()) for hook in hooks] == ["fixture_a", "fixture_b"]
    assert get_enabled_hooks("thing.happened", []) == []
    assert get_enabled_hooks("unknown.hook", ["fixture_a"]) == []


def test_hooks_default_to_the_modules_the_config_enables(fixture_modules_path, monkeypatch):
    _hook_module(fixture_modules_path, "fixture_x")
    monkeypatch.setattr("app.modules.registry.load_enabled_module_keys", lambda: ["fixture_x"])

    assert len(get_enabled_hooks("thing.happened")) == 1


async def test_background_tasks_of_enabled_modules_run_and_are_cancelled_on_stop(fixture_modules_path):
    _module(
        fixture_modules_path,
        "fixture_bg",
        """
        import asyncio

        STATE = {"started": 0, "cancelled": 0}

        async def task():
            STATE["started"] += 1
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                STATE["cancelled"] += 1
                raise

        MANIFEST_ARGS = dict(background_tasks=(task,))
        """,
    )
    _module(
        fixture_modules_path,
        "fixture_bg_off",
        """
        async def task():
            raise AssertionError("not enabled")

        MANIFEST_ARGS = dict(background_tasks=(task,))
        """,
    )

    tasks = start_background_tasks(["fixture_bg"])
    await asyncio.sleep(0)
    state = sys.modules["app.modules.fixture_bg"].STATE
    assert len(tasks) == 1 and state["started"] == 1

    await stop_background_tasks(tasks)

    assert state["cancelled"] == 1 and all(t.done() for t in tasks)


async def test_a_background_task_that_raises_is_logged_and_does_not_escape(fixture_modules_path, caplog):
    _module(
        fixture_modules_path,
        "fixture_bad",
        """
        async def task():
            raise RuntimeError("boom")

        MANIFEST_ARGS = dict(background_tasks=(task,))
        """,
    )

    with caplog.at_level(logging.ERROR):
        tasks = start_background_tasks(["fixture_bad"])
        await asyncio.gather(*tasks)

    assert "fixture_bad" in caplog.text and "boom" in caplog.text
    assert tasks[0].exception() is None
