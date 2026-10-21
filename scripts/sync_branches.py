#!/usr/bin/env python3
# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""
Carry changes made on `main` into every other branch of the repository.

Usage:
    python scripts/sync_branches.py
    python scripts/sync_branches.py --dry-run
    python scripts/sync_branches.py --no-pull --no-push
    python scripts/sync_branches.py --exclude "wip-*" --exclude old-app

1. Checks out `core`, pulls it, merges `main` into it and pushes it.
2. Does the same for every other local branch in turn, merging `core` into it.
3. Returns to the branch it was started on and lists what did not go through.

Pulling is `git pull --ff-only`: a branch that has diverged from its upstream is
reported and left alone instead of being merged blindly. Pushing is a plain
`git push`, done only after the merge went through. A branch without an upstream
(never pushed) is neither pulled nor pushed. `main` itself is never pulled or
pushed - it is where the manual edits are made.

A branch stops at the first step that fails. A merge that does not go through is
aborted on the spot, so the branch is left exactly as it was: conflicts are never
resolved here. A push that fails leaves the merge in place locally. A failure
never stops the remaining branches from being tried (if `core` could not take
`main`, the other branches simply get `core` as it was). It refuses to start with
uncommitted changes to tracked files, since every checkout would carry them along.

Only local branches are considered. Branches matching DEFAULT_EXCLUDE (Claude
Code's scratch branches) or an --exclude glob are skipped. The exit code is 1
when anything failed.
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
    stage: str  # checkout, pull, merge or push
    reason: str
    files: list[str] = field(default_factory=list)
    stuck: bool = False  # the merge could not even be aborted

    def describe(self) -> str:
        if self.stage == "merge":
            return f"merging {self.source} failed: {self.reason}"
        if self.stage == "push":
            return f"merged locally, push failed: {self.reason}"
        return f"{self.stage} failed: {self.reason}"


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


def push_reason(text: str) -> str:
    """git push ends with a generic 'failed to push some refs'; the cause is the '!' line above it."""
    for line in text.splitlines():
        if line.lstrip().startswith("!"):
            return line.strip()
    return last_line(text)


def local_branches() -> list[str]:
    return git_out("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()


def has_upstream(branch: str) -> bool:
    return git("rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{branch}@{{u}}").returncode == 0


def current_position() -> str:
    """The branch HEAD is on, or the commit when HEAD is detached."""
    return git("symbolic-ref", "--short", "-q", "HEAD").stdout.strip() or git_out("rev-parse", "HEAD")


def sync(source: str, target: str, *, pull: bool, push: bool) -> Failure | None:
    """Check out `target`, pull it, merge `source` into it and push it.

    None when every step went through; the first step that fails ends the work
    on this branch.
    """

    def failed(stage: str, reason: str, files: list[str] | None = None) -> Failure:
        print(f"  {target} <- {source}: FAILED at {stage} ({reason})")
        return Failure(target, source, stage, reason, files or [])

    checkout = git("checkout", target)
    if checkout.returncode != 0:
        return failed("checkout", last_line(checkout.stderr))

    tracked = has_upstream(target)
    if pull and tracked:
        result = git("pull", "--no-rebase", "--ff-only")
        if result.returncode != 0:
            return failed("pull", last_line(result.stderr or result.stdout))

    before = git_out("rev-parse", "HEAD")
    result = git("merge", "--no-edit", source)
    if result.returncode != 0:
        files = git("diff", "--name-only", "--diff-filter=U").stdout.splitlines()
        stuck = False
        if git("rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
            stuck = git("merge", "--abort").returncode != 0
        failure = failed(
            "merge", "conflicts" if files else last_line(result.stderr or result.stdout), files
        )
        failure.stuck = stuck
        return failure
    outcome = "merged" if git_out("rev-parse", "HEAD") != before else "already up to date"

    if push and tracked:
        result = git("push")
        if result.returncode != 0:
            return failed("push", push_reason(result.stderr or result.stdout))
        outcome += ", pushed"
    elif push:
        outcome += ", not pushed (no upstream)"
    print(f"  {target} <- {source}: {outcome}")
    return None


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
        print("Everything went through.")
        return
    print(f"{len(failures)} branch(es) did not go through:")
    for failure in failures:
        print(f"  {failure.target}  ({failure.describe()})")
        for name in failure.files[:MAX_FILES_SHOWN]:
            print(f"      {name}")
        if len(failure.files) > MAX_FILES_SHOWN:
            print(f"      ... and {len(failure.files) - MAX_FILES_SHOWN} more")
    if any(f.target == CORE and f.stage != "push" for f in failures):
        print(f"'{CORE}' did not take '{MAIN}', so the other branches got '{CORE}' as it was.")
    stuck = next((f for f in failures if f.stuck), None)
    if stuck:
        print(f"'{stuck.target}' is still in the middle of a merge that could not be aborted;")
        print("run 'git merge --abort' there, then re-run the script.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Pull, merge and push: {MAIN} into {CORE}, then {CORE} into every other local branch."
    )
    parser.add_argument("--dry-run", action="store_true", help="only list the steps, change nothing")
    parser.add_argument("--no-pull", action="store_true", help="do not pull before merging")
    parser.add_argument("--no-push", action="store_true", help="do not push after merging")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB",
        help=f"skip branches matching this glob (repeatable; always skipped: {', '.join(DEFAULT_EXCLUDE)})",
    )
    args = parser.parse_args()
    pull, push = not args.no_pull, not args.no_push

    existing = local_branches()
    for required in (MAIN, CORE):
        if required not in existing:
            sys.exit(f"Local branch '{required}' not found.")

    branches, skipped = select_branches(args.exclude)
    steps = [(MAIN, CORE), *((CORE, name) for name in branches)]

    if args.dry_run:
        verbs = [verb for verb, on in (("pull", pull), ("merge", True), ("push", push)) if on]
        print(f"Would {', '.join(verbs)}:")
        for source, target in steps:
            local_only = (pull or push) and not has_upstream(target)
            print(f"  {target} <- {source}" + ("  (no upstream: not pulled, not pushed)" if local_only else ""))
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
        failure = sync(source, target, pull=pull, push=push)
        if failure:
            failures.append(failure)
            if failure.stuck:
                break

    if not any(f.stuck for f in failures):
        back = git("checkout", start)
        if back.returncode != 0:
            print(f"Could not return to '{start}': {last_line(back.stderr)}")
        else:
            print(f"Back on '{start}'.")
    print()
    report(failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
