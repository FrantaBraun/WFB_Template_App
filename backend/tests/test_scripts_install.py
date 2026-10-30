# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for what scripts/install.sh writes into the nginx config about
/sitemap.xml. It used to proxy it to the `boards` module unconditionally, so on
every application without that module a crawler got a 404 from the backend (and
robots.txt pointed at it). scripts/ is not a package and the script needs root,
so these read it as text and, where bash is available, run the sitemap snippet.
The script reaches bash on stdin as UTF-8 bytes: a Windows checkout stores it
with CRLF line endings and Git's bash mangles Windows paths given as arguments."""

import shutil
import subprocess
from pathlib import Path

import pytest

INSTALL_SH = Path(__file__).resolve().parents[2] / "scripts" / "install.sh"
BOARDS_PROXY = "/api/modules/boards/sitemap.xml"
BOARDS_TEST = 'if [[ -d "${INSTALL_DIR}/backend/app/modules/boards" ]]; then'

# The bash on PATH, by its full path: a bare "bash" is looked up by Windows in System32
# first, which is the WSL launcher (another file system), not Git's bash.
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not available")


def _text() -> str:
    # read_text translates CRLF to LF, which is what git stores and a server runs
    return INSTALL_SH.read_text(encoding="utf-8")


def _bash(script: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, *flags], input=script.encode("utf-8"), capture_output=True)


def test_the_script_is_valid_bash():
    result = _bash(_text(), "-n")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


def test_the_boards_proxy_exists_once_and_only_inside_the_module_check():
    text = _text()
    assert text.count(BOARDS_PROXY) == 1
    assert BOARDS_TEST in text
    assert text.index(BOARDS_TEST) < text.index(BOARDS_PROXY) < text.index("else", text.index(BOARDS_PROXY))


def test_the_nginx_config_takes_the_location_from_the_variable():
    assert "\n${SITEMAP_LOCATION}\n" in _text()


def _sitemap_location(with_boards: bool) -> str:
    """Runs the script's own `if ... fi` for the sitemap against a fresh install directory."""
    text = _text()
    start = text.index(BOARDS_TEST)
    end = text.index("\nfi\n", start) + len("\nfi\n")
    make_module = 'mkdir -p "$INSTALL_DIR/backend/app/modules/boards"\n' if with_boards else 'mkdir -p "$INSTALL_DIR/backend/app/modules"\n'
    script = (
        'INSTALL_DIR="$(mktemp -d)"\nBACKEND_PORT=8123\n'
        + make_module
        + text[start:end]
        + '\nprintf "%s" "$SITEMAP_LOCATION"\nrm -rf "$INSTALL_DIR"\n'
    )
    result = _bash(script)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout.decode("utf-8")


def test_an_application_with_the_boards_module_has_the_sitemap_proxied():
    location = _sitemap_location(with_boards=True)

    assert "location = /sitemap.xml" in location
    assert "proxy_pass         http://127.0.0.1:8123" + BOARDS_PROXY in location
    assert "try_files" not in location


def test_any_other_application_serves_the_built_file_or_404s():
    location = _sitemap_location(with_boards=False)

    assert "location = /sitemap.xml" in location
    assert "/frontend;" in location
    assert "try_files /sitemap.xml =404;" in location
    assert "proxy_pass" not in location
