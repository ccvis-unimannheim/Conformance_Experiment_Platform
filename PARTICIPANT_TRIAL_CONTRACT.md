# Participant Trial Data Contract

> What the backend sends the participant frontend for each task trial. This is
> the **stable contract**: it depends on what the admin configured for the
> experiment (see `ADMIN_EXPERIMENT_SETUP.md`), never on which task is being
> shown.

## Endpoints

- `GET /participant/assignment/{experiment_id}/trials` — the participant's
  ordered, personalised trial list (one idiom per task).
- `GET /participant/experiment/active` — same trial shape for the active
  experiment (no per-user assignment).
- `GET /participant/vis/{dataset_id}/{task_id}/{idiom_id}?experiment_id=...` —
  the SVG for a trial.
- `POST /survey/answer` — submit one answer (see *Answer submission* below).

### SVG resolution (`/vis`)

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
| `answer_format` | string | canonical answer format (see catalogue below) |
| `answer_type` | string | derived widget type for the answer panel (see mapping) |
| `number_kind` | string | `percentage` \| `integer` \| `decimal`; only meaningful for `number` / `number-set` |
| `options` | `Option[]` | present for option-bearing formats; `[]` otherwise |
| `svg_available` | bool | whether the SVG exists on disk |

`Option`:

| Field | Type | Notes |
|---|---|---|
| `label` | string | shown to participant |
| `value` | string | submitted value (defaults to `label` if empty) |

> Options carry no correctness marking — there is none to carry. The set the
> participant sees is the set the admin authored on /answer-format.

## Answer-format catalogue (canonical `answer_format`)

Seven global formats, defined in `app/answer_formats.py`. Every task may use
every format; the admin chooses per experiment.

| `answer_format` | Meaning | Entry rule | `options`? |
|---|---|---|---|
| `number` | single number | per `number_kind` (below) | no |
| `number-set` | one number per labelled row | each cell per `number_kind` | rows = labels |
| `mc-single` | one option from a closed set | radio; exactly one | yes |
| `mc-multi` | select-all over a closed set | checkboxes | yes |
| `rank` | ordering of given items | drag-to-order | yes (items) |
| `matrix` | co-occurrence / pairwise grid | toggle grid; set of selected cells | yes (cells, `a__b`) |
| `free-text` | interpretive answer | open box; coded by hand against the task rubric | no |

`number_kind` configures both numeric formats:

| `number_kind` | Input |
|---|---|
| `percentage` | 0–100, one decimal, rendered with a `%` suffix |
| `integer` | whole number ≥ 0 |
| `decimal` | any decimal value |

`rank` options are **shuffled** before they are sent. The stored order is the
admin's authoring order and carries no answer, but presenting it unchanged to
every participant would still bias responses toward it.

## `answer_format` → `answer_type` (widget) mapping

The backend returns both the canonical `answer_format` and a derived
`answer_type` so the current `TaskAnswerPanel` keeps working with minimal change.
New widgets should switch on `answer_format` directly.

| `answer_format` | derived `answer_type` |
|---|---|
| `mc-single` | `single_choice` |
| `mc-multi` | `multiple_choice` |
| `number` | `numeric` |
| `number-set` | `numeric_set` |
| `rank` | `rank` |
| `matrix` | `matrix` |
| `free-text` | `free_text` |

## Fallback (format not yet chosen)

If a task instance has no `answer_format`, the participant side falls back to
`answer_format = "free-text"`, `answer_type = "free_text"`, `options = []`. The
app therefore always renders something valid — but /overview blocks publishing
until every task has a format, and options wherever the format needs them.

## Answer submission (`POST /survey/answer`)

Body fields the frontend sends (`AnswerFromFrontend`): `experiment_id`,
`question_id`, `task_id`, `idiom_id`, `dataset_id`, `trial_index`,
`presentation_order`, `answer`, `response_time_ms`. The `answer` string encoding
per format:

| `answer_format` | `answer` encoding |
|---|---|
| `number` | the number as a string, e.g. `"96"`, `"42"`, `"0.42"` |
| `number-set` | JSON object `{label: value}` |
| `mc-single` | the chosen option `value` |
| `mc-multi` | JSON array of chosen option `value`s |
| `rank` | JSON array of `value`s in chosen order |
| `matrix` | JSON array of selected cell tokens |
| `free-text` | the raw text |

> Answers are **stored as submitted and never scored**. Analysis happens on the
> exported data; free-text answers are coded by hand against the task's `RUBRIC`
> (`GET /admin/tasks/{task_key}/rubric`).
