---
name: new-app
description: Fork a new application branch directly from `core` in this repo's multi-app template structure, then customize its CLAUDE.md/README, branding, starting version, and changelog from a name/purpose/description gathered from the user. Use this whenever the user wants to start, create, spin up, bootstrap, or fork a brand-new application in this family of apps - e.g. "start a new app", "create a new application branch", "let's build a new app off core", "add an app to the family", or invoking /new-app directly. This is specifically for a new member of the app family forked from `core` - NOT for editing an existing application branch, and NOT for `template_app` (that's a separate, standalone one-off clone-and-rename template, unrelated to this family workflow).
---

# New application

Forks a new application branch directly from `core` in this multi-app template repo, then customizes its identity from a name, basic purpose, and detailed description gathered from the user. This creates a git branch and commits scaffolding, so only run it when the user has clearly asked to start a new application - never as a side effect of something else.

## Why `core`, not `template_app`

This repo also has a `template_app` branch, but that's a *different* thing: a standalone, generically-branded template for someone who wants to clone-and-rename this repo for a one-off app outside the family. Real family applications fork straight from `core` instead, so they inherit only the shared foundation with no template-specific branding to undo. Don't confuse the two, and don't fork from `template_app` for this.

## 1. Gather the three inputs

If the user already gave some of these when invoking the skill, don't re-ask for them - just fill in whatever's missing:

- **Application name** - short, human name (e.g. "Rezervace Salonu").
- **Basic purpose** - one or two sentences: what the app is for.
- **Detailed description** - as much as the user wants to share: features, key entities/flows, target users. This is what step 5 writes into the app's own docs and step 7 draws suggestions from, so it's worth encouraging something more specific than a one-liner.

Ask conversationally, in plain language - these are open-ended answers, not a closed decision, so don't reach for a multiple-choice question tool here.

## 2. Derive a branch name

Slugify the application name: lowercase, transliterate/strip diacritics, replace anything outside `[a-z0-9-]` with `-`, collapse repeats, trim leading/trailing `-`. E.g. "Rezervace Salónu" -> `rezervace-salonu`.

Check it doesn't collide with an existing branch:

```bash
git branch -a
```

If the slug already exists (local or `remotes/origin/...`), tell the user and ask for a different name rather than silently picking a variant - untangling a colliding branch name later is much more annoying than asking once now.

## 3. Safety checks before branching

```bash
git status
```

If the working tree isn't clean, stop and ask the user how to proceed (commit, stash, or something else) instead of silently carrying uncommitted changes onto the new branch - that state might be unrelated in-progress work that has no business in a fresh app branch.

Then make sure a local `core` branch exists:

```bash
git branch -a
```

- Only listed as `remotes/origin/core`? Create a local tracking branch: `git branch core origin/core`.
- Not listed at all? Stop and tell the user - don't guess at a substitute branch to fork from.

## 4. Create the branch

```bash
git checkout -b <slug> core
```

This creates and switches to it in one step, forked from `core`'s current tip.

## 5. Scaffold the application's identity

Everything below is an edit to an existing file - no new files. The goal is to make this branch read like the named application instead of the generic template. See the note at the end of this section for why that stops short of actual feature code.

- **`CLAUDE.md`** - insert a new section right after the opening two lines (the title and the "guidance for Claude Code" sentence), before the existing `## Repository purpose`:

  ```markdown
  ## Application: <Name>

  **Purpose:** <basic purpose>

  <detailed description>

  Forked from `core` by the `new-app` skill on <date - ask the user or leave as a placeholder for them to fill in; there's no way to read today's date from inside these instructions>.
  ```

  Leave the existing `## Repository purpose` / `### Branch structure` content below it untouched - it documents the repo-wide branch model (core / template_app / application branches) and still applies here. A future session working on this app still needs that context, e.g. to know that this branch's own divergence from `core` is intentional and not something to "fix".

- **`README.md`** - replace the H1 title and the first paragraph under it with the application's name and basic purpose. Add the detailed description as its own new section right after that (before the existing `## Branches` section). Leave the rest - tech stack table, prerequisites, getting started, branches, deployment - alone; it's all still accurate.

- **Branding** - update these to the application's name:
  - `frontend/index.html`'s `<title>`
  - the `nav.brand` key in both `frontend/src/i18n/locales/cs.json` and `en.json`
  - the `FastAPI(title=...)` argument in `backend/app/main.py`

- **Database name** - `backend/.env.example`'s `DATABASE_URL` and `backend/app/config.py`'s matching default both currently point at `template_db`; rename both to `<slug>_db`.

- **Versions** - read `backend/version.json` and `frontend/public/version.json` first rather than assuming their shape, then reset each to a fresh starting version (e.g. `"0.1.0"`), keeping whatever other fields are already there.

- **Release news** - reset both `unreleased` and `releases` to `[]` in `backend/release_news.json` and `frontend/public/release_news.json`. This app's changelog starts empty rather than inheriting the shared template's own release history as if it were this app's own.

**Don't scaffold domain code here.** However detailed the description is, resist turning it into database models, migrations, endpoints, pages, or business logic at this stage - that's real feature work that deserves its own review and iteration, not something to generate sight-unseen while branching. Step 7 is where the description's content actually gets put to use: as suggestions, not as code that's already been written.

## 6. Commit

One commit for everything in step 5:

```
Initialize <Name> from core
```

## 7. Register the branch on `main`

Other tooling (the `new-module` skill) rolls new modules out to every branch downstream of `core` by reading a list in `main`'s own `CLAUDE.md`, not by guessing from `git branch -a` - so a freshly forked application needs to be added to it there, not just exist as a branch:

```bash
git checkout main
```

In `CLAUDE.md`, find the `**Branches synced from \`core\`:**` line (just below `### Branch structure`) and append `<slug>` to that list.

```bash
git add CLAUDE.md
git commit -m "Register <slug> as a branch synced from core"
git checkout <slug>
```

That last checkout returns you to the new application branch - the rest of this session's work (and the report below) continues there, not on `main`.

## 8. Report and suggest next steps

Tell the user which branch was created, that it's now registered in `main`'s `CLAUDE.md` as a branch synced from `core`, and what got customized. Then, reading back over the detailed description they gave you, suggest a short, concrete list of what they'd likely want to build first - as recommendations in chat, not code you've already written. Ground these in what already exists to extend, so the suggestions are actionable rather than generic:

- Candidate fields for the local `User` model (`backend/app/models/user.py`) if the description implies account data beyond what the auth service's own profile already covers.
- Candidate `frontend/public/config.json` attributes for anything per-user that belongs on the auth service instead.
- Whether the description's features look like a natural fit for this repo's pluggable feature-module system (`app/modules/<key>/` + `src/modules/<key>/` - see `CLAUDE.md`'s "Feature modules" section) rather than being built directly into the core pages.
- Candidate new pages/routes.

Make clear these are a starting point for the next conversation, not a plan you've already executed.
