# Change Log

Tracks files modified or created during development sessions.

## Session: Admin Experiments List Scrollable (2026-06-11)

### Problem solved

The Experiments section on `/admin` had no height limit, so the page grew taller as more experiment instances accumulated, eventually pushing other content off-screen and breaking the two-column layout balance.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Added `max-h-72 overflow-y-auto pr-1` to the experiments list container (`<div className="space-y-4 mb-10">`). The list now caps at 288px (≈3–4 cards visible), scrolls vertically when exceeded, and `pr-1` reserves space for the scrollbar so card content isn't clipped. |

---

## Session: Task List Natural Sort (2026-06-11)

### Problem solved

Tasks on `/admin/experiments/task` were displayed in MongoDB insertion order rather than logical order (task1, task2, …, taskN). With more than 9 tasks, lexicographic string sort would also break (e.g. task10 before task2).

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Added `import re` at top. In `GET /admin/tasks`, added a natural-sort step after fetching: `tasks.sort(key=lambda t: int(re.search(r'\d+', t.get("task_key", "0")).group()))`. Tasks are now returned in task1 → task2 → … → taskN order regardless of insertion order in MongoDB. |

---

## Session: Experiment Overview Page (2026-05-24)

### Goal
Add a read-only overview page as the final step of the admin experiment-setup wizard (after idiom selection), showing all selected tasks and idioms. Migrate "Save as Draft" and "Publish Experiment" actions from idiom-selection to this new page. Add per-task placeholder sections for two upcoming features: answer-type configuration and ground-truth generation.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/experiments/overview/page.js` | **New** — Step 3 overview page. Fetches experiment, tasks, and idioms in parallel via `Promise.all`; groups `task_configs` by `task_id`. Top metadata strip shows experiment name, ID, task count, and a live status badge (yellow = draft, green = published). One card per task with three sections: **Selected Idioms** (non-interactive chips showing label + granularity · renderer), **Answer Type** (dashed-border placeholder, "Coming Soon" pill, disabled "Configure" button), **Ground Truth** (dashed-border placeholder, "Coming Soon" pill, disabled "Generate" button). Sticky footer: ← Previous Step, **Save as Draft** (`PATCH {status: "draft"}`), **Publish Experiment** (`PATCH /status?status=published`). After publish the status badge flips to "published" and the Publish button disables — page stays open. |
| `provi-frontend/src/app/admin/experiments/idiom/page.js` | Replaced `saveExperiment` with `handleNext`: PATCHes only `task_configs`, then navigates to `/admin/experiments/overview?experiment_id=…`. Removed `showSuccess`, `successDetail`, `expModalOpen`, `experiments` state; removed `saveExperiment` and `viewExperiments` functions; removed success-banner JSX, "Save as Draft" / "Publish Experiment" footer buttons, and "View All Experiments" modal — all superseded by the overview page. Footer now has a single "Next →" button. Also fixed a latent bug: the old `publish` branch referenced an undefined `BASE_URL`. |
| `provi-frontend/src/app/admin/idiom-selection/page.js` | Same changes as `experiments/idiom/page.js` — this is the legacy parallel flow. |

---

## Session: Safari Cookie Fix (2026-05-18)

### Problem solved

The pipeline completed successfully in Chrome but the `/knowledgequestion` submit failed silently in Safari (returned 401 "No cookie detected").

**Root cause:** `auth.py` set the `provi_user_id` cookie with `Secure=True; SameSite=None`. Chrome exempts `localhost` from the HTTPS requirement for `Secure` cookies, so it accepted and resent the cookie over plain HTTP. Safari does not make this exception — it strictly dropped any `Secure` cookie received over HTTP, so every subsequent request arrived without a cookie and was rejected by the backend.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `.env` | Added `COOKIE_SECURE=false` — disables the `Secure` flag for local HTTP dev. Set to `true` in production (HTTPS). |
| `ProViBackend/app/routers/auth.py` | Reads `COOKIE_SECURE` env var (defaults to `true`). When `false`, sets `secure=False, samesite="lax"` on the `provi_user_id` cookie instead of `secure=True, samesite="none"`. (`SameSite=None` requires `Secure` by spec, so both attributes must change together.) Production behaviour is unchanged. |
| `docker-compose.override.yml` | Added `COOKIE_SECURE: "false"` to the `provibackend` service environment. The override file is gitignored and local-only, so production (`docker-compose.yml`) is unaffected. Restart with `docker compose up -d provibackend` — no rebuild needed. |


---

## Session: SVG Path Fix & Participant Assignment Endpoints (2026-05-11)

### Problem solved

Two bugs prevented visualization images from loading for participants:

1. **`admin.py` used the wrong base path** — `DATA_DIRECTORY = pl.Path("/data")` stored uploaded datasets at `/data/{pair_id}/…` inside the container, while `participant.py` read SVGs from `config.BASE_DIRECTORY / "data" / {pair_id} / …` (`/code/ProViBackend/data/…`). These paths never matched, so SVG fetches always returned 404.

2. **`data/` was not excluded from the Docker build context** — `provibackend/ProViBackend/data/` is gitignored, so generated SVG files are never committed. Because `ProViBackend/data/` was missing from `.dockerignore`, local SVG files were silently baked into images built on developer machines. Anyone who cloned the repo fresh got an image with no SVGs and broken visualizations on `/taskexecution`.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Replaced `DATA_DIRECTORY = pl.Path("/data")` with `DATA_DIRECTORY = config.BASE_DIRECTORY / "data"`. Dataset files now land in the `provibackend_data` Docker volume (`/code/ProViBackend/data/{pair_id}/…`), matching the path `participant.py` reads from. |
| `ProViBackend/app/routers/participant.py` | Added `POST /participant/assignment` — idempotent endpoint that assigns a participant to an experiment using balanced random allocation and persists a `UserAssignment` document. Added `GET /participant/assignment/{user_id}/{experiment_id}/trials` — returns the participant's personalised trial list (full task/idiom metadata, `svg_available` flag, `trial_index`) from their stored `trial_sequence`. |

### Infra

| File | Change |
|------|--------|
| `provibackend/.dockerignore` | Added `ProViBackend/data/` — prevents locally generated SVG/dataset files from being baked into Docker images, ensuring consistent builds for all team members. |

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
| `.github/workflows/deploy.yml` | **New** — Single root-level workflow; triggers on push to `develop`; self-hosted runner writes `.env` from `SECRET_ENV` GitHub secret then runs `docker compose up -d --build`. Uses `actions/checkout@v4`. Includes a pre-deploy step that force-removes any containers left over from the previous manual setup (`docker rm -f redis mongo provibackend provifrontend nginx`) so naming conflicts don't block the first compose-managed deploy. |
| `ProViFrontend/Dockerfile` | Rewrote to fix three issues: (1) `ARG NEXT_PUBLIC_API_BASE` moved to after `FROM` — args declared before `FROM` are global scope and not available inside the build stage; (2) added explicit `sharp` install (`npm install sharp`) after the main `npm install` — `sharp` is an optional Next.js peer dependency and is required at build time to generate blur placeholders for imported PNG images; (3) `CMD` changed to JSON array form to handle OS signals correctly. |
| `ProViFrontend/.dockerignore` | **New** — Excludes `provi-frontend/node_modules` and `provi-frontend/.next` from the Docker build context. Without this, `COPY . .` overwrites the Linux node_modules (installed inside the container) with the local macOS ones, whose native binaries (e.g. `sharp`) cannot run on Linux. |
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

## Session: Dataset structure, task/idiom source of truth, path unification (2026-05-08)

### Goal
Restructure file storage to `data/{pair_id}/input/` + `data/{pair_id}/output/task1..task6/`, make Tasks and Idioms backend-authoritative (auto-seeded, no frontend hardcoding), expose a `GET /admin/task-idioms` endpoint, and rename the Save button to "Save and Generate Graphs".

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/scripts/tasks/task1-6.py` | Added module-level `IDIOMS = [...]` constant to each script listing canonical idiom_keys that script generates (post-rename). Single source of truth for task→idiom mapping. |
| `ProViBackend/app/seed_data.py` | **New** — `CANONICAL_TASKS` (6 tasks, task_key=`task1..task6`) and `CANONICAL_IDIOMS` (13 idioms). Replaces the frontend `ALL_TASKS` and `ALL_IDIOMS` constants. |
| `ProViBackend/app/main.py` | Added `asynccontextmanager` lifespan. On startup: if `Task` or `Idiom` collection is empty, inserts from `seed_data.py` with stable UUIDs (`uuid5`). Eliminates manual "Seed" buttons. |
| `ProViBackend/app/routers/admin.py` | Added `GET /admin/task-idioms` — returns `{task_key: [idiom_key, ...]}` from each task module's `IDIOMS` constant. Updated `POST /admin/datasets/pair`: saves uploaded files in `data/{pair_id}/input/` (preserving original filename), writes graphs to `data/{pair_id}/output/`, calls `run_pipeline(pair_dir)` instead of old `create_all_visualizations`. Updated `_sync_participant_experiment`: `svg_path = f"data/{pair_id}/output/{task_key}/{idiom_key}.svg"`. |
| `ProViBackend/app/routers/participant.py` | Updated fallback `svg_path` construction to match new `data/{pair_id}/output/...` layout. |
| `ProViBackend/scripts/create_all_visualizations.py` | Replaced per-filename discovery with extension-based scanning (`LOG_EXTENSIONS={".xes",".csv"}`, `MODEL_EXTENSIONS={".bpmn"}`). Added `_FILE_RENAME` constant (idiom name normalisation). `run_pipeline()` now also strips `taskN_` prefix and applies `_FILE_RENAME` after each generator. Removed old `create_all_visualizations()` function (T-01 naming). |

### Infra

| File | Change |
|------|--------|
| `docker-compose.yml` | Renamed volume `provibackend_output → provibackend_data`, mount path `/code/ProViBackend/output/ → /code/ProViBackend/data/`. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/page.js` | Renamed "Save" button → "Save and Generate Graphs"; loading state → "Saving and generating...". |
| `src/components/Admin/SaveResultModal.js` | Success copy updated to inform user that graph generation runs in the background (~30s). |
| `src/app/admin/experiments/task/page.js` | Removed hardcoded `ALL_TASKS`, "Seed Tasks" button, "Add Task" modal. Tasks now fetched purely from `GET /api/admin/tasks` (auto-seeded from backend on startup). |
| `src/app/admin/experiments/idiom/page.js` | Removed hardcoded `ALL_IDIOMS`, `TASK_IDIOM_KEYS`, "Seed Idioms" button. Idioms fetched from `GET /api/admin/idioms`; task→idiom filter mapping fetched from `GET /api/admin/task-idioms`. Both fetched in parallel via `Promise.all`. |

### Deploy action required
```bash
docker compose down -v          # removes provibackend_output volume
# drop Task, Idiom, Experiment, DatasetPair, ParticipantExperiment collections in MongoDB
docker compose up -d --build    # auto-seeds Task + Idiom on first startup
```

### Known gap
`task3.py` declares `flow_chart_table` in its `IDIOMS` list (matching the original frontend mapping) but does not yet generate a `task3_flow_chart_table.svg`. Selecting this idiom for task3 will produce a missing-SVG 404 for participants. Needs a generator added to `task3.py`.

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
