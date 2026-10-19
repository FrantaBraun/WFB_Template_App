# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for how scripts/build.py gets the frontend build's .env: it copies the
development directory's frontend/.env as it is stored and writes none of its
own. scripts/ is not a package, so the script is loaded by path (importing it
only defines functions - main() runs under __main__ only)."""

import importlib.util
import inspect
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

BUILD_PY = Path(__file__).resolve().parents[2] / "scripts" / "build.py"

_spec = importlib.util.spec_from_file_location("build_script", BUILD_PY)
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def _write_env(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_the_env_is_copied_byte_for_byte(tmp_path):
    # comments, blank lines, quotes and Windows line endings all stay as stored
    content = b'# a comment\r\nVITE_API_URL="https://example.com"\r\n\r\nVITE_APP_URL=https://example.com\r\nVITE_API_KEY=abc\r\n'
    source = _write_env(tmp_path / "source.env", content)
    dest = tmp_path / "dest.env"

    build.copy_frontend_env(dest, source)

    assert dest.read_bytes() == content


def test_a_missing_env_stops_the_build_with_guidance(tmp_path):
    with pytest.raises(SystemExit) as stopped:
        build.copy_frontend_env(tmp_path / "dest.env", tmp_path / "missing.env")

    message = str(stopped.value)
    assert "missing.env" in message
    assert "frontend/.env.example" in message
    assert not (tmp_path / "dest.env").exists()


def test_it_names_the_variables_but_never_prints_their_values(tmp_path, capsys):
    source = _write_env(tmp_path / "source.env", b"VITE_API_URL=https://example.com\nVITE_API_KEY=top-secret-key\n")

    build.copy_frontend_env(tmp_path / "dest.env", source)

    out = capsys.readouterr().out
    assert "VITE_API_URL, VITE_API_KEY" in out
    assert "top-secret-key" not in out
    assert "WARNING" not in out


@pytest.mark.parametrize(
    "line",
    [
        "VITE_API_URL=http://localhost:8000",
        "VITE_API_URL=http://127.0.0.1:8000",
        "VITE_APP_URL=http://localhost:5173/",
        'VITE_AUTH_URL="http://[::1]:9000"',
        "VITE_API_URL=http://0.0.0.0:8000",
    ],
)
def test_a_url_that_points_at_this_machine_is_warned_about_but_still_copied(tmp_path, capsys, line):
    source = _write_env(tmp_path / "source.env", (line + "\n").encode())
    dest = tmp_path / "dest.env"

    build.copy_frontend_env(dest, source)

    assert dest.exists()
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert line.split("=")[0] in out


def test_only_urls_are_checked_for_a_local_address(tmp_path, capsys):
    source = _write_env(
        tmp_path / "source.env",
        b"# VITE_API_URL=http://localhost:8000\nVITE_NOTE=localhost\nVITE_API_URL=https://example.com\n",
    )

    build.copy_frontend_env(tmp_path / "dest.env", source)

    assert "WARNING" not in capsys.readouterr().out


def test_an_empty_env_is_copied_and_says_so(tmp_path, capsys):
    source = _write_env(tmp_path / "source.env", b"")
    dest = tmp_path / "dest.env"

    build.copy_frontend_env(dest, source)

    assert dest.read_bytes() == b""
    assert "no variables" in capsys.readouterr().out


def test_the_default_source_is_the_development_directorys_frontend_env():
    assert build._FRONTEND_ENV == BUILD_PY.parents[1] / "frontend" / ".env"


def test_the_frontend_build_writes_no_env_of_its_own():
    source = inspect.getsource(build.build_frontend)

    assert "copy_frontend_env(" in source
    assert "VITE_" not in source
    assert "withfbraun.com" not in source
    assert "client_api_key" not in source


def test_build_frontend_builds_with_the_copied_env_in_place(tmp_path, monkeypatch):
    """The whole path with git, npm and the file system faked: the env is next
    to the extracted sources when npm runs, and the resulting dist/ is zipped."""
    env = _write_env(tmp_path / "frontend.env", b"VITE_API_URL=https://example.com\nVITE_API_KEY=abc\n")
    monkeypatch.setattr(build, "_FRONTEND_ENV", env)

    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("package.json", "{}")
    monkeypatch.setattr(build, "git_archive_bytes", lambda ref, subtree: archive.getvalue())
    monkeypatch.setattr(build.shutil, "which", lambda name: "npm")

    seen: list[tuple[tuple[str, ...], bytes]] = []

    def fake_run(command, cwd, check):
        seen.append((tuple(command), (Path(cwd) / ".env").read_bytes()))
        if command[1] == "run":
            (Path(cwd) / "dist").mkdir()
            (Path(cwd) / "dist" / "index.html").write_text("<html></html>")

    monkeypatch.setattr(build.subprocess, "run", fake_run)

    output = tmp_path / "frontend.zip"
    build.build_frontend("HEAD", output, {})

    assert [command[1] for command, _ in seen] == ["install", "run"]
    assert all(content == env.read_bytes() for _, content in seen)
    with zipfile.ZipFile(output) as z:
        assert z.namelist() == ["index.html"]
