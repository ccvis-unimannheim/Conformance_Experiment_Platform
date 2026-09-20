# Admin Experiment Setup — Parameters, Generation, Answer Formats

How an admin turns a set of tasks and idioms into a publishable experiment, and
which code owns each step. This describes the platform as built (it replaces
`ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md`, which was a plan for a ground-truth
workflow the platform no longer has).

> **There is no automatic grading.** Answers are recorded, not scored. Free-text
> answers are coded by hand against a task's `RUBRIC`; every other format is
> analysed from the exported answers. Nothing in the platform decides whether a
> participant was right.

## Workflow

```
/new → /prequestionnaire → /knowledge → /concepts → /task → /idiom → /specify → /answer-format → /overview → publish
```

/new offers a second route: **Start from a downloaded zip**
(`POST /admin/experiments/from-bundle`). The zip decides the tasks, the idioms
and — from manifest version 3 — the answer formats, so there is no dataset to
choose and nothing to generate. Such an experiment is marked `bundle_only`, goes
straight to /overview (or /answer-format, when an older zip carries no formats),
and skips /specify; its images can only be replaced, never reverted, since there
is no generated image behind them. Everything before the tasks
(/prequestionnaire, /knowledge, /concepts) keeps its defaults, which the
*Participant flow* card on /overview states and links to.

/idiom also skips /specify when every selected idiom is an uploaded image:
nothing about such a task is generated, and `PATCH /admin/experiments/{id}`
marks it `ready` as it is saved.

`/prequestionnaire`, `/knowledge` and `/concepts` configure what participants
see before the tasks (see [Intro pages](#intro-pages) for `/concepts`); the
table below covers the task steps.

| Step | Page | What the admin does | Stored on the task instance |
|---|---|---|---|
| /specify | `admin/experiments/specify` | Set each task's hyperparameters, then trigger generation | `parameters` |
| — | (background job) | Render every idiom SVG for the chosen parameters | `generation_status`, `generation_error` |
| /answer-format | `admin/experiments/answer-format` | Choose how participants answer; author options; read the rubric | `answer_format`, `number_kind`, `answer_options` |
| /overview | `admin/experiments/overview` | Review and publish | — |

Publishing is gated on every task being `generation_status: "ready"` with an
answer format chosen, and — for formats that present a closed set — at least
one option.

## Data model

An experiment holds one `TaskInstance` per task (`app/datamodels/data_schemas.py`):

```python
TaskInstance
├─ task_id, dataset_id, idiom_ids, question_ids
├─ parameters        : dict          # keys defined by the task's PARAM_SPEC
├─ answer_format     : str | None    # one of the 7 global formats
├─ number_kind       : str | None    # percentage | integer | decimal
├─ answer_options    : [{label, value}]
├─ generation_status : pending | running | ready | failed
└─ images_imported_from : dict | None  # set by an idiom import; locks `parameters`
```

`task_configs` (one row per task × idiom) is the legacy shape, kept in sync by
`utils/database/migration.py` for older readers.

## The task contract

A `taskNN.py` module declares what it *draws* and what it needs *configured* —
never how its question is answered:

| Attribute | Type | Purpose |
|---|---|---|
| `IDIOMS` | `list[str]` | idiom keys this task renders |
| `PARAM_SPEC` | `list[dict]` | hyperparameters shown on /specify |
| `validate_params` | `callable \| None` | semantic validation, hard-fails generation |
| `RUBRIC` | `str \| None` | reference text for manually coding free-text answers |
| `generate(...)` | callable | writes the SVGs |

`scripts/tasks/task_registry.py` discovers these and supplies safe fallbacks, so
a task that declares nothing still renders a working /specify page.

Answer formats are deliberately **not** in this list. See below.

## PARAM_SPEC

One entry per hyperparameter:

```python
{
  "key": "outcome_activity",
  "label": "Log split condition (activity present in trace marks the Positive group)",
  "hint": "The 'Positive' group is made up of traces that contain this activity",
  "hide_hint": False,          # True = internal to reading the chart, not shown to participants
  "widget": "activity-picker", # select-one | select-many | number | threshold | text | *-picker
  "source": "log.activities",  # optional dataset enumerator that fills `options`
  "default": "",
  "required": True,
}
```

`widget` controls rendering; `source` only populates candidate values. They are
independent. `GET /admin/tasks/{task_key}/param-spec?dataset_id=…` resolves each
`source` through `_param_candidates` in `app/routers/admin.py`.

Parameters reach the drawings through `make_task_generators` in
`scripts/create_all_visualizations.py`, which is the single place that knows
each task's `generate()` signature. A parameter almost always acts on the
shared data kernel a task computes before drawing, so every idiom of that task
reflects it consistently.

Validation runs before generation, in two layers: a generic pass (required
fields present; values that name a `source` exist in the log) and the task's own
`validate_params`. Failures are returned as a hard error, not a warning.

## Answer formats

Formats are **global**: every task may use every format. The registry is
`app/answer_formats.py`, served by `GET /admin/answer-formats`.

| Format | Widget | Needs options | Notes |
|---|---|---|---|
| `mc-single` | `single_choice` | yes | one choice from a closed set |
| `mc-multi` | `multiple_choice` | yes | select-all over a closed set |
| `rank` | `rank` | yes | drag to order; shuffled before display |
| `matrix` | `matrix` | yes | pairwise grid; option values are `a__b` tokens |
| `number-set` | `numeric_set` | yes | one number per labelled row |
| `number` | `numeric` | no | single number |
| `free-text` | `free_text` | no | open text, coded by hand |

`number` and `number-set` take a `number_kind` — `percentage` (0–100, one
decimal, `%` suffix), `integer` (whole, ≥ 0) or `decimal` (unconstrained). This
replaces the former separate `pct` / `count` / `decimal` formats.

### Where options come from

Options are authored on /answer-format, either imported from the event log or
typed by hand. Import sources are dataset-level and task-independent:

```
GET /admin/datasets/{id}/option-sources
GET /admin/datasets/{id}/option-candidates?source=&granularity=&pairs=&axis_limit=
```

| Source | Produces |
|---|---|
| `log.activities` | activity names |
| `log.violations` | `activity \| move_type` pairs, by trace coverage |
| `log.candidate_attributes` | case-attribute buckets |
| `log.time_bins` | period labels at a chosen granularity |
| `log.trace_ids` | trace ids |
| `log.worst_traces` | worst-fitness traces |

`pairs=true` (matrix) builds the upper triangle from one shared axis, capped at
`axis_limit` because the grid is read cell by cell.

## What the participant receives

`app/routers/participant.py` assembles the trial contract; see
`PARTICIPANT_TRIAL_CONTRACT.md` for the wire format. Options are passed through
as `{label, value}`; `rank` is shuffled so the authoring order cannot bias the
response.

## Generation

`POST /admin/experiments/{id}/generate` validates every task instance, then runs
a background job that renders per experiment into
`data/{dataset_id}/output/{experiment_id}/{task_key}/{idiom_key}.svg`, so two
experiments sharing a dataset never overwrite each other. Alignments are
computed once per dataset and cached (`get_or_compute_alignments`) — PM4Py
alignments are non-deterministic, so the cache is what keeps /specify's
violation enumeration and the rendered idioms consistent.

Generation only draws. It computes nothing about answers.

Images the admin uploaded or imported for the experiment (next section) are
stored apart from this output and take precedence over it, so regenerating
never replaces them. /specify warns before generating when there are any.
A task whose every selected idiom has such an image is skipped by generation
altogether (`_fully_uploaded_task_ids` in `app/routers/admin.py`): its status
stays `ready` and its parameters are not validated.

## Custom idioms

*Upload Custom Idiom* on /idiom (`POST /admin/idioms/upload`) adds an `Idiom`
document with `is_custom: true`, a fixed image in `data/_custom_idioms/`, the
tasks it applies to (`task_keys`) and the experiment it was uploaded in
(`experiment_id`). `/admin/task-idioms?experiment_id=…` offers it to that
experiment only, so one study's uploads do not turn up in the next. Custom
idioms uploaded before `experiment_id` was recorded are offered only to
experiments that already select them or that own the custom task they are bound
to. Participants and the overview resolve idioms by id, so neither depends on
what is offered. Deleting an experiment deletes the custom idioms uploaded in it.

## Idiom previews on /idiom

The preview on the idiom step (`POST`/`GET /admin/idiom-preview/{task_key}…`)
is drawn by the same generator as an experiment's images, from the bundled
sample dataset with default parameters — so it shows how the current code
draws an idiom, not the experiment's data. It is generated once per task and
container, into `scripts/sample_data/output/__idiom_preview/`, which is not on
the data volume and not committed: every image rebuild (every code change)
starts it empty. At startup `prewarm_idiom_previews` draws all tasks in a
background thread, one after another; a task requested before its turn is
drawn on that request instead. Outside Docker, delete that directory after
changing a task to see its new previews.

## Idiom images: export, import, replace

For reproducibility, the images participants see can be taken out of the
platform and put back in (`app/routers/idiom_bundle.py`, paths in
`utils/idiom_files.py`):

- **Download** (`GET /admin/experiments/{id}/idioms/export`; the overview page,
  and the experiment list once published) — a zip of every image participants
  see, laid out as `<task_key>/<idiom_key>.<ext>`, plus each task's
  `traces.json` and a `manifest.json` recording the experiment, each task's
  dataset (id, title and the checksums of its log and guideline — manifest
  version 2) and parameters, and where every image came from (`generated`,
  `uploaded`, `custom`, `legacy`). `git_commit` is filled from the backend's
  `GIT_COMMIT` environment variable, which the deploy does not set yet.
- **Import** (`POST …/idioms/import?mode=specify|overview`) — puts such a zip
  into this experiment or any other with the same tasks and idioms, matched by
  `task_key` and `idiom_key`, never by experiment id. No page calls it any more
  — the Overview page's *Import* button that offered `overview` mode is gone,
  and the Specify page never called it (`specify` mode is only reachable
  directly against the API now). A zip with its own tasks, idioms and settings
  builds a whole new experiment on /new instead; swapping one experiment's
  images for another's is a single-image *Replace* on Overview, or *Replace
  with a different zip* on /new for a bundle experiment. The endpoint and its
  checks stay, since nothing about them changed. The manifest is
  required, because every task is checked against it before any of its files is
  taken:
  - **Dataset** (both modes): a task exported from a different dataset is
    rejected. Checksums decide when both sides have them, so the same log
    uploaded on another server still matches; a version-1 manifest has to name
    the same dataset id.
  - **Parameters**: in `specify` mode (the Specify step — reproducing a study)
    the images arrive with the parameters they were drawn with, which replace
    the task's. In `overview` mode (the Overview page — swapping images into a
    task already set up) the task's parameters stay, and a task whose
    parameters differ from the zip's is rejected, listing the differences.
    Missing keys count as their `PARAM_SPEC` default, and multi-selects ignore
    order.

  Every file not taken is listed back as `rejected` with its reason, next to
  the `imported` list; nothing is written if no file is taken. Custom tasks and
  custom idioms get random keys, so they only match within the experiment and
  server they were exported from.
- **Replace one image** (`POST`/`DELETE …/idioms/{task_key}/{idiom_key}`) — an
  SVG/PNG/JPG from the admin's computer in place of one generated image, and
  back. The overview page asks for confirmation, since the parameters shown to
  participants do not change to match the new image.

A task that received images from an import is marked `images_imported_from`
on its `TaskInstance` (source experiment, file, export and import times).
While marked, its parameters are locked: the Specify page shows them read-only
with the reason, and `PATCH /admin/experiments/{id}` keeps the stored
parameters and the marker whatever the caller sends
(`_keep_imported_parameters`). Those parameters are what the participant-facing
parameter hints and any later export are built from, so the lock is what keeps
them true to the images. Reverting releases the task — *Revert all* on the
overview page or *Discard import* on the Specify page for every task, and a
single revert once the task has no uploaded image left.

Uploaded and imported images live in
`data/_idiom_overrides/{experiment_id}/` and win over generated ones (see
`PARTICIPANT_TRIAL_CONTRACT.md`, *SVG resolution*). After an import or
replacement, a task whose selected idioms all have an image is marked
`ready`, so an imported experiment can be published without generating.
Import, replace and revert are refused unless the experiment is a draft, so the
stimuli cannot change under participants mid-study; download always works.

## Intro pages

`/concepts` configures the two pages participants see between the knowledge
questions and the tasks: *Key Concepts* (`/conformance-terms`) and *Before You
Begin* (`/taskintro`). Per experiment (fields on `Experiment`):

- `concept_sections` / `taskintro_sections` — which sections each page shows.
  An empty list skips that page; the participant pages route around it
  (`utils/introPages.js`). Experiments without the fields show every section.
- `concept_citation_*` / `taskintro_citation_*` — whether each page shows its
  citation, and its text (`null` = the default Carmona et al. reference). A
  citation only appears when the page shows at least one definition section.
- `process_model_ext` — set when the admin uploaded an image of their own
  process model, stored at `data/_process_models/{experiment_id}{ext}` and
  shown on both pages instead of the bundled order-to-cash diagram.

## Adding a task

1. Write `taskNN.py` with `IDIOMS` and `generate()`.
2. Add `PARAM_SPEC` for anything the admin must choose, plus `validate_params`
   if some choices are illegal.
3. Add `RUBRIC` if the task will be answered as free text.
4. Register the module in `task_registry.TASK_MODULES` and add its `generate()`
   call to `make_task_generators`.
5. Smoke-test the import:
   `cd provibackend && PYTHONPATH=ProViBackend:ProViBackend/scripts python -c "import ProViBackend.scripts.tasks.taskNN"`

Nothing about answer formats needs touching — the admin picks those per
experiment.
