# Participant Trial Data Contract

> What the backend sends the participant frontend for each task trial, so the
> answer-input widgets can be built independently of per-task authoring
> (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md, step 7). This is the **stable contract** —
> it does not change as individual tasks are authored in step 6.

## Endpoints

- `GET /participant/assignment/{experiment_id}/trials` — the participant's
  ordered, personalised trial list (one idiom per task).
- `GET /participant/experiment/active` — same trial shape for the active
  experiment (no per-user assignment).
- `GET /participant/vis/{dataset_id}/{task_id}/{idiom_id}?experiment_id=...` —
  the SVG for a trial.
- `POST /survey/answer` — submit one answer (see *Answer submission* below).

### SVG resolution (`/vis`, §7)

`experiment_id` is an **optional** query parameter. SVGs are generated
per-experiment via `POST /admin/experiments/{id}/generate`, which writes to
`data/{dataset_id}/output/{experiment_id}/{task_key}/{idiom_key}.svg`. When
`experiment_id` is given and that file exists, it is served; otherwise the
endpoint falls back to the legacy shared path
`data/{dataset_id}/output/{task_key}/{idiom_key}.svg` (older datasets generated
before per-experiment paths existed). The frontend should always pass the
`experiment_id` from the trial response (`experiment_id` field on
`/experiment/active`, or the `{experiment_id}` path segment on
`/assignment/{experiment_id}/trials`).

`svg_available` on each trial reflects this same resolution (per-experiment
path first, legacy path fallback), independent of `generation_status` below.

### `generation_status` (admin-side, not sent to participants)

Each `task_instance` on the `Experiment` document (admin contract, not part of
the trial object below) carries a `generation_status`:
`pending | running | ready | failed`, set by
`POST /admin/experiments/{id}/generate` and polled via
`GET /admin/experiments/{id}`. This tracks whether the pipeline has been *run*
for that task; `svg_available` tracks whether a file currently *exists* on
disk. The two usually agree, but `svg_available` can be `true` via the legacy
fallback path even while `generation_status` is `pending` for a freshly
created experiment that reuses an older dataset's SVGs.

## Trial object

Each element of `trials[]` (and the active-experiment `trials[]`) has:

| Field | Type | Notes |
|---|---|---|
| `trial_index` | int | order index (assignment endpoint only) |
| `task_id` | string | Task document id |
| `idiom_id` | string | Idiom document id (the one shown this trial) |
| `dataset_id` | string | dataset pair id |
| `task_key` | string | e.g. `task01` |
| `task_label` | string | question text shown to the participant |
| `idiom_key` | string | e.g. `bar_chart` |
| `idiom_label` | string | human-readable idiom name |
| `answer_format` | string | **canonical** answer format (col-D key, see below) |
| `answer_type` | string | **derived widget type** for the existing panel (see mapping) |
| `decisive` | bool | `true` = auto-gradable GT, `false` = reference only |
| `options` | `Option[]` | present for choice/grid formats; `[]` otherwise |
| `svg_available` | bool | whether the SVG exists on disk |

`Option`:

| Field | Type | Notes |
|---|---|---|
| `label` | string | shown to participant |
| `value` | string | submitted value (defaults to `label` if empty) |

> The frontend must **never** receive `correct` flags or any other ground-truth
> value — only the option `label`/`value` set. Correctness lives server-side.

## Answer-format catalogue (canonical `answer_format`)

From the design doc §1.1. This set is fixed; every widget can be built up front.

| `answer_format` | Meaning | Entry rule | `options`? |
|---|---|---|---|
| `pct` | scalar percent | integer percent with `%`, e.g. `96%` | no |
| `count` | scalar integer | non-negative integer, e.g. `42` | no |
| `decimal` | scalar decimal | two decimals w/ leading zero, e.g. `0.42` | no |
| `pct-set` | one percent per labelled row | each cell follows `pct`; sum-to-100 for distributions | rows = labels |
| `count-set` | one count per labelled row | each cell follows `count` | rows = labels |
| `mc-single` | one correct option | radio; exactly one | yes |
| `mc-multi` | select-all over a closed set | checkboxes; graded as set equality | yes |
| `rank` | ordering of given items | drag-to-order | yes (items) |
| `matrix` | co-occurrence / pairwise grid | toggle grid; set of selected cells | yes (cells) |
| `free-text` | interpretive answer | open box; not auto-graded (rubric) | no |

## `answer_format` → `answer_type` (widget) mapping

The backend returns both the canonical `answer_format` and a derived
`answer_type` so the current `TaskAnswerPanel` keeps working with minimal change.
New widgets should switch on `answer_format` directly.

| `answer_format` | derived `answer_type` |
|---|---|
| `mc-single` | `single_choice` |
| `mc-multi` | `multiple_choice` |
| `pct`, `count`, `decimal` | `numeric` |
| `pct-set`, `count-set` | `numeric_set` |
| `rank` | `rank` |
| `matrix` | `matrix` |
| `free-text` | `free_text` |

## Fallback (task not yet authored — step 6 pending)

Until a task declares its contract, the registry default applies:
`answer_format = "free-text"`, `answer_type = "free_text"`, `options = []`,
`decisive = false`. So the running app always renders *something* valid; the
non-free-text widgets are exercised with real data once their task is authored
(or with mock trial data matching this contract in the meantime).

## Answer submission (`POST /survey/answer`)

Body fields the frontend sends (`AnswerFromFrontend`): `experiment_id`,
`question_id`, `task_id`, `idiom_id`, `dataset_id`, `ground_truth_id?`,
`trial_index`, `presentation_order`, `answer`, `response_time_ms`. The `answer`
string encoding per format:

| `answer_format` | `answer` encoding |
|---|---|
| `pct` / `count` / `decimal` | the scalar as a string, e.g. `"96%"`, `"42"`, `"0.42"` |
| `pct-set` / `count-set` | JSON object `{label: value}` |
| `mc-single` | the chosen option `value` |
| `mc-multi` | JSON array of chosen option `value`s |
| `rank` | JSON array of `value`s in chosen order |
| `matrix` | JSON array of selected cell ids |
| `free-text` | the raw text |

> Auto-grading (`is_correct`) against the decisive ground truth is **out of scope
> for now** — answers are stored as-is. When added, grading happens server-side
> by comparing `answer` to the instance's `ground_truth`.
