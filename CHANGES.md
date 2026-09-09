# Change Log

Tracks files modified or created during development sessions.

## Session: Answer-Format Refactor — Formats Decoupled from Tasks, Grading Removed (2026-09-09)

### Problem solved

Answer formats were a per-task whitelist (`ANSWER_FORMATS`), and the option set a
participant chose from was computed by the same code that decided which option was
correct (`compute_ground_truth`). That coupled three things that should be
independent: what a task draws, how its question is answered, and whether an answer
is right. It also meant a task could only use the formats its module happened to
declare — 17 of 37 tasks declared none at all.

Automatic grading is removed entirely (answers are recorded, analysed later by hand),
formats are global (any task may use any format), and option sets are authored by the
admin — imported from the event log or typed in. Grading rubrics are kept unchanged:
they never fed automatic scoring, they are reference text for manually coding
free-text answers.

Formats consolidated 11 → 7: `yes-no` folded into `mc-single`; `pct`/`count`/`decimal`
into `number` with a `number_kind` setting; `pct-set`/`count-set` into `number-set`;
`rank` — implemented but never used by any task — becomes available for the first time.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `app/answer_formats.py` | **New file.** The global format registry: 7 formats with widget + `needs_options` + `numeric`, `NUMBER_KINDS`, and the `widget_for` / `needs_options` helpers. Replaces the per-task `ANSWER_FORMATS` whitelist. |
| `app/scoring.py` | **Deleted** (129 lines). Answers are no longer scored. |
| `app/datamodels/data_schemas.py` | `OptionItem` loses `correct`. `GroundTruthBlock` and the legacy `GroundTruth` model deleted. `TaskInstance.ground_truth` → `answer_options: List[OptionItem]`, plus `number_kind`. `Answer.is_correct`, `Answer.ground_truth_id` and `PreliminaryAnswers.ground_truth_id` removed. |
| `app/routers/admin.py` | Added `GET /admin/answer-formats` (global), `GET /admin/datasets/{id}/option-sources` and `GET /admin/datasets/{id}/option-candidates` (with `pairs=true` for matrix upper triangles). Removed `GET /admin/tasks/{key}/answer-formats`, `POST /admin/groundtruth`, `_build_gt_block`, `_resolve_answer_format`, and the ground-truth branch of the generation job. `/tasks/{key}/rubric` kept, minus `gt_tier`. Export drops the `ground_truth` column. |
| `app/routers/participant.py` | `_participant_options` collapses to pass-through plus the `rank` shuffle (now justified by presentation-order bias, not by hiding an answer). Sends `number_kind`; stops sending `decisive`. |
| `app/routers/questionnaire.py` | Submit no longer grades: `_lookup_ground_truth` and the `scoring` call removed. |
| `scripts/create_all_visualizations.py` | Generation only draws — the `compute_ground_truth` loop and the per-task module table are gone. Added `get_log_time_bins` + the shared `_trace_start_timestamps` reader. Removed the `--high-cooccurrence-threshold` and `--target-violation` CLI flags and their (dead) wiring. |
| `scripts/tasks/*.py` | Across 20 modules: `ANSWER_FORMATS`, `GT_TIER` and the 16 `compute_ground_truth` functions (~950 lines) removed, plus the two helpers only they used. All 11 `RUBRIC` constants kept as-is. task08's `high_cooccurrence_threshold` removed — it only ever flagged matrix cells correct and affected no drawing. |
| `scripts/tasks/task_registry.py` | Lost `get_answer_formats`, `get_gt_tier`, `get_compute_ground_truth` and their defaults. The task contract is now `IDIOMS` / `PARAM_SPEC` / `validate_params` / `RUBRIC`. |
| `scripts/drop_ground_truth_data.py` | **New file.** One-off cleanup: unsets the ground-truth fields on experiments and answers, drops the `GroundTruth` collection, and clears `answer_format` (every stored key was retired). `--dry-run` / `--yes`; idempotent. |
| `utils/database/migration.py` | Task-instance defaults follow the new shape (`answer_options: []`, `number_kind: None`). No conversion — existing data is discarded. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/answer-format/page.js` | **New file**, replacing `answer-format-groundtruth/` (802 → ~630 lines). The six ground-truth editors collapse into one `OptionsEditor` serving every option-bearing format: import from an event-log source (with a granularity picker for time bins and an axis size for matrices) or author rows by hand, reorder, delete. Adds `NumberKindSelector`; lifts `RubricPanel` out of the old free-text-only editor so the rubric shows for every format. |
| `src/app/admin/experiments/overview/page.js` | `GroundTruthSummary` splits into `AnswerSummary` (option preview) and `RubricSummary`. The Decisive/Reference badge becomes option-count and number-kind chips. The publish gate now also requires options wherever the format needs them. |
| `src/app/admin/experiments/specify/page.js` | Redirects to `/answer-format`. |
| `src/components/Task/AnswerWidgets.js` | `numericMeta` keys off `number_kind` instead of the retired numeric formats. The `yes-no` special case in the `single_choice` dispatcher is gone. |
| `src/components/Task/TaskAnswerPanel.js`, `src/app/taskexecution/page.js` | Thread `number_kind` through in place of `answer_format`. |

### Documentation

| File | Change |
|------|--------|
| `ADMIN_EXPERIMENT_SETUP.md` | **New file**, replacing `ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md`. Describes the setup workflow as built rather than as planned. |
| `PARTICIPANT_ANSWER_WIDGETS.md` | **New file**, replacing `PARTICIPANT_ANSWER_WIDGETS_PLAN.md` — the widgets as built. |
| `TASK_GT_DEVELOPMENT_GUIDE.md` | **Deleted.** Ground-truth authoring no longer exists. |
| `PARTICIPANT_TRIAL_CONTRACT.md` | Format catalogue 11 → 7; `decisive` replaced by `number_kind`; grading notes removed. |
| `TASK_CONTRACT_PROMPT.md` | Rewritten as a PARAM_SPEC-only authoring prompt, with an explicit "not in scope" section for the removed attributes. |
| 17 code comments | `ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §N` references repointed at `ADMIN_EXPERIMENT_SETUP.md`. |

### Verification

- All 37 tasks rendered against `data/test` (BPIC12, 13087 traces) with this code and
  with the pre-refactor code from a git worktree, over the same dataset directory and
  alignment cache. Two identical runs first identify 18 nondeterministic SVGs (network
  diagrams, Petri-net/BPMN layouts, alignment-order-dependent renderers); of the 244
  deterministic ones, **244/244 are byte-identical** after normalising SVG ids and dates.
- `/answer-format` driven end to end in a real browser against the live option-candidate
  endpoints: format selection, import (10 activities from BPIC12), the publish gate
  blocking on missing options, and the saved payload carrying no legacy field.
- `drop_ground_truth_data.py` exercised against an in-memory Mongo with legacy documents,
  including idempotence on a second run.

### Known gaps

- 18 SVGs differ between two identical renders. Pre-existing and unrelated to this
  change, but it blocks any visual regression testing until fixed.
- `rank` has never run against real data — no task ever declared it. Worth exercising
  once before relying on it.

---

## Session: Knowledge Questions — Full DB Implementation (2026-06-11)

### Problem solved

Knowledge questions were hardcoded in the frontend. Admins had no way to add new questions or configure which questions each experiment uses without touching the source code.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `app/datamodels/data_schemas.py` | Added `KnowledgeQuestion` and `KnowledgeQuestionCreate` models. Added `KnowledgeQuestionIds` model. Updated `KnowledgeAnswersRequest` to `{answers: Dict[str, int], tools: List[str]}` (server-side scoring). Added `knowledge_question_ids: List[str] = []` field to `Experiment` (empty = all system questions). |
| `app/seed_data.py` | Added `CANONICAL_KNOWLEDGE_QUESTIONS` with the 6 existing hardcoded questions seeded as `is_system=True`. |
| `app/main.py` | Imported `CANONICAL_KNOWLEDGE_QUESTIONS`; added seed call for `KnowledgeQuestion` collection on startup. |
| `app/routers/admin.py` | Added `GET /admin/knowledge-questions`, `POST /admin/knowledge-questions`, `DELETE /admin/knowledge-questions/{id}` (system questions protected, 409 if referenced by experiments), `PATCH /admin/experiments/{id}/knowledge-questions` endpoints. |
| `app/routers/participant.py` | Added `GET /participant/knowledge-questions` (active experiment, strips `correct_option_index`). Added `GET /participant/experiment/{id}/knowledge-questions` (admin preview). |
| `app/routers/auth.py` | Updated `POST /auth/knowledge` to accept `{answers: {qid: optionIndex}, tools: [...]}`. Score computed server-side by comparing submitted indices against `correct_option_index` in DB. Stored format (`notes`, `score`, `level` in `KnowledgeAnswers`) unchanged for CSV export compatibility. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/knowledge/page.js` | **New file.** Wizard step 2 between `/new` and `/task`. Lists all KQ with checkboxes (system + custom sections). "Add Question" opens a modal to create a new DB question with 2–6 options, optional "I don't know" toggle, and correct answer selection. On "Next", PATCHes the experiment with selected question IDs. |
| `src/app/admin/experiments/new/page.js` | Changed post-create redirect from `/admin/experiments/task` to `/admin/experiments/knowledge`. |
| `src/app/admin/page.js` | "Continue Editing" for experiments without task configs now points to `/admin/experiments/knowledge` instead of `/admin/experiments/task`. |
| `src/app/knowledgequestion/page.js` | Replaced hardcoded question array with dynamic fetch from `GET /api/participant/knowledge-questions`. Answers submitted as `{answers: {question_id: option_index}, tools: [...]}` instead of pre-computed `{notes, score, level}`. Questions grouped by `section_title` from DB. |

---

## Session: Scrollable Dataset Tables (2026-06-11)

### Problem solved

Both dataset display surfaces lacked consistent scroll behaviour when the dataset list grew long.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | Added `max-h-72 overflow-y-auto pr-1` to the table wrapper so the Choose Dataset(s) table on `/admin/experiments/new` scrolls vertically beyond 288 px. Added `sticky top-0 bg-surface-container-lowest z-10` to `<thead>` so column headers remain visible while scrolling. |

*Note: the `/admin` Datasets list already had `max-h-72 overflow-y-auto pr-1` from the Datasets Section Redesign session.*

---

## Session: Timestamp Timezone Fix (2026-06-11)

### Problem solved

Dataset upload timestamps were displaying in UTC instead of the admin's local (Berlin) time. Root cause: the backend stores naive UTC datetime strings (e.g. `"2026-06-11 12:32:00.123456"`) without timezone info. JavaScript's `new Date()` treats space-separated datetime strings as local time rather than UTC, so no UTC→local conversion was applied and the times appeared 2 hours behind CEST.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Updated `formatDateTime`: replaces the space separator with `T`, then appends `Z` if no timezone offset is already present (checked via `/Z$\|[+-]\d{2}:?\d{2}$/`). `new Date()` now parses the value as UTC and `getHours()`/`getMinutes()` output the browser's local time — Berlin time for German admins, system time elsewhere. |
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | Same `formatDateTime` fix, so the "Uploaded:" timestamp in `/admin/experiments/new` is also timezone-correct. |

---

## Session: Experiment Manage Mode (2026-06-11)

### Problem solved

The Experiments section on `/admin` had no way to delete experiments. Admins needed a Manage mode (mirroring the Datasets section) with a two-phase delete flow that surfaces participant-data counts and offers a "Download data first" link before force-deleting.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | **New `DELETE /admin/experiments/{experiment_id}?force=false`**. Counts `UserAssignment`, `Answer`, and `UILogging` documents for the experiment. If `status != "draft"` **or** any count > 0 and `force=false` → returns 409 with `detail.experiment` (name, status) and `detail.counts` (assignments, answers, ui_logs). If `force=true` or a draft with no data → cascades `delete_many` across all three collections then deletes the `Experiment` document. Returns `deleted_counts` in the response body. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Added Manage mode to the Experiments right column, mirroring the Datasets left column: `expManageMode`, `selectedExpIds`, `expDeleteConfirmOpen`, `expForceConfirm` state; `toggleSelectExp`, `exitExpManage`, `performExpDelete`, `handleExpDeleteConfirmed`, `handleExpForceConfirmed` helpers. In Manage mode each experiment card shows a checkbox; action buttons (Continue Editing / Mark as Finished / Download Data) are hidden to avoid misclicks. Footer switches to `[Cancel] [Delete Selected (n)]`. Delete follows the same two-phase pattern as datasets: first confirm modal lists selected names with a note that draft-with-no-data experiments delete immediately; if any return 409, a second force-confirm modal shows per-experiment data counts (assignments · answers · UI logs) and a "Download data first ↓" link for experiments with answers > 0, warning that force delete permanently removes all participant data. Renamed dataset manage state vars to `dsManageMode`/`selectedDsIds` to avoid collision with the new experiment equivalents. |

---

## Session: Datasets Section Redesign (2026-06-11)

### Problem solved

The admin home page had a permanently-open "Upload Dataset" form on the left and no way to view, browse, or delete existing datasets. Admins had no UI to see what was already uploaded or to clean up obsolete datasets, and there was no protection against uploading a second dataset with the same name as an existing one (silently producing two entries with identical titles).

### Approach

Replaced the left column with a "Datasets" section that lists existing datasets (scrollable) with upload date/time and exposes Manage / Upload affordances. Upload is now an explicit modal action. Duplicate-name detection happens client-side at save time; deletes use a two-phase confirm-then-force flow so the admin can choose to abort or proceed when referenced experiments would be demoted.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Added `import shutil` and `Form` from fastapi. **POST `/admin/datasets/pair`** now accepts an optional `dataset_title` form field that overrides the default log-stem-derived title (used by the frontend's "Keep Both" rename flow). **New `DELETE /admin/datasets/{dataset_id}`** with `force: bool = False` query param: when `force=false` and any `Experiment.dataset_ids` references the dataset, returns 409 with `detail.referencing_experiments` (list of `{_id, name, status}`); when `force=true` (or no references exist), demotes each referencing experiment to `draft` (also removing the deleted dataset id from `dataset_ids`), removes the `data/{dataset_id}/` directory via `shutil.rmtree`, and deletes the `DatasetPair` document. Response includes `demoted_experiments` so the UI can name what was reverted. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/components/Admin/UploadDatasetModal.js` | **New** — modal that wraps the previous upload UI (two `FileUploadCard`s + Save button). Receives `existingDatasets` to derive the title set; on Save derives `title` from the log filename stem and checks for collision. If a collision exists, renders an inner conflict dialog with three actions: **Cancel** (return to upload form), **Keep Both** (computes next-available `"{title} ({n})"` starting at n=2, posts with `dataset_title` form field), **Replace** (DELETEs the existing dataset with `?force=true` then re-posts with default title). Backdrop and close button are disabled while `isSaving` to prevent mid-upload close. |
| `provi-frontend/src/app/admin/page.js` | Replaced the "Upload Dataset" left column with a "Datasets" section: scrollable list (max-h-72) showing `dataset_title` + `formatDateTime(insert_datetime)` (dd/mm/yy HH:MM, minute precision). Footer has two modes — **default**: `[Manage] [Upload]`; **manage**: per-row checkboxes + `[Cancel] [Delete Selected (n)]`. Delete uses a two-phase flow: first confirm modal (list of names + warning), then iterate `DELETE /api/admin/datasets/{id}` without force. 409 responses are collected into `forceConfirm` state; when present, a second modal lists each conflicting dataset alongside its referencing experiments (name + status) and offers `[Cancel] [Force Delete]`. Force path re-issues DELETE with `?force=true` and reports demoted experiment names in a toast. Removed `FileUploadCard`/`SaveResultModal` imports and the related `logFile`/`guidelineFile`/`isSaving`/`handleSave`/`modal` state — all migrated into the new modal. Added `Toast` for inline feedback (replaces the post-upload `SaveResultModal`). |
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | Added inline `formatDateTime` helper (same dd/mm/yy HH:MM format) and swapped the two `new Date(...).toLocaleDateString()` calls under "Uploaded:" to use it, so timestamps on `/admin/experiments/new` match the new datasets list and include minute precision. |

### Notes

- `/admin/experiments/new` already fetches from the same `GET /api/admin/datasets` endpoint, so the data source is consistent without further changes.
- "Force Delete" is destructive but reversible only in the sense that the demoted experiments can be re-published manually after their datasets are re-uploaded. The admin sees exactly which experiments will be affected before confirming.
- Frontend duplicate detection is client-side (against the in-memory `datasets` list). A race condition exists if two admins upload simultaneously, but is harmless: the second upload will succeed with a different UUID and the duplicate title will simply coexist until cleaned up.

---

## Session: Publish Mutex Check (2026-06-11)

### Problem solved

The overview page's "Publish Experiment" button always called `PATCH /experiments/{id}/status?status=published` unconditionally, allowing multiple experiments to be in `published` state simultaneously. Business rule: at most one experiment may be published at a time.

### Approach

Frontend-only check on the overview page. When the admin clicks Publish, the page refetches the experiments list to detect any other experiment with `status === "published"`. If one is found, a confirmation modal blocks the action and offers two choices:

- **Cancel** — abort publishing.
- **Finish & Publish** — PATCH the conflicting experiment to `finished`, then publish the current one.

No backend change yet, so a race condition remains if two admins click Publish simultaneously. Backend 409 enforcement is deferred to a future session (likely bundled with merging the two status-update endpoints).

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/experiments/overview/page.js` | Added `publishConflict` and `publishing` state. Split `publishExperiment()` into a validation entrypoint (refetches experiments, detects another published one, opens modal if found) and a private `_doPublish()` helper that contains the actual `PATCH …/status?status=published` call. Added `confirmFinishAndPublish()` which PATCHes the conflicting experiment to `finished` then calls `_doPublish()`. Publish button now also disables during `publishing` and shows "Publishing…". New inline conflict modal (styled like `SaveResultModal`) displays the conflicting experiment name with Cancel / "Finish & Publish" actions. |

---

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
