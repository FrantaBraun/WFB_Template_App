# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for where scripts/install.sh and scripts/upgrade.sh get the builds:
from directories on the machine itself (BACKEND_RELEASES_DIR /
FRONTEND_RELEASES_DIR in deploy.config.sh) - the FTP/SFTP server build.py
uploads to runs there - instead of downloading them over FTP. scripts/ is not a
package and the scripts need root, so the two helpers are cut out of the text
and run in bash (the script goes in on stdin as UTF-8 bytes: a Windows checkout
stores it with CRLF and Git's bash mangles Windows paths given as arguments;
the archives are made inside that bash, from base64, for the same reason)."""

import base64
import re
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
INSTALL_SH = SCRIPTS / "install.sh"
UPGRADE_SH = SCRIPTS / "upgrade.sh"
BOTH = [INSTALL_SH, UPGRADE_SH]

# The bash on PATH, by its full path: a bare "bash" is looked up by Windows in System32
# first, which is the WSL launcher (another file system, no unzip), not Git's bash.
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not available")


def _text(path: Path) -> str:
    # read_text translates CRLF to LF, which is what git stores and a server runs
    return path.read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.S | re.M)
    assert match, f"no function {name}()"
    return match.group(0)


def _bash(script: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, *flags], input=script.encode("utf-8"), capture_output=True)


def _needs_unzip():
    if _bash("command -v unzip").returncode != 0:
        pytest.skip("unzip is not available in bash")


# ── the scripts as text ───────────────────────────────────────────────────────

@pytest.mark.parametrize("path", BOTH, ids=lambda p: p.name)
def test_the_script_is_valid_bash(path):
    result = _bash(_text(path), "-n")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("path", BOTH, ids=lambda p: p.name)
def test_the_script_downloads_nothing_over_ftp(path):
    text = _text(path)

    for leftover in ("--ftp-pasv", "ftp://", "FTP_USER", "FTP_PASS", "FTP_HOST", "FTP_BACKEND_PATH", "ftp_download", "ftp_latest_file"):
        assert leftover not in text


@pytest.mark.parametrize("name", ["latest_archive", "require_release_dirs"])
def test_the_two_scripts_carry_the_same_helper(name):
    assert _function(_text(INSTALL_SH), name) == _function(_text(UPGRADE_SH), name)


@pytest.mark.parametrize("path", BOTH, ids=lambda p: p.name)
def test_the_archives_are_unpacked_straight_from_the_release_directories(path):
    text = _text(path)

    assert 'unzip -q "$BACKEND_ARCHIVE"' in text
    assert 'unzip -q "$FRONTEND_ARCHIVE"' in text
    assert 'latest_archive "$BACKEND_RELEASES_DIR" "backend-"' in text
    assert 'latest_archive "$FRONTEND_RELEASES_DIR" "frontend-"' in text


def test_upgrade_looks_for_the_archives_before_it_stops_the_service():
    text = _text(UPGRADE_SH)

    assert text.index('step "Locate the new archives"') < text.index('step "1/7  Stop service"')
    assert text.index("require_release_dirs\n") < text.index('step "1/7  Stop service"')


@pytest.mark.parametrize("path, total", [(INSTALL_SH, 10), (UPGRADE_SH, 7)], ids=["install", "upgrade"])
def test_the_numbered_steps_run_from_one_to_the_total(path, total):
    steps = re.findall(r'^step "(\d+)/(\d+) ', _text(path), re.M)

    assert [(int(n), int(t)) for n, t in steps] == [(n, total) for n in range(1, total + 1)]


# ── the helpers, run ──────────────────────────────────────────────────────────

DIE = 'die() { echo -e "ERROR: $*" >&2; exit 1; }\n'


def _zip_base64() -> str:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("hello.txt", "hello")
    return base64.b64encode(buffer.getvalue()).decode()


def _latest_archive(setup: str, call: str) -> subprocess.CompletedProcess:
    """Runs the scripts' latest_archive in a fresh release directory ($D, with a space in its name)."""
    _needs_unzip()
    script = (
        "set -euo pipefail\n" + DIE + _function(_text(INSTALL_SH), "latest_archive")
        + 'D="$(mktemp -d)/release dir"\nmkdir -p "$D"\n'
        + f'ZIP="{_zip_base64()}"\n'
        + 'mk() { echo "$ZIP" | base64 -d > "$D/$1"; touch -d "@$2" "$D/$1"; }\n'
        + setup + "\n" + call + '\nrc=$?\nrm -rf "$(dirname "$D")"\nexit $rc\n'
    )
    return _bash(script)


def test_it_picks_the_archive_uploaded_last_not_the_highest_name():
    result = _latest_archive(
        "mk backend-B-1.10.0.zip 1000\nmk backend-B-1.9.0.zip 2000\nmk backend-snapshot-20261030-abc.zip 1500\n",
        'latest_archive "$D" backend-',
    )

    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.decode().strip().endswith("/release dir/backend-B-1.9.0.zip")


def test_it_ignores_other_prefixes_half_names_and_directories():
    result = _latest_archive(
        "mk backend-B-1.0.0.zip 1000\nmk frontend-F-9.9.9.zip 5000\nmk backend-B-2.0.0.zip.part 6000\n"
        'mk backendX.zip 7000\nmkdir "$D/backend-folder.zip"\ntouch -d @8000 "$D/backend-folder.zip"\n',
        'latest_archive "$D" backend-',
    )

    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.decode().strip().endswith("/release dir/backend-B-1.0.0.zip")


def test_each_prefix_gets_its_own_newest_archive():
    result = _latest_archive(
        "mk backend-B-1.zip 9000\nmk frontend-F-1.zip 1000\nmk frontend-F-2.zip 2000\n",
        'latest_archive "$D" frontend-',
    )

    assert result.stdout.decode().strip().endswith("/release dir/frontend-F-2.zip")


def test_a_missing_release_directory_stops_with_its_name():
    result = _latest_archive("", 'latest_archive "$D/nope" backend-')

    assert result.returncode != 0
    assert "Release directory not found" in result.stderr.decode() and "nope" in result.stderr.decode()


def test_an_empty_release_directory_stops_with_a_message():
    result = _latest_archive("mk frontend-F-1.zip 1000\n", 'latest_archive "$D" backend-')

    assert result.returncode != 0
    assert "No backend-*.zip archive found" in result.stderr.decode()


def test_an_archive_that_is_not_a_whole_zip_stops_the_script():
    """A build that is still being uploaded is the newest file and not yet a zip."""
    result = _latest_archive(
        'mk backend-B-1.zip 1000\nprintf "PK\\003\\004 half an upload" > "$D/backend-B-2.zip"\ntouch -d @2000 "$D/backend-B-2.zip"\n',
        'latest_archive "$D" backend-',
    )

    assert result.returncode != 0
    assert "Not a complete zip archive" in result.stderr.decode()
    assert "backend-B-2.zip" in result.stderr.decode()
    assert result.stdout.decode() == ""


def _require(config: str) -> subprocess.CompletedProcess:
    script = (
        "set -euo pipefail\n" + DIE + 'CONFIG_FILE="/srv/scripts/deploy.config.sh"\n'
        + _function(_text(INSTALL_SH), "require_release_dirs") + config + "\nrequire_release_dirs\necho fine\n"
    )
    return _bash(script)


def test_two_absolute_release_directories_are_accepted():
    result = _require('BACKEND_RELEASES_DIR=/home/ftp/releases/backend\nFRONTEND_RELEASES_DIR=/home/ftp/releases/frontend')

    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.decode().strip() == "fine"


@pytest.mark.parametrize(
    "config, named",
    [
        ('FTP_HOST=ftp.example.com\nFTP_BACKEND_PATH=/releases/backend', "BACKEND_RELEASES_DIR"),  # a config from before the change
        ("BACKEND_RELEASES_DIR=/a", "FRONTEND_RELEASES_DIR"),
        ("BACKEND_RELEASES_DIR=releases/backend\nFRONTEND_RELEASES_DIR=/b", "BACKEND_RELEASES_DIR"),  # relative
        ('BACKEND_RELEASES_DIR=""\nFRONTEND_RELEASES_DIR=/b', "BACKEND_RELEASES_DIR"),
    ],
    ids=["old-ftp-config", "frontend-missing", "relative", "empty"],
)
def test_a_missing_or_relative_release_directory_stops_the_script_naming_it(config, named):
    result = _require(config)
    error = result.stderr.decode()

    assert result.returncode != 0
    assert named in error
    assert "/srv/scripts/deploy.config.sh" in error and "deploy.config.sh.example" in error
    assert "fine" not in result.stdout.decode()
