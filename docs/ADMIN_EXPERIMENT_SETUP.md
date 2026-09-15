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
/new → /knowledge → /task → /idiom → /specify → /answer-format → /overview → publish
```

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
└─ generation_status : pending | running | ready | failed
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
