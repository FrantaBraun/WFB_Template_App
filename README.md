# With FBraun — App Family Template

A shared foundation for a family of full-stack applications: a **FastAPI** backend, a **Vite + React + TypeScript** frontend, and deployment tooling — pre-wired to a shared, external authorization service so you don't have to build login, registration, or session handling from scratch.

This repository doesn't ship a single app — it hosts a shared core plus one branch per application, so improvements to the shared foundation are made once and carried into every app instead of being duplicated per app.

## Branches

- **`core`** — the shared foundation (the code described in this README). Cross-cutting changes land here first.
- **Application branches** — one per real app, branched **directly from `core`** (the `new-app` skill automates this). They diverge with app-specific code while periodically pulling in updates from `core`.
- **`template_app`** — also branched from `core` and kept in sync with it, but *not* the fork point for the applications above. It's a separate, standalone one-off template for cloning and renaming into a single app outside this family.

Want a one-off template to clone and rename for a single, standalone app rather than joining this family? Start from `template_app` instead.

## What's included

- **Backend-for-frontend authorization** — the backend proxies every auth call to a shared identity service ([auth.withfbraun.com](https://auth.withfbraun.com)); the browser never sees an API key. Email/password login, Google OAuth, and a custom in-app consent flow all work out of the box.
- **A local account model** — your own Postgres-backed `User` table, linked to (but never duplicating) the identity data the auth service owns. Extend it with whatever fields your app actually needs.
- **A working Account page** — two independently-saved cards: one for your app's own local data, one for the shared profile (name, avatar, birth date, ...), plus a config-file-driven system for adding more profile fields without touching code.
- **Multi-language UI** — `react-i18next` already wired up (Czech + English), including switching to a signed-in user's own language preference automatically.
- **Async-only backend** — SQLAlchemy + `asyncpg`, Alembic migrations, time-rotating logging, and a parametrizable email service, all configured from a single `.env` file.
- **Independent versioning** — the backend and frontend version and deploy separately; a `/version` diagnostic page flags it if they drift out of compatibility.
- **Deployment scripts** — package and FTP-upload backend/frontend releases, plus Linux systemd/nginx install/upgrade scripts.

## Tech stack

| | |
|---|---|
| Backend | FastAPI, SQLAlchemy (async) + asyncpg, Alembic, PyJWT, httpx, fastapi-mail |
| Frontend | Vite, React 19, TypeScript, Tailwind CSS v4, react-router-dom, react-i18next |
| Database | PostgreSQL |
| Deployment | Python build/FTP scripts, systemd + nginx (Linux) |

## Project structure

```
backend/    FastAPI app — REST API under /api, Postgres via SQLAlchemy, Alembic migrations
frontend/   Vite + React app — pages, i18n, the auth/account UI
scripts/    Build + FTP packaging, and Linux deployment scripts
```

Backend, frontend, and scripts are versioned and deployed independently — see `CLAUDE.md` for details.

## Prerequisites

- Python 3.14+
- Node.js 20+
- PostgreSQL 14+
- An application registered on [auth.withfbraun.com](https://auth.withfbraun.com) (for your own `AUTH_API_KEY` — see below)

## Getting started

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate on Linux/macOS
pip install -r requirements.txt

cp .env.example .env          # fill in DATABASE_URL, AUTH_API_KEY, mail settings, etc.

python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`, under the `/api` prefix.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env           # defaults already point at the local backend
npm run dev
```

The app is now running at `http://localhost:5173`.

### 3. Getting an `AUTH_API_KEY`

This template doesn't implement its own authentication — it delegates to a shared identity service. Register your own application on [auth.withfbraun.com](https://auth.withfbraun.com) to get an API key, then set `AUTH_API_KEY` in `backend/.env`. Every single call to the auth service requires it — the backend refuses to make the request at all if it's missing, rather than silently sending an empty key (the auth service treats an empty key as "no application context" and skips its consent check entirely).

## Running tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest    # .venv/bin/python on Linux/macOS
```

Every backend route talks to a mocked version of the auth service in tests (via `respx`) — no test ever calls the real `auth.withfbraun.com`.

## Building on this template

- Add your own fields to `backend/app/models/user.py` (see the existing `nickname` field for the pattern) and a matching Alembic migration.
- Extend `backend/app/api/account/` for anything that's purely local to your app; keep it separate from the auth-service-proxying endpoints in `backend/app/api/auth/`.
- Add extra profile fields the shared identity service should store per-application via `frontend/public/config.json` — no backend changes required.
- Swap the branding, favicon, and translations under `frontend/src/i18n/locales/`.

Changes that should benefit every application (auth flow, theming, i18n, deployment tooling, etc.) belong on the `core` branch — merge them out into `template_app` and each application branch rather than duplicating them there.

## Deployment

`scripts/build.py` archives and FTP-uploads tagged (`B-x.y.z` / `F-x.y.z`) or snapshot builds of the backend and frontend independently; `scripts/install.sh` / `upgrade.sh` provision a Linux server (systemd + nginx + Postgres) from those archives. See `scripts/*.example` for configuration templates.

## Documentation

`CLAUDE.md` has the full technical deep-dive — architecture decisions, known auth-service quirks, and non-obvious constraints worth reading before making changes.

## License

Free to use as a starting point for your own applications.

## Author

František Braun — [frantisek.braun95@gmail.com](mailto:frantisek.braun95@gmail.com)
