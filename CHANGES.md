# Change Log

Tracks files modified or created during development sessions.

---

## Session: Docker One-Command Deploy (2026-05-07)

### GitHub repository configuration (done via GitHub web UI)

| Setting | Value |
|---------|-------|
| Actions permissions | All actions allowed (Settings → Actions → General) |
| Secret `SECRET_ENV` | Added under Settings → Secrets and variables → Actions. Contains the prod `.env` file content: `PUBLIC_API_BASE`, `MONGO_USERNAME`, `MONGO_PASSWORD`, `COMPOSE_PROFILES`. |
| Self-hosted runner `cc-vis` | Registered for this repo (Settings → Actions → Runners). Installed on the server as a systemd service (`sudo ./svc.sh install && sudo ./svc.sh start`) so it survives reboots. Architecture: x64 Linux. |
| Collaborator access | Team members added as collaborators with write access (Settings → Collaborators) so they can push to `develop` directly. |

### Infrastructure (file changes)

| File | Change |
|------|--------|
| `docker-compose.yml` | **New** — Root-level compose file consolidating all four services (mongo, redis, provibackend, provifrontend) plus nginx behind a `prod` profile. Uses `build:` so `--build` compiles images from source. Named volumes replace hard-coded host paths. `depends_on` with `condition: service_healthy` so backend waits for mongo and redis to be ready. `restart: unless-stopped` on every service. |
| `.env.example` | **New** — Documents env vars needed: `PUBLIC_API_BASE` (Next.js build-time API URL), `MONGO_USERNAME`, `MONGO_PASSWORD`, `COMPOSE_PROFILES` (`prod` on server activates nginx). |
| `Makefile` | **New** — `make up` / `make down` / `make logs` shortcuts. |
| `.github/workflows/deploy.yml` | **New** — Single root-level workflow; triggers on push to `develop`; self-hosted runner writes `.env` from `SECRET_ENV` GitHub secret then runs `docker compose up -d --build`. Uses `actions/checkout@v4`. |
| `ProViFrontend/Dockerfile` | Added `ARG NEXT_PUBLIC_API_BASE` and `ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE` before `npm run build` so the API URL is baked into the Next.js bundle per environment. |
| `ProViFrontend/.dockerignore` | **New** — Excludes `provi-frontend/node_modules` and `provi-frontend/.next` from the Docker build context. Without this, local macOS node_modules (with macOS-native `sharp` binaries) overwrite the Linux ones installed inside the container, crashing the build. |
| `.gitignore` | Added `.env` so machine-specific env files are never committed. |
| `ProViFrontend/docker-compose.yml` | **Deleted** — replaced by root compose file. |
| `provibackend/docker-compose.yml` | **Deleted** — replaced by root compose file. |
| `provibackend/docker-compose.override.yml` | **Deleted** — named volumes in root compose file replace this. |
| `provibackend/docker-compose.local.yml` | **Deleted** — local/prod distinction now handled by `.env` + `COMPOSE_PROFILES`. |
| `provibackend/.github/workflows/deploy.yml` | **Deleted** — dead code (GitHub only reads `.github/workflows/` at repo root). |
| `ProViFrontend/.github/workflows/deploy.yml` | **Deleted** — same reason. |

### Current server config (temporary, until TLS certs are available)

`SECRET_ENV` on the server uses direct IP access with no nginx:
```
PUBLIC_API_BASE=http://134.155.106.59:1234/api
MONGO_USERNAME=root
MONGO_PASSWORD=example
COMPOSE_PROFILES=
```
Frontend accessible at `http://134.155.106.59:22222`. Once TLS certs are in place, switch to `COMPOSE_PROFILES=prod` and `PUBLIC_API_BASE=https://cc-vis.rz.uni-mannheim.de/api`.

### How to deploy

**Local dev** — copy `.env.example` to `.env` (defaults work as-is), then:
```bash
docker compose up -d --build   # or: make up
```

**Server** — push to `develop`; the self-hosted runner deploys automatically.

---

## Session: Admin API URL Unification (2026-05-08)

### Problem solved

All four admin pages were using inconsistent strategies to reach the backend:
- `admin/page.js` read from `localStorage` via `lib/apiConfig.js` (with an on-page input box for pasting the API base URL)
- `admin/experiments/{new,task,idiom}/page.js` each declared their own `const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1234"` — an env var that was never set in any build or deploy config, so they always fell back to `localhost:1234` and were broken on the server

Additionally, the server is accessed via SSH local-port forwarding (`-L 3000:127.0.0.1:22222`), so `window.location.hostname` is always `localhost` regardless of environment — runtime hostname detection would not have distinguished local from tunnelled-server access.

### Approach

Next.js `rewrites()` in `next.config.mjs` proxy all `/api/*` requests from the browser to the backend over the internal Docker network. The browser only ever talks to the frontend; Next.js (running inside the container on the server) forwards `/api/:path*` → `http://provibackend:80/api/:path*`. One Docker image works for local dev and the server with no env var, no input box, and no rebuild.

The SSH tunnel command can now be simplified — the backend forward (`-L 8000:127.0.0.1:1234`) is no longer needed:
```bash
ssh -p 1907 -L 3000:127.0.0.1:22222 ccvis@134.155.106.59
```

### Infrastructure

| File | Change |
|------|--------|
| `ProViFrontend/provi-frontend/next.config.mjs` | Added `async rewrites()` — proxies `/api/:path*` to `${BACKEND_INTERNAL_URL}/api/:path*` (defaults to `http://provibackend:80`) |
| `docker-compose.yml` | Replaced `NEXT_PUBLIC_API_BASE` build arg with `BACKEND_INTERNAL_URL: http://provibackend:80` runtime env var on `provifrontend` service |
| `ProViFrontend/Dockerfile` | Removed `ARG NEXT_PUBLIC_API_BASE` and `ENV NEXT_PUBLIC_API_BASE=...` lines — no longer needed at build time |
| `.env.example` | Removed `PUBLIC_API_BASE` — superseded by the rewrite approach |
| `ProViFrontend/provi-frontend/src/lib/apiConfig.js` | **Deleted** — `getApiBase`, `setApiBase`, `normalizeApiBase`, localStorage logic no longer needed |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Removed "API base URL" input box section, `apiBaseInput` state, related `useEffect`, and `apiConfig` imports. All three `fetch` calls switched to relative `/api/...` URLs. |
| `provi-frontend/src/app/admin/experiments/new/page.js` | Removed top-level `BASE_URL` const. Both `fetch` calls switched to relative `/api/...` URLs. |
| `provi-frontend/src/app/admin/experiments/task/page.js` | Removed top-level `BASE_URL` const. All five `fetch` calls switched to relative `/api/...` URLs. Cleaned up error message that previously printed `BASE_URL`. |
| `provi-frontend/src/app/admin/experiments/idiom/page.js` | Removed top-level `BASE_URL` const. All eight `fetch` calls switched to relative `/api/...` URLs. |

### Note on `SECRET_ENV`

The `PUBLIC_API_BASE` line in `SECRET_ENV` (GitHub Actions secret) is now unused and can be removed when convenient. The other three vars (`MONGO_USERNAME`, `MONGO_PASSWORD`, `COMPOSE_PROFILES`) remain needed.

---

## Session: Admin Passcode Gate (2026-05-04)

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/layout.js` | Converted to client component; gates all `/admin/*` routes. Hydrates `authed` from `localStorage["adminAuthed"]` (no backend, no admin record — flag only). Unauthed visits to suffix routes (`/admin/experiments/new`, etc.) `router.replace("/admin")`. On `/admin` while unauthed, renders `LoginModal` overlay; on success sets the flag and reveals content. Authed users navigate freely; flag persists across tab/browser restarts until cleared. |

---

## Session: Admin Home — Two-Column Layout (2026-05-03)

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Added `GET /admin/experiments` — returns list of all experiments (id, name, status, created_at) |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Redesigned admin home as two-column layout: left column retains Upload Dataset + API base URL config; right column shows live experiment list fetched from `GET /admin/experiments`, with status-coded border colours (blue = published, amber = draft, grey = closed). "Create New Experiment" button links to `/admin/experiments/new` (the existing experiment setup page). |

---

## Session: Experiment Creation Wizard — Step 1 (Name, Description, Dataset)

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/datamodels/data_schemas.py` | Revised `Experiment` model (removed `experiment_created_by`, `experiment_description` made optional, nullable defaults for enum fields, list defaults); added `ExperimentCreate` and `ExperimentPatch` models |
| `ProViBackend/app/routers/admin.py` | Repurposed `GET /admin/datasets` to return `DatasetPair` collection; added `POST /admin/experiments` (create draft); added `PATCH /admin/experiments/{id}` (partial update) |
| `ProViBackend/utils/database/connection.py` | Added `create_experiment`, `get_experiment`, `update_experiment` helpers |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/experiments/new/page.js` | **New** — Step 1 page: fetches dataset pairs, POSTs draft experiment on Next, navigates to `/admin/experiments/[id]/design` |
| `provi-frontend/src/components/Admin/ExperimentDetailsForm.js` | **New** — Controlled name + description inputs |
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | **New** — Checkbox multi-select table of dataset pairs |
| `provi-frontend/src/components/Admin/AdminNav.js` | Added "Experiment Setup" nav item |
