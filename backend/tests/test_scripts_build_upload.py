# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for how scripts/build.py uploads a built zip: over FTP as before, or
over SFTP - the OpenSSH `sftp` command in batch mode, chosen by an [sftp]
section in the config - for a server whose firewall lets only port 22 through
(passive FTP needs a second, high port). scripts/ is not a package, so the
script is loaded by path; nothing here touches the network or runs sftp."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

BUILD_PY = Path(__file__).resolve().parents[2] / "scripts" / "build.py"

_spec = importlib.util.spec_from_file_location("build_script_upload", BUILD_PY)
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


# ── the batch of sftp commands ────────────────────────────────────────────────

def test_the_batch_makes_the_directory_one_segment_at_a_time_then_puts_the_file():
    assert build._sftp_batch("/releases/backend", "backend-1.zip") == (
        '-mkdir "/releases"\n'
        '-mkdir "/releases/backend"\n'
        'put "backend-1.zip" "/releases/backend/backend-1.zip"\n'
    )


def test_a_directory_without_a_leading_slash_stays_relative_to_the_home_directory():
    assert build._sftp_batch("releases/backend", "b.zip") == (
        '-mkdir "releases"\n'
        '-mkdir "releases/backend"\n'
        'put "b.zip" "releases/backend/b.zip"\n'
    )


@pytest.mark.parametrize("remote_dir, expected", [("/", 'put "b.zip" "/b.zip"\n'), ("", 'put "b.zip" "b.zip"\n')])
def test_with_no_directory_the_file_goes_into_the_root_or_home(remote_dir, expected):
    assert build._sftp_batch(remote_dir, "b.zip") == expected


def test_the_mkdir_lines_ignore_a_directory_that_exists_and_the_put_does_not():
    lines = build._sftp_batch("/a/b", "x.zip").splitlines()

    assert [line.startswith("-mkdir") for line in lines] == [True, True, False]
    assert lines[-1].startswith("put ")


def test_spaces_quotes_and_backslashes_stay_inside_one_argument():
    batch = build._sftp_batch("/my dir", 'a "b" \\c.zip')

    assert batch.splitlines()[-1] == 'put "a \\"b\\" \\\\c.zip" "/my dir/a \\"b\\" \\\\c.zip"'


# ── the command line ──────────────────────────────────────────────────────────

@pytest.fixture
def sftp_on_path(monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda name: "/usr/bin/sftp" if name == "sftp" else None)


def test_the_command_reads_a_batch_from_stdin_and_never_asks_for_a_password(sftp_on_path):
    command = build._sftp_command({"host": "example.com", "user": "deploy"})

    assert command[0] == "/usr/bin/sftp"
    assert command[command.index("-b") + 1] == "-"
    assert command[command.index("-P") + 1] == "22"
    assert "BatchMode=yes" in command
    assert command[-1] == "deploy@example.com"
    assert "-i" not in command


def test_the_port_and_a_key_file_come_from_the_config(sftp_on_path):
    command = build._sftp_command({"host": "h", "user": "u", "port": 2222, "key_file": "~/keys/deploy_key"})

    assert command[command.index("-P") + 1] == "2222"
    key = command[command.index("-i") + 1]
    assert not key.startswith("~") and key.endswith("keys/deploy_key")
    assert "IdentitiesOnly=yes" in command


def test_a_missing_sftp_command_stops_with_a_message(monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda name: None)

    with pytest.raises(SystemExit) as stop:
        build._sftp_command({"host": "h", "user": "u"})

    assert "sftp" in str(stop.value) and "PATH" in str(stop.value)


# ── the upload ────────────────────────────────────────────────────────────────

def _fake_run(monkeypatch, returncode=0):
    seen = {}

    def run(command, input=None, cwd=None, **kwargs):  # noqa: A002 - subprocess.run's own name
        seen.update(command=command, input=input, cwd=cwd, kwargs=kwargs)
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(build.subprocess, "run", run)
    return seen


def test_the_upload_sends_the_batch_as_bytes_from_the_zips_directory(tmp_path, sftp_on_path, monkeypatch, capsys):
    seen = _fake_run(monkeypatch)
    zip_path = tmp_path / "backend-1.zip"
    zip_path.write_bytes(b"zip")

    build.upload_sftp(zip_path, "/releases/backend", {"sftp": {"host": "example.com", "user": "deploy"}})

    assert seen["cwd"] == tmp_path
    assert isinstance(seen["input"], bytes) and b"\r" not in seen["input"]
    assert seen["input"].decode().endswith('put "backend-1.zip" "/releases/backend/backend-1.zip"\n')
    assert "Upload complete" in capsys.readouterr().out


def test_a_failed_sftp_stops_the_build_and_says_what_to_check(tmp_path, sftp_on_path, monkeypatch):
    _fake_run(monkeypatch, returncode=255)

    with pytest.raises(SystemExit) as stop:
        build.upload_sftp(tmp_path / "b.zip", "/releases/backend", {"sftp": {"host": "example.com", "user": "deploy", "port": 2200}})

    message = str(stop.value)
    assert "255" in message
    assert "ssh -p 2200 deploy@example.com" in message
    assert "/releases/backend" in message


def test_the_upload_never_prints_the_config_credentials(tmp_path, sftp_on_path, monkeypatch, capsys):
    _fake_run(monkeypatch)

    build.upload_sftp(tmp_path / "b.zip", "/d", {"sftp": {"host": "example.com", "user": "deploy", "key_file": "~/secret_key"}})

    out = capsys.readouterr().out
    assert "secret_key" not in out and "deploy@" not in out


# ── which upload, and where to ────────────────────────────────────────────────

def test_an_sftp_section_picks_sftp_and_without_one_it_is_ftp(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(build, "upload_sftp", lambda *args: calls.append("sftp"))
    monkeypatch.setattr(build, "upload_ftp", lambda *args: calls.append("ftp"))

    build.upload(tmp_path / "b.zip", "/d", {"ftp": {}, "sftp": {}})
    build.upload(tmp_path / "b.zip", "/d", {"ftp": {}})

    assert calls == ["sftp", "ftp"]


FTP_PATHS = {"backend": "/ftp/backend", "frontend": "/ftp/frontend", "scripts": "/ftp/scripts"}


def test_without_an_sftp_section_the_paths_are_the_ftp_ones():
    assert build.remote_dir_for({"ftp": {"paths": FTP_PATHS}}, "backend") == "/ftp/backend"


def test_sftp_paths_win_and_a_target_they_leave_out_uses_the_ftp_path():
    cfg = {"ftp": {"paths": FTP_PATHS}, "sftp": {"paths": {"backend": "/home/ftp/backend"}}}

    assert build.remote_dir_for(cfg, "backend") == "/home/ftp/backend"
    assert build.remote_dir_for(cfg, "frontend") == "/ftp/frontend"


def test_an_sftp_section_without_paths_falls_back_to_the_ftp_ones():
    assert build.remote_dir_for({"ftp": {"paths": FTP_PATHS}, "sftp": {}}, "scripts") == "/ftp/scripts"


def test_a_target_with_no_path_anywhere_stops_with_a_message_naming_the_section():
    with pytest.raises(SystemExit) as only_sftp:
        build.remote_dir_for({"sftp": {"host": "h"}}, "backend")
    with pytest.raises(SystemExit) as only_ftp:
        build.remote_dir_for({"ftp": {"paths": {}}}, "backend")

    assert "[sftp.paths]" in str(only_sftp.value)
    assert "[ftp.paths]" in str(only_ftp.value)
