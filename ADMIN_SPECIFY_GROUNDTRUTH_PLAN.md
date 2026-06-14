# Plan: Per-Task Hyperparameters, On-Demand Generation, Answer-Format & Ground-Truth Workflow

> Status: **approved plan, not yet implemented**. Scope: change the admin
> experiment-creation flow to specify per-task hyperparameters, generate idioms
> and ground truth from them, and let the admin choose answer formats and
> review/edit ground truth. Implementation proceeds **one task at a time with
> manual hand-holding** (see §14–§15).

## 0. Goal

Insert a `/specify` step (per-task hyperparameters) and an
`/answer-format-groundtruth` step (pick answer format, review/edit computed
ground truth) into the admin experiment-creation flow; move idiom generation to
**after** params are set; compute ground truth (and rubrics for free-text
answers) from those params; surface all of it on `/overview`.

References: `CC_Experiment_Task_Design_2_1.md` §2 — col **D** = answer format,
col **E** = "Admin must specify" (hyperparameters), col **G** = GT tier, col
**H** = "GT method / tool".

## 1. Guiding principle — framework once, per-task content incrementally

Every task differs in its parameters (col E), its allowed answer formats and GT
shape (col D), and how GT is computed (col H). So we build **generic,
data-driven scaffolding once**, then **author each task's content one at a time,
with hand-holding**:

- The two new pages render purely from what a task *declares* (its "contract").
  They do not hard-code any task.
- Each task's contract + GT computation is filled in incrementally. Until a task
  is authored, the pages **degrade gracefully** (param-free stub, generic
  free-text GT) so the platform keeps working.
- Per-task work is a tight loop: author contract → implement GT → generate on a
  real dataset → eyeball that task's two pages → adjust → next task.

## 2. New workflow sequence

```
/new → /knowledge → /task → /idiom → /specify → /answer-format-groundtruth → /overview → publish
```

`/specify` is **after** `/idiom` so generation renders only the selected idioms.
`/specify` also triggers generation; `/answer-format-groundtruth` and `/overview`
read its results.

## 3. Data model — "group per task"

`Experiment.task_configs` (flat, one row per task×idiom) becomes
`task_instances` (one entry per task, holding its idiom list plus the shared
params/format/GT):

```python
class TaskInstance(BaseModel):
    task_id: str
    dataset_id: str
    idiom_ids: List[str]
    parameters: Dict[str, Any] = {}        # col E computational params (may be empty)
    answer_format: Optional[str] = None    # chosen col D format
    generation_status: str = "pending"     # pending|running|ready|failed
    generation_error: Optional[str] = None
    ground_truth: Optional[GroundTruthBlock] = None
    question_ids: List[str] = []

class GroundTruthBlock(BaseModel):
    tier: str                  # AUTO|SEMI|MANUAL
    format: str                # the answer_format this GT is shaped for
    decisive: bool             # derived from format, admin-overridable
    value: Any = None          # scalar/set/rank/matrix per format
    options: List[OptionItem] = []   # MC: full closed set incl. distractors, editable
    reference: Optional[str] = None  # free-text rubric (seeded from the task's static RUBRIC, editable)
    artefact_path: Optional[str] = None  # disk cache of computed support
```

A thin adapter expands `task_instances` back into per-(task,idiom) **trials** so
participant assignment/balancing barely changes.

**Migration (decided): migrate in place.** A one-shot migration converts every
existing experiment's flat `task_configs` → `task_instances`, backfilling:
`parameters` from the old pipeline defaults, `answer_format` from
`Task.answer_type`, `ground_truth` left empty. Rationale: single code path
everywhere (participant/overview/trial logic only ever sees the new schema), no
dual-schema branching, small data volume at this stage. (Alternative —
start-fresh / dual-read — rejected to avoid persistent dual-schema complexity.)

## 4. Per-task contract — colocated in each `taskNN.py`

Rather than a monolithic central catalog, **each task module declares its own
contract**, mirroring the existing `IDIOMS` pattern the admin router already
reads:

```python
# in taskNN.py
IDIOMS = [...]                      # already exists
GT_TIER = "SEMI"                    # AUTO|SEMI|MANUAL  (see §6)
PARAM_SPEC = [                      # computational params only; [] if none
  {"key": "outcome_activity", "label": "...", "widget": "activity-picker",
   "source": "log.activities", "default": "A_ACTIVATED", "required": True},
]
ANSWER_FORMATS = [                  # allowed col-D formats; each declares its GT shape
  {"key": "pct-set",   "gt_shape": "labelled-set", "decisive_default": True},
  {"key": "free-text", "gt_shape": "reference",    "decisive_default": False},
]
RUBRIC = "..."                      # static free-text grading rubric, authored once per task (see §8)
def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    # optional; returns {value, options, correct, support_artefact}
```

- `widget ∈ {select-one, select-many, number, text, activity-picker,
  attribute-picker, threshold, time-binning, severity-map}`; `source` tells the
  backend how to enumerate candidates from the dataset's log.
- **Starting point for `PARAM_SPEC` already exists**: most `generate()`
  signatures already accept the right kwargs (`outcome_activity`,
  `compare_attribute`, `predominant_threshold`, …) — authoring is largely
  surfacing those.
- A small **`task_registry.py`** aggregates these attributes across modules and
  supplies safe **fallbacks for unauthored tasks** (`PARAM_SPEC=[]`,
  `ANSWER_FORMATS=[free-text]`, `GT_TIER=MANUAL`, no `compute_ground_truth`).
  Endpoints serve from the registry.

## 5. Generic, data-driven page scaffolding

- `GET /admin/tasks/{task_key}/param-spec?dataset_id=…` returns that task's
  `PARAM_SPEC` **with candidate values populated** from the dataset's log
  (distinct activities, case attributes, resources, or fixed enums). Powers the
  "list all options; admin picks or types" combobox.
- `GET /admin/tasks/{task_key}/answer-formats` returns its `ANSWER_FORMATS`.
- Both pages render entirely from these responses, so an authored task simply
  "lights up" with no page changes.

## 6. Ground-truth tier classification (AUTO / SEMI / MANUAL)

Rule: **MANUAL is unchanged; among the rest, a task is AUTO iff its col-E
("Admin must specify") is "—", otherwise SEMI.**

- **MANUAL** (unchanged): #13, #15, #16, #19, #20, #21, #22, #23
- **AUTO** (col-E is "—"): #6, #12, #25, #35  *(#35's param is optional → "—" → AUTO)*
- **SEMI** (everything else): #1, #2, #3, #4, #5, #7, #8, #9, #10, #11, #14, #17,
  #18, #24, #26, #27, #28, #29, #30, #31, #32, #33, #34, #36, #37

This **reclassifies #2 and #34 from AUTO → SEMI** versus the design-doc §3
summary (both have non-empty col-E), consistent with the rule above.

`GT_TIER` governs **only** whether a decisive GT *value* is auto-computed
(AUTO/SEMI compute it; MANUAL does not). Rubric availability is orthogonal — see
§8.

## 7. Generation pipeline refactor

- **Move generation off dataset-upload** to a triggered job; upload only stores
  files. (No upload-time default render — assumed; see §16.)
- Write to **per-experiment folders**:
  `data/{dataset_id}/output/{experiment_id}/{task_key}/{idiom_key}.svg`.
  Experiment metadata stays in Mongo; editable GT stored in Mongo on the
  instance; raw computed support cached on disk.
- Shared artefacts (log, Petri net, alignments, `fitness_df`) computed **once per
  run**, reused across the experiment's tasks.
- `POST /admin/experiments/{id}/generate` runs a **BackgroundTask**: per
  `task_instance`, feed `parameters` into `generate(...)`, render only
  `idiom_ids`, then call `compute_ground_truth` (if authored) + rubric (if
  free-text is an allowed format), and set `generation_status`. `/specify` and
  `/answer-format-groundtruth` **poll** status.
- Update `_resolve_svg_path` and `_sync_participant_experiment` to include
  `{experiment_id}` in the path.

## 8. Ground-truth contract, decisive vs reference, and rubrics

- GT is a **format-tagged structured block** (§3) — its shape follows the chosen
  format (pct→number, mc→labelled option set, rank→ordering, matrix→cell set,
  free-text→rubric). It is **not** a single free-form string.
- **decisive vs reference** derived from format: auto-gradable
  (`pct, count, decimal, pct-set, count-set, mc-single, mc-multi, rank, matrix`)
  → `decisive=true`; `free-text` → `decisive=false`. Admin can override.
- If `compute_ground_truth` is absent for a task, the instance gets a
  blank/fallback GT so the flow still works — enabling one-task-at-a-time
  rollout.

**Rubrics are per-task, not per (experiment, task).** A rubric is derived from
the task's *description*, which is fixed per task — it does not depend on the
dataset, experiment, or hyperparameters. So there is **no runtime rubric-
generation function** in the pipeline. Instead:

- Each task carries a **static `RUBRIC` string** (a module constant, §4),
  available **whenever `free-text` ∈ that task's `ANSWER_FORMATS`** — which covers
  all MANUAL tasks *and* the SEMI split tasks (#14, #17, #18, #24, #37). So a SEMI
  split task auto-computes its mc/numeric GT *and* carries an editable rubric for
  when free-text is the chosen format.
- The `RUBRIC` text is **authored once per task** during the per-task loop
  (step 6). Producing it may be **Claude-assisted or hand-written** — but that is
  an *authoring-time aid*, not shipped runtime code, and needs no API key at run
  time.
- At experiment-generation, the static `RUBRIC` is simply **copied into
  `ground_truth.reference`** as the editable seed (a dict copy). The seed stays
  **generic**; the admin adds any dataset-specific detail by editing, with the
  computed supporting artefact shown read-only alongside as a guide.
- The `/answer-format-groundtruth` page offers a **"Reset to default rubric"**
  button that re-copies the task's static `RUBRIC`.

## 9. Params are optional

- Col E splits into **computational params** (→ `PARAM_SPEC`, shown on
  `/specify`) vs **reference/rubric** entries (→ free-text GT, handled in §8,
  *not* on `/specify`). AUTO tasks have `PARAM_SPEC=[]`.
- `/specify` renders param forms only for tasks with non-empty `PARAM_SPEC`;
  param-free tasks show a "No parameters required — ready to generate" stub and
  are auto-marked complete.
- `/specify` **always runs** (it is the generation trigger). If no task needs
  params, it degrades to a pure Generate + status screen (optionally auto-firing
  on load).
- "Next" gate = "all *required* params set **and** generation `ready`."

## 10. `/specify` page (new)

Loads `task_instances`; per task renders its `param-spec` combobox / number /
threshold widgets with dataset-derived suggestions (pick or type); param-free or
unauthored tasks show stubs. "Generate" persists params and fires the job; shows
live `generation_status`.

## 11. `/answer-format-groundtruth` page (new)

Per task: answer-format selector limited to its `ANSWER_FORMATS` (single-format
tasks locked / preselected). On select, render the GT editor whose **shape comes
from the selected format's declared `gt_shape`**:

- scalar / set → editable fields;
- **mc-single / mc-multi → GT + distractors together, all editable, correct
  one(s) flagged**;
- rank / matrix → editable ordering / grid;
- free-text → read-only supporting artefact + editable rubric (+ Regenerate).

A **decisive ↔ reference** toggle (preset from format, overridable). Changing the
format reshapes the GT block. Unauthored tasks fall back to a generic free-text
GT.

## 12. `/overview` + participant side

- Replace the two "Coming Soon" placeholders with live `answer_format`, GT
  value / options, the decisive/reference badge, and `generation_status`.
  Publish gated on all instances `ready` + format chosen.
- Participant: `answer_type` read from `task_instance.answer_format` (not the
  global `Task.answer_type`); MC `options` (currently passed `[]`) populated from
  `ground_truth.options`; SVG resolution uses the per-experiment path.
  (Auto-grading against decisive GT is out of scope here — GT is stored/served.)

## 13. Answer-type / GT coupling note

Separating *format selection* from *GT* is fine, but they cannot be fully
independent — GT shape depends on format. Hence `answer_format` lives on the
per-task instance and GT nests under it; the legacy global `Task.answer_type`
becomes a default hint only.

## 14. Per-task authoring recipe (the hand-holding loop)

For each task, **in task-ID order (#1 → #37)**, with the user:

1. Author `PARAM_SPEC` from col E (surface existing `generate()` kwargs).
2. Author `ANSWER_FORMATS` + per-format `gt_shape` from col D.
3. Implement `compute_ground_truth` per col H (incl. the MC distractor set).
4. If `free-text` ∈ `ANSWER_FORMATS`, author the static `RUBRIC` string
   (Claude-assisted or hand-written; see §8).
5. Run generation on a real dataset; eyeball that task's `/specify` +
   `/answer-format-groundtruth`; adjust.
6. Mark authored; move on.

## 15. Build order

1. Data model + in-place migration (`task_instances`, `GroundTruthBlock`) +
   trial adapter.
2. Per-task contract attributes + `task_registry.py` (with fallbacks) +
   `param-spec` / `answer-formats` endpoints.
3. Pipeline refactor: per-experiment paths, on-demand `…/generate`, status,
   shared-artefact reuse.
4. `/specify` page (data-driven).
5. GT scaffold + `/answer-format-groundtruth` page (seeds `reference` from each
   task's static `RUBRIC`; works with fallback GT). No runtime rubric service.
6. Per-task contracts + `compute_ground_truth`, **one task at a time in ID order
   (#1 → #37)** — the §14 loop.
7. `/overview` wiring + participant-side reads.

## 16. Open items

- **Resolved:** migration → **migrate in place** (§3).
- **Resolved:** rubrics are static per-task `RUBRIC` constants copied into each
  instance — no runtime rubric service, no API key needed at run time (§8).
  Authoring the text once per task may use Claude as an offline aid.
- Upload-time default render: plan assumes **none** (generation happens on
  `/specify`).
