---
name: new-module
description: Design, implement, test, and roll out a new pluggable feature module (backend `app/modules/<key>/` + frontend `src/modules/<key>/`) from a name/purpose/functionality description - builds and verifies it on `main`, merges it into `core`, then merges `core` into every branch CLAUDE.md lists as synced from it (currently `template_app` and `slavickovy-knihohratky`, growing as more applications exist). Use whenever the user wants to add, build, create, or ship a new module or shared feature for the core - e.g. "add a reservations module", "build a new module for X and roll it out", "create a module across all the apps", or /new-module directly. Unlike /new-app (identity/branding only), this one writes real backend and frontend code and merges it across multiple branches, so only run it when the user has clearly asked for a new module to be built - never as a side effect of something else.
---

# New module

Builds a new pluggable feature module from a name, purpose, and functionality description, verifies it actually works, then carries it through `main` -> `core` -> every application branch. This writes real code and merges across several branches - a much bigger action than `/new-app`'s scaffolding-only pass - so treat each stage's verification as load-bearing, not a formality to rush past.

## 1. Gather the three inputs

If the user already gave some of these, don't re-ask - just fill in whatever's missing:

- **Module name** - short, human name (e.g. "Rezervace prohlídek").
- **Purpose** - one or two sentences: what problem this module solves.
- **Functionality description** - concrete enough to design from: what data it manages, what a user (and, if relevant, an admin) can do with it, whether it needs its own page(s) or just an API other modules could call. A one-liner like "add a newsletter module" doesn't say whether there's an admin view, what a subscriber record holds, or whether it sends real email - if the description leaves a decision like that genuinely open, ask ONE focused follow-up question before you start designing; don't guess at something that expensive to redo, but don't interrogate every minor detail either (wording, exact colors, etc. are yours to decide).

Ask conversationally - these are open-ended answers, not a closed decision, so don't reach for a multiple-choice question tool here.

## 2. Derive a module key and check for collisions

Unlike an application branch's slug (hyphens are fine there), a module's key becomes a **Python package directory name** (`app.modules.<key>`) on the backend, so it must be a valid Python identifier: lowercase, transliterate/strip diacritics, replace anything outside `[a-z0-9_]` with `_`, collapse repeats, and make sure it doesn't start with a digit. E.g. "Rezervace prohlídek" -> `rezervace_prohlidek`. Use the exact same string as the frontend folder name under `src/modules/` - the manifest/`ModuleDefinition` contract requires the key to match the folder on both sides.

```bash
git status
ls backend/app/modules/ frontend/src/modules/
```

If a folder with that key already exists on either side, tell the user and ask for a different name or confirm you're meant to be extending the existing module instead of creating a new one - don't silently overwrite. If the working tree isn't clean, stop and ask how to proceed rather than building on top of unrelated uncommitted changes.

## 3. Design before writing code

The module contract can evolve, so re-read it fresh rather than trusting memory from a previous run:

- `CLAUDE.md`'s "Feature modules (pluggable, per-application)" section
- `backend/app/modules/base.py` and `registry.py`
- `frontend/src/modules/types.ts` and `registry.ts`

Then look at one existing core resource as a convention reference rather than inventing house style from scratch - `backend/app/api/account/` (router + schemas + how it depends on `get_current_user`/`get_db`) for backend patterns, and `frontend/src/pages/Account.tsx` or `HomePage.tsx` for frontend patterns (`apiFetch`, `useTranslation`, dark-mode classes, auth-gating a page by redirecting in a `useEffect` when there's no user). A module extends this vocabulary; it doesn't invent a new one.

From the purpose and description, sketch - in your head or a short scratch note, not into the codebase yet - what's actually needed: a `models.py` only if something must persist; which endpoints in `router.py` (+ `schemas.py`) the frontend actually calls, not a speculative full CRUD set the description didn't ask for; which frontend route(s)/page(s) and whether a nav entry makes sense; which `cs`/`en` translation strings both sides need. Keep it to what was described - this is going into the shared core every application inherits, so restraint here matters more than in a one-off app branch.

## 4. Implement

**Backend** (`backend/app/modules/<key>/`):
- `__init__.py` exposing `manifest = ModuleManifest(key="<key>", router=..., ...)`
- `router.py` (+ `schemas.py` for request/response models) implementing the designed endpoints
- `models.py` only if something persists. If you add one, generate the migration for real rather than hand-writing it:
  ```bash
  cd backend
  .venv/Scripts/python.exe -m alembic revision --autogenerate -m "add <key> tables"
  ```
  Read the generated migration before trusting it - autogenerate misses some changes and over-eagerly includes others.

**Frontend** (`frontend/src/modules/<key>/`):
- `index.tsx` default-exporting a `ModuleDefinition` (`routes`, optional `nav`, optional `locales`)
- Any page components the routes need, co-located in the same folder
- Both `cs` and `en` entries in `locales` for every string the UI shows - this repo has no untranslated hardcoded copy anywhere, and a module is no exception

Give every new file the standard project header (see `CLAUDE.md`'s "File headers" section for the exact text).

## 5. Verify it actually works

Don't treat this as a formality - a module going into the shared core that turns out broken affects every application that later enables it.

1. `cd backend && .venv/Scripts/python.exe -m pytest` - the **whole** suite, not just a new test file, so a break elsewhere is caught now. Write `backend/tests/test_modules_<key>_router.py` (or split further if the router is large) covering the new endpoints first, following `tests/conftest.py`'s documented fixtures and patterns (respx for any outbound calls, the `ASGITransport` pattern for a route needing both a real JWT dependency and the DB in one test).
2. `cd frontend && npm run build` - `tsc` plus the bundle.
3. Exercise it for real in a browser: temporarily add `<key>` to `backend/.env`'s `ENABLED_MODULES` and to `frontend/public/modules.json`'s `enabled` array, start both dev servers, and click through the golden path plus any obvious edge case, in both light and dark mode if the module has UI. Afterwards, undo both: `backend/.env` is gitignored (never committed), so just edit the key back out by hand; `frontend/public/modules.json` **is** tracked, so `git checkout -- frontend/public/modules.json` cleanly reverts it. `core` itself should not ship with the new module switched on by default - enabling it is each downstream branch's own call, in step 9.

Fix anything that breaks before moving on - don't carry a known-broken module into the merges below.

## 6. Commit on `main`

Prepend a bullet to `backend/release_news.json`'s `unreleased` array and/or `frontend/public/release_news.json`'s, whichever side(s) actually changed, in the same commit.

## 7. Merge `main` into `core`

```bash
git status
git branch -a
```

Create a local tracking branch (`git branch core origin/core`) if `core` only exists remotely; stop and tell the user if it doesn't exist at all.

```bash
git checkout core
git merge main -m "Merge main into core (add <key> module)"
```

Conflicts here are real signal, not noise - `core` may have moved on its own since `main` last merged into it. For each one, read both sides and understand *why* they differ before resolving; keep both sides' intent (e.g. two independently-prepended `release_news.json` entries both stay, newest first) rather than mechanically picking one - the same approach as resolving any other feature merge in this repo. After resolving, rerun step 5's verification (pytest + build) on `core` itself before committing the merge - a clean auto-merge can still combine into something that doesn't build.

## 8. Merge `core` into every branch synced from it

Read `CLAUDE.md`'s `**Branches synced from \`core\`:**` line (just below `### Branch structure`) for the current target list - don't hardcode the branch names from this file or a previous run, since the list grows as applications are added.

For each branch in that list:

```bash
git branch -a   # create a local tracking branch from origin if it's remote-only
git checkout <branch>
git merge core -m "Merge core into <branch> (add <key> module)"
```

Resolve conflicts the same careful way as step 7. Then verify again on this branch specifically: `pytest` and `npm run build`. A test failure here might not be your merge's fault - this branch can have its own pre-existing issues. Before concluding you broke something, check whether the same test already failed *before* your merge (e.g. temporarily check out the branch's pre-merge commit, rerun just that test, then return to the merge commit) rather than assuming or silently ignoring it either way. Commit the merge once verification is accounted for, then move to the next branch in the list.

When every branch is done, `git checkout main`.

## 9. Report

Summarize: the module's key and what it does; which branches it landed on cleanly versus needed conflict resolution (and what those conflicts actually were); the verification result on each branch, including any pre-existing failure you found and attributed rather than caused. Remind the user the module ships **disabled by default everywhere** - flip its key into `ENABLED_MODULES` / `public/modules.json`'s `enabled` array on whichever branch(es) should actually use it, as a separate, deliberate step.
