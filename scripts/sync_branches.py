#!/usr/bin/env python3
# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""
Carry changes made on `main` into every other branch of the repository.

Usage:
    python scripts/sync_branches.py
    python scripts/sync_branches.py --dry-run
    python scripts/sync_branches.py --exclude "wip-*" --exclude old-app

1. Checks out `core` and merges `main` into it.
2. Checks out every other local branch in turn and merges `core` into it.
3. Returns to the branch it was started on and lists the merges that failed.

A merge that does not go through is aborted on the spot, so that branch is left
exactly as it was: conflicts are never resolved here, and a failure never stops
the remaining branches from being tried (if `core` could not take `main`, the
other branches simply get `core` as it was). Nothing is pushed. It refuses to
start with uncommitted changes to tracked files, since every checkout would
carry them along.

Only local branches are considered. Branches matching DEFAULT_EXCLUDE (Claude
Code's scratch branches) or an --exclude glob are skipped. The exit code is 1
when any merge failed.
"""

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN = "main"
CORE = "core"
DEFAULT_EXCLUDE = ("claude/*",)
MAX_FILES_SHOWN = 5


@dataclass
class Failure:
    target: str
    source: str
    reason: str
    files: list[str] = field(default_factory=list)
    stuck: bool = False  # the merge could not even be aborted


# ─── Git helpers ──────────────────────────────────────────────────────────────

def git(*args: str) -> subprocess.CompletedProcess:
    """Run a git command at the repo root; the caller looks at the return code."""
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace"
    )


def git_out(*args: str) -> str:
    """Run a git command that must succeed and return its stdout."""
    result = git(*args)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.rstrip()


def last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "git gave no reason"


def local_branches() -> list[str]:
    return git_out("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()


def current_position() -> str:
    """The branch HEAD is on, or the commit when HEAD is detached."""
    return git("symbolic-ref", "--short", "-q", "HEAD").stdout.strip() or git_out("rev-parse", "HEAD")


def merge(source: str, target: str) -> Failure | None:
    """Check out `target` and merge `source` into it; None when it went through."""
    checkout = git("checkout", target)
    if checkout.returncode != 0:
        return Failure(target, source, f"checkout failed: {last_line(checkout.stderr)}")

    before = git_out("rev-parse", "HEAD")
    result = git("merge", "--no-edit", source)
    if result.returncode == 0:
        moved = git_out("rev-parse", "HEAD") != before
        print(f"  {target} <- {source}: {'merged' if moved else 'already up to date'}")
        return None

    files = git("diff", "--name-only", "--diff-filter=U").stdout.splitlines()
    failure = Failure(
        target, source, "conflicts" if files else last_line(result.stderr or result.stdout), files
    )
    if git("rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
        failure.stuck = git("merge", "--abort").returncode != 0
    print(f"  {target} <- {source}: FAILED ({failure.reason})")
    return failure


# ─── Selection and reporting ──────────────────────────────────────────────────

def select_branches(exclude: list[str]) -> tuple[list[str], list[str]]:
    """Split the local branches (minus main and core) into (to merge, skipped)."""
    patterns = (*DEFAULT_EXCLUDE, *exclude)
    selected, skipped = [], []
    for name in local_branches():
        if name in (MAIN, CORE):
            continue
        hit = any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
        (skipped if hit else selected).append(name)
    return selected, skipped


def report(failures: list[Failure]) -> None:
    if not failures:
        print("All merges went through.")
        return
    print(f"{len(failures)} merge(s) did not go through:")
    for failure in failures:
        print(f"  {failure.target}  (merging {failure.source}: {failure.reason})")
        for name in failure.files[:MAX_FILES_SHOWN]:
            print(f"      {name}")
        if len(failure.files) > MAX_FILES_SHOWN:
            print(f"      ... and {len(failure.files) - MAX_FILES_SHOWN} more")
    if any(f.target == CORE for f in failures):
        print(f"'{CORE}' did not take '{MAIN}', so the other branches got '{CORE}' as it was.")
    stuck = next((f for f in failures if f.stuck), None)
    if stuck:
        print(f"'{stuck.target}' is still in the middle of a merge that could not be aborted;")
        print("run 'git merge --abort' there, then re-run the script.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Merge {MAIN} into {CORE}, then {CORE} into every other local branch."
    )
    parser.add_argument("--dry-run", action="store_true", help="only list the merges, change nothing")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB",
        help=f"skip branches matching this glob (repeatable; always skipped: {', '.join(DEFAULT_EXCLUDE)})",
    )
    args = parser.parse_args()

    existing = local_branches()
    for required in (MAIN, CORE):
        if required not in existing:
            sys.exit(f"Local branch '{required}' not found.")

    branches, skipped = select_branches(args.exclude)
    steps = [(MAIN, CORE), *((CORE, name) for name in branches)]

    if args.dry_run:
        print("Would merge:")
        for source, target in steps:
            print(f"  {target} <- {source}")
        if skipped:
            print(f"Skipped: {', '.join(skipped)}")
        return 0

    dirty = git_out("status", "--porcelain", "--untracked-files=no")
    if dirty:
        sys.exit(f"Uncommitted changes to tracked files; commit or stash them first:\n{dirty}")

    start = current_position()
    if skipped:
        print(f"Skipping: {', '.join(skipped)}")

    failures: list[Failure] = []
    for source, target in steps:
        failure = merge(source, target)
        if failure:
            failures.append(failure)
            if failure.stuck:
                break

    if not any(f.stuck for f in failures):
        back = git("checkout", start)
        if back.returncode != 0:
            print(f"Could not return to '{start}': {last_line(back.stderr)}")
        else:
            print(f"Back on '{start}'. Nothing was pushed.")
    print()
    report(failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
