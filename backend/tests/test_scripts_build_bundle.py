# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the zip that `build.py --target scripts` makes for the server. It is
built from the files of the development machine, which on Windows are stored
with CRLF line endings: a CRLF install.sh fails there with "/bin/bash^M: bad
interpreter", and every value read from deploy.config.sh or .env would end in a
carriage return. The bundle therefore carries LF and Unix permissions (scripts
executable, the two files with secrets private) whatever the checkout stored.
scripts/ is not a package, so build.py is loaded by path."""

import importlib.util
import stat
import zipfile
from pathlib import Path

import pytest

BUILD_PY = Path(__file__).resolve().parents[2] / "scripts" / "build.py"

_spec = importlib.util.spec_from_file_location("build_script_bundle", BUILD_PY)
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


@pytest.fixture
def crlf_checkout(tmp_path, monkeypatch):
    """A scripts directory the way a Windows checkout stores it, with the build's constants pointed at it."""
    scripts = tmp_path / "scripts"
    (tmp_path / "backend").mkdir()
    scripts.mkdir()
    (scripts / "install.sh").write_bytes(b"#!/bin/bash\r\nset -euo pipefail\r\necho install\r\n")
    (scripts / "upgrade.sh").write_bytes(b"#!/bin/bash\r\necho upgrade\r\n")
    (scripts / "deploy.config.sh").write_bytes(b'INSTALL_DIR="/srv/app"\r\nBACKEND_PORT=8002\r\n')
    (scripts / "deploy.config.sh.example").write_bytes(b'INSTALL_DIR="/srv/example"\r\n')
    (tmp_path / "backend" / ".env").write_bytes(b"DATABASE_URL=postgresql+asyncpg://u:p@localhost/db\r\nLOGGING_MESSAGE_FORMAT=a\\tb\r\n")
    monkeypatch.setattr(build, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(build, "_DEPLOY_CONFIG", scripts / "deploy.config.sh")
    monkeypatch.setattr(build, "_DEPLOY_CONFIG_EXAMPLE", scripts / "deploy.config.sh.example")
    return scripts


def _bundle(tmp_path) -> zipfile.ZipFile:
    output = tmp_path / "scripts.zip"
    build.build_scripts(output)
    return zipfile.ZipFile(output)


def test_everything_in_the_bundle_has_lf_line_endings(tmp_path, crlf_checkout):
    with _bundle(tmp_path) as z:
        assert sorted(z.namelist()) == [".env", "deploy.config.sh", "install.sh", "upgrade.sh"]
        for name in z.namelist():
            assert b"\r" not in z.read(name), name
        assert z.read("install.sh").startswith(b"#!/bin/bash\nset -euo pipefail\n")
        assert z.read("deploy.config.sh") == b'INSTALL_DIR="/srv/app"\nBACKEND_PORT=8002\n'


def test_only_the_line_endings_change(tmp_path, crlf_checkout):
    with _bundle(tmp_path) as z:
        # a backslash-t in .env is two characters and stays two characters
        assert z.read(".env") == b"DATABASE_URL=postgresql+asyncpg://u:p@localhost/db\nLOGGING_MESSAGE_FORMAT=a\\tb\n"


def test_a_lone_carriage_return_inside_a_line_is_not_touched():
    assert b"a\rb\r\n".replace(b"\r\n", b"\n") == b"a\rb\n"


def test_a_file_that_is_already_lf_is_bundled_byte_for_byte(tmp_path, crlf_checkout):
    (crlf_checkout / "upgrade.sh").write_bytes(b"#!/bin/bash\necho upgrade\n")

    with _bundle(tmp_path) as z:
        assert z.read("upgrade.sh") == b"#!/bin/bash\necho upgrade\n"


def _mode(z: zipfile.ZipFile, name: str) -> int:
    return stat.S_IMODE(z.getinfo(name).external_attr >> 16)


def test_the_scripts_unpack_executable_and_the_secrets_private(tmp_path, crlf_checkout):
    with _bundle(tmp_path) as z:
        assert _mode(z, "install.sh") == 0o755
        assert _mode(z, "upgrade.sh") == 0o755
        assert _mode(z, ".env") == 0o600
        assert _mode(z, "deploy.config.sh") == 0o600


def test_the_modes_are_marked_as_unix_so_that_unzip_applies_them(tmp_path, crlf_checkout):
    with _bundle(tmp_path) as z:
        assert {info.create_system for info in z.infolist()} == {3}
        assert stat.S_ISREG(z.getinfo("install.sh").external_attr >> 16)


def test_without_a_deploy_config_the_example_is_bundled_as_deploy_config_sh(tmp_path, crlf_checkout, capsys):
    (crlf_checkout / "deploy.config.sh").unlink()

    with _bundle(tmp_path) as z:
        assert z.read("deploy.config.sh") == b'INSTALL_DIR="/srv/example"\n'
        assert _mode(z, "deploy.config.sh") == 0o600
    assert "WARNING" in capsys.readouterr().out


def test_a_missing_script_stops_the_build(tmp_path, crlf_checkout):
    (crlf_checkout / "upgrade.sh").unlink()

    with pytest.raises(SystemExit) as stop:
        build.build_scripts(tmp_path / "scripts.zip")

    assert "upgrade.sh" in str(stop.value)


def test_the_repository_keeps_shell_scripts_lf_in_every_checkout():
    attributes = (BUILD_PY.parents[1] / ".gitattributes").read_text(encoding="utf-8")

    assert "*.sh text eol=lf" in attributes
