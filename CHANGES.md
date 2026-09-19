# Change Log

Tracks files modified or created during development sessions.

## Session: task03 Asks About Overall Behavior; Readable Boolean Buckets (2026-09-19)

| File | Change |
|------|--------|
| `provibackend/ProViBackend/app/seed_data.py` | task03's description matches its question (already "overall behavior", from Tasks and Idioms.pdf): compare the groups over the chosen attributes, throughput time by default — no longer "which group is slower". |
| `provibackend/ProViBackend/scripts/tasks/task03.py` | Module docstring and `RUBRIC` follow the question: any compared attribute, throughput time as the default. |
| `provibackend/ProViBackend/scripts/trace_features.py` | `as_bucketable(..., key=)`: a `contains::X` boolean buckets as "With 'X'" / "Without 'X'" instead of a bare Yes / No. |
| `scripts/tasks/task03.py`, `tasks/task13.py`, `trace_response.py` | Pass the key. task30 and `violation_profile` prefix every label with the attribute already, so they keep Yes / No. |

`py_compile` only; not rendered.

## Session: task02 Idioms Show the Same Information (2026-09-19)

| File | Change |
|------|--------|
| `provibackend/ProViBackend/scripts/tasks/task02.py` | Table reduced to Mean Fitness and Fitness Threshold, what the tile and bar chart show; its trace counts and "% conformant" (cut at 1.0 beside a 0.8 threshold) are gone. Bar chart: the threshold label sat on the navy bar, dark on dark — it moves to a legend below the axes, and the dashed line gets a white outline so it shows across the bar. |
| `docs/AGGREGATE_FITNESS_CLASS.md` | §2 matches: the table's threshold is a column, the bar chart's is named in a legend, and the three idioms carry the same two numbers. |

`py_compile` only; not rendered.

## Session: task01 Idioms Show the Same Information (2026-09-19)

### Problem solved

task01's idioms showed different data: the bar chart only each group's mean
fitness, the table counts, % conformant and the mean, the matrix, stacked bar
and parallel sets counts per fitness category. Participants given different
idioms were given different information, not the same information drawn
differently. Counts also made the larger group look better.

### Changes

| File | Change |
|------|--------|
| `provibackend/ProViBackend/scripts/tasks/task01.py` | One kernel, `_task01_category_counts`: per group, traces in Major (<0.8) / Minor (0.8–<1.0) / Conformant (=1.0). Every idiom but the box plot draws its within-group shares, with `n` in the group label. Bar chart → grouped bars per category; table and table + bar chart → `count (share%)` per category (mean fitness dropped); stacked bar → 100% stacked; parallel sets → equal-height groups; matrix → row shares on a fixed 0–100% scale. Category colours: Major yellow, Minor ochre, Conformant navy — yellow is low fitness, and both deviation categories stay on cividis's yellow end so deviating vs conformant reads as yellow vs blue (the slate blue `categorical_colors(3)` gives Minor drew a log without major deviations all blue). `_task01_group_stats` removed. |
| `provibackend/ProViBackend/scripts/shared.py` | The colour-direction comment: yellow is the low end of what is encoded, so fitness categories run yellow (deviating) → navy (conformant). |

The box plot is unchanged and cannot show this: it draws quantiles, and with
most fitness values at exactly 1.0 its boxes collapse. It stays in `IDIOMS`.
task04 at log level draws task01's figures, so it changes with them.

### Verification

`py_compile` only. Not rendered: check the /idiom previews after deploying.

## Session: Custom Idioms Belong to Their Experiment (2026-09-19)

### Problem solved

A custom idiom was a global `Idiom` document bound only to tasks, so every
later experiment offered it for those tasks — test uploads included — and no
page could remove one.

### Changes

| File | Change |
|------|--------|
| `provibackend/ProViBackend/app/datamodels/data_schemas.py` | `Idiom.experiment_id`. |
| `provibackend/ProViBackend/app/routers/admin.py` | `POST /idioms/upload` requires `experiment_id` and records it. `/task-idioms` offers a custom idiom only to its experiment; older ones (no `experiment_id`) only where already selected or bound to the experiment's own custom task. Deleting an experiment deletes the custom idioms uploaded in it. |
| `ProViFrontend/provi-frontend/src/components/Admin/UploadIdiomModal.js`, `src/app/admin/experiments/idiom/page.js` | The modal posts the experiment id and says the idiom belongs to this experiment. |

`docs/ADMIN_EXPERIMENT_SETUP.md` gains *Custom idioms*.

### Verification

`py_compile` and `eslint` on the changed files. Not run end to end. Nothing is
deleted from the database: an experiment already using a custom idiom — a
published one included — resolves it by id as before.

## Session: Grey-Free Idiom Colours, First Five Tasks (2026-09-19)

### Problem solved

The palette guide moved every chart to cividis, but cividis is nearly neutral
grey in its middle, and the stops the tasks used sit there: `GREY_MED` (0.45) is
`#727274`, saturation 0.01. Group comparisons, move types and category ramps
therefore still drew in grey. The eight tasks of the published experiment are
left as they are; this starts the others.

### Backend (`provibackend/ProViBackend/scripts/`)

| File | Change |
|------|--------|
| `shared.py` | New `PAIR_COLORS`, `MOVE_LOG` / `MOVE_MODEL` / `MOVE_MISMATCH` / `MOVE_SYNC` and `categorical_colors(n)`, all sampled outside cividis's grey middle; `GREY_*` values unchanged. `render_conformance_line_graph` takes `line_color` / `mean_color` (defaults = the old grey, which task10 keeps). `draw_grouped_box_plot` picks each median line's colour for contrast with its box — white vanished on a yellow box; no frozen task calls it. |
| `tasks/task01.py` | Positive / Negative blue / yellow; conformance categories `categorical_colors(3)`. |
| `tasks/task02.py` | The single bar is blue. |
| `tasks/task05.py` | Sub-logs blue / yellow; stacked-bar segments and the parallel sets' right axis `categorical_colors`; box-plot jitter points neutral dark. |
| `tasks/task07.py` | Line graph blue with a neutral mean line; horizon chart already blue / yellow. |
| `tasks/task08.py` | Network nodes by `MOVE_*`, edges on cividis's blue end instead of `plt.cm.Greys`; matrix cell text by `contrasting_text_color`. |

### Docs

The rule — data colours come from cividis's blue and yellow ends, grey only for
axes, borders, text, reference lines and empty cells, the eight frozen tasks
untouched — is recorded in the comment above the new constants in `shared.py`.
(`PALETTE_GUIDE.md` has the same as §0, but that file is git-ignored.)

### Verification

- `py_compile` over the changed files. The eight frozen tasks are unaffected by
  construction: no `GREY_*` value changed, the line graph's defaults are the old
  colours, and none of them calls `draw_grouped_box_plot`.
- **Not rendered:** the new colours are to be checked on the /idiom previews after
  deploying.

### Known gaps

- `categorical_colors(n)` for n ≈ 10 puts its first three blues close together;
  task05's stacked bar can have 11 segments (top 10 + Other).
- Box-plot whiskers keep the box colour, so yellow whiskers are faint on white.

## Session: Idiom Previews Drawn by the Current Code (2026-09-19)

### Problem solved

The preview on the idiom step served SVGs committed to the repo on 2026-07-19
(12 tasks, exported from a container by `export_idiom_previews.sh`), and marked
those tasks ready at startup without ever drawing them. The task modules have
changed substantially since, so an admin choosing idioms saw July's drawings,
while the Overview page — and participants — saw the current generator's
output.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Previews are only ever drawn at runtime, into a container-local cache that every image rebuild empties. `prewarm_idiom_previews` draws all tasks one after another; `_claim_idiom_preview` (under a lock) keeps it and admin requests from drawing the same task twice. Sample-dataset check factored into `_sample_dataset_ready`. Preview SVGs are served with `Cache-Control: no-cache`. |
| `ProViBackend/app/main.py` | Starts the prewarm in a daemon thread once the sample dataset exists. |
| `ProViBackend/scripts/sample_data/output/__idiom_preview/` | **Deleted** (84 committed SVGs); now in `.gitignore`. |
| `scripts/export_idiom_previews.sh` | **Deleted** — it existed to commit those SVGs. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/idiom/page.js` | The page text, the preview button's tooltip and a note in the preview modal say what a preview is: roughly how the idiom looks, drawn from a bundled BPIC 2012 loan-application log with default parameters, not the admin's dataset — the real images come from generating on the Specify step. The note is left out for custom idioms, whose preview is the real image. |

### Docs

`docs/ADMIN_EXPERIMENT_SETUP.md` (*Idiom previews on /idiom*).

### Verification

- `py_compile` over the changed Python files.
- **Not verified end to end:** the prewarm's duration and its effect on
  request latency right after a deploy are unmeasured; its log lines
  (`[idiom-preview] … in Ns`, `prewarm finished in Ns`) report both on the
  server.

### Known gaps

- Still the sample dataset with default parameters, not the experiment's own
  dataset — a preview shows how an idiom is drawn, not this experiment's data.
- Generation shares the interpreter with request handling; the prewarm runs one
  task at a time with a pause, but requests may still be slower until it ends.

## Session: Idiom Import Checks Dataset and Parameters (2026-09-19)

### Problem solved

- **Importing required generating first.** Import lived on the Overview page,
  but /specify's Next only unlocks once every task is `ready`. An admin
  reproducing a study had to set parameters and generate images only to replace
  them a step later — and the wizard gave no hint that import existed at all.
- **Imported images kept the wrong parameters.** Import pinned the images but
  left the experiment's parameters as set on /specify. The participant-facing
  parameter hints and any later export were built from those, so both could
  describe something other than what the images showed.
- **Nothing checked where images came from.** A zip from an experiment on
  another dataset, or drawn with other parameters, was imported as long as the
  task and idiom keys matched.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/idiom_bundle.py` | Import takes `mode=specify\|overview` and checks each task before taking its files: rejected if exported from another dataset (by log/guideline checksum, or dataset id for version-1 manifests); in `overview` mode also if its parameters differ (differences listed). `specify` mode writes the zip's parameters onto the task. Imported tasks get `images_imported_from`; reverting clears it. A manifest is now required. Export writes manifest version 2 with each task's dataset title and checksums. The response lists `imported` and `rejected` (was `skipped`) plus `dataset_mismatch`. |
| `ProViBackend/app/routers/admin.py` | `PATCH /experiments/{id}` keeps an imported task's parameters and marker whatever the caller sends (`_keep_imported_parameters`). Generation skips tasks whose every idiom shows an uploaded image (`_fully_uploaded_task_ids`), neither validating nor re-running them; if that is every task, it returns without starting a job. |
| `ProViBackend/app/datamodels/data_schemas.py` | `TaskInstance.images_imported_from`. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/components/Admin/IdiomImport.js` | **New.** Import button (posts with a mode) and result view: imported files, rejected files with reasons, a dataset warning, and — for parameter rejections on Overview — a pointer to the Specify step. |
| `src/app/admin/experiments/specify/page.js` | "Images from an earlier experiment" card: import (`specify` mode), count of imported tasks, *Discard import*. Imported tasks show a lock notice and read-only parameters. Generate leaves imported, ready tasks alone and is disabled once every task is imported. |
| `src/app/admin/experiments/overview/page.js` | Import uses `overview` mode with the new result view and says which images it accepts. Replacing a single image asks for confirmation. Preview fallback text no longer points at the removed idiom selection page. |
| `src/components/Admin/UploadIdiomModal 2.js` | **Deleted** — an unreferenced Finder duplicate of `UploadIdiomModal.js`. |

### Docs

`docs/ADMIN_EXPERIMENT_SETUP.md` (data model, *Generation*, *Idiom images*).

### Verification

- `py_compile` over the changed Python files; `eslint` over the changed JS
  files — no new findings (the `react/no-unescaped-entities` errors in
  `overview/page.js` are the pre-existing ones in the publish-conflict dialog).
- **Not verified end to end:** no endpoint or page was run locally; testing
  happens on the `develop` deployment.

### Known gaps

- Zips exported before this change are version 1 and carry no checksums, so
  they only import into an experiment on the same server using the same
  dataset id; exporting again from the source experiment produces a version-2
  zip.
- *Discard import* reverts every uploaded image of the experiment, including
  single replacements made on the Overview page.
- An experiment's dataset can still be changed after an import; the lock does
  not re-check it, so the imported images would then no longer match.

## Session: Configurable Intro Pages, Idiom Image Export/Import (2026-09-18)

### Problem solved

- **The intro pages were hard-coded.** *Key Concepts* (`/conformance-terms`)
  and *Before You Begin* (`/taskintro`) were fixed JSX tied to the
  order-to-cash dataset, with a fixed citation. An experiment on another
  process showed participants the wrong diagram and definitions, and the only
  way out was editing code.
- **Stimuli were not reproducible.** Idiom images existed only as generator
  output on the server. Regenerating after the generator code changed (as the
  violation-profile refactor did to seven tasks) silently changed what
  participants saw, and there was no way to archive the images a study used or
  load them into another experiment.
- **Custom idiom assets did not survive a deploy.** They were written to
  `app/static/custom_idioms`, inside the container rather than on the
  `/srv/provi-data` volume, so every redeploy that rebuilt `provibackend` lost
  them while their `Idiom` records stayed. (Checked on the server before this
  change: the directory did not exist and no custom `Idiom` records existed, so
  nothing had been lost yet.)

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/datamodels/data_schemas.py` | `Experiment` gains `concept_sections`, `taskintro_sections`, per-page `*_citation_enabled` / `*_citation_text`, and `process_model_ext`; defaults reproduce the old pages. New `IntroPageSections` request model. |
| `ProViBackend/app/routers/admin.py` | `PATCH /experiments/{id}/intro-pages`; `POST`/`DELETE`/`GET /experiments/{id}/process-model`. The overview preview (`/experiments/{id}/vis/…`) shows an uploaded image first. Deleting an experiment removes its process model image and idiom overrides. Custom idiom assets served as `image/jpeg` instead of the invalid `image/jpg`. |
| `ProViBackend/app/routers/idiom_bundle.py` | **New.** Export an experiment's images as a zip with a manifest; import one into any draft experiment, matched by `task_key`/`idiom_key`; replace or revert a single image; list and revert all overrides. |
| `ProViBackend/app/routers/participant.py` | `GET /participant/intro-pages` and `/participant/process-model` for the active experiment. Image and `traces.json` resolution goes through `utils/idiom_files`, so uploaded images win. |
| `ProViBackend/utils/idiom_files.py` | **New.** The one place deciding which file is shown for an idiom (upload → custom asset → generated → legacy); override storage; moves custom idiom assets out of the old location at startup. |
| `ProViBackend/utils/config.py` | `CUSTOM_IDIOM_DIRECTORY` moves to `data/_custom_idioms`; new `IDIOM_OVERRIDE_DIRECTORY` and `PROCESS_MODEL_DIRECTORY`, all on the volume. |
| `ProViBackend/utils/utils.py` | `process_model_path`, `image_media_type`. |
| `ProViBackend/app/main.py` | Registers `idiom_bundle`; runs the custom idiom move at startup. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/concepts/page.js` | **New wizard step** (after `/knowledge`): sections of both intro pages, per-page citation toggle and text, process model upload. Shows the participant flow and marks pages that will be skipped. |
| `src/utils/introPages.js` | **New.** Section lists, defaults, fetching the config, and where each intro page leads when its neighbour is skipped. |
| `src/components/General/ProcessModelImage.js`, `IntroCitation.js` | **New.** The diagram (uploaded image via `<img>`, so scripts in an SVG never run) and the citation box, shared by both pages and the admin preview. |
| `src/app/conformance-terms/page.js`, `src/app/taskintro/page.js` | Render only the configured sections; skip themselves when empty; text that pointed at another section or at order-to-cash follows what is actually shown. |
| `src/app/knowledgequestion/page.js` | Goes on to the first intro page that is enabled; the button names it. Combined with develop's "no knowledge questions" skip. |
| `src/app/admin/experiments/overview/page.js` | *Idiom Images* panel (download, import, revert all, import report); per-idiom replace/revert and an "Uploaded" badge. |
| `src/app/admin/experiments/specify/page.js` | Confirms before generating when uploaded images exist, since they stay in place. |
| `src/app/admin/page.js` | `concepts` in `WIZARD_STEPS`; idiom download link on published/finished experiments. |
| `src/app/admin/experiments/knowledge/page.js` | Next leads to `/concepts`. |

### Docs

`docs/ADMIN_EXPERIMENT_SETUP.md` (workflow, *Idiom images*, *Intro pages*),
`docs/PARTICIPANT_TRIAL_CONTRACT.md` (*SVG resolution*).

### Verification

- `py_compile` over the changed Python files; `@babel/parser` and `eslint` over
  the changed JS files — clean apart from pre-existing
  `react/no-unescaped-entities` errors in `admin/page.js` and
  `overview/page.js` that this change did not touch.
- **Not verified end to end:** no endpoint or page was run locally; testing
  happens on the `develop` deployment.

### Known gaps

- Imported images are pinned: regenerating does not replace them until the
  admin reverts them. Intended, but a surprise if the /specify warning is
  dismissed.
- The manifest's `git_commit` is `null` until the deploy sets `GIT_COMMIT` for
  the backend.
- Custom tasks and custom idioms only match on import within the experiment
  and server they came from, since their keys are random.
- `.bpmn` files are not accepted as process models; only images.

---

## Session: DFG / Main-App Data Isolation (2026-09-14)

### Problem solved

`dfg-service` and the main app share one Mongo database (`TeamProject`) and one
nginx origin, so nothing but naming kept the two studies' data apart — and two
names still overlapped:

- DFG wrote participant answers and UI logs into `Answer` / `UILogging`, the
  same collections the idiom study uses. The main app's bulk exports
  (`generate_csv_for_download`, called with `query={}`) dump those collections
  whole, with no field identifying which study a row came from, so "download
  Answers" returned a CSV mixing both studies — with columns that shift
  depending on which rows are present, since the two answer schemas diverged in
  the 2026-09-09 refactor.
- Both apps set a session cookie named `provi_user_id`, neither with a `path`,
  on one origin — so whichever study a participant opened last owned the
  identity for the whole site. The main app's write endpoints take that cookie
  as `user_id` verbatim, so a participant who opened the DFG card on the landing
  page mid-study and came back had their next answer stored under a DFG user id:
  a row joinable to no `User` / `PreliminaryAnswers` / `KnowledgeAnswers`
  record, with no error raised.

Both leaks ran one-directionally into the idiom study's data, and both were
silent. Two rules now keep them closed: every DFG collection is prefixed `Dfg`,
and the two studies never share a cookie name.

### DFG service (`dfg-service/`)

| File | Change |
|------|--------|
| `backend/DfgBackend/utils/database/connection.py` | `create_answer` → `DfgAnswer`, `save_ui_logging_data` → `DfgUILogging`, completing the `DfgUser`/`DfgDataset` prefixing this service already applied elsewhere. **Deleted nine helpers** that wrote to the main app's collections — `create_user`, `create_dataset`, `update_dataset_is_active_status` (`User`/`Dataset`), `save_knowledge_answers` (`KnowledgeAnswers`+`User`), `create_experiment`, `get_experiment`, `update_experiment`, `get_user_assignment`, `update_trial_index` (`Experiment`/`UserAssignment`): all uncalled by any DFG router, but one stray call away from writing into the other study. Header comment records the prefix rule. |
| `backend/DfgBackend/app/routers/admin.py` | Its two CSV exports read `DfgAnswer` / `DfgUILogging` to match the renamed writes. |
| `backend/DfgBackend/app/routers/auth.py` | Session cookie issued as `dfg_user_id` instead of `provi_user_id`; `GET /auth/test` reads the new name. Comment records why a shared cookie name is unsafe here. |
| `backend/DfgBackend/app/routers/vis.py`, `questionnaire.py`, `ui_tracking.py` | Read `dfg_user_id`. No frontend change was needed — `dfg-service/frontend` never names the cookie, relying on `credentials: "include"`. |

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/utils/database/connection.py` | **New `user_exists(user_id)`** — true only when this app issued the id (a `User` document exists for it). |
| `ProViBackend/app/routers/questionnaire.py`, `app/routers/auth.py`, `app/routers/participant.py` | The four endpoints that write cookie-keyed data — `POST /survey/answer`, `POST /auth/knowledge`, `POST /auth/feedback`, `POST /participant/assignment` — now return 401 on a cookie this app did not issue. Belt-and-braces after the rename; what it actually catches is a pre-rename `provi_user_id` cookie still sitting in a participant's browser (they live one day). `POST /participant/complete` needed nothing: it already 404s when no assignment exists. |
| `nginx/nginx.conf` | Comment on the `/dfg/` blocks rewritten — it previously documented the shared `provi_user_id` cookie as intended behaviour, which is exactly what this session removed. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/components/Task/TaskAnswerPanel.js` | `submitWithRatings` advanced the trial from a `finally` block, so a failed `POST /api/survey/answer` — a 500, a dropped connection, or the 401 added above — discarded the participant's answer, cleared the form and moved on, recording the loss only as a `console.error`. Now the trial advances only after a 2xx; a failure leaves the rating modal open with the answer and both ratings intact, shows what went wrong, and turns the button into "Try again". `response_time_ms` is still the value captured on first click, so retrying does not inflate it. Needed for the 401 above to be visible rather than silent. |

### Verification

- `py_compile` over all ten changed Python files — clean.
- `eslint` on `TaskAnswerPanel.js` — clean apart from one pre-existing
  `react-hooks/exhaustive-deps` warning about `options`, untouched by this change.
- Re-grepped `dfg-service/backend` for `provi_user_id`, `"Answer"` and
  `"UILogging"` after the edits: only the explanatory comment in `auth.py` is
  left.
- Confirmed each of the nine deleted helpers was uncalled anywhere in
  `dfg-service/backend`, and that `dfg-service/frontend` never references the
  cookie by name.
- **Not verified end to end:** nothing was run against a live Mongo or a
  browser. Neither study's participant flow was exercised after the change.

### Known gaps

- Rows written *before* the rename are still in `Answer` / `UILogging` and will
  still appear in the main app's bulk exports. They are identifiable — a row is
  DFG's if its `user_id` is present in `DfgUser` — but were left untouched,
  since moving or deleting them is a call on live data. Needs a one-off script
  in the style of `scripts/drop_ground_truth_data.py` (`--dry-run` / `--yes`).
- The retry path in `TaskAnswerPanel.js` was reasoned through but not exercised
  in a browser — no failing-backend scenario was actually played out against the
  running app.
- The cookie rename invalidates any in-flight DFG session on deploy, and the
  `test_cookie_ssl` / `_strict` / `_lax` dev routes in `provibackend`'s
  `auth.py` now hand out cookies that the four guarded endpoints reject.

---

## Session: DFG Study Extracted Into a Standalone Service (2026-09-10)

### Problem solved

The previous team's DFG (Directly-Follows-Graph) tool had lived inside
`provibackend` / `ProViFrontend` since the repo's initial commit (`9967cb4`,
2026-03-09), sharing their dependencies, routers and build. The idiom study has
since grown its own task / idiom / answer-format model around those same files,
so neither study could be changed or deployed without touching the other. The
DFG study is still needed, so it was moved out intact rather than deleted.

Done copy-first: the code was duplicated into `dfg-service/` and made to work
there (Phase 1) before being removed from the main project (Phase 2), so the
main app was never left broken by a half-finished move.

### New service (`dfg-service/`)

| Commit | Change |
|--------|--------|
| `055ebc1` | **Phase 1 — copy.** `dfg-service/backend/DfgBackend` (FastAPI plus `FilterModel/`, `MentalMapModel/`) and `dfg-service/frontend` (Next.js: graph view, sliders, questionnaire) created as copies — 59 files. `docker-compose.yml` gains `dfgbackend` / `dfgfrontend`; `provibackend/nginx/nginx.conf` gains the `/dfg/`, `/dfg/api/` and `/dfg/api/admin/` blocks. |
| `ced5edc`, `d0d586d` | Deps missing from the copied `package.json`, each surfacing at build time: `react-zoom-pan-pinch`, `@mui/icons-material`, `@coreui/react`, then `autoprefixer`. |
| `dfbede8` | The dataset upload/activation pipeline had been dropped in the copy; restored. |
| `b150a39` | The copied admin page had been replaced by a placeholder test page; the previous team's real one restored. |
| `dcc23d5` | Static assets 404'd. Fixed by `basePath: "/dfg"` in `next.config.mjs` plus nginx's `/dfg/` block **not** stripping the prefix — unlike the `/dfg/api/` blocks, which must strip it. |
| `7c574fb`, `ca4492f` | Previous team's original ProVi logo and favicon restored. |

### Removed from the main project

| Commit | Change |
|--------|--------|
| `18618a4` | **Phase 2 — delete**, once the standalone service worked: 22 files, 2440 lines. From `provibackend`: `ProViBackend/FilterModel/` (7 files), `ProViBackend/MentalMapModel/` (3 files), `app/routers/vis.py`, `app/routers/ui_tracking.py`. From `ProViFrontend`: `app/home/page.js`, `components/Graph/*` (4 files), `components/Questionnaire/*` (2 files), `components/General/Navigation.js`, part of `ExpNavigation.js`, and the deps they were the only users of in `package.json`. |

### Known gaps

- `dfgbackend`'s volume mount maps the host's `/srv/provi-data` to
  `/code/DfgBackend/data`, but the service writes uploads and generated SVGs to
  `/code/DfgBackend/output` — an unmounted path. The mount therefore does
  nothing, and because `.github/workflows/deploy.yml` force-removes the
  `dfgbackend` container on every deploy, DFG's datasets and SVGs are wiped each
  time and have to be re-uploaded and re-activated.
- `dfg-service`'s copies of the shared data models are frozen at extraction
  time and will drift from `provibackend`'s as it evolves; the same model name
  in the two services no longer implies the same shape.
- Data isolation between the two studies was not addressed here — the two apps
  still shared collections and a cookie name. See the 2026-09-14 entry.

---

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
| `src/app/admin/experiments/answer-format/page.js` | **New file**, replacing `answer-format-groundtruth/` (802 → ~630 lines). The six ground-truth editors collapse into one `OptionsEditor` serving every option-bearing format: import from an event-log source (with a granularity picker for time bins and an axis size for matrices) or author rows by hand, reorder, delete. Adds `NumberKindSelector`, and carries over develop's editable, DB-backed `RubricEditor` so the rubric shows (and can be edited) for every format, not just free-text. |
| `src/app/admin/experiments/overview/page.js` | `GroundTruthSummary` splits into `AnswerSummary` (option preview) and `RubricSummary`. The Decisive/Reference badge becomes option-count and number-kind chips. The publish gate now also requires options wherever the format needs them. |
| `src/app/admin/experiments/specify/page.js` | Redirects to `/answer-format`. |
| `src/components/Task/AnswerWidgets.js` | `numericMeta` keys off `number_kind` instead of the retired numeric formats. The `yes-no` special case in the `single_choice` dispatcher is gone. |
| `src/components/Task/TaskAnswerPanel.js`, `src/app/taskexecution/page.js` | Thread `number_kind` through in place of `answer_format`. |

### Documentation

| File | Change |
|------|--------|
| `docs/ADMIN_EXPERIMENT_SETUP.md` | **New file**, replacing `ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md`. Describes the setup workflow as built rather than as planned. |
| `docs/PARTICIPANT_ANSWER_WIDGETS.md` | **New file**, replacing `PARTICIPANT_ANSWER_WIDGETS_PLAN.md` — the widgets as built. |
| `TASK_GT_DEVELOPMENT_GUIDE.md` | **Deleted.** Ground-truth authoring no longer exists. |
| `docs/PARTICIPANT_TRIAL_CONTRACT.md` | Format catalogue 11 → 7; `decisive` replaced by `number_kind`; grading notes removed. |
| `docs/TASK_CONTRACT_PROMPT.md` | Rewritten as a PARAM_SPEC-only authoring prompt, with an explicit "not in scope" section for the removed attributes. |
| 17 code comments | `ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §N` references repointed at `docs/ADMIN_EXPERIMENT_SETUP.md`. |

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
