#!/usr/bin/env python3
# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""
Build and upload script for backend, frontend and deployment scripts.

Usage:
    python scripts/build.py --mode STABLE --target backend [--tag B-1.2.3]
    python scripts/build.py --mode STABLE --target frontend [--tag F-1.2.3]
    python scripts/build.py --mode STABLE --target scripts
    python scripts/build.py --mode STABLE --target all
    python scripts/build.py --mode SNAPSHOT --target all
    python scripts/build.py --mode SNAPSHOT --target backend --no-upload

Tags must follow the convention:  B-x.y.z  (backend)  /  F-x.y.z  (frontend)
The 'scripts' target has no tag — it always bundles the current filesystem state.
Configuration is read from scripts/build.config.toml (see build.config.toml.example).
The zips are uploaded over FTP/FTPS ([ftp]), or over SFTP with the OpenSSH `sftp`
command when the config has an [sftp] section (a key login, no password in the file).

STABLE backend/frontend builds also seal that component's release_news.json:
accumulated `unreleased` entries move into a new release dated today, tagged
with the resolved version, and `unreleased` is cleared. This edits the local
working-tree file only - commit it and create the release tag from that
commit *before* running this script, or the archived build won't include it.
"""

import argparse
import ftplib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPTS_DIR / "build.config.toml"


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load scripts/build.config.toml, exiting with guidance if it's missing."""
    if not CONFIG_FILE.exists():
        sys.exit(
            f"Config file not found: {CONFIG_FILE}\n"
            "Copy scripts/build.config.toml.example and fill in your values."
        )
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


# ─── Git helpers ──────────────────────────────────────────────────────────────

def git(*args: str) -> str:
    """Run a git command at the repo root and return its stdout, stripped."""
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def latest_tag(prefix: str) -> str:
    """Return the highest semver tag matching  PREFIX-x.y.z."""
    tags = git("tag", "--list", f"{prefix}-*").splitlines()
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)\.(\d+)\.(\d+)$")
    versioned = []
    for tag in tags:
        m = pattern.match(tag)
        if m:
            versioned.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), tag))
    if not versioned:
        sys.exit(f"No tags found matching {prefix}-x.y.z")
    return sorted(versioned)[-1][3]


def short_hash() -> str:
    """Return the current commit's short SHA, used in SNAPSHOT filenames."""
    return git("rev-parse", "--short", "HEAD")


def git_archive_bytes(ref: str, subtree: str) -> bytes:
    """Return raw zip bytes of  ref:subtree  (files at archive root, no prefix)."""
    proc = subprocess.run(
        ["git", "archive", "--format=zip", f"{ref}:{subtree}"],
        cwd=ROOT, capture_output=True,
    )
    if proc.returncode != 0:
        sys.exit(f"git archive {ref}:{subtree} failed:\n{proc.stderr.decode().strip()}")
    return proc.stdout


# ─── Release news ─────────────────────────────────────────────────────────────

def seal_release_news(path: Path, version: str) -> None:
    """Move a release_news.json's accumulated `unreleased` entries into a new
    dated release entry tagged with `version`, then clear `unreleased` - a
    no-op if there's nothing pending (running this twice for the same
    release is therefore safe). Operates on the local working-tree file, not
    a git ref: for the sealed entry to actually ship in the archived build,
    commit this change and create the release tag from that commit before
    running the archive/upload step below."""
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    unreleased = data.get("unreleased", [])
    if not unreleased:
        return

    sealed = {
        "version": version,
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "changes": unreleased,
    }
    data["releases"] = [sealed, *data.get("releases", [])]
    data["unreleased"] = []
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    count = len(unreleased)
    print(f"  Sealed {count} unreleased entr{'y' if count == 1 else 'ies'} into {path.name} as {version}")


# ─── Build: backend ───────────────────────────────────────────────────────────

def build_backend(ref: str, output_path: Path) -> None:
    """Archive backend/ at the given git ref straight into a zip - no build
    step, since the backend ships as source (installed via requirements.txt
    on the target server)."""
    print(f"  Archiving backend/ from {ref} …")
    output_path.write_bytes(git_archive_bytes(ref, "backend"))
    size_kb = output_path.stat().st_size // 1024
    print(f"  Created {output_path.name}  ({size_kb} KB)")


# ─── Build: scripts ───────────────────────────────────────────────────────────

_DEPLOY_CONFIG         = SCRIPTS_DIR / "deploy.config.sh"
_DEPLOY_CONFIG_EXAMPLE = SCRIPTS_DIR / "deploy.config.sh.example"
_SCRIPT_FILES          = ["install.sh", "upgrade.sh", "./../backend/.env"]


def build_scripts(output_path: Path) -> None:
    """Bundle the deployment scripts (install.sh, upgrade.sh), the local
    deploy config, and the current backend/.env - the target server needs
    its own copy of .env to provision the Postgres role/DB during install.
    This package always reflects the current local filesystem, never a git
    ref: unlike backend/frontend it isn't meant to be redistributed as part
    of the template, only pushed to this project's own live server."""
    if _DEPLOY_CONFIG.exists():
        config_src = _DEPLOY_CONFIG
        config_label = "deploy.config.sh"
    else:
        config_src = _DEPLOY_CONFIG_EXAMPLE
        config_label = "deploy.config.sh.example → deploy.config.sh"
        print("  WARNING: deploy.config.sh not found — bundling example as placeholder.")

    print("  Bundling deployment scripts …")
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in _SCRIPT_FILES:
            src = (SCRIPTS_DIR / name).resolve()
            arcname = src.name   # store as bare filename, no path traversal
            if not src.exists():
                sys.exit(f"File not found: {src}")
            z.write(src, arcname)
            print(f"    + {arcname}")
        z.write(config_src, "deploy.config.sh")
        print(f"    + deploy.config.sh  (from {config_label})")

    size_kb = output_path.stat().st_size // 1024
    print(f"  Created {output_path.name}  ({size_kb} KB)")


# ─── Build: frontend ──────────────────────────────────────────────────────────

_FRONTEND_ENV = ROOT / "frontend" / ".env"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def copy_frontend_env(dest: Path, source: Path | None = None) -> None:
    """Put the development directory's frontend/.env next to the extracted
    sources, byte for byte as it is stored - the build writes no .env of its own.

    Like backend/.env in build_scripts() this is the current local file, never
    one from the git ref (it is untracked). So the build takes whatever the
    development directory has: VITE_API_URL, VITE_APP_URL, VITE_AUTH_URL ...
    Vite bakes these into the static bundle, hence the warning when a URL still
    points at this machine (a development value) - only a warning, since a
    local build for a local check is legitimate. Values are never printed."""
    source = source or _FRONTEND_ENV
    if not source.is_file():
        sys.exit(
            f"File not found: {source}\n"
            "The frontend build takes its settings from the development directory's frontend/.env - "
            "copy frontend/.env.example to frontend/.env and fill in the values for the build."
        )
    shutil.copyfile(source, dest)

    keys, local = [], []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        keys.append(key)
        if key.endswith("_URL") and urlsplit(value.strip().strip("\"'")).hostname in _LOCAL_HOSTS:
            local.append(key)
    print(f"  Using {source} as it is stored ({', '.join(keys) or 'no variables'}).")
    if local:
        print(f"  WARNING: {', '.join(local)} point at a local address - fine for a local check, "
              "wrong for a build that is going to a server.")


def build_frontend(ref: str, output_path: Path, cfg: dict) -> None:
    """Extract frontend/ at the given git ref into a temp dir, copy the
    development directory's frontend/.env into it (see copy_frontend_env), run
    npm install + build there, and zip the resulting dist/ - the frontend ships
    as a static build, not source."""
    npm = shutil.which("npm") or cfg.get("build", {}).get("npm_command", "npm")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src = tmp / "src"
        src.mkdir()

        print(f"  Extracting frontend/ from {ref} …")
        zip_data = git_archive_bytes(ref, "frontend")
        archive = tmp / "src.zip"
        archive.write_bytes(zip_data)
        with zipfile.ZipFile(archive) as z:
            z.extractall(src)

        copy_frontend_env(src / ".env")

        print("  npm install …")
        subprocess.run([npm, "install", "--prefer-offline"], cwd=src, check=True)

        print("  npm run build …")
        subprocess.run([npm, "run", "build"], cwd=src, check=True)

        dist = src / "dist"
        if not dist.exists():
            sys.exit("Frontend build did not produce a dist/ directory.")

        print(f"  Zipping dist/ → {output_path.name} …")
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
            for file in sorted(dist.rglob("*")):
                if file.is_file():
                    z.write(file, file.relative_to(dist))

    size_kb = output_path.stat().st_size // 1024
    print(f"  Created {output_path.name}  ({size_kb} KB)")


# ─── FTP upload ───────────────────────────────────────────────────────────────

def _ftp_mkdirs(ftp: ftplib.FTP, remote_dir: str) -> None:
    """Create remote_dir on the FTP server one path segment at a time,
    since most FTP servers reject mkd on a nested path that doesn't exist yet."""
    parts = remote_dir.strip("/").split("/")
    current = ""
    for part in parts:
        current += f"/{part}"
        try:
            ftp.cwd(current)
        except ftplib.error_perm:
            ftp.mkd(current)
            ftp.cwd(current)


def upload_ftp(local_path: Path, remote_dir: str, cfg: dict) -> None:
    """Upload a built zip to remote_dir over FTP or FTPS, per cfg["ftp"]
    (host/port/credentials/tls/passive - see build.config.toml.example)."""
    fc = cfg["ftp"]
    host, port = fc["host"], fc.get("port", 21)
    use_tls = fc.get("tls", False)

    print(f"  Uploading → ftp{'s' if use_tls else ''}://{host}{remote_dir}/{local_path.name} …")

    FTPClass = ftplib.FTP_TLS if use_tls else ftplib.FTP
    with FTPClass() as ftp:
        ftp.connect(host, port, timeout=30)
        ftp.login(fc["user"], fc["password"])
        if use_tls:
            ftp.prot_p()
        ftp.set_pasv(fc.get("passive", True))

        _ftp_mkdirs(ftp, remote_dir)

        with open(local_path, "rb") as f:
            ftp.storbinary(f"STOR {local_path.name}", f)

    print(f"  Upload complete.")


# ─── SFTP upload ──────────────────────────────────────────────────────────────

def _sftp_quote(value: str) -> str:
    """A value as one argument of an sftp batch command: double-quoted, with
    quotes and backslashes escaped."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _sftp_batch(remote_dir: str, file_name: str) -> str:
    """The sftp batch that makes remote_dir one path segment at a time (a
    leading '-' lets a directory that already exists pass) and puts file_name,
    taken from the working directory, into it."""
    parts = [part for part in remote_dir.split("/") if part]
    prefix = "/" if remote_dir.startswith("/") else ""
    lines = []
    current = prefix
    for part in parts:
        current += part
        lines.append(f"-mkdir {_sftp_quote(current)}")
        current += "/"
    remote_file = f"{prefix}{'/'.join(parts)}/{file_name}" if parts else f"{prefix}{file_name}"
    lines.append(f"put {_sftp_quote(file_name)} {_sftp_quote(remote_file)}")
    return "\n".join(lines) + "\n"


def _sftp_command(sc: dict) -> list[str]:
    """The OpenSSH `sftp` command line for cfg["sftp"]: batch mode (it can not
    ask for a password, so the login is a key - `key_file`, else the ssh agent
    or the default keys), the commands are read from stdin."""
    exe = shutil.which("sftp")
    if not exe:
        sys.exit("The 'sftp' command (the OpenSSH client) is not on PATH, but the config has an [sftp] section.")
    command = [exe, "-b", "-", "-P", str(sc.get("port", 22)),
               "-o", "BatchMode=yes", "-o", "ConnectTimeout=30", "-o", "ServerAliveInterval=30"]
    if sc.get("key_file"):
        command += ["-i", Path(sc["key_file"]).expanduser().as_posix(), "-o", "IdentitiesOnly=yes"]
    command.append(f"{sc['user']}@{sc['host']}")
    return command


def upload_sftp(local_path: Path, remote_dir: str, cfg: dict) -> None:
    """Upload a built zip to remote_dir over SFTP with the OpenSSH `sftp`
    command, per cfg["sftp"] (host/port/user/key_file - see
    build.config.toml.example). No password is kept in the config: the login
    is a key."""
    sc = cfg["sftp"]
    print(f"  Uploading → sftp://{sc['host']}{remote_dir}/{local_path.name} …")

    # bytes, not text: in text mode Windows would send CRLF, which sftp reads as part of the path
    result = subprocess.run(
        _sftp_command(sc),
        input=_sftp_batch(remote_dir, local_path.name).encode("utf-8"),
        cwd=local_path.parent,
    )
    if result.returncode != 0:
        sys.exit(
            f"sftp failed (exit code {result.returncode}).\n"
            f"Check, by hand, that `ssh -p {sc.get('port', 22)} {sc['user']}@{sc['host']}` logs in without asking for "
            "a password (run it once: it also records the server's host key, which a batch can not confirm), "
            f"and that {remote_dir} is writable for that user."
        )
    print("  Upload complete.")


def remote_dir_for(cfg: dict, target: str) -> str:
    """Where a target's zip goes: [sftp.paths] when uploading over SFTP and it
    has the target (the SSH account can see the server's disk differently from
    the FTP account, e.g. outside the FTP root), else [ftp.paths]."""
    sections = ["sftp", "ftp"] if "sftp" in cfg else ["ftp"]
    for section in sections:
        path = cfg.get(section, {}).get("paths", {}).get(target)
        if path:
            return path
    sys.exit(f"No remote directory for '{target}' in {CONFIG_FILE.name}: set it under [{sections[0]}.paths].")


def upload(local_path: Path, remote_dir: str, cfg: dict) -> None:
    """Upload over SFTP when the config has an [sftp] section, otherwise over FTP/FTPS."""
    if "sftp" in cfg:
        upload_sftp(local_path, remote_dir, cfg)
    else:
        upload_ftp(local_path, remote_dir, cfg)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def resolve_ref(mode: str, target: str, tag: str | None) -> str:
    """Resolve which git ref to build from: HEAD for SNAPSHOT/scripts, an
    explicit --tag if given, otherwise the latest B-/F- tag for the target."""
    if mode == "SNAPSHOT" or target == "scripts":
        return "HEAD"
    if tag:
        return tag
    prefix = "B" if target == "backend" else "F"
    ref = latest_tag(prefix)
    print(f"  Latest tag: {ref}")
    return ref


def zip_name(mode: str, target: str, ref: str) -> str:
    """Build the output zip's filename: tag-based in STABLE mode, date +
    short commit hash in SNAPSHOT mode (or for the untagged scripts target)."""
    date = datetime.now().strftime("%Y%m%d")
    if target == "scripts":
        if mode == "STABLE":
            return f"auth-scripts-{date}.zip"
        return f"auth-scripts-snapshot-{date}-{short_hash()}.zip"
    if mode == "STABLE":
        return f"{target}-{ref}.zip"
    return f"{target}-snapshot-{date}-{short_hash()}.zip"


def main() -> None:
    """CLI entry point: parse args, resolve the ref/output name per target,
    seal pending release news under the resolved version (STABLE
    backend/frontend only), build each requested target, and upload it
    unless --no-upload is set."""
    parser = argparse.ArgumentParser(
        description="Build and upload backend/frontend packages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mode", choices=["STABLE", "SNAPSHOT"], required=True,
                        help="STABLE builds from a git tag; SNAPSHOT from HEAD.")
    parser.add_argument("--target", choices=["backend", "frontend", "scripts", "all"], required=True)
    parser.add_argument("--tag",
                        help="Specific tag (e.g. B-1.2.3 or F-1.2.3). "
                             "Only for STABLE backend/frontend; incompatible with scripts and all.")
    parser.add_argument("--no-upload", action="store_true",
                        help="Build locally without uploading.")
    parser.add_argument("--output-dir", type=Path, metavar="DIR",
                        help="Override output directory from config.")
    args = parser.parse_args()

    if args.tag and args.target in ("all", "scripts"):
        parser.error("--tag cannot be combined with --target all or scripts "
                     "(tags are per-component; run backend and frontend separately).")
    if args.tag and args.mode == "SNAPSHOT":
        parser.error("--tag is only valid in STABLE mode.")

    cfg = load_config()
    out_dir_cfg = cfg.get("build", {}).get("output_dir", "dist")
    output_dir = args.output_dir or Path(out_dir_cfg)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = ["backend", "frontend", "scripts"] if args.target == "all" else [args.target]

    for target in targets:
        print(f"\n{'='*55}")
        print(f"  {target.upper()}  |  {args.mode}")
        print(f"{'='*55}")

        ref = resolve_ref(args.mode, target, args.tag)

        # STABLE backend/frontend builds have a real version number (ref is a
        # "B-x.y.z"/"F-x.y.z" tag) - seal that component's accumulated
        # unreleased entries under it before archiving. SNAPSHOT/scripts have
        # no such version, so there's nothing meaningful to seal.
        if args.mode == "STABLE" and target in ("backend", "frontend"):
            version = ref.split("-", 1)[1] if "-" in ref else ref
            news_dir = ROOT / target if target == "backend" else ROOT / "frontend" / "public"
            seal_release_news(news_dir / "release_news.json", version)

        zname = zip_name(args.mode, target, ref)
        zip_path = output_dir / zname

        if target == "backend":
            build_backend(ref, zip_path)
        elif target == "frontend":
            build_frontend(ref, zip_path, cfg)
        else:  # scripts
            build_scripts(zip_path)

        if not args.no_upload:
            upload(zip_path, remote_dir_for(cfg, target), cfg)
        else:
            print(f"  Upload skipped (--no-upload).")

    print(f"\nDone. Output: {output_dir}")


if __name__ == "__main__":
    main()
