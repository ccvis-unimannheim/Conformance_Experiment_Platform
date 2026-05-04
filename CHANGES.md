# Change Log

Tracks files modified or created during development sessions.

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
